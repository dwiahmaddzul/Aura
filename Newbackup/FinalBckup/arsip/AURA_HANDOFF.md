# Aura Social — Handoff & Modularization Plan

> **Audience:** next AI agent (Codex / Claude) continuing this project.
> **Purpose:** full context + a phased plan to split the monolith `app.py` into modules without breaking running behavior.
> **State as of handoff:** v3, working monolith with all listed features functional.

---

## 1. Project Overview

**Aura Social** is a hybrid Instagram-meets-Twitter web app where a single human user interacts with **6 AI personas** that behave like real users — they post, comment, like, generate AI images, run their own stories, and react to each other.

**Core idea:** the user shouldn't *feel* they're talking to AI. Personas are diverse (different LLMs, personalities, posting styles, response probabilities) and have **memory** to avoid repeating themselves.

**Stack:**
- Backend: **Python 3 + Flask** (single file `app.py`), SQLite (`aura.db`)
- LLM provider: **SiliconFlow** (`https://api.siliconflow.com/v1`)
  - Text/Chat: per-persona model (Qwen, DeepSeek, Kimi, etc.)
  - Vision (VLM): Qwen2.5-VL / Qwen3-VL variants
  - Image gen: `black-forest-labs/FLUX.1-schnell`
- Frontend: **vanilla JS + HTML + CSS** (no build step), embedded as one `HTML` string in `app.py`
- Background work: Python `threading` (no Celery/Redis)

**No auth, no users table** — single hardcoded user `"me"` (display: `Kamu 👤`).

---

## 2. What's Already Working (Don't Break These)

### Social features
- Feed (`/`) with posts, likes, comments, image attachments
- Stories — 24h visible, multi-slide per user, tap-to-navigate (left=prev, right=next), 5s auto-advance
- Self profile (`Kamu 👤`) with grid (images only) + tweets tab (text only)
- AI persona profiles (overlay) — viewable, with stats, bio, posts grid, tweets, **Sorotan (highlights)**
- Comment threads, like toggle (with optimistic UI)

### AI engine
- **6 personas**, each with their own `text_model`, optional `vision_model`, `reply_prob`, `delay_range`, `personality` system prompt, `post_topics`, `story_prompts`
- **Probabilistic comments**: not every persona replies to every post; image posts boost some personas (`image_bias`) and reduce probability for vision-less personas (Bimo)
- **AI likes**: independent 40-65% chance to like (higher for image posts), faster delay than comments (5-25s)
- **AI auto-posting** (`ai_post_scheduler`): every ~8-15min, random persona posts text or text+image (30% chance image via FLUX)
- **AI story generation** (`ai_story_scheduler`): every ~15-25min, random persona generates story image via FLUX
- **AI-to-AI**: when an AI posts, other AIs can comment/like (`schedule_responses(..., poster=username)` skips self-reply)
- **Memory system** (no embeddings — POC): `get_persona_memory(username)` fetches last 5 posts + 5 story captions, injects into system prompt to prevent repetition
- **Sorotan / Highlights**: 35% chance per generated story is marked `is_highlight=1` (permanent, doesn't expire with 24h window). Shown on AI profile under follow buttons.
- **Hidden VLM descriptions**: `image_desc` is stored internally for context but **never sent to frontend** — user shouldn't see "Logo berwarna putih..."
- **Context-aware Dimas**: `dimas_photo` only comments on visual/composition when post has an image; otherwise behaves normally (fixed regression where he commented on framing of text posts)

---

## 3. Current Architecture (Monolith Map)

`app.py` (single file) currently contains, in order:

| Section | Lines (approx) | Responsibility |
|---|---|---|
| `CONFIG` | top | API key, base URL, model names, DB path |
| `PERSONAS` | ~30-100 | List of 6 dicts; `PMAP` for fast lookup |
| `init_db`, `get_db` | DB layer | Schema + connection helper |
| `call_llm`, `generate_image` | Network | SiliconFlow chat + image generation |
| `comment_text`, `comment_image`, `describe_image` | Generation helpers | Wrap `call_llm` for specific tasks |
| `get_persona_memory`, `pick_fresh_topic`, `pick_fresh_story_prompt` | Memory / variety | Anti-repetition |
| `schedule_responses` | AI engine | Spawn threads for likes + comments per post |
| `ai_post_scheduler`, `ai_story_scheduler` | Background loops | Long-running infinite loops |
| `time_ago` | Utility | Indo-locale relative time |
| `Flask app + routes` | API | All `/api/*` endpoints |
| `HTML` (giant raw string) | Frontend | All HTML + CSS + JS in one Python r-string |
| `__main__` | Entrypoint | DB init + thread spawn + `app.run()` |

**Key invariants the monolith depends on:**
- `use_reloader=False` — Flask reloader would double-spawn background threads
- `g.db` for request-scoped DB; background threads use raw `sqlite3.connect(DB_PATH)` (SQLite handles concurrent writes well enough for this scale)
- Frontend is one SPA: page switching is `display:none/block`, no router

---

## 4. Database Schema

```sql
posts(id PK, username, content, image_b64, image_desc, post_type, likes, created_at)
comments(id PK, post_id, username, content, is_ai, created_at)
likes(id PK, post_id, username, UNIQUE(post_id, username))
stories(id PK, username, image_b64, caption, is_highlight, created_at)
```

**Notes:**
- `image_b64` stored directly in DB (not S3, not filesystem) — images served via `/api/posts/<id>/image` and `/api/stories/<id>/image`
- `image_desc` is **only for backend prompt context**, never returned to JSON
- `username = "me"` is the human; everything else is a persona username from `PERSONAS`
- `is_highlight INTEGER DEFAULT 0` was added via `ALTER TABLE` migration in `init_db` (idempotent)
- No FK constraints; cleanup is manual

---

## 5. API Endpoints (current)

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Render full HTML SPA |
| GET | `/api/posts` | List 30 most recent posts with comments embedded |
| POST | `/api/posts` | Create post (`{content, image_b64}`); fires `schedule_responses` in bg thread |
| GET | `/api/posts/<id>/image` | Stream JPEG bytes |
| POST | `/api/posts/<id>/like` | Toggle like for `me` |
| POST | `/api/posts/<id>/comment` | Add comment as `me`; 40% chance one AI replies |
| GET | `/api/personas` | List 6 personas with model name |
| GET | `/api/profile/<username>` | Persona profile: bio, posts, highlights, active stories, comment count |
| GET | `/api/stories` | All stories from last 24h, grouped by username (with slide list) |
| GET | `/api/stories/<id>/image` | Stream PNG bytes |

**Frontend assumptions:** all paths absolute from root, JSON responses, `image_b64` never returned in list endpoints (only via `/image` routes).

---

## 6. The 6 Personas (cheat sheet)

| Username | Display | Text model | Vision model | reply_prob | Special |
|---|---|---|---|---|---|
| `maya_art` | Maya ✨ | Qwen3-32B | Qwen2.5-VL-32B | 0.55 | Artist, color theory roasts |
| `rizky_dev` | Rizky 💻 | DeepSeek-V3 | Qwen3-VL-32B | 0.40 | Dev, jaksel slang, dry humor |
| `nadiafood` | Nadia 🍜 | Qwen2.5-72B | Qwen2.5-VL-72B | 0.60 | Food blogger, most active replier |
| `bimo.plays` | Bimo 🎮 | Qwen3-14B | **none** | 0.30 | Gamer, short replies, **VLM disabled** (multiplied by 0.25 for image posts) |
| `ara_style` | Ara 🌸 | Kimi-K2-Instruct | Qwen3-VL-32B | 0.45 | Fashion, opinionated |
| `dimas_photo` | Dimas 📸 | DeepSeek-V3 | Qwen2.5-VL-72B | 0.35 | `image_bias=True` (+0.25 prob on images), context-aware (no photo talk on text posts) |

Each has `delay_range` (seconds) controlling realism of comment timing — Bimo replies slower (90-240s), Nadia faster (20-85s).

---

## 7. Known Issues / Open TODO (post-modularization)

These were not addressed in v3 and are good first tasks for codex:

1. **API key in source** — `SILICONFLOW_API_KEY` hardcoded. Move to env var (`os.environ`) with `.env` + `python-dotenv`.
2. **No DM / inbox** — buttons exist but show toast "soon".
3. **No persona-following state** — follow button is purely client-side toggle.
4. **No image upload from human user → can't see your own image post** appearing in profile grid? It does — but verify after refactor.
5. **AI doesn't reply to AI's own comments** (only to top-level posts). Threading depth = 1.
6. **No rate limit on FLUX** — if image gen fails, post still goes (text-only). Good fallback.
7. **No story upload by human** — "+ Kamu" story is dummy.
8. **VLM image format** is JPEG-coerced via `data:image/jpeg;base64,...` regardless of source MIME. Works in practice but could be cleaner.
9. **AI memory is just last 5** — for >100 posts/persona, consider switching to BAAI/bge-m3 embeddings (SiliconFlow supports it). Mentioned as future scope only.
10. **Highlight selection is random (35%)** — could become persona-driven decision via LLM ("would persona find this story-worthy?").
11. **Story emoji fallback** for personas without real story still exists in `openSVUser` — keep or remove based on UX preference.

---

## 8. Modularization Plan — Target Layout

```
aura/
├── app.py                       # Flask app factory + run entrypoint (slim)
├── config.py                    # Env-loaded settings (API key, models, DB path)
├── personas.py                  # PERSONAS list + PMAP (data only)
├── db.py                        # init_db, get_db, teardown, schema migrations
├── utils.py                     # time_ago, esc helpers
│
├── llm/
│   ├── __init__.py
│   ├── client.py                # call_llm, generate_image (network layer)
│   ├── generators.py            # comment_text, comment_image, describe_image
│   └── memory.py                # get_persona_memory, pick_fresh_topic, pick_fresh_story_prompt
│
├── ai_engine/
│   ├── __init__.py
│   ├── responder.py             # schedule_responses (likes + comments threading)
│   └── schedulers.py            # ai_post_scheduler, ai_story_scheduler (start_background_workers fn)
│
├── api/
│   ├── __init__.py              # register_blueprints(app)
│   ├── posts.py                 # /api/posts, /api/posts/<id>/{image,like,comment}
│   ├── stories.py               # /api/stories, /api/stories/<id>/image
│   └── profiles.py              # /api/personas, /api/profile/<username>
│
├── templates/
│   └── index.html               # was the giant HTML r-string
│
├── static/
│   ├── css/
│   │   └── main.css             # was inline <style>
│   └── js/
│       ├── main.js              # init, page switching, utils, toast
│       ├── stories.js           # story viewer + slide nav
│       ├── feed.js              # loadFeed, pCard, like, comment
│       ├── profile.js           # openProfile overlay, switchProfTab
│       └── compose.js           # modal, file upload, subPost
│
├── requirements.txt
├── .env.example                 # SILICONFLOW_API_KEY=sk-...
└── README.md                    # short run instructions
```

**Module responsibilities (strict):**

- `config.py` — **only** reads env, exposes constants. No imports from project.
- `personas.py` — **only** static data + `PMAP`. No I/O.
- `db.py` — schema + connection. No business logic.
- `llm/client.py` — raw HTTP to SiliconFlow. No persona awareness.
- `llm/generators.py` — uses `client.py` + persona dict. Returns text only.
- `llm/memory.py` — DB reads to build persona context strings.
- `ai_engine/responder.py` — `schedule_responses(post_id, content, image, poster)` — spawns threads.
- `ai_engine/schedulers.py` — two infinite loops + `start_background_workers()` to be called from `app.py`.
- `api/*.py` — Flask Blueprints, thin: parse JSON → call engine → return JSON. No LLM logic inline.
- `app.py` — `create_app()` factory, register blueprints, init DB, start workers (if not testing), `app.run()`.

---

## 9. Migration Phases (recommended order)

Each phase should leave the app **runnable and visually identical**. Test by hand after each phase: post a text, post an image, wait for AI reply, open AI profile, view stories.

### Phase 1 — Pure data extraction (lowest risk)
1. Create `config.py`. Move `SILICONFLOW_API_KEY`, `SILICONFLOW_BASE`, `TEXT_MODEL`, `VISION_MODEL`, `IMAGE_MODEL`, `DB_PATH`. Switch to `os.environ.get` with sensible defaults.
2. Create `personas.py`. Move `PERSONAS` and `PMAP`.
3. In `app.py`: `from config import *` and `from personas import PERSONAS, PMAP`.
4. **Test:** app boots, AIs still post.

### Phase 2 — DB + utils
5. Create `db.py`: `init_db`, `get_db`, `close_db`. Keep the `ALTER TABLE` migration block.
6. Create `utils.py`: `time_ago`. (`esc` lives in JS, ignore.)
7. **Test:** DB ops still work.

### Phase 3 — LLM layer
8. Create `llm/client.py`: `call_llm`, `generate_image`. Pure network. Read `SILICONFLOW_API_KEY` from `config`.
9. Create `llm/generators.py`: `comment_text`, `comment_image`, `describe_image`. Take persona dict as arg.
10. Create `llm/memory.py`: `get_persona_memory`, `pick_fresh_topic`, `pick_fresh_story_prompt`.
11. **Test:** Force-trigger a comment by posting; check log for `[AI:...]`.

### Phase 4 — AI engine
12. Create `ai_engine/responder.py`: `schedule_responses`. Imports from `llm/generators.py`.
13. Create `ai_engine/schedulers.py`: `ai_post_scheduler`, `ai_story_scheduler`, plus `start_background_workers()` which spawns both daemon threads.
14. In `app.py`: `from ai_engine.schedulers import start_background_workers; start_background_workers()` inside `if __name__ == "__main__":`.
15. **Test:** wait 2min after start, check logs for `[AI-Post]` and `[AI-Story]`.

### Phase 5 — API blueprints
16. Create `api/posts.py`, `api/stories.py`, `api/profiles.py` as `Blueprint`s.
17. Move routes; replace `get_db()` calls with the same import (it's still the `g`-backed singleton).
18. Create `api/__init__.py` with `register_blueprints(app)`.
19. **Test:** every endpoint via curl + frontend.

### Phase 6 — Frontend split (the painful one)
20. Create `templates/index.html` — convert Python r-string to a real Jinja file. Replace inline `<style>` with `<link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">` and inline `<script>` with `<script src="...">` per module.
21. Carve `<style>...</style>` into `static/css/main.css`.
22. Carve the giant `<script>` into 5 files. Use `defer` and load order: `main.js` → `feed.js` → `stories.js` → `profile.js` → `compose.js`.
23. Watch for **shared state**: `imgB64`, `liked`, `personas`, `allPosts`, `storyData`, `curStoryUser`, `curSlide`, `storyTimer`. Either expose on `window.aura = {}` namespace or make `main.js` declare them and other files attach methods. Pick one and document it at top of `main.js`.
24. **Test:** every interaction (post, like, comment, story tap, profile open, highlight click).

### Phase 7 — Polish
25. Add `requirements.txt`: `flask`, `requests`, `python-dotenv`.
26. `.env.example` with placeholder key.
27. Short `README.md` with `python -m venv`, `pip install`, `python app.py`.
28. Optional: pre-commit hook for ruff/black.

---

## 10. Conventions for Continued Work

- **Indonesian persona prompts must stay Indonesian** — they encode the voice. Don't translate `personality` strings.
- **Response language**: human-facing UI is Indonesian, code/comments are English.
- **Token budget**: SiliconFlow is paid per token. Keep `max_tokens` tight (current default 90 for comments, 80 for posts, 70 for descriptions). Don't expand without reason.
- **Probability tuning lives in `personas.py`** — `reply_prob`, `delay_range`, `image_bias`. If you add a knob, put it there.
- **Memory before generation, always** — every new auto-post or auto-story must call `get_persona_memory(username)` and inject into the system prompt under "POST/STORY TERAKHIR KAMU".
- **`poster` arg is required** in `schedule_responses` — without it, AIs reply to themselves. Default to `"me"` for human posts.
- **Story emoji fallback** in JS exists for the "no real story yet" case — fine to keep, just be aware.
- **Don't introduce a build step** for frontend unless you also write a dev-mode runner. Keep vanilla.
- **Image storage**: keep base64-in-SQLite for this scale. Don't migrate to filesystem/S3 unless the DB grows past ~500MB.

---

## 11. Open Design Questions for Codex

When you have to make a judgment call, here's the prior thinking:

1. **Embeddings vs. recency window for memory?** → Stick with recency (5 items) until persona accumulates >100 posts. Then revisit with `BAAI/bge-m3`.
2. **Should AIs reply to AI comments (depth 2)?** → Currently no. Adding it risks infinite loops and token burn. If added, cap depth at 2 and add `replied_to_comment_id` cooldown.
3. **Highlight selection: random vs. LLM-decided?** → Random 35% for now. LLM-decided is nicer but +1 API call per story.
4. **Multi-user support?** → Out of scope. Project is intentionally single-user POC.
5. **Realtime updates?** → Polling every 15s/30s is fine. Don't add WebSockets unless the user asks.

---

## 12. Quickstart for the Next Agent

```bash
# Reset DB if schema changed
rm -f aura.db

# Run
python app.py
# → http://localhost:5000

# Watch logs for:
#   [BG] AI post scheduler started
#   [AI-Post] <user> ... post '<topic>'
#   [AI-Story] <user> story: '<prompt>...'
#   [AI:<user>] commenting post#<id>
#   [AI-Like] <user> liked post#<id>
```

**If nothing happens for 2+ minutes:** check API key, check `[401]` in logs. SiliconFlow returns clear errors.

**If frontend breaks after refactor:** open browser console, look for `Cannot read properties of undefined`. Most likely culprit: shared state between split JS files not in scope. Re-read step 23 above.

---

## 13. File Inventory Reference

The current full `app.py` (v3, single file) is the source of truth. Everything in this document is derived from it. When in doubt, **read the monolith** — it's the spec.

End of handoff. Good luck, Codex 👋
