#!/usr/bin/env python3
import os
import json
import asyncio
import subprocess
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

DOWNLOAD_DIR = "downloads"
OUTPUT_FILE = "output_htmlvideo.json"
URL_FILE = "urls.txt"


def sanitize_filename(name: str):
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    return safe or "video"


def contains_video_stream(path: str) -> bool:
    """Gunakan ffprobe untuk memastikan file punya stream video (bukan audio-only)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, text=True
        )
        return "video" in result.stdout
    except Exception:
        return True


async def scrape_one(context, url: str):
    data = {
        "url": url,
        "title": "",
        "metas": {},
        "images": [],
        "videos": [],
        "saved_path": None
    }

    page = await context.new_page()
    print(f"🔍 Membuka: {url}")
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(5000)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    # Judul dan meta
    data["title"] = soup.title.string.strip() if soup.title else "MetaAI"
    for meta in soup.find_all("meta"):
        k = meta.get("property") or meta.get("name")
        v = meta.get("content")
        if k and v:
            data["metas"][k] = v

    # Ambil semua gambar (opsional)
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            data["images"].append(urljoin(url, src))

    # 🎯 Ambil langsung video dari <video> dan <source>
    videos = []
    for tag in soup.find_all(["video", "source"]):
        src = tag.get("src")
        if src and ".mp4" in src:
            videos.append(urljoin(url, src))
    data["videos"] = sorted(set(videos))

    # Ambil hanya video pertama (paling relevan di HTML)
    if data["videos"]:
        best = data["videos"][0]
        print(f"⬇️ Mengunduh video utama: {best}")
        safe_title = sanitize_filename(data["title"])
        filename = os.path.join(DOWNLOAD_DIR, f"{safe_title}.mp4")
        try:
            resp = await context.request.get(best)
            if resp.ok:
                with open(filename, "wb") as f:
                    f.write(await resp.body())
                if contains_video_stream(filename):
                    data["saved_path"] = filename
                else:
                    print("🗑️ File tidak mengandung stream video. Menghapus.")
                    os.remove(filename)
                    data["saved_path"] = None
            else:
                print(f"⚠️ Gagal mengunduh: status={resp.status}")
        except Exception as e:
            print(f"⚠️ Error saat unduh: {e}")
    else:
        print("⚠️ Tidak ditemukan tag <video> atau <source> di halaman.")

    await page.close()
    return data


async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    if not os.path.exists(URL_FILE):
        print(f"❌ File {URL_FILE} tidak ditemukan!")
        return

    with open(URL_FILE, "r", encoding="utf-8") as f:
        urls = [u.strip() for u in f if u.strip()]

    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        for url in urls:
            try:
                r = await scrape_one(context, url)
                results.append(r)
            except Exception as e:
                print(f"❌ Gagal memproses {url}: {e}")

        await browser.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"✅ Selesai! Hasil tersimpan di {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
