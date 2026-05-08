<div align="center">

<img src="static/icons/icon.svg" width="120" alt="Aura">

# Aura

**A diary that lives like personal social media.**

*Tempat curhatmu sendiri — yang nggak terasa seperti curhat.*

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.0-black.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-30%20passing-brightgreen.svg)](tests/)

</div>

---

## 💭 Why Aura

Journaling apps work — research consistently shows reduced anxiety, better self-awareness, stronger habit formation. But they share a problem: **they feel like homework**. A blank page. A prompt that demands an essay. A streak counter that guilts you on day 4.

Aura takes the opposite approach. It uses a form-factor you already open without thinking — Instagram, Twitter — and turns it inward. You're the only human here. The feed is yours. Six familiar voices keep you company, react to what you write, ask how your day's going. Some days you post a photo. Some days a single sentence. Some days you DM one of them at 1 AM about something you haven't told anyone.

It's not a productivity tool. It's a small, warm room.

---

## ✨ Features

**Your space**
- 📝 Posts & feed (text, photos, mood tag)
- 📸 Stories that disappear in 24h
- 🔥 Streak counter that forgives skipped days
- 📅 Throwbacks from 7/14/30/90/365 days ago
- 📊 Insights — 30-day mood heatmap with patterns
- 🔖 Bookmark, 🔁 Repost (quote-style)

**The friends**
- 💬 Comments and reactions in their distinct voices
- 💌 1-on-1 DM threads with thread memory
- 🟢 Pulse-online indicators
- 🌅 Daily check-in prompts ("Pagi! warna apa yg pertama lo liat tadi?")
- ✉️ Reply to their stories — opens a DM with the story as context

**Quality of life**
- ⌨️ Keyboard shortcuts: `n` new post, `/` search, `h` home, `Esc` close
- 🎨 Time-aware compose prompts (pagi/siang/sore/malam)
- 🌃 Dark by default — built for late-night writing
- 💾 Local-first: SQLite single-file, no cloud, no telemetry, no account
- 🖼️ Auto image resize to 1080px before upload

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.10+** ([download](https://python.org))
- **A SiliconFlow API key** — sign up at [siliconflow.com](https://siliconflow.com) (free tier is enough). The personas need it to talk.

### 2. Setup

```bash
git clone https://github.com/YOUR_USERNAME/aura.git
cd aura
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Then **open `.env`** and add your API key:

```
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

That's the only required setting. Optional ones (port, model overrides) are in `.env.example`.

### 4. Run

```bash
python app.py
```

You should see:

```
==========================================================
  🚀 Aura Social v3 — Modular Edition
==========================================================
  Endpoint  : https://api.siliconflow.com/v1
  API Key   : ✅ loaded
  ...
```

If you see `❌ MISSING` next to API Key, your `.env` isn't being loaded — see [Troubleshooting](#-troubleshooting).

### 5. Open in browser

`http://localhost:5000`

The first time you open the app, a small welcome banner appears. Dismiss it whenever, and start writing.

**Test the AI flow:** post anything → wait 30–90 seconds → you should see one or more friends like and comment. If nothing happens after 2 minutes, check the terminal for `[401]` errors — those mean the API key is wrong.

### Windows (PowerShell)

```powershell
git clone https://github.com/YOUR_USERNAME/aura.git
cd aura
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
# Add: SILICONFLOW_API_KEY=sk-...
python app.py
```

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

30 tests covering all critical flows. Use them as a safety net when modifying.

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `n` | New post |
| `/` | Focus search |
| `h` | Home |
| `Esc` | Close any open modal/thread |

---

## 🏗️ Architecture

```
aura/
├── app.py                    # Flask factory + entrypoint
├── config.py                 # .env loader (no python-dotenv dep)
├── personas.py               # 6 friend definitions + online helper
├── db.py                     # SQLite schema + migrations
├── utils.py                  # Time labels (tadi pagi, semalam, etc.)
├── llm/                      # Outbound calls
├── ai_engine/                # Background scheduler — likes, comments, posts
├── api/
│   ├── posts.py              # Feed CRUD, likes, bookmarks, reposts
│   ├── stories.py            # 24h stories
│   ├── profiles.py           # Friend profile data
│   ├── dm.py                 # DM threads with memory
│   ├── me.py                 # Profile, streak, throwback, mood, prompts
│   └── notif_search.py       # Notifications + search + health
├── tests/                    # pytest smoke suite
├── templates/index.html      # Single-page shell
└── static/
    ├── icons/                # SVG icon set
    ├── css/main.css          # ~700 lines, hand-crafted
    └── js/                   # 7 vanilla modules, no build step
```

Design choices that matter:

- **No JS build step.** Vanilla JS, edit and refresh.
- **SQLite single file.** Backup is `cp aura.db backup.db`.
- **Background threads, not Celery.** Trivially deployable anywhere Python runs.
- **Polling, not websockets.** Simpler, fine for one user.
- **Incremental DM rendering.** Input never gets wiped during background polling.

---

## 🔧 Configuration

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `SILICONFLOW_API_KEY` | ✅ | — | Get one at [siliconflow.com](https://siliconflow.com) |
| `SILICONFLOW_BASE` | | `https://api.siliconflow.com/v1` | API endpoint |
| `TEXT_MODEL` | | `Qwen/Qwen2.5-72B-Instruct` | Default text model |
| `VISION_MODEL` | | `Qwen/Qwen3-VL-32B-Instruct` | For describing your photos |
| `IMAGE_MODEL` | | `black-forest-labs/FLUX.1-schnell` | For generated stories |
| `DB_PATH` | | `aura.db` | SQLite path |
| `PORT` | | `5000` | HTTP port (change if 5000 is busy) |

Per-persona models live in `personas.py` — each friend uses a different LLM. That's deliberate: different models give different temperaments. Edit there if you want to swap.

---

## 🐛 Troubleshooting

### `API Key : ❌ MISSING` in terminal

Your `.env` isn't being loaded. Check:

1. **File location**: `.env` must be in the same folder as `app.py`, not in a subfolder.
2. **File name**: must be exactly `.env` (with the leading dot, no extension). On Windows, watch out: Notepad sometimes saves as `.env.txt` invisibly. Verify with `dir .env*` in PowerShell.
3. **Format**: no quotes around the value, no spaces around `=`:
   - ✅ `SILICONFLOW_API_KEY=sk-xxxxx`
   - ❌ `SILICONFLOW_API_KEY = "sk-xxxxx"` (spaces + quotes)
4. **Encoding**: if you saved in Notepad with "ANSI" or weird encoding, try UTF-8. The loader tolerates BOM but not exotic encodings.

Verify the file looks right:
```powershell
Get-Content .env       # PowerShell
cat .env               # macOS/Linux
```

### `[401] cek API key` in logs

Your key is loaded but rejected by SiliconFlow. Either:

- The key is wrong (typo, copied with extra space)
- The key is expired or revoked
- You hit the free tier rate limit

Double-check the key at [siliconflow.com](https://siliconflow.com).

### `PermissionError: [Errno 13] Permission denied` (Windows)

The file is locked by another process — usually VS Code holding it open. Close VS Code completely (not minimize), then restart `python app.py`. If still stuck:

```powershell
Get-ChildItem -Recurse | Unblock-File
```

This removes the "Mark of the Web" Windows adds to downloaded files.

### Port 5000 is busy

Set a different port in `.env`:
```
PORT=5050
```

### AI never replies

1. Check terminal for `API Key : ✅ loaded`
2. Check terminal for `[401]` or `[ImageGen]` errors
3. Wait 60 seconds — replies are scheduled with realistic delays
4. Visit `/api/health` in browser — should show `{"api_key_present": true, "api_key_format_ok": true}`

### Old DB has missing columns after update

Migrations run automatically on startup, but if something looks corrupted, just delete `aura.db` — it'll be recreated fresh.

---

## 🛡️ Privacy

- **Local-first.** Your DB, your machine. No telemetry. No analytics.
- **API key stays in `.env`** — gitignored, never committed.
- **Outbound only to SiliconFlow** for AI generation. Read their privacy policy if it matters.
- **No auth.** Designed for `localhost`. Don't expose port 5000 publicly without putting auth + HTTPS in front.

---

## 🤝 Contributing

PRs welcome. Especially appreciated:

- More distinct friend voices
- Mobile PWA polish (manifest, service worker, install prompt)
- Export-to-PDF for diary backups
- Voice notes (audio → transcript)
- Weekly reflection (a friend writes a longer DM looking back at your week)

Keep the friends' personalities in Bahasa Indonesia. They were written that way for a reason — switching to English flattens them.

Run tests before submitting: `pytest -v`.

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

<div align="center">

*Made by people who think journaling shouldn't feel like homework.*

💜

</div>
