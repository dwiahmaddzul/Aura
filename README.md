<div align="center">

# ✨ Aura

**A diary that lives like personal social media.**

*Tempat curhatmu sendiri — yang nggak terasa seperti curhat.*

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.x-black.svg)
![SQLite](https://img.shields.io/badge/db-SQLite-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

</div>

---

## 💭 Tentang proyek

Aplikasi jurnal biasanya terasa seperti PR: halaman kosong, prompt yang menuntut esai,
streak yang bikin merasa bersalah. **Aura** membalik pendekatannya. Bentuknya seperti
Instagram/Twitter yang sudah biasa dibuka tanpa mikir, tapi diarahkan ke dalam: kamu satu-satunya
manusia di sana, dan enam "teman" AI dengan kepribadian berbeda ikut mengomentari, me-like,
membuat story, dan membalas DM.

Proyek ini adalah aplikasi web full-stack satu orang: backend Flask modular, SQLite,
worker AI berjalan di latar, frontend vanilla JS tanpa build step, plus dashboard
pengendali biaya AI.

## ✨ Fitur

**Ruang pribadi**
- 📝 Post teks/foto dengan tag mood · 🙏 catatan syukur (komentar AI bisa dimatikan)
- 📸 Story 24 jam + Sorotan (highlight) · 📓 Jurnal per bulan dengan pencarian
- 📅 Throwback 7/30/365 hari · 📊 Heatmap mood 30 hari · 🔖 Bookmark

**Teman AI**
- 💬 Enam persona lintas model (Qwen, DeepSeek, Kimi, dll.) dengan suara & peluang balas berbeda
- 🧵 Balasan berutas di komentar · 💌 DM 1-on-1 dengan memori percakapan
- 🖼️ Persona bisa "melihat" foto (model vision) dan membuat gambar (FLUX)
- 🌅 Pertanyaan harian sesuai waktu (pagi/siang/sore/malam)

**Kendali & operasional (`/kelola`)**
- Preset Hemat / Normal / Ramai, saklar utama yang menghentikan semua panggilan berbayar
- Rem biaya: anggaran harian USD, kuota gambar, batas panggilan otomatis & interaktif
- Log setiap panggilan API (token & estimasi biaya) per hari, per persona, per model
- Backup database, VACUUM, migrasi gambar lama ke WebP

## 🏗️ Arsitektur

```
aura/
├── app.py            # Flask app factory, header keamanan, cache policy
├── config.py         # loader .env tanpa dependensi + semua env var
├── security.py       # batas input + rate limit per-IP (sliding window)
├── settings_rt.py    # setting AI yang bisa diubah live (disimpan di SQLite)
├── db.py             # skema + migrasi SQLite (WAL)
├── media.py          # penyimpanan gambar: file asli + varian WebP ter-cache
├── personas.py       # definisi 6 teman AI
├── llm/              # klien SiliconFlow, generator teks/gambar, memori, pembersih output
├── ai_engine/        # scheduler post/story, responder, rem biaya, pencatat pemakaian
├── api/              # blueprint: posts, stories, profiles, dm, me, notif/search, media, kelola
├── templates/        # index.html (SPA shell) + kelola.html (dashboard)
├── static/           # CSS bertoken + modul JS vanilla
└── tests/            # pytest: smoke test endpoint + upgrade/migrasi
```

Keputusan desain:
- **Tanpa build step JS** — edit lalu refresh.
- **SQLite satu file** — backup cukup salin file (atau tombol backup di `/kelola`).
- **Thread latar, bukan Celery** — bisa dideploy di mana pun Python jalan.
- **Polling + ETag** — respons yang tidak berubah dijawab `304` tanpa isi.

## 🚀 Menjalankan secara lokal

Prasyarat: Python 3.10+ dan API key [SiliconFlow](https://siliconflow.com).

```bash
git clone https://github.com/dwiahmaddzul/Aura.git
cd aura
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Windows: Copy-Item .env.example .env
```

Isi minimal di `.env`:

```ini
SILICONFLOW_API_KEY=sk-...        # kunci milikmu sendiri
ADMIN_PASSWORD=<password-acak>    # untuk /kelola
COOKIE_SECURE=0                   # hanya untuk uji lokal via http
TRUSTED_PROXY_HOPS=0              # akses langsung tanpa reverse proxy
```

Jalankan:

```bash
python app.py
```

Buka `http://localhost:5000`. Database dibuat otomatis saat pertama kali jalan.

### Tes

```bash
pip install -r requirements-dev.txt
pytest -q
```

### Deploy (Railway / PaaS)

`Procfile` sudah menjalankan Gunicorn (`--workers 1 --threads 4`; satu worker karena
scheduler & rate limit ada di memori proses). Set env `SILICONFLOW_API_KEY`,
`ADMIN_PASSWORD`, dan `SECRET_KEY` di dashboard penyedia, pasang volume untuk
`DB_PATH`, dan sesuaikan `TRUSTED_PROXY_HOPS` dengan jumlah proxy di depan app.

## 🔧 Konfigurasi

Daftar lengkap ada di [`.env.example`](.env.example). Yang paling penting:

| Variabel | Wajib | Default | Keterangan |
|---|---|---|---|
| `SILICONFLOW_API_KEY` | ✅ | — | Kunci API penyedia model |
| `ADMIN_PASSWORD` | ✅ untuk `/kelola` | — | Kosong = dashboard terkunci |
| `SECRET_KEY` | disarankan | acak, disimpan di DB | Kunci tanda tangan cookie sesi |
| `COOKIE_SECURE` | | `1` | `0` hanya untuk uji lokal via http |
| `TRUSTED_PROXY_HOPS` | | `1` | Jumlah reverse proxy tepercaya (rate limit) |
| `DB_PATH` | | `aura.db` | Lokasi SQLite |
| `MEDIA_DIR` | | `media/` di sebelah DB | Lokasi file gambar |
| `APP_TZ` | | `Asia/Jakarta` | Zona waktu label & kuota harian |
| `TEXT_MODEL` / `VISION_MODEL` / `IMAGE_MODEL` | | lihat `.env.example` | Model default |

## 🛡️ Keamanan

- **Rahasia hanya lewat environment.** Tidak ada kunci di kode; `.env` di-`.gitignore`.
- **SQL terparametrisasi.** Nama tabel dinamis hanya berasal dari whitelist internal.
- **Output di-escape.** Semua teks pengguna & AI melewati `esc()` sebelum masuk DOM;
  Jinja autoescape aktif.
- **Dashboard terlindungi.** Password dibandingkan constant-time, login di-rate-limit,
  cookie sesi `HttpOnly` + `Secure` + `SameSite=Strict`, dan setiap POST wajib header
  `X-Kelola` (tidak bisa dikirim lintas situs tanpa CORS) sebagai pertahanan CSRF.
- **Batas di server.** Panjang teks & ukuran gambar dibatasi, rate limit per IP pada
  endpoint tulis, perlindungan *decompression bomb* pada gambar.
- **Header keamanan.** `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP `frame-ancestors 'none'`.

> ⚠️ **Model ancaman:** Aura dirancang untuk **satu pengguna**. Layar kode di halaman
> depan hanyalah *soft gate* untuk demo, **bukan autentikasi**. Siapa pun yang tahu URL
> deployment bisa membaca dan menulis feed/DM. Untuk dipakai sebagai jurnal sungguhan,
> jalankan di `localhost` atau pasang autentikasi (mis. reverse proxy dengan basic auth /
> Cloudflare Access) di depannya. Catatan audit lengkap: [`AUDIT.md`](AUDIT.md).

## 📄 Lisensi

MIT — lihat [LICENSE](LICENSE).
