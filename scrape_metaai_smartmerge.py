#!/usr/bin/env python3
import os
import json
import asyncio
import subprocess
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

DOWNLOAD_DIR = "downloads"
OUTPUT_FILE = "output_playwright.json"
URL_FILE = "urls.txt"


def sanitize_filename(name: str):
    return "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()


def get_media_type(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "a:v", path],
            capture_output=True, text=True
        )
        if "codec_type=video" in result.stdout and "codec_type=audio" in result.stdout:
            return "av"
        elif "codec_type=video" in result.stdout:
            return "video"
        elif "codec_type=audio" in result.stdout:
            return "audio"
    except Exception:
        pass
    return "unknown"


def get_duration(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


async def scrape_meta(page, url):
    data = {"url": url, "title": "", "metas": {}, "images": [], "videos": []}
    collected_videos = set()

    page.on("request", lambda req: (
        collected_videos.add(req.url)
        if any(ext in req.url for ext in [".mp4", ".m3u8"])
        else None
    ))

    print(f"🔍 Membuka: {url}")
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(5000)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    data["title"] = soup.title.string.strip() if soup.title else ""
    for meta in soup.find_all("meta"):
        k = meta.get("property") or meta.get("name")
        v = meta.get("content")
        if k and v:
            data["metas"][k] = v

    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            data["images"].append(urljoin(url, src))

    data["videos"] = sorted(collected_videos)
    return data


async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if not os.path.exists(URL_FILE):
        print(f"❌ File {URL_FILE} tidak ditemukan!")
        return

    with open(URL_FILE, "r", encoding="utf-8") as f:
        urls = [u.strip() for u in f if u.strip()]

    all_data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        for url in urls:
            page = await context.new_page()
            data = await scrape_meta(page, url)
            all_data.append(data)

            safe_title = sanitize_filename(data["title"]) or "video"
            video_files = []

            for i, vurl in enumerate(data["videos"], 1):
                filename = os.path.join(DOWNLOAD_DIR, f"{safe_title}_{i}.mp4")
                try:
                    print(f"⬇️ Mengunduh {vurl}")
                    resp = await context.request.get(vurl)
                    if resp.ok:
                        with open(filename, "wb") as f:
                            f.write(await resp.body())
                            video_files.append(filename)
                except Exception as e:
                    print(f"⚠️ Gagal unduh {vurl}: {e}")

            audio_tracks, video_tracks = [], []
            for vf in video_files:
                mtype = get_media_type(vf)
                if mtype == "audio":
                    audio_tracks.append(vf)
                elif mtype == "video":
                    video_tracks.append(vf)

            print(f"🎬 Deteksi {len(video_tracks)} video-only, {len(audio_tracks)} audio-only")

            if video_tracks and audio_tracks:
                merged = os.path.join(DOWNLOAD_DIR, f"{safe_title}_merged.mp4")
                v = video_tracks[0]
                a = min(audio_tracks, key=lambda x: abs(get_duration(x) - get_duration(v)))
                print(f"🔗 Menggabungkan: {os.path.basename(v)} + {os.path.basename(a)} -> {merged}")
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", v, "-i", a, "-c:v", "copy", "-c:a", "aac", merged],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                except Exception as e:
                    print(f"⚠️ Gagal merge: {e}")

        await browser.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Selesai! Lihat folder {DOWNLOAD_DIR}/ untuk hasil gabungan.")


if __name__ == "__main__":
    asyncio.run(main())
