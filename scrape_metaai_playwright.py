#!/usr/bin/env python3
"""
scrape_metaai_playwright.py
===========================
Versi Playwright — untuk mengambil URL video (mp4/m3u8) dari halaman Meta.ai
"""

import sys
import json
import asyncio
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


async def scrape_meta(url):
    data = {"url": url, "title": "", "metas": {}, "images": [], "videos": []}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"🔍 Membuka halaman: {url}")
        await page.goto(url, wait_until="networkidle")

        # ambil HTML setelah JavaScript selesai
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        # judul & meta tags
        data["title"] = soup.title.string.strip() if soup.title else ""
        for meta in soup.find_all("meta"):
            k = meta.get("property") or meta.get("name")
            v = meta.get("content")
            if k and v:
                data["metas"][k] = v

        # ambil semua <img>
        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                data["images"].append(urljoin(url, src))

        # ambil semua permintaan (request) di network log
        videos = set()
        for req in page.context.requests:
            if any(ext in req.url for ext in [".mp4", ".m3u8"]):
                videos.add(req.url)

        data["videos"] = sorted(videos)
        await browser.close()
        return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scrape_metaai_playwright.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    print("🚀 Menjalankan Playwright scraper...")
    result = asyncio.run(scrape_meta(url))

    with open("output_playwright.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("✅ Selesai! Hasil tersimpan di output_playwright.json")
    print(json.dumps(result, indent=2, ensure_ascii=False)[:800])
