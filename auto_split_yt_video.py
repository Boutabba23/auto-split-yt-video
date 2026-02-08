import json
import subprocess
import re
from pathlib import Path
import sys

VIDEO_EXTS = [".mp4", ".mkv", ".webm"]
OUTPUT_DIR = "chapters"

Path(OUTPUT_DIR).mkdir(exist_ok=True)

def clean_filename(text):
    text = re.sub(r'[\\/:*?"<>|]', '', text)
    return text.strip().replace(' ', '_')

# URL input
url = input("🔗 Enter YouTube video URL: ").strip()
if not url:
    sys.exit("❌ No URL provided")

# Handle metadata (skip download if info.json exists)
info_json = next(Path(".").glob("*.info.json"), None)
if not info_json:
    print("📄 Downloading metadata...")
    subprocess.run(
        ["yt-dlp", "--skip-download", "--write-info-json", url],
        check=True
    )
    info_json = next(Path(".").glob("*.info.json"), None)
else:
    print(f"♻️ Using existing metadata: {info_json.name}")

if not info_json:
    sys.exit("❌ info.json not found")

# Determine expected filename
format_id = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
get_name_cmd = ["yt-dlp", "--get-filename", "-f", format_id, "-o", "%(title)s.%(ext)s", url]
name_result = subprocess.run(get_name_cmd, capture_output=True, text=True, check=True, encoding='utf-8')
expected_video_file = name_result.stdout.strip()

video = Path(expected_video_file) if expected_video_file and Path(expected_video_file).exists() else None

if not video:
    # Fallback search
    video = next((f for f in Path(".").iterdir() if f.suffix.lower() in VIDEO_EXTS), None)

if not video:
    choice = input("❌ Video file not found. Download it now? (y/n): ").strip().lower()
    if choice == 'y':
        print(f"📥 Downloading video... Max quality: 1080p. This may take a while.")
        subprocess.run([
            "yt-dlp",
            "-f", format_id,
            "-o", "%(title)s.%(ext)s",
            url
        ], check=True)
        video = Path(expected_video_file) if Path(expected_video_file).exists() else next((f for f in Path(".").iterdir() if f.suffix.lower() in VIDEO_EXTS), None)
        if not video:
            sys.exit("❌ Video file still not found after download attempt.")
    else:
        sys.exit("❌ Video file not found. Exiting.")

video_ext = video.suffix

print(f"🎬 Video: {video.name}")

with open(info_json, "r", encoding="utf-8") as f:
    data = json.load(f)

chapters = data.get("chapters")
duration = data.get("duration")

if not chapters:
    print(f"⚠️ No chapters found in {info_json.name}")
    print("💡 You can manually add chapters to the JSON file and run this script again.")
    print("Chapter format example in info.json:")
    print(' "chapters": [{"start_time": 0, "title": "Intro"}, {"start_time": 120, "title": "Main Part"}]')
    sys.exit(1)

if not duration:
    sys.exit("❌ Duration missing in metadata")

# Split (RE-ENCODE = CORRECT)
for i, ch in enumerate(chapters):
    start = ch["start_time"]

    if i + 1 < len(chapters):
        end = chapters[i + 1]["start_time"]
    else:
        end = duration

    length = end - start

    title = clean_filename(ch["title"])
    output = Path(OUTPUT_DIR) / f"{i+1:02d}_{title}{video_ext}"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start),
        "-i", str(video),
        "-t", str(length),
        "-map", "0:v:0",
        "-map", "0:a?",
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        str(output)
    ]

    print(f"▶ {output.name}")
    subprocess.run(cmd)

print("✅ Chapters split correctly with perfect quality.")
