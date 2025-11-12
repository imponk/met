#!/usr/bin/env python3
"""
scrape_metaai_auto.py
=====================
Scraper otomatis Meta.ai dengan Playwright.
- Membaca daftar URL dari urls.txt
- Menjalankan headless browser
- Menyimpan semua .mp4 ke folder downloads/
- Menyimpan data JSON lengkap
"""

import os
import json
import asyncio
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


DOWNLOAD_DIR = "downloads"
URL_FILE = "urls.txt"
OUTPUT_FILE = "output_playwright.json"


async def scrape_meta(page, url):
    """Scrape satu halaman Meta.ai"""
    data = {"url": url, "title": "", "metas": {}, "images": [], "videos": []}
    collected_videos = set()

    page.on("request", lambda req: (
        collected_videos.add(req.url)
        if any(ext in req.url for ext in [".mp4", ".m3u8"])
        else None
    ))

    print(f"🔍 Membuka: {url}")
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(5000)  # tunggu 5 detik biar video sempat load

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
        urls = [line.strip() for line in f if line.strip()]

    all_data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        for url in urls:
            page = await context.new_page()
            try:
                data = await scrape_meta(page, url)
                all_data.append(data)

                # Unduh video-video
                for i, vurl in enumerate(data["videos"], 1):
                    filename = os.path.join(DOWNLOAD_DIR, f"{data['title']}_{i}.mp4")
                    print(f"⬇️  Mengunduh video {i}: {vurl}")
                    try:
                        video_data = await context.request.get(vurl)
                        if video_data.ok:
                            with open(filename, "wb") as vf:
                                vf.write(await video_data.body())
                    except Exception as e:
                        print(f"⚠️ Gagal unduh {vurl}: {e}")

            except Exception as e:
                print(f"❌ Gagal scrape {url}: {e}")

        await browser.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Selesai! Hasil disimpan ke {OUTPUT_FILE} dan folder {DOWNLOAD_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
