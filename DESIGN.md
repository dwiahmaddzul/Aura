# Aura — Design System ("Dusk Journal")

Single source of truth for Aura's visual language. Read this before touching any
UI. The thesis behind every choice: **Aura is a calm private diary, not an
engagement machine.** When a pattern borrowed from social apps fights that
thesis, the thesis wins.

> For future agent sessions (Codex / Claude): the live tokens are in
> `static/css/main.css` under `:root`. Class names are stable contracts — the JS
> generates DOM with these exact names, so **restyle by changing rules, never by
> renaming classes.** If `main.css` and this doc disagree, `main.css` wins.

---

## 1. Principles

1. **Calm over engagement.** No streaks, no vanity counts, no red urgency dots,
   no "repost". Nothing that turns journaling into homework or a numbers game.
2. **One accent.** Warm amber-gold (`--acc`) is Aura's soul. Spend boldness in
   *one* place (the moment card); keep everything else quiet.
3. **Invisible AI.** No "AI" badges, no model names, no sycophancy. Personas read
   as friends, not features. (Carried over from the product spec.)
4. **Serif for warmth.** A literary serif (Fraunces) signals *journal*, used with
   restraint for display only. Body stays in a clean humanist sans (Sora).
5. **Hairlines, not walls.** Separate with faint rgba lines and surface shifts,
   not heavy borders. Generous, consistent spacing.

---

## 2. Color tokens

Warm-dark, violet-tinted near-black. One accent; dusk + rose are *atmosphere
only* (used in the story ring and the moment-card wash — never as a 2nd brand
color).

| Token | Hex | Use |
|-------|-----|-----|
| `--bg` | `#0e0b12` | app background (warm near-black) |
| `--s1` | `#15121d` | raised surface (cards, sheets) |
| `--s2` | `#1d1a28` | inputs, chips |
| `--s3` | `#272234` | hover / toast |
| `--bd` | `rgba(236,231,241,.07)` | hairline border |
| `--bd2`| `rgba(236,231,241,.13)` | stronger hairline |
| `--tx` | `#ece7f1` | primary text (warm off-white) |
| `--tx2`| `#b4afc4` | secondary text |
| `--mu` | `#878197` | muted / captions |
| `--acc` | `#dba96d` | **the** accent (amber-gold) |
| `--acc-soft` | `#eccea1` | accent highlight / serif headings on dark |
| `--acc-ink` | `#1a130a` | text on accent fills |
| `--dusk` | `#8a74ff` | atmosphere only (story ring, throwback icon, washes) |
| `--rose` | `#e07bb0` | atmosphere only (story ring) |
| `--red` | `#ef607c` | like / destructive |
| `--on` | `#56d39a` | online / positive |

---

## 3. Typography

- **Display — `--fd` = Fraunces** (serif). Logo, the moment card, page titles,
  names (post author, persona, DM), big stat numbers, comment author. Weights
  500–600. Optical sizing on. Use *with restraint* — it's the personality, not
  the workhorse.
- **Body / UI — `--fb` = Sora** (sans). Body text, captions, buttons, inputs,
  uppercase micro-labels (with letter-spacing).
- **Rule of thumb:** if it's a *name, a title, or a number that matters*, it's
  Fraunces. Everything else is Sora. Uppercase eyebrow labels stay Sora (a serif
  reads odd in all-caps).
- Body line-height 1.6–1.7. Base size 14px; post body 15px for comfortable
  reading.

---

## 4. Spacing / radius / elevation

- **Spacing scale (4px base):** `--s 4 · --sp2 8 · --sp3 12 · --sp4 16 ·
  --sp5 20 · --sp6 24 · --sp7 32 · --sp8 40`. Page gutter `--gut: 18px`.
  Don't invent in-between values — pick from the scale.
- **Radius:** `--r1 10 · --r2 14 · --r3 18 · --r4 24 · --rf 999`.
- **Elevation:** `--sh1` (subtle), `--sh2` (sheets/cards/toast), `--glow`
  (accent CTA only). Soft shadows, never hard.

---

## 5. Signature element — the "moment" card

`.daily-bn` (the daily prompt) is the one place Aura is bold: Fraunces headline,
a faint gold→dusk radial wash, generous padding, soft shadow. The throwback
(`.thr-bn`) sits beneath as a *quiet companion line*, not a competing card.
Everything else on Home stays disciplined so this card carries the warmth.

---

## 6. Product decisions baked into this redesign

What changed in the UX rationalization, and why — so nobody re-adds the cruft:

- **Streak — removed.** A "don't break the chain" counter turns journaling into
  homework. Direct contradiction of the thesis.
- **Like-as-metric — removed from profile.** The like *button* stays as a quiet
  "this resonated" gesture; the vanity *count* on the profile header is gone.
- **Repost — removed.** Reposting to a feed only you see is conceptually empty.
  (Any reposts already in the DB still render read-only via `.rp-w`; the *create*
  flow is gone. If the backend still generates AI reposts, disable that next.)
- **Search → "Jurnal".** Searching 6 fixed personas + your own handful of posts
  was dead UI. It's now a real **archive of your own entries**, grouped by month,
  searchable by text. This is genuinely useful for a diary.
- **Notifications → "Aktivitas".** Same data (who responded to you — that's the
  core payoff), minus the anxiety: no permanent red dot, calmer framing.
- **Profile stats** are now **Entri** + **Bulan ini** — reflection, not scores.
- **Icons unified.** Chrome uses SVG (Lucide-style) everywhere. Emoji survive
  only as *content*: the mood picker, the emoji panel, and the story reaction
  (immersive full-screen context). No emoji-as-icon in nav/buttons.

Still on the table (intentionally not done this pass, low-risk follow-ups):
- Persona overlay shows a random "Followers" number — fake engagement; replace or
  drop.
- Profile sub-tabs (grid/tweets/liked/saved/mood) could trim to fewer.

---

## 7. Quality floor (keep it)

- Mobile-first single column, `max-width: 430px`.
- Visible keyboard focus (`:focus-visible` accent ring).
- `prefers-reduced-motion` respected (animations collapse).
- `env(safe-area-inset-bottom)` on the nav, sheets, and inputs for notch phones.
- No build step. Vanilla CSS + JS, class-name contracts intact.

---

*Direction generated with the `ui-ux-pro-max` skill (pattern: Minimal Single
Column; principles: no emoji-as-icon, soft shadows, WCAG-minded), then adapted to
Aura's own warm-dark, serif-led identity rather than the skill's default palette.*
