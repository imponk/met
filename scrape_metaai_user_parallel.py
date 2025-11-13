import asyncio
import os
import re
import json
import aiofiles
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

URL_FILE = "urls.txt"
DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def scroll_profile(page):
    """Scroll agar semua postingan user termuat."""
    last_height = 0
    for _ in range(15):  # sampai 15 kali scroll panjang
        await page.mouse.wheel(0, 30000)
        await page.wait_for_timeout(1500)
        new_height = await page.evaluate("() => document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


async def collect_posts_from_user(context, username):
    url = f"https://meta.ai/{username}"
    page = await context.new_page()

    print(f"🔍 Mengambil postingan dari profil: {url}")
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(2000)

    # scroll to load all posts
    await scroll_profile(page)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    links = [a.get("href") for a in soup.find_all("a", href=True)]
    posts = [f"https://meta.ai{l}" for l in links if "/post/" in l]

    print(f"✅ Ditemukan {len(posts)} posting dari {username}")

    await page.close()
    return posts


async def extract_best_video(context, post_url):
    """Ambil video terbaik dari 1 posting Meta.ai"""
    page = await context.new_page()
    print(f"➡️ Membuka: {post_url}")

    await page.goto(post_url, wait_until="networkidle")
    await page.wait_for_timeout(2000)

    # Try HTML analysis
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    # Cari semua tag <video>
    video_tags = soup.find_all("video")
    candidates = []

    for v in video_tags:
        src = v.get("src")
        if src and src.endswith(".mp4"):
            candidates.append(src)

    # Cari MP4 lewat regex dari HTML
    regex_links = re.findall(r'https?://[^"<>\s]+\.mp4[^"<>\s]*', html)
    for l in regex_links:
        if l not in candidates:
            candidates.append(l)

    # Ambil link yang ditangkap Playwright dari request intercept
    async def log_req(req):
        url = req.url
        if ".mp4" in url and url not in candidates:
            candidates.append(url)

    page.on("request", log_req)
    await page.wait_for_timeout(2000)

    await page.close()

    # Pilih link MP4 terpanjang berdasarkan query byteend
    def score(url):
        m = re.search(r"byteend=(\d+)", url)
        return int(m.group(1)) if m else 0

    candidates = sorted(candidates, key=score, reverse=True)

    if not candidates:
        print("❌ Tidak ada video ditemukan.")
        return None

    best = candidates[0]
    print(f"🎯 Video terbaik ditemukan:\n{best}\n")
    return best


async def download_video(url, filename):
    """Download MP4"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                print(f"⚠️ Gagal download {url}")
                return
            data = await resp.read()
            async with aiofiles.open(filename, "wb") as f:
                await f.write(data)
            print(f"💾 Disimpan: {filename}")


async def process_post(context, post_url):
    best_video = await extract_best_video(context, post_url)

    out_json = os.path.join(DOWNLOAD_DIR, "output_playwright.json")

    data_entry = {
        "post_url": post_url,
        "video": best_video
    }

    # append ke json list
    if not os.path.exists(out_json):
        json.dump([data_entry], open(out_json, "w"), indent=2)
    else:
        arr = json.load(open(out_json))
        arr.append(data_entry)
        json.dump(arr, open(out_json, "w"), indent=2)

    if best_video:
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", post_url)
        file_path = os.path.join(DOWNLOAD_DIR, f"{safe_name}.mp4")
        await download_video(best_video, file_path)


async def main():
    urls = []

    # Baca input dari urls.txt
    with open(URL_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            urls.append(line)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        final_urls = []

        # deteksi username
        for u in urls:
            if u.startswith("@"):
                posts = await collect_posts_from_user(context, u)
                final_urls.extend(posts)
            else:
                final_urls.append(u)

        print(f"📌 Total URL posting yang akan diproses: {len(final_urls)}")

        tasks = [process_post(context, u) for u in final_urls]
        await asyncio.gather(*tasks)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
