import sys
import json
import subprocess
import re
import os
import urllib.request
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QProgressBar, QTextEdit, QFrame, QAbstractItemView,
    QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont, QIcon, QColor, QPalette, QPixmap

# --- Portable Path Handling ---
def get_app_dir():
    if getattr(sys, 'frozen', False):
        # Running as a bundled executable
        return os.path.dirname(sys.executable)
    # Running as a script
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()
os.chdir(APP_DIR)  # Ensure CWD is always where the app/exe is

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def format_seconds(secs):
    """Convert seconds to HH:MM:SS format."""
    hrs = int(secs // 3600)
    mins = int((secs % 3600) // 60)
    secs = int(secs % 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

def parse_time(time_str):
    """Convert HH:MM:SS or MM:SS or seconds string to float seconds."""
    if not time_str: return 0.0
    try:
        parts = str(time_str).strip().split(':')
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(time_str)
    except ValueError:
        return 0.0

# --- Configuration ---
VIDEO_EXTS = [".mp4", ".mkv", ".webm"]
OUTPUT_DIR = os.path.join(APP_DIR, "chapters")

# --- Styling (QSS) - YouTube ChapterSplit Theme ---
STYLE_SHEET = """
/* ===== Base Styles ===== */
QMainWindow {
    background-color: #0f0f0f;
}

QWidget {
    color: #ffffff;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    font-size: 13px;
}

/* ===== Glass Panels ===== */
QFrame#GlassPanel {
    background-color: rgba(255, 255, 255, 0.03);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

QFrame#HeaderPanel {
    background-color: rgba(0, 0, 0, 0.5);
    border-radius: 0px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

/* ===== Inputs ===== */
QLineEdit {
    background-color: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 14px;
    color: #ffffff;
    selection-background-color: #ff0000;
}

QLineEdit:focus {
    border: 1px solid rgba(255, 0, 0, 0.5);
}

QLineEdit::placeholder {
    color: #6b7280;
}

QLineEdit:disabled {
    background-color: rgba(0, 0, 0, 0.2);
    color: #4b5563;
}

/* ===== Primary Button (Red Gradient) ===== */
QPushButton {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #ff0000, stop:1 #cc0000);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 12px 24px;
    font-weight: 600;
    font-size: 14px;
}

QPushButton:hover {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #ff3333, stop:1 #dd0000);
}

QPushButton:pressed {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #cc0000, stop:1 #aa0000);
}

QPushButton:disabled {
    background-color: #333333;
    color: #666666;
}

/* ===== Secondary Buttons ===== */
QPushButton#SecondaryBtn {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #9ca3af;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton#SecondaryBtn:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: #ffffff;
}

/* ===== Download/Start Button ===== */
QPushButton#DownloadBtn {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #ff0000, stop:1 #cc0000);
    font-size: 15px;
    font-weight: bold;
    padding: 14px 32px;
}

QPushButton#DownloadBtn:hover {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #ff3333, stop:1 #dd0000);
}

QPushButton#DownloadBtn:disabled {
    background-color: #333333;
    color: #555555;
}

/* ===== ComboBox ===== */
QComboBox {
    background-color: rgba(26, 26, 26, 1);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    color: #ffffff;
    min-width: 200px;
}

QComboBox:hover {
    border-color: rgba(255, 0, 0, 0.5);
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox QAbstractItemView {
    background-color: #1a1a1a;
    border: 1px solid rgba(255, 255, 255, 0.1);
    selection-background-color: #ff0000;
    color: #ffffff;
}

/* ===== Table (Chapters) ===== */
QTableWidget {
    background-color: transparent;
    gridline-color: rgba(255, 255, 255, 0.05);
    border: none;
    border-radius: 12px;
    font-size: 13px;
    alternate-background-color: rgba(255, 255, 255, 0.02);
    outline: none; /* Removes the "line through" / dashed focus rect */
}

QTableWidget::item {
    padding: 0px 12px; /* Horizontal padding only */
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

QTableWidget::item:selected {
    background-color: rgba(0, 0, 0, 0.1);
    color: #ffffff;
}

QTableWidget::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

/* Style the editor (simple input look) */
QTableWidget QLineEdit, 
QAbstractItemView QLineEdit {
    background-color: #1a1a1a;
    background: #1a1a1a;
    border: 1px solid #ff0000;
    border-radius: 4px;
    padding: 0px 8px;
    margin: 4px;
    color: #ffffff;
    selection-background-color: #ff0000;
    selection-color: #ffffff;
    font-size: 13px;
    min-height: 28px;
}

QHeaderView::section {
    background-color: rgba(255, 255, 255, 0.03);
    color: #9ca3af;
    padding: 12px;
    border: none;
    font-weight: 500;
    font-size: 12px;
}

/* ===== Progress Bar ===== */
QProgressBar {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    text-align: center;
    font-weight: bold;
    color: #ffffff;
    min-height: 8px;
    max-height: 8px;
}

QProgressBar::chunk {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #f87171);
    border-radius: 4px;
}

/* ===== Log Area ===== */
QTextEdit#LogArea {
    background-color: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 11px;
    color: #6b7280;
    padding: 12px;
}

/* ===== Labels ===== */
QLabel#TitleLabel {
    font-size: 24px;
    font-weight: bold;
    color: #ff0000;
}

QLabel#GradientTitle {
    font-size: 24px;
    font-weight: bold;
    color: #ff6b6b;
}

QLabel#SubtitleLabel {
    font-size: 12px;
    color: #9ca3af;
    font-weight: 400;
}

QLabel#SectionLabel {
    font-size: 12px;
    color: #6b7280;
    font-weight: 500;
}

QLabel#VideoTitleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#VideoInfoLabel {
    font-size: 13px;
    color: #9ca3af;
}

QLabel#ChapterCountBadge {
    font-size: 11px;
    color: #ffffff;
    background-color: rgba(255, 255, 255, 0.1);
    padding: 2px 8px;
    border-radius: 10px;
}

/* ===== Scrollbar ===== */
QScrollBar:vertical {
    background-color: rgba(255, 255, 255, 0.05);
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: rgba(255, 255, 255, 0.3);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
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
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
            data = json.loads(result.stdout)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))

class ProcessWorker(QThread):
    progress = Signal(int, str)
    download_progress = Signal(str, str)  # (percent, eta)
    finished = Signal()
    error = Signal(str)

    def __init__(self, url, format_id, chapters, video_filename=None):
        super().__init__()
        self.url = url
        self.format_id = format_id
        self.chapters = chapters
        self.video_filename = video_filename

    def find_video_file(self, expected_name=None, title_hint=None):
        """Ultra-robust fuzzy file discovery (Unicode-aware)."""
        # 1. Try exact match first
        if expected_name and Path(expected_name).exists():
            return str(expected_name)
        
        # 2. Try alphanumeric/Unicode fuzzy match
        # \w matches word characters including Unicode if supported by re.LOCALE or re.UNICODE (default in py3)
        def clean_name(name):
            if not name: return ""
            # Strip symbols but KEEP letters (Unicode), numbers, and underscores
            cleaned = re.sub(r'[^\w]', '', Path(name).stem).lower()
            return cleaned

        target_base = clean_name(expected_name)
        hint_base = clean_name(title_hint) if title_hint else ""

        # Scan folder for candidates
        candidates = []
        for f in Path(".").iterdir():
            if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
                f_clean = clean_name(f.name)
                # Check against predicted name or title hint
                if target_base and (target_base in f_clean or f_clean in target_base):
                    candidates.append(f)
                elif hint_base and (hint_base in f_clean or f_clean in hint_base):
                    candidates.append(f)
        
        if candidates:
            # Prefer the most recent file if multiple matches found
            best_match = max(candidates, key=lambda x: x.stat().st_mtime)
            return str(best_match)
        
        return None

    def run(self):
        try:
            Path(OUTPUT_DIR).mkdir(exist_ok=True)
            
            # Helper to get the actual filename yt-dlp would/did use
            get_name_cmd = ["yt-dlp", "--get-filename", "-f", self.format_id, "-o", "%(title)s.%(ext)s", self.url]
            name_result = subprocess.run(get_name_cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
            expected_video_file = (name_result.stdout or "").strip()
            
            # 1. Discover existing video
            title_hint = self.video_filename if self.video_filename else None 
            video_file = self.find_video_file(expected_video_file, title_hint=title_hint)

            # 2. Download if not found
            if not video_file or not Path(video_file).exists():
                self.progress.emit(10, "📥 Downloading video...")
                
                # Use Popen to capture real-time progress
                cmd = ["yt-dlp", "--newline", "--progress", "-f", self.format_id, "-o", "%(title)s.%(ext)s", self.url]
                # Regex for percentage and ETA: [download]  1.2% of 10.00MiB at  2.41MiB/s ETA 00:03
                re_progress = re.compile(r"\[download\]\s+([\d\.]+)%\s+of\s+.*\s+at\s+.*\s+ETA\s+([\d:]+)")
                
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                    text=True, encoding='utf-8', errors='replace', bufsize=1
                )
                
                for line in process.stdout:
                    match = re_progress.search(line)
                    if match:
                        percent = match.group(1)
                        eta = match.group(2)
                        self.download_progress.emit(f"{percent}%", f"Remaining: {eta}")
                
                process.wait()
                if process.returncode != 0:
                    raise Exception(f"yt-dlp download failed with code {process.returncode}")
                
                # Search again after download
                video_file = self.find_video_file(expected_video_file, title_hint=title_hint)

            if not video_file or not Path(video_file).exists():
                self.error.emit(f"Video file not found: {expected_video_file or 'Unknown'}")
                return

            video_path = Path(video_file)
            video_ext = video_path.suffix
            self.progress.emit(15, f"✅ Using file: {video_path.name}")

            # 2. Split into chapters
            total = len(self.chapters)
            for i, ch in enumerate(self.chapters):
                title = ch['title']
                start = ch['start_time']
                length = ch['length']
                
                clean_title = re.sub(r'[\\/:*?"<>|]', '', title or "Chapter").strip().replace(' ', '_')
                output = Path(OUTPUT_DIR) / f"{i+1:02d}_{clean_title}{video_ext}"
                
                self.progress.emit(int(20 + (i/total)*80), f"✂️ Splitting: {title}")
                
                cmd = [
                    "ffmpeg", "-y", "-ss", str(start), "-i", str(video_path),
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
        # Set Window Icon
        icon_path = resource_path("split-tube-icon.PNG")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setWindowTitle("ChapterSplit")
        self.resize(1000, 700)
        self.setStyleSheet(STYLE_SHEET)
        self.video_data = None
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 0, 24, 24)
        main_layout.setSpacing(16)

        # ===== Header Bar =====
        header_bar = QFrame()
        header_bar.setObjectName("HeaderPanel")
        header_bar.setFixedHeight(56)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(8, 0, 8, 0)

        logo_label = QLabel()
        icon_path = resource_path("split-tube-icon.PNG")
        logo_pixmap = QPixmap(icon_path)
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header_layout.addWidget(logo_label)
            header_layout.addSpacing(4)

        title_label = QLabel("ChapterSplit")
        title_label.setObjectName("TitleLabel")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        main_layout.addWidget(header_bar)

        # ===== Two Column Layout =====
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)

        # ========== LEFT COLUMN ==========
        left_column = QVBoxLayout()
        left_column.setSpacing(16)

        # --- Card 1: URL Input ---
        url_panel = QFrame()
        url_panel.setObjectName("GlassPanel")
        url_layout = QVBoxLayout(url_panel)
        url_layout.setContentsMargins(20, 20, 20, 20)
        url_layout.setSpacing(12)

        url_label = QLabel("YouTube Video URL")
        url_label.setObjectName("SectionLabel")
        url_layout.addWidget(url_label)

        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_input.setMinimumHeight(44)
        self.fetch_btn = QPushButton("🔍  Analyze")
        self.fetch_btn.setMinimumHeight(44)
        self.fetch_btn.setMinimumWidth(120)
        self.fetch_btn.clicked.connect(self.fetch_metadata)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.fetch_btn)
        url_layout.addLayout(url_row)

        hint_label = QLabel("Supports: youtube.com, youtu.be, shorts")
        hint_label.setObjectName("SubtitleLabel")
        url_layout.addWidget(hint_label)

        left_column.addWidget(url_panel)

        # --- Card 2: Video Info with Thumbnail ---
        info_panel = QFrame()
        info_panel.setObjectName("GlassPanel")
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(20, 20, 20, 20)
        info_layout.setSpacing(16)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setObjectName("ThumbnailLabel")
        self.thumbnail_label.setFixedSize(320, 180)
        self.thumbnail_label.setStyleSheet("""
            QLabel#ThumbnailLabel {
                background-color: #1a1a1a;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setText("🎬")
        self.thumbnail_label.setScaledContents(False)
        info_layout.addWidget(self.thumbnail_label, 0, Qt.AlignCenter)

        # Video Title
        self.video_title_label = QLabel("No video loaded")
        self.video_title_label.setObjectName("VideoTitleLabel")
        self.video_title_label.setWordWrap(True)
        self.video_title_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.video_title_label)

        # Video Info (channel, duration)
        self.video_info_label = QLabel("Enter a URL and click Analyze")
        self.video_info_label.setObjectName("VideoInfoLabel")
        self.video_info_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.video_info_label)

        # Quality Selector
        quality_row = QHBoxLayout()
        quality_label = QLabel("Quality:")
        quality_label.setObjectName("SectionLabel")
        self.quality_combo = QComboBox()
        self.quality_combo.setMinimumWidth(200)
        self.quality_combo.addItem("Analyze video first...")
        quality_row.addStretch()
        quality_row.addWidget(quality_label)
        quality_row.addWidget(self.quality_combo)
        quality_row.addStretch()
        info_layout.addLayout(quality_row)

        left_column.addWidget(info_panel, 1)

        columns_layout.addLayout(left_column, 1)

        # ========== RIGHT COLUMN ==========
        right_column = QVBoxLayout()
        right_column.setSpacing(16)

        # --- Card 3: Chapters ---
        chapters_panel = QFrame()
        chapters_panel.setObjectName("GlassPanel")
        chapters_layout = QVBoxLayout(chapters_panel)
        chapters_layout.setContentsMargins(20, 16, 20, 16)
        chapters_layout.setSpacing(12)

        # Section Header
        section_header = QHBoxLayout()
        chapters_title = QLabel("📋  Chapters")
        chapters_title.setObjectName("VideoTitleLabel")
        self.chapter_count_label = QLabel("0")
        self.chapter_count_label.setObjectName("ChapterCountBadge")
        section_header.addWidget(chapters_title)
        section_header.addWidget(self.chapter_count_label)
        section_header.addStretch()

        self.add_chapter_btn = QPushButton("+ Add")
        self.add_chapter_btn.setObjectName("SecondaryBtn")
        self.add_chapter_btn.setMinimumWidth(80)
        self.add_chapter_btn.clicked.connect(self.add_row)

        self.del_chapter_btn = QPushButton("− Remove")
        self.del_chapter_btn.setObjectName("SecondaryBtn")
        self.del_chapter_btn.setMinimumWidth(100)
        self.del_chapter_btn.clicked.connect(self.delete_row)

        section_header.addWidget(self.add_chapter_btn)
        section_header.addWidget(self.del_chapter_btn)
        chapters_layout.addLayout(section_header)

        # Table
        self.chapter_table = QTableWidget(0, 3)
        self.chapter_table.setHorizontalHeaderLabels(["Chapter Title", "Start", "End"])
        self.chapter_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.chapter_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.chapter_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.chapter_table.verticalHeader().setDefaultSectionSize(40)
        self.chapter_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.chapter_table.setAlternatingRowColors(True)
        self.chapter_table.verticalHeader().setVisible(False)
        chapters_layout.addWidget(self.chapter_table)

        # Footer
        footer_row = QHBoxLayout()
        self.stats_label = QLabel("0 chapters")
        self.stats_label.setObjectName("SubtitleLabel")
        footer_row.addWidget(self.stats_label)
        footer_row.addStretch()

        self.start_btn = QPushButton("⬇  Start Splitting")
        self.start_btn.setObjectName("DownloadBtn")
        self.start_btn.setMinimumHeight(44)
        self.start_btn.setMinimumWidth(160)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_process)
        footer_row.addWidget(self.start_btn)
        chapters_layout.addLayout(footer_row)

        right_column.addWidget(chapters_panel, 1)

        # --- Card 4: Progress & Log ---
        progress_panel = QFrame()
        progress_panel.setObjectName("GlassPanel")
        progress_layout = QVBoxLayout(progress_panel)
        progress_layout.setContentsMargins(20, 16, 20, 16)
        progress_layout.setSpacing(10)

        progress_title = QLabel("📊  Progress")
        progress_title.setObjectName("SectionLabel")
        progress_layout.addWidget(progress_title)

        # Progress Info (Percentage and ETA)
        self.progress_info_layout = QHBoxLayout()
        self.progress_percent_label = QLabel("")
        self.progress_percent_label.setStyleSheet("color: #ff6b6b; font-weight: bold; font-size: 14px;")
        self.progress_eta_label = QLabel("")
        self.progress_eta_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        self.progress_info_layout.addWidget(self.progress_percent_label)
        self.progress_info_layout.addStretch()
        self.progress_info_layout.addWidget(self.progress_eta_label)
        progress_layout.addLayout(self.progress_info_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("LogArea")
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(80)
        self.log_area.setPlaceholderText("Activity log...")
        progress_layout.addWidget(self.log_area)

        right_column.addWidget(progress_panel)

        columns_layout.addLayout(right_column, 1)

        main_layout.addLayout(columns_layout, 1)

    def load_thumbnail(self, url):
        """Load thumbnail from URL and display it."""
        try:
            # Download the thumbnail
            with urllib.request.urlopen(url, timeout=5) as response:
                data = response.read()
            
            # Create pixmap from data
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            
            # Scale to fit the label while maintaining aspect ratio
            scaled = pixmap.scaled(320, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled)
        except Exception as e:
            self.log(f"⚠️ Could not load thumbnail: {e}")
            self.thumbnail_label.setText("🎬")

    def log(self, message):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def fetch_metadata(self):
        url = (self.url_input.text() or "").strip()
        if not url:
            self.log("❌ Enter a URL first")
            return

        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("⏳ Analyzing...")
        self.start_btn.setEnabled(False)
        self.log("📡 Analyzing video...")
        
        self.metaworker = MetadataWorker(url)
        self.metaworker.finished.connect(self.on_metadata_fetched)
        self.metaworker.error.connect(self.on_error)
        self.metaworker.start()

    def on_metadata_fetched(self, data):
        self.video_data = data
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("🔍  Analyze")
        self.log("✅ Video analyzed successfully")

        # Load Thumbnail
        thumbnail_url = data.get('thumbnail', '')
        if thumbnail_url:
            self.load_thumbnail(thumbnail_url)

        # Update Video Info Labels
        title = data.get('title', 'Unknown Title')
        duration = data.get('duration', 0)
        duration_str = format_seconds(duration)
        channel = data.get('channel', data.get('uploader', 'Unknown'))
        
        self.video_title_label.setText(title[:60] + "..." if len(title) > 60 else title)
        self.video_info_label.setText(f"👤 {channel}  •  🕐 {duration_str}")

        # Enable Start Button
        self.start_btn.setEnabled(True)

        # Update Qualities
        self.quality_combo.clear()
        formats = data.get('formats', [])
        # Filter: bestvideo with height <= 1080. Fallback to best if none.
        seen_qualities = set()
        for f in formats:
            height = f.get('height')
            if height and height <= 1080:
                ext = f.get('ext')
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                if vcodec != 'none':
                    label = f"{height}p ({ext}) - {f.get('format_note', '')}"
                    if label not in seen_qualities:
                        # Append +bestaudio/best to ensure audio is merged
                        fmt_id = f['format_id']
                        if acodec == 'none':
                            fmt_id += "+bestaudio/best"
                        self.quality_combo.addItem(label, fmt_id)
                        seen_qualities.add(label)
        
        self.quality_combo.addItem("Best Available (Auto)", "bestvideo[height<=1080]+bestaudio/best[height<=1080]")

        # Update Chapters
        self.chapter_table.setRowCount(0)
        chapters = data.get('chapters', [])

        if chapters:
            for i, ch in enumerate(chapters):
                start = ch['start_time']
                end = chapters[i+1]['start_time'] if i+1 < len(chapters) else duration
                self.add_row(ch['title'], start, end)
        else:
            self.log("⚠️ No chapters found. Full video will be processed.")
            self.add_row("Full Video", 0, duration)

    def add_row(self, title="", start=0, end=0):
        row = self.chapter_table.rowCount()
        self.chapter_table.insertRow(row)
        self.chapter_table.setItem(row, 0, QTableWidgetItem(str(title)))
        self.chapter_table.setItem(row, 1, QTableWidgetItem(format_seconds(float(start))))
        self.chapter_table.setItem(row, 2, QTableWidgetItem(format_seconds(float(end))))
        self.update_table_stats()

    def delete_row(self):
        rows = self.chapter_table.selectionModel().selectedRows()
        if not rows:
            # Fallback for when no rows are selected - remove last
            self.chapter_table.removeRow(self.chapter_table.rowCount() - 1)
        else:
            for row in reversed(rows):
                self.chapter_table.removeRow(row.row())
        self.update_table_stats()

    def update_table_stats(self):
        count = self.chapter_table.rowCount()
        self.chapter_count_label.setText(str(count))
        
        total_sec = 0
        for row in range(count):
            try:
                start = parse_time(self.chapter_table.item(row, 1).text())
                end = parse_time(self.chapter_table.item(row, 2).text())
                total_sec += (end - start)
            except:
                pass
        
        dur_str = format_seconds(total_sec)
        self.stats_label.setText(f"{count} {'chapter' if count == 1 else 'chapters'} • {dur_str} total")

    def on_error(self, msg):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("🔍  Analyze")
        self.progress_percent_label.setText("")
        self.progress_eta_label.setText("")
        # Only enable start if we already have video data
        if self.video_data:
            self.start_btn.setEnabled(True)
        self.log(f"❌ Error: {msg}")

    def start_process(self):
        url = (self.url_input.text() or "").strip()
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
            start = parse_time(self.chapter_table.item(row, 1).text())
            end = parse_time(self.chapter_table.item(row, 2).text())
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
        
        # Pass the title to the worker as a hint
        title_hint = self.video_data.get('title', '') if self.video_data else None

        self.worker = ProcessWorker(self.url_input.text().strip(), self.quality_combo.currentData(), chapters, video_filename=title_hint)
        self.worker.progress.connect(self.on_progress)
        self.worker.download_progress.connect(self.on_download_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.log(msg)
        # Clear download info if we moved past download
        if val > 15:
            self.progress_percent_label.setText("")
            self.progress_eta_label.setText("")

    def on_download_progress(self, percent, eta):
        self.progress_percent_label.setText(percent)
        self.progress_eta_label.setText(eta)

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_percent_label.setText("")
        self.progress_eta_label.setText("")
        self.log("✨ All processing complete!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AutoSplitApp()
    window.show()
    sys.exit(app.exec())
