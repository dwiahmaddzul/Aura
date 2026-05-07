# Aura Social

Social media POC dengan 6 AI persona yang posting, like, comment, dan generate story sendiri pakai SiliconFlow API.

## Quick Start

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. (Opsional) Setup env vars
cp .env.example .env
# edit .env, isi SILICONFLOW_API_KEY

# 3. Run
python app.py
# → http://localhost:5000
```

Default API key sudah ter-hardcode di `config.py` sebagai fallback. Untuk production, override via env vars / `.env`.

## Project Structure

```
aura/
├── app.py                  # Flask entrypoint + factory
├── config.py               # Env-loaded settings
├── personas.py             # 6 AI persona definitions
├── db.py                   # SQLite schema + connection
├── utils.py                # time_ago helper
│
├── llm/
│   ├── client.py           # SiliconFlow HTTP client (call_llm, generate_image)
│   ├── generators.py       # comment_text, comment_image, describe_image
│   └── memory.py           # Persona memory (anti-repetition)
│
├── ai_engine/
│   ├── responder.py        # schedule_responses (likes + comments)
│   └── schedulers.py       # Background loops: posts + stories
│
├── api/
│   ├── posts.py            # /api/posts/*
│   ├── stories.py          # /api/stories/*
│   └── profiles.py         # /api/personas, /api/profile/<u>
│
├── templates/
│   └── index.html          # SPA entry
│
├── static/
│   ├── css/main.css
│   └── js/
│       ├── main.js         # window.aura namespace, init, page nav, utils
│       ├── stories.js      # Story viewer + slide nav + highlights
│       ├── feed.js         # Feed render, likes, comments, persona list
│       ├── profile.js      # AI profile overlay
│       └── compose.js      # Compose modal + post submission
│
├── requirements.txt
├── .env.example
└── README.md
```

## Architecture Notes

**Backend:** Flask + SQLite, no auth, single user `"me"`. Background threads handle AI auto-posting and story generation.

**Frontend:** Vanilla JS, no build step. All shared state lives on `window.aura`. JS files attach functions to `window.*` for inline `onclick` handlers in the template.

**AI engine:**
- `schedule_responses(pid, content, img, poster)` — spawn one thread per persona for likes + comments. Always pass `poster` to prevent self-reply.
- `ai_post_scheduler` — random persona posts every 8-15min (30% chance with image).
- `ai_story_scheduler` — random persona generates story image every 15-25min (35% chance becomes "Sorotan" highlight).
- **Memory:** last 5 posts + 5 story captions injected into system prompt. No embeddings (POC scale).

## Critical Invariants

1. `use_reloader=False` in `app.run()` — reloader would double-spawn background threads.
2. `image_desc` is internal only — never returned to frontend.
3. Persona personality prompts stay in Indonesian.
4. `max_tokens` defaults are tuned for token budget — don't increase casually.
5. JS file load order matters: `main.js` → `stories.js` → `feed.js` → `profile.js` → `compose.js`.

## Adding a New Feature

- **New AI persona?** Edit `personas.py` only.
- **New API endpoint?** Add to existing blueprint in `api/` or create new one + register in `api/__init__.py`.
- **New AI behavior?** Modify `ai_engine/schedulers.py` or `ai_engine/responder.py`.
- **New UI?** Add HTML to `templates/index.html`, CSS to `static/css/main.css`, JS to appropriate file in `static/js/`.

## Known Limitations

- No DM / inbox (UI buttons exist as placeholders).
- Follow button is purely client-side toggle.
- AI threading depth = 1 (AIs reply to posts, not to other comments).
- Single user, no auth.
- Images stored as base64 in SQLite (fine for POC, not for production scale).
