<div align="center">

# ✨ Aura

**A diary that lives like personal social media.**

*Tempat curhatmu sendiri — yang nggak terasa seperti curhat.*

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0-black.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

</div>

---

## 💭 Why Aura

Journaling apps work — research consistently shows reduced anxiety, better self-awareness, stronger habit formation. But they share a problem: **they feel like homework**. A blank page. A prompt that demands an essay. A streak counter that guilts you on day 4.

Aura takes the opposite approach. It uses a form-factor you already open without thinking — Instagram, Twitter — and turns it inward. You're the only human here. The feed is yours. Six familiar voices keep you company, react to what you write, ask how your day's going. Some days you post a photo. Some days a single sentence. Some days you DM one of them at 1 AM about something you haven't told anyone.

It's not a productivity tool. It's a small, warm room.

---

## ✨ What's inside

### Your space
- 📝 **Posts & feed** — text, photos, a mood tag — like Twitter for one
- 🙏 **Gratitude notes** — a separate writing mode; you choose whether your circle responds
- 📸 **Stories** that disappear in 24h
- 📓 **Jurnal** — every entry you've written, grouped by month and searchable
- 📅 **Throwbacks** — gentle reminders of who you were 7, 30, 365 days ago
- 📊 **Insights** — 30-day mood heatmap with patterns you wouldn't notice yourself
- 🔖 **Bookmark** moments worth coming back to

### The friends
- 💬 **They comment, like, and post** — each with a distinct voice
- 🧵 **Reply to their comments** — short threads, and they reply back in-thread
- 💌 **DM them** anytime, 1-on-1, with thread memory
- 🟢 **Pulse-online indicators** — they feel present, not on-demand
- 🌅 **Daily check-in** — "Pagi! warna apa yg pertama lo liat tadi?"

### Quality of life
- ⌨️ **Keyboard shortcuts** — `/` search, `n` new post, `Esc` close, `h` home
- 🎨 **Time-aware prompts** — pagi, siang, sore, malam each get different vibes
- 🌃 **Dark by default** — built for late-night writing
- 💾 **All local** — SQLite single-file. No cloud, no telemetry, no account
- 🖼️ **Auto image resize** — drop in a 12MB photo, it becomes 1080px before storing

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- A [SiliconFlow](https://siliconflow.com) API key (free tier is enough)

### Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/aura.git
cd aura

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Open .env, paste your SILICONFLOW_API_KEY

# 4. Run
python app.py
```

Open `http://localhost:5000` and start writing.

### Windows (PowerShell)

```powershell
git clone https://github.com/YOUR_USERNAME/aura.git
cd aura
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python app.py
```

The DB seeds itself the first time. The first time you open the app, a small welcome banner appears — feel free to dismiss it and start writing whatever's in your head.

---

## ⌨️ Shortcuts

| Key | Action |
|-----|--------|
| `n` | New post |
| `/` | Focus search |
| `h` | Home |
| `Esc` | Close any open modal/thread |

---

## 🧪 Tests & hardening

```bash
pip install -r requirements-dev.txt
pytest -q
```

A smoke suite covers the core endpoints plus the parts most likely to break:
threaded-comment nesting, gratitude entry typing, input caps, and the rate limiter.

Because the demo is publicly reachable, every write endpoint is defended on the
server — not just in the UI:

- **Input caps** — post / comment / DM length and image-payload size are clamped
  server-side (`security.py`), never trusting the client.
- **Rate limiting** — per-IP sliding window on all writes (HTTP 429 when exceeded).
- **DB hygiene** — a background worker drops expired non-highlight stories and trims
  the AI timeline so SQLite can't grow without bound; your own entries are always kept.
- **Safe by default** — every query is parameterized, all rendered content is HTML-escaped.

---

## 🏗️ Architecture

```
aura/
├── app.py                    # Flask factory + entrypoint
├── config.py                 # .env loader (no dotenv dep)
├── personas.py               # 6 friend definitions
├── db.py                     # SQLite schema + migrations
├── security.py               # Input caps + per-IP rate limiting
├── utils.py                  # Time labels (tadi pagi, semalam, etc.)
├── llm/                      # Outbound calls to language models
├── ai_engine/                # Background workers — posts, stories, AI reactions, DB cleanup
├── api/
│   ├── posts.py              # Feed, comments + threaded replies, likes, bookmarks
│   ├── stories.py            # Stories (24h) + highlights
│   ├── profiles.py           # Friend profile data
│   ├── dm.py                 # DM threads with memory
│   ├── me.py                 # Profile, throwback, mood, prompts
│   └── notif_search.py       # Notifications + search
├── tests/                    # pytest smoke suite
├── templates/index.html      # Single-page shell
└── static/
    ├── css/main.css          # tokenized "dusk journal" design system
    └── js/                   # 7 vanilla modules, no build step
```

Design choices that matter:
- **No JS build step.** Vanilla JS, edit and refresh.
- **SQLite single file.** Backup is `cp aura.db backup.db`.
- **Background threads, not Celery.** Trivially deployable anywhere Python runs.
- **Polling, not websockets.** Simpler, fine for one user.

---

## 🔧 Configuration

`.env` knobs:

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `SILICONFLOW_API_KEY` | ✅ | — | Get one at siliconflow.com |
| `SILICONFLOW_BASE` | | `https://api.siliconflow.com/v1` | API endpoint |
| `TEXT_MODEL` | | `Qwen/Qwen2.5-72B-Instruct` | Default text model |
| `VISION_MODEL` | | `Qwen/Qwen3-VL-32B-Instruct` | For describing your photos |
| `IMAGE_MODEL` | | `black-forest-labs/FLUX.1-schnell` | For friends' generated stories |
| `DB_PATH` | | `aura.db` | SQLite path |

The voices in `personas.py` use a mix of models — different temperaments need different reasoning styles. You can change them, swap them, add a 7th friend.

---

## 🛡️ Privacy

- **Local-first.** Your DB, your laptop. No telemetry. No analytics.
- **API key in `.env`** — gitignored, never committed.
- **Outbound only to one provider** for AI generation. Read SiliconFlow's policy if it matters.
- **No auth.** Designed to run on `localhost`. Don't expose port 5000 publicly.

If you fork this for a server, add auth and HTTPS first.

---

## 🤝 Contributing

PRs welcome. Especially appreciated:
- More distinct friend voices
- Mobile PWA polish (manifest, service worker)
- Export-to-PDF for backups
- Voice notes (audio → transcript)

Keep the friends' personalities in Bahasa Indonesia. They were written that way for a reason — switching to English flattens them.

---

## 📄 License

MIT — [LICENSE](LICENSE)

---

<div align="center">

*Made by people who think journaling shouldn't feel like homework.*

💜

</div>
