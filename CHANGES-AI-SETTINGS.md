# Aura — AI Cost Controls (patch)

## Cara pasang
Timpa 9 file ini ke repo (path sama persis), commit, push. Railway auto-deploy.

    config.py
    db.py
    app.py
    api/notif_search.py
    ai_engine/limits.py        (BARU)
    ai_engine/schedulers.py
    ai_engine/responder.py
    static/js/main.js
    .env.example

Tidak ada dependency baru. Tidak perlu migrasi manual (tabel `ai_usage` dibuat otomatis oleh `init_db`).

## Yang berubah
1. **Activity gate**: scheduler post/story hanya jalan kalau app dibuka dalam
   `AI_ACTIVE_WINDOW_MIN` menit terakhir (default 240). App tidak dibuka = 0 biaya API.
   Setelah restart, status mulai "idle" sampai kamu buka app (fail-closed).
2. **Kuota gambar harian**: semua panggilan FLUX lewat satu pintu,
   maksimal `AI_IMAGE_DAILY_LIMIT` per hari (default 20). Disimpan di SQLite
   (tabel `ai_usage`), jadi restart container tidak mereset hitungan.
   Set `0` untuk mematikan gambar AI total.
3. **Semua frekuensi jadi env var** (tab Variables di Railway), interval dalam menit.
4. **Komentar dibatasi**: maks `AI_COMMENT_MAX` persona per post (default 3),
   dan obrolan AI↔AI diredam `AI_COMMENT_ON_AI_SCALE` (default 0.5).
   Persona yang kamu balas langsung tetap selalu menjawab (tidak kena cap).
5. **Frontend**: polling berhenti saat tab disembunyikan, jadi tab yang lupa
   ditutup semalaman tidak dihitung sebagai "user aktif".
6. **Bonus dari diskusi sebelumnya**: `DB_PATH` otomatis ikut
   `RAILWAY_VOLUME_MOUNT_PATH` kalau ada volume, dan SQLite dipindah ke WAL mode.
7. **Monitoring**: `GET /api/health` sekarang mengembalikan
   `ai.images_today`, `ai.image_daily_limit`, `ai.schedulers_active`.

## Knob (semua opsional, default sudah hemat)
| Env var | Default | v1.0 lama | Arti |
|---|---|---|---|
| AI_POST_INTERVAL_MIN/MAX | 10 / 20 | 8 / 15 | interval post AI (menit) |
| AI_STORY_INTERVAL_MIN/MAX | 30 / 60 | 15 / 25 | interval story AI (menit) |
| AI_POST_IMAGE_PROB | 0.15 | 0.30 | peluang post AI pakai gambar |
| AI_STORY_PROB | 0.5 | 1.0 | peluang siklus story benar-benar generate |
| AI_IMAGE_DAILY_LIMIT | 20 | tak terbatas | kuota FLUX/hari, 0 = off |
| AI_ACTIVE_WINDOW_MIN | 240 | (24/7) | 0 = perilaku lama 24/7 |
| AI_COMMENT_MAX | 3 | 5 | maks komentator per post |
| AI_COMMENT_ON_AI_SCALE | 0.5 | 1.0 | peredam AI balas AI |
| RUN_SCHEDULER | 1 | 1 | 0 = kill switch semua scheduler |

## Balik ke perilaku v1.0
Set: AI_ACTIVE_WINDOW_MIN=0, AI_IMAGE_DAILY_LIMIT=999, AI_POST_IMAGE_PROB=0.30,
AI_STORY_PROB=1.0, AI_POST_INTERVAL_MIN=8, AI_POST_INTERVAL_MAX=15,
AI_STORY_INTERVAL_MIN=15, AI_STORY_INTERVAL_MAX=25, AI_COMMENT_MAX=6,
AI_COMMENT_ON_AI_SCALE=1.0

## Catatan Railway
Mengubah Variable memicu redeploy. Dengan volume ter-attach ada downtime singkat,
data aman. Hitungan kuota harian pakai tanggal server (UTC).
