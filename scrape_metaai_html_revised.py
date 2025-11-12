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
        return True  # fallback, dianggap video


async def scrape_one(context, url: str):
    """Scrape satu halaman Meta.ai"""
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

    # Tunggu sampai elemen video muncul (maks 10 detik)
    try:
        await page.wait_for_selector("video, source", timeout=10000)
    except:
        print("⚠️ Tidak ada elemen <video> atau <source> setelah 10 detik.")

    # Tambah waktu sedikit untuk load konten dinamis
    await page.wait_for_timeout(2000)

    # Ambil isi HTML setelah elemen video muncul
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    # Ambil judul dan meta
    data["title"] = soup.title.string.strip() if soup.title else "MetaAI"
    for meta in soup.find_all("meta"):
        k = meta.get("property") or meta.get("name")
        v = meta.get("content")
        if k and v:
            data["metas"][k] = v

    # Ambil gambar (opsional)
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            data["images"].append(urljoin(url, src))

    # Ambil video dari tag <video> dan <source>
    videos = []
    for tag in soup.find_all(["video", "source"]):
        src = tag.get("src") or tag.get("data-src") or tag.get("srcset")
        if src and ".mp4" in src:
            full_url = urljoin(url, src)
            videos.append(full_url)
            print(f"🎥 Ditemukan: {full_url}")

    data["videos"] = sorted(set(videos))

    # Unduh hanya 1 video pertama
    if data["videos"]:
        best = data["videos"][0]
        safe_title = sanitize_filename(data["title"])
        filename = os.path.join(DOWNLOAD_DIR, f"{safe_title}.mp4")
        print(f"⬇️ Mengunduh video utama: {best}")

        try:
            resp = await context.request.get(best)
            if resp.ok:
                with open(filename, "wb") as f:
                    f.write(await resp.body())

                if contains_video_stream(filename):
                    data["saved_path"] = filename
                    print(f"✅ Tersimpan: {filename}")
                else:
                    print(f"🗑️ {filename} tidak mengandung stream video, dihapus.")
                    os.remove(filename)
                    data["saved_path"] = None
            else:
                print(f"⚠️ Gagal mengunduh: status={resp.status}")
        except Exception as e:
            print(f"⚠️ Error saat unduh: {e}")
    else:
        print("⚠️ Tidak ditemukan video yang valid di halaman.")

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

    # Simpan hasil JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"✅ Selesai! Hasil tersimpan di {OUTPUT_FILE}")

    # Debug tampilan isi folder downloads
    print("\n📂 Daftar isi folder downloads:")
    os.system("ls -lh downloads || true")


if __name__ == "__main__":
    asyncio.run(main())
