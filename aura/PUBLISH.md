# Publishing to GitHub — Step by Step

This guide walks you through pushing Aura to GitHub for the first time, **safely** (without leaking your `.env`).

---

## 1. Pre-flight check

Before anything, verify your `.env` is **gitignored**:

```bash
cat .gitignore | grep ".env"
```

You should see `.env` (and `.env.local`). If not, stop and add it before continuing.

Run the test suite to confirm everything works:

```bash
pytest -v
```

You should see `30 passed`. If anything fails, fix that first — don't push broken code.

---

## 2. Initialize git

```bash
cd path/to/aura
git init
git branch -M main
```

---

## 3. Stage and verify

```bash
git add .
git status
```

**Look at the output carefully.** You should NOT see:

- `.env` ❌ (your API key would leak)
- `aura.db` ❌ (your private journal entries)
- `__pycache__/` ❌ (Python cache, useless)
- `.pytest_cache/` ❌ (test cache)

You SHOULD see:

- `.env.example` ✅
- `.gitignore` ✅
- `LICENSE`, `README.md`, `CHANGELOG.md` ✅
- `app.py`, `config.py`, etc. ✅
- `static/`, `templates/`, `tests/` ✅

If something sensitive is staged, **stop now**. Add it to `.gitignore` and:

```bash
git rm --cached <filename>
git add .gitignore
```

---

## 4. First commit

```bash
git commit -m "Aura v1.0 — diary that lives like personal social media"
```

---

## 5. Create the repo on GitHub

### Option A — via web

1. Go to <https://github.com/new>
2. Name: `aura` (or whatever you want)
3. Description: *Tempat curhatmu sendiri — diary yang ngalir kayak medsos pribadi*
4. **Public** (or Private, your call)
5. **Don't** check "Initialize with README" — we already have one
6. Create repository
7. Copy the URL it shows you (`https://github.com/USERNAME/aura.git`)

### Option B — via GitHub CLI (`gh`)

If you have [gh](https://cli.github.com/) installed:

```bash
gh repo create aura --public --source=. --remote=origin --push
```

Skip step 6 below if you used this — it pushes automatically.

---

## 6. Push

```bash
git remote add origin https://github.com/YOUR_USERNAME/aura.git
git push -u origin main
```

If asked for credentials, use a [Personal Access Token](https://github.com/settings/tokens) (not your password — GitHub deprecated that).

---

## 7. Verify on GitHub

Open `https://github.com/YOUR_USERNAME/aura` in browser:

- ✅ README renders with the icon
- ✅ Your `.env` is **NOT** in the file list
- ✅ `aura.db` is **NOT** in the file list
- ✅ All folders (`api/`, `static/`, etc.) are present

If you see `.env` listed, **immediately**:

1. Delete the repo on GitHub (Settings → Danger Zone → Delete)
2. **Rotate your API key** at siliconflow.com (the old one is compromised)
3. Add `.env` to `.gitignore` properly
4. Re-init from step 2

---

## 8. After-first-push workflow

For future updates:

```bash
git add .
git commit -m "describe what you changed"
git push
```

---

## Suggested .gitattributes (optional)

For consistent line endings across OS:

```bash
echo "* text=auto eol=lf" > .gitattributes
echo "*.bat text eol=crlf" >> .gitattributes
git add .gitattributes
git commit -m "Add gitattributes for line endings"
```

---

## Branch protection (recommended for serious projects)

Settings → Branches → Add rule for `main`:

- Require pull request reviews before merging
- Require status checks (run `pytest` via GitHub Actions)
- Disable force push

---

## Repo description & topics

On GitHub, go to your repo → click ⚙️ next to "About" → add:

- **Description**: *Tempat curhatmu sendiri — diary that lives like personal social media*
- **Website**: (your demo URL or empty)
- **Topics**: `journaling`, `diary`, `flask`, `python`, `bahasa-indonesia`, `local-first`, `single-page-app`

---

## When you screw up — emergency: leaked secret

If you accidentally pushed a real API key:

1. **Immediately** rotate it at siliconflow.com
2. Force-rewrite history to scrub the key:
   ```bash
   git filter-repo --replace-text <(echo "sk-xxxxxxxx==>REMOVED")
   git push --force
   ```
3. Even after history rewrite, the key is in GitHub's archives. **Always rotate.**

Better to never push it in the first place — that's why `.gitignore` exists. ✨
