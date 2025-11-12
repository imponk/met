# 🧩 MetaAI Scraper

Scraper sederhana untuk mengambil **data publik** dari halaman [Meta.ai](https://meta.ai) atau Facebook AI.  
Dibuat untuk kebutuhan riset & analisis data pribadi, **bukan untuk distribusi ulang konten pihak lain**.

## 🚀 Cara Jalankan di GitHub Actions

1. Fork atau buat repo baru.
2. Upload semua file ini.
3. Edit URL target di `.github/workflows/run_scraper.yml`.
4. GitHub akan otomatis menjalankan scraper dan menyimpan hasil ke `output.json`.

## 🧰 Jalankan Lokal

```bash
python3 -m pip install --user requests beautifulsoup4
python3 scrape_metaai_full.py "https://meta.ai/@username/post/..."
```

Output disimpan ke `output.json`.
