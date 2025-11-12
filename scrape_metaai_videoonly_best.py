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
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    return safe or "video"

async def head_size(context, url: str) -> int:
    # Coba dapatkan Content-Length dari HEAD/GET (tanpa download penuh)
    try:
        resp = await context.request.head(url, timeout=15000)
        if resp.ok:
            cl = resp.headers.get("content-length")
            if cl and cl.isdigit():
                return int(cl)
    except Exception:
        pass
    try:
        # fallback ke GET range kecil
        resp = await context.request.get(url, headers={"Range": "bytes=0-0"}, timeout=15000)
        if resp.ok:
            cl = resp.headers.get("content-length") or resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                return int(cl)
    except Exception:
        pass
    return 0

def heuristic_score(url: str) -> float:
    # Skor berdasarkan karakteristik URL (tanpa network). Lebih tinggi = lebih baik.
    score = 0.0
    if ".mp4" not in url:
        return -1e9  # buang non-mp4
    if "bytestart" in url or "byteend" in url:
        score -= 100.0  # segmen parsial
    if "dash" in url or "base" in url:
        score += 10.0
    if "/video" in url or "/f2/m" in url or "/m412/" in url:
        score += 5.0
    score += len(url) / 100.0  # panjang URL sedikit memberi bobot
    return score

async def pick_best_video(context, urls):
    # Pilih 1 URL video terbaik (mp4, non-segmen, ukuran terbesar jika tersedia).
    candidates = [u for u in urls if (".mp4" in u)]
    if not candidates:
        return None
    prelim = sorted(candidates, key=lambda u: heuristic_score(u), reverse=True)[:8]  # top 8
    sized = []
    for u in prelim:
        sz = await head_size(context, u)
        sized.append((sz, heuristic_score(u), u))
    sized.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return sized[0][2] if sized else prelim[0]

def contains_video_stream(path: str) -> bool:
    # Gunakan ffprobe untuk memastikan file punya stream video (bukan audio-only).
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, text=True
        )
        return "video" in result.stdout
    except Exception:
        return True  # fallback: anggap valid jika ffprobe tidak tersedia

async def scrape_one(context, url: str):
    data = {"url": url, "title": "", "metas": {}, "images": [], "videos": [], "picked_video": None, "saved_path": None}
    page = await context.new_page()

    collected = set()
    page.on("request", lambda req: (collected.add(req.url) if (".mp4" in req.url or ".m3u8" in req.url) else None))

    print(f"🔍 Membuka: {url}")
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(5000)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    data["title"] = soup.title.string.strip() if soup.title else "MetaAI"
    for meta in soup.find_all("meta"):
        k = meta.get("property") or meta.get("name")
        v = meta.get("content")
        if k and v:
            data["metas"][k] = v
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            data["images"].append(urljoin(url, src))

    data["videos"] = sorted(collected)
    best = await pick_best_video(context, data["videos"])
    data["picked_video"] = best

    if best:
        safe_title = sanitize_filename(data["title"])
        filename = os.path.join(DOWNLOAD_DIR, f"{safe_title}.mp4")
        print(f"⬇️ Mengunduh 1 video terbaik: {best}")
        try:
            resp = await context.request.get(best)
            if resp.ok:
                with open(filename, "wb") as f:
                    f.write(await resp.body())
                if contains_video_stream(filename):
                    data["saved_path"] = filename
                else:
                    print("🗑️ File terunduh tidak mengandung stream video. Menghapus.")
                    os.remove(filename)
                    data["saved_path"] = None
            else:
                print(f"⚠️ Gagal mengunduh: status={resp.status}")
        except Exception as e:
            print(f"⚠️ Error unduh: {e}")

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

    print("✅ Selesai. Hanya 1 video terbaik per URL disimpan.")

if __name__ == "__main__":
    asyncio.run(main())
