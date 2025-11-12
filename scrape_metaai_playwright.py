#!/usr/bin/env python3
"""
scrape_metaai_playwright.py
===========================
Versi Playwright (diperbaiki) — untuk mengambil URL video (mp4/m3u8) dari Meta.ai
"""

import sys
import json
import asyncio
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


async def scrape_meta(url):
    data = {"url": url, "title": "", "metas": {}, "images": [], "videos": []}
    collected_videos = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Event listener untuk setiap request
        page.on("request", lambda req: (
            collected_videos.add(req.url)
            if any(ext in req.url for ext in [".mp4", ".m3u8"])
            else None
        ))

        print(f"🔍 Membuka halaman: {url}")
        await page.goto(url, wait_until="networkidle")

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
