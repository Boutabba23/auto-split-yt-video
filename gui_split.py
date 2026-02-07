import sys
import json
import subprocess
import re
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QProgressBar, QTextEdit, QFrame, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont, QIcon, QColor, QPalette

# --- Configuration ---
VIDEO_EXTS = [".mp4", ".mkv", ".webm"]
OUTPUT_DIR = "chapters"

# --- Styling (QSS) ---
STYLE_SHEET = """
QMainWindow {
    background-color: #0f0f0f;
}

QWidget {
    color: #e0e0e0;
    font-family: 'Segoe UI', Roboto, sans-serif;
}

QFrame#MainContainer {
    background-color: #1a1a1a;
    border-radius: 15px;
    border: 1px solid #333;
}

QLineEdit {
    background-color: #262626;
    border: 2px solid #333;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
    color: #fff;
    selection-background-color: #3d5afe;
}

QLineEdit:focus {
    border: 2px solid #3d5afe;
}

QPushButton {
    background-color: #3d5afe;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 14px;
}

QPushButton:hover {
    background-color: #536dfe;
}

QPushButton:pressed {
    background-color: #304ffe;
}

QPushButton#SecondaryBtn {
    background-color: #333;
}

QPushButton#SecondaryBtn:hover {
    background-color: #444;
}

QComboBox {
    background-color: #262626;
    border: 1px solid #333;
    border-radius: 5px;
    padding: 5px 10px;
}

QTableWidget {
    background-color: #1a1a1a;
    gridline-color: #333;
    border: 1px solid #333;
    border-radius: 8px;
    font-size: 13px;
}

QHeaderView::section {
    background-color: #262626;
    color: #aaa;
    padding: 5px;
    border: none;
    font-weight: bold;
}

QProgressBar {
    background-color: #262626;
    border-radius: 5px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #3d5afe, stop:1 #00e5ff);
    border-radius: 5px;
}

QTextEdit#LogArea {
    background-color: #0f0f0f;
    border: 1px solid #333;
    border-radius: 8px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    color: #888;
}
"""

# --- Worker Threads ---

class MetadataWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            # Fetch formats and metadata
            cmd = ["yt-dlp", "--dump-json", "--skip-download", self.url]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
            data = json.loads(result.stdout)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))

class ProcessWorker(QThread):
    progress = Signal(int, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, url, format_id, chapters, video_filename=None):
        super().__init__()
        self.url = url
        self.format_id = format_id
        self.chapters = chapters
        self.video_filename = video_filename

    def run(self):
        try:
            Path(OUTPUT_DIR).mkdir(exist_ok=True)
            
            # 1. Download video if needed
            video_file = self.video_filename
            if not video_file or not Path(video_file).exists():
                self.progress.emit(10, "📥 Downloading video...")
                cmd = ["yt-dlp", "-f", self.format_id, "-o", "%(title)s.%(ext)s", self.url]
                subprocess.run(cmd, check=True)
                
                # Find the downloaded file
                video_file = next((f for f in Path(".").iterdir() if f.suffix.lower() in VIDEO_EXTS), None)

            if not video_file:
                self.error.emit("Video file not found after download.")
                return

            # 2. Split into chapters
            total = len(self.chapters)
            for i, ch in enumerate(self.chapters):
                title = ch['title']
                start = ch['start_time']
                length = ch['length']
                
                clean_title = re.sub(r'[\\/:*?"<>|]', '', title).strip().replace(' ', '_')
                output = Path(OUTPUT_DIR) / f"{i+1:02d}_{clean_title}.mp4"
                
                self.progress.emit(int(20 + (i/total)*80), f"✂️ Splitting: {title}")
                
                cmd = [
                    "ffmpeg", "-y", "-ss", str(start), "-i", str(video_file),
                    "-t", str(length), "-map", "0:v:0", "-map", "0:a?",
                    "-c", "copy", "-avoid_negative_ts", "make_zero",
                    "-movflags", "+faststart", str(output)
                ]
                subprocess.run(cmd, capture_output=True)

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

# --- Main Window ---

class AutoSplitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Split Video - Pro")
        self.resize(1000, 700)
        self.setStyleSheet(STYLE_SHEET)
        self.video_data = None
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header Container
        header_container = QFrame()
        header_container.setObjectName("MainContainer")
        header_layout = QVBoxLayout(header_container)
        
        title_label = QLabel("YouTube Video Auto-Splitter")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #3d5afe;")
        header_layout.addWidget(title_label)

        # URL Input Area
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube URL here...")
        self.fetch_btn = QPushButton("Fetch Metadata")
        self.fetch_btn.clicked.connect(self.fetch_metadata)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_btn)
        header_layout.addLayout(url_layout)

        # Quality and Controls
        ctrl_layout = QHBoxLayout()
        self.quality_combo = QComboBox()
        self.quality_combo.setMinimumWidth(300)
        self.quality_combo.addItem("Select Quality (Fetch first)")
        
        self.add_chapter_btn = QPushButton("+ Add Chapter")
        self.add_chapter_btn.setObjectName("SecondaryBtn")
        self.add_chapter_btn.clicked.connect(self.add_row)
        
        self.del_chapter_btn = QPushButton("- Delete Selected")
        self.del_chapter_btn.setObjectName("SecondaryBtn")
        self.del_chapter_btn.clicked.connect(self.delete_row)

        ctrl_layout.addWidget(QLabel("Video Quality:"))
        ctrl_layout.addWidget(self.quality_combo)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.add_chapter_btn)
        ctrl_layout.addWidget(self.del_chapter_btn)
        header_layout.addLayout(ctrl_layout)
        
        main_layout.addWidget(header_container)

        # Tables / Editor Container
        editor_container = QFrame()
        editor_container.setObjectName("MainContainer")
        editor_layout = QVBoxLayout(editor_container)
        
        self.chapter_table = QTableWidget(0, 3)
        self.chapter_table.setHorizontalHeaderLabels(["Chapter Title", "Start Time (sec)", "End Time (sec)"])
        self.chapter_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.chapter_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        editor_layout.addWidget(self.chapter_table)
        
        main_layout.addWidget(editor_container)

        # Execution Area
        exec_container = QFrame()
        exec_container.setObjectName("MainContainer")
        exec_layout = QVBoxLayout(exec_container)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        exec_layout.addWidget(self.progress_bar)

        self.start_btn = QPushButton("START SPLITTING PROCESS")
        self.start_btn.setStyleSheet("font-size: 16px; height: 50px; background-color: #00c853;")
        self.start_btn.clicked.connect(self.start_process)
        exec_layout.addWidget(self.start_btn)
        
        self.log_area = QTextEdit()
        self.log_area.setObjectName("LogArea")
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(100)
        exec_layout.addWidget(self.log_area)

        main_layout.addWidget(exec_container)

    def log(self, message):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def fetch_metadata(self):
        url = self.url_input.text().strip()
        if not url:
            self.log("❌ Enter a URL first")
            return

        self.fetch_btn.setEnabled(False)
        self.log("📡 Fetching metadata...")
        
        self.metaworker = MetadataWorker(url)
        self.metaworker.finished.connect(self.on_metadata_fetched)
        self.metaworker.error.connect(self.on_error)
        self.metaworker.start()

    def on_metadata_fetched(self, data):
        self.video_data = data
        self.fetch_btn.setEnabled(True)
        self.log("✅ Metadata fetched successfully")

        # Update Qualities
        self.quality_combo.clear()
        formats = data.get('formats', [])
        # Filter: bestvideo with height <= 1080. Fallback to best if none.
        seen_qualities = set()
        for f in formats:
            height = f.get('height')
            if height and height <= 1080:
                ext = f.get('ext')
                vcodec = f.get('vcodec', 'unknown')
                if vcodec != 'none':
                    label = f"{height}p ({ext}) - {f.get('format_note', '')}"
                    if label not in seen_qualities:
                        self.quality_combo.addItem(label, f['format_id'])
                        seen_qualities.add(label)
        
        self.quality_combo.addItem("Best Available (Auto)", "bestvideo[height<=1080]+bestaudio/best[height<=1080]")

        # Update Chapters
        self.chapter_table.setRowCount(0)
        chapters = data.get('chapters', [])
        duration = data.get('duration', 0)

        if chapters:
            for i, ch in enumerate(chapters):
                start = ch['start_time']
                end = chapters[i+1]['start_time'] if i+1 < len(chapters) else duration
                self.add_row(ch['title'], start, end)
        else:
            self.log("⚠️ No chapters found. Please add them manually.")
            self.add_row("Intro", 0, duration)

    def add_row(self, title="", start=0, end=0):
        row = self.chapter_table.rowCount()
        self.chapter_table.insertRow(row)
        self.chapter_table.setItem(row, 0, QTableWidgetItem(str(title)))
        self.chapter_table.setItem(row, 1, QTableWidgetItem(str(start)))
        self.chapter_table.setItem(row, 2, QTableWidgetItem(str(end)))

    def delete_row(self):
        rows = self.chapter_table.selectionModel().selectedRows()
        for row in reversed(rows):
            self.chapter_table.removeRow(row.row())

    def on_error(self, msg):
        self.fetch_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.log(f"❌ Error: {msg}")

    def start_process(self):
        url = self.url_input.text().strip()
        if not url:
            self.log("❌ Enter a URL first")
            return
        
        format_id = self.quality_combo.currentData()
        if not format_id:
            self.log("❌ Select a quality first")
            return

        chapters = []
        for row in range(self.chapter_table.rowCount()):
            title = self.chapter_table.item(row, 0).text()
            start = float(self.chapter_table.item(row, 1).text())
            end = float(self.chapter_table.item(row, 2).text())
            chapters.append({
                'title': title,
                'start_time': start,
                'length': end - start
            })

        if not chapters:
            self.log("❌ No chapters to split")
            return

        self.start_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
        # Check if video already exists in current dir
        video_filename = None
        if self.video_data:
            # We assume title-based naming for local search
            title_part = self.video_data.get('title', '')
            for f in Path(".").iterdir():
                if f.suffix.lower() in VIDEO_EXTS and title_part in f.name:
                    video_filename = str(f)
                    break

        self.worker = ProcessWorker(url, format_id, chapters, video_filename)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.log(msg)

    def on_finished(self):
        self.progress_bar.setValue(100)
        self.start_btn.setEnabled(True)
        self.log("✨ ALL DONE! Chapters saved in 'chapters' folder.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AutoSplitApp()
    window.show()
    sys.exit(app.exec())
