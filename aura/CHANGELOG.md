# Changelog

All notable changes to Aura.

## [1.0.0] — Final release

The first version that feels finished. Reframed from "an AI persona experiment" into "a diary that lives like personal social media." If you can use it for a week and forget the friends are language models, it worked.

### Added
- **Onboarding** — First-time users get a soft welcome banner instead of an empty home
- **Time-aware prompts** — Compose placeholder shifts by part of day (pagi/siang/sore/malam) with 3-4 prompts each
- **Smart timestamps** — "tadi pagi", "semalam", "kemarin sore" instead of `5h lalu`
- **Insights tab** — 30-day mood heatmap + post count + dominant mood pattern
- **Online indicators** — Pulse dots on friends, deterministic per 10-min bucket so they don't flicker
- **Real notifications** — Aggregated likes/comments/DMs from friends, sorted by recency
- **Real search** — Across posts, friends, and DM history, with debouncing
- **Keyboard shortcuts** — `n` new post, `/` search, `Esc` close, `h` home
- **Loading skeletons** — Replaced text "Loading…" with shimmer placeholders
- **Image client-side resize** — Photos > 1080px get downscaled before upload (saves DB + tokens)
- **Polished empty states** — Each one written to invite, not scold

### Changed
- **Removed all "AI" labels** from the UI — no more `AI` badges on posts/comments
- **Hidden model names** — Friend profiles no longer show `Qwen/Qwen3-32B` etc.
- **De-AI-ified copy** — "AI Personas" → "Teman", "robot" emojis → softer alternatives
- **Empty states reworded** — "Belum ada percakapan" → "Tulis sapaan pertama 👋"
- **README reframed** — From technical AI demo to product-grade diary app pitch

### Fixed
- **DM polling bug** — Input field no longer wipes mid-typing during background polling. Switched from full re-render to incremental append-only updates
- **Typing indicator flicker** — No longer disappears and reappears between polls
- **Profile overlay error** — `${u}` undefined → fixed reference to `${d.username}`
- **Empty `me_profile` row** — `init_db` now seeds default profile in `create_app`, not just when running directly

### Security
- **Removed hardcoded API key** from `config.py`. Now strict env-based with built-in `.env` loader (no python-dotenv dependency)
- **Added `.gitignore`** covering `.env`, DBs, caches, IDE files
- **MIT LICENSE** added

---

## [0.9.0] — Feature explosion

Heavy lifting on features. Major rebuild of frontend.

### Added
- DM with persona threads + memory (last 12 messages of context)
- Story upload by user
- Edit profile (name, bio, avatar)
- Bookmark / unbookmark with persistence
- Repost (quote-style with original post embedded)
- Liked tab in profile
- Daily check-in banner from a random friend
- On This Day throwback (7/14/30/90/365 days)
- Mood timeline (30-day grid)
- Streak counter (allows yesterday-anchor for grace)
- Share profile button
- Emoji picker in compose (24 common emojis)

### Changed
- 3 profile tabs → 5 (grid/tweets/liked/saved/mood)
- DM modal → DM page

---

## [0.5.0] — Modularization

Split monolithic `app.py` (~900 lines) into proper modules.

```
config / personas / db / utils
llm/{client, generators, memory}
ai_engine/{responder, schedulers}
api/{posts, stories, profiles}
static/js/{main, stories, feed, profile, compose}
```

No behavior change — same routes, same DB, same UI. Just cleaner.

---

## [0.4.0] — Mood tagging

Posts gained a mood field. 6 emoji moods. AI sees `[mood: X]` prefix when responding so reactions adapt.

---

## [0.1.0] — First posts

Six personas, a feed, basic stories, comments, likes. The core loop.
