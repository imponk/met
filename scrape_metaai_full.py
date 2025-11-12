#!/usr/bin/env python3
"""
scrape_metaai_full.py
=====================
Scraper sederhana untuk mengambil data teks, meta tags, gambar, dan video URL (mp4/m3u8)
dari halaman publik Meta.ai atau Facebook AI.

Dapat dijalankan lokal maupun otomatis lewat GitHub Actions.

Usage:
    python3 scrape_metaai_full.py "https://meta.ai/@username/post/..."
"""

import sys
import re
import json
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Jalankan dulu:")
    print("    pip install requests beautifulsoup4")
    sys.exit(1)


def fetch(url):
    """Ambil HTML dari URL target."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html",
        "Referer": "https://meta.ai/",
    }
    res = requests.get(url, headers=headers, timeout=25)
    res.raise_for_status()
    return res.text


def extract_data(html, base_url):
    """Ekstraksi data dari HTML."""
    soup = BeautifulSoup(html, "html.parser")

    data = {
        "title": soup.title.string.strip() if soup.title else "",
        "metas": {},
        "images": [],
        "videos": [],
    }

    # ambil meta tags
    for meta in soup.find_all("meta"):
        k = meta.get("property") or meta.get("name")
        v = meta.get("content")
        if k and v:
            data["metas"][k] = v

    # ambil semua gambar
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            data["images"].append(urljoin(base_url, src))

    # ambil elemen video / iframe
    for tag in soup.find_all(["video", "source", "iframe"]):
        src = tag.get("src") or tag.get("data-src")
        if src:
            data["videos"].append(urljoin(base_url, src))

    # cari pola URL video (mp4 / m3u8) langsung dari HTML mentah
    data["videos"] += re.findall(r"https?://[^\s\"'<>]+\.mp4[^\s\"'<>]*", html)
    data["videos"] += re.findall(r"https?://[^\s\"'<>]+\.m3u8[^\s\"'<>]*", html)

    # hapus duplikat & urutkan
    data["images"] = sorted(set(data["images"]))
    data["videos"] = sorted(set(data["videos"]))

    return data


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scrape_metaai_full.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    try:
        html = fetch(url)
    except Exception as e:
        print("❌ Gagal mengambil halaman:", e)
        sys.exit(1)

    data = extract_data(html, url)

    # simpan hasil ke file output.json
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("✅ Selesai! Data tersimpan di output.json")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:800])


if __name__ == "__main__":
    main()
