#!/usr/bin/env python3
import os
import json
import asyncio
import subprocess
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

DOWNLOAD_DIR = "downloads"
OUTPUT_FILE = "output_playwright.json"
URL_FILE = "urls.txt"


def sanitize_filename(name: str):
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    return safe or "video"


def contains_video_stream(path: str) -> bool:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True,
            text=True,
        )
        return "video" in result.stdout
    except Exception:
        return True


async def pick_best_video(urls):
    if not urls:
        return None
    video_urls = [u for u in urls if ".mp4" in u and "audio" not in u.lower()]
    prioritized = [u for u in video_urls if any(x in u.lower() for x in ["dash", "hd", "vid"])]
    if prioritized:
        return prioritized[0]
    return sorted(video_urls, key=len, reverse=True)[0] if video_urls else None


async def scrape_one(context, url):
    data = {"url": url, "title": "", "videos": [], "picked_video": None, "saved_path": None}
    page = await context.new_page()
    print(f"🔍 Membuka halaman: {url}")
    collected = set()
    page.on("request", lambda req: collected.add(req.url) if ".mp4" in req.url else None)
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(8000)
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    data["title"] = soup.title.string.strip() if soup.title else "MetaAI"
    data["videos"] = sorted(collected)
    best = await pick_best_video(data["videos"])
    data["picked_video"] = best

    if best:
        safe_title = sanitize_filename(data["title"])
        filename = os.path.join(DOWNLOAD_DIR, f"{safe_title}.mp4")
        if os.path.exists(filename):
            print(f"📁 Skip {filename}, sudah ada.")
            data["saved_path"] = filename
            return data
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
                    print("🗑️ File hanya audio, dihapus.")
                    os.remove(filename)
            else:
                print(f"⚠️ Gagal unduh video. Status: {resp.status}")
        except Exception as e:
            print(f"⚠️ Error unduh: {e}")
    else:
        print("⚠️ Tidak ada file video .mp4 ditemukan.")
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

        async def process_url(u):
            try:
                r = await scrape_one(context, u)
                results.append(r)
            except Exception as e:
                print(f"❌ Gagal memproses {u}: {e}")

        await asyncio.gather(*(process_url(u) for u in urls))
        await browser.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("🎯 Selesai! Semua video tersimpan di folder downloads/.")


if __name__ == "__main__":
    asyncio.run(main())
