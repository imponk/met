#!/usr/bin/env python3
import os
import json
import asyncio
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import async_playwright

DOWNLOAD_DIR = "downloads"
OUTPUT_FILE = "output_playwright.json"
URL_FILE = "urls.txt"


def sanitize_filename(name: str):
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    return safe or "video"


def contains_video_stream(path: str) -> bool:
    """Gunakan ffprobe untuk pastikan file mengandung stream video."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, text=True
        )
        return "video" in result.stdout
    except Exception:
        return True


async def pick_best_video(urls):
    """Pilih satu video .mp4 terbaik."""
    if not urls:
        return None
    good = [u for u in urls if ".mp4" in u and "bytestart" not in u and "byteend" not in u]
    if not good:
        good = [u for u in urls if ".mp4" in u]
    return sorted(good, key=len, reverse=True)[0] if good else None


async def scrape_one(context, url):
    """Scrape satu postingan Meta.ai"""
    data = {"url": url, "title": "", "metas": {}, "videos": [], "saved_path": None}

    page = await context.new_page()
    print(f"🔍 Membuka: {url}")

    collected = set()
    # Dengarkan semua permintaan jaringan .mp4
    page.on("request", lambda req: collected.add(req.url) if ".mp4" in req.url else None)

    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(8000)  # tunggu JS selesai

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    data["title"] = soup.title.string.strip() if soup.title else "MetaAI"

    data["videos"] = sorted(collected)
    best = await pick_best_video(data["videos"])
    data["picked_video"] = best

    if best:
        safe_title = sanitize_filename(data["title"])
        filename = os.path.join(DOWNLOAD_DIR, f"{safe_title}.mp4")
        print(f"⬇️ Mengunduh: {best}")
        try:
            resp = await context.request.get(best)
            if resp.ok:
                with open(filename, "wb") as f:
                    f.write(await resp.body())
                if contains_video_stream(filename):
                    data["saved_path"] = filename
                    print(f"✅ Tersimpan: {filename}")
                else:
                    print("🗑️ File tidak berisi video, dihapus.")
                    os.remove(filename)
            else:
                print(f"⚠️ Gagal: status={resp.status}")
        except Exception as e:
            print(f"⚠️ Error unduh: {e}")
    else:
        print("⚠️ Tidak ditemukan .mp4 di network log.")

    await page.close()
    return data


async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if not os.path.exists(URL_FILE):
        print("❌ File urls.txt tidak ditemukan!")
        return

    urls = [u.strip() for u in open(URL_FILE, "r", encoding="utf-8") if u.strip()]
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        for u in urls:
            try:
                r = await scrape_one(context, u)
                results.append(r)
            except Exception as e:
                print(f"❌ Gagal memproses {u}: {e}")

        await browser.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("🎯 Selesai! Video disimpan di folder downloads/.")


if __name__ == "__main__":
    asyncio.run(main())
