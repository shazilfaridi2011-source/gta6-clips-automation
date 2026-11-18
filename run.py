import io
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

ROOT = Path(__file__).parent
MAX_DOWNLOAD_BYTES = 450 * 1024 * 1024
MAX_CLIP_SECONDS = 58
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def fail(message):
    raise RuntimeError(message)

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def get_allowed():
    data = load_json(ROOT / "approved_streamers.json")
    return {
        (x["name"].strip().casefold(), x["permission_reference"].strip())
        for x in data.get("approved_streamers", [])
        if x.get("name") and x.get("permission_reference")
        and not x["name"].startswith("REPLACE_")
        and not x["permission_reference"].startswith("REPLACE_")
    }

def fetch_feed(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        fail("CLIP_FEED_URL must be a valid HTTPS URL.")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data.get("clips"), list):
        fail("Feed JSON must contain a 'clips' array.")
    return data["clips"]

def download_clip(url, destination):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        fail("Clip media URL must use HTTPS.")
    with requests.get(url, stream=True, timeout=(20, 120)) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "video" not in content_type and "octet-stream" not in content_type:
            fail(f"Expected a video download; got content-type {content_type!r}.")
        total = 0
        with open(destination, "wb") as out:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    fail("Clip exceeds the 450 MB safety limit.")
                out.write(chunk)

def find_font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None

def make_overlay(path, title, commentary, streamer):
    image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font_path = find_font()
    title_font = ImageFont.truetype(font_path, 54) if font_path else ImageFont.load_default()
    body_font = ImageFont.truetype(font_path, 34) if font_path else ImageFont.load_default()
    small_font = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()

    # Readable top and bottom panels; text comes from the approved feed.
    draw.rounded_rectangle((48, 90, 1032, 340), radius=32, fill=(0, 0, 0, 170))
    draw.rounded_rectangle((48, 1510, 1032, 1815), radius=32, fill=(0, 0, 0, 175))

    def wrap(text, font, max_width, max_lines):
        words = str(text).split()
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
            if len(lines) >= max_lines:
                break
        if current and len(lines) < max_lines:
            lines.append(current)
        return lines

    y = 125
    for line in wrap(title, title_font, 900, 2):
        draw.text((88, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += 72

    draw.text((88, 1545), f"CLIP FROM: {streamer[:48]}", font=small_font, fill=(120, 220, 255, 255))
    y = 1600
    for line in wrap(commentary, body_font, 900, 4):
        draw.text((88, y), line, font=body_font, fill=(255, 255, 255, 255))
        y += 48
    draw.text((88, 1760), "streamergta6yuio[clips", font=small_font, fill=(255, 220, 100, 255))
    image.save(path)

def edit_video(source, output, overlay):
    cmd = [
        "ffmpeg", "-y", "-i", str(source), "-i", str(overlay),
        "-t", str(MAX_CLIP_SECONDS),
        "-filter_complex",
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[base];"
        "[base][1:v]overlay=0:0[v]",
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        "-pix_fmt", "yuv420p", str(output)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def youtube_client():
    required = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        fail("Missing GitHub Actions secrets: " + ", ".join(missing))
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def upload(youtube, video_path, clip):
    title = str(clip.get("title", "GTA 6 streamer moment")).strip()
    title = re.sub(r"\s+", " ", title)[:85]
    if "#Shorts" not in title:
        title = (title[:76] + " #Shorts").strip()
    commentary = str(clip.get("commentary", "")).strip()
    if len(commentary) < 20:
        fail("Each clip needs meaningful original commentary (at least 20 characters).")
    description = str(clip.get("description", "")).strip()
    description += "\n\nOriginal commentary/context added. Clip used with creator permission."
    description += "\n#GTA6 #Shorts"
    tags = list(dict.fromkeys(["GTA6", "gaming", "Shorts"] + [
        str(x).strip() for x in clip.get("tags", []) if str(x).strip()
    ]))[:15]
    body = {
        "snippet": {
            "title": title,
            "description": description[:4900],
            "tags": tags,
            "categoryId": "20",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True),
    )
    response = request.execute()
    print("Uploaded video ID:", response.get("id"))

def main():
    feed_url = os.getenv("CLIP_FEED_URL", "").strip()
    if not feed_url:
        fail("Set the CLIP_FEED_URL GitHub Actions secret.")
    allowed = get_allowed()
    if not allowed:
        fail("Add at least one real, explicitly approved streamer to approved_streamers.json.")

    state_path = ROOT / "state.json"
    state = load_json(state_path)
    processed = set(state.get("processed_clip_ids", []))
    clips = fetch_feed(feed_url)

    selected = None
    for clip in clips:
        clip_id = str(clip.get("id", "")).strip()
        streamer = str(clip.get("streamer", "")).strip().casefold()
        permission_ref = str(clip.get("permission_reference", "")).strip()
        if not clip_id or clip_id in processed:
            continue
        if (streamer, permission_ref) not in allowed:
            print("Skipping clip not matched to allowlist:", clip_id)
            continue
        if not clip.get("video_url") or not clip.get("title") or not clip.get("commentary"):
            print("Skipping incomplete feed item:", clip_id)
            continue
        selected = clip
        break

    if selected is None:
        print("No new, eligible clip found. Nothing to upload.")
        return

    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        source = temp / "source.mp4"
        overlay = temp / "overlay.png"
        output = temp / "short.mp4"
        download_clip(selected["video_url"], source)
        make_overlay(overlay, selected["title"], selected["commentary"], selected["streamer"])
        edit_video(source, output, overlay)
        youtube = youtube_client()
        upload(youtube, output, selected)

    processed.add(str(selected["id"]))
    state["processed_clip_ids"] = sorted(processed)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
