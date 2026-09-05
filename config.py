"""
Aura Social — Configuration
All settings loaded from environment variables with sensible defaults.

Setup:
  1. Copy .env.example → .env
  2. Edit .env and set SILICONFLOW_API_KEY=...
  3. Run python app.py

The .env file is loaded automatically below. Never commit .env to git.
"""
import os
from pathlib import Path


def _load_dotenv():
    """Lightweight .env loader (no dependency on python-dotenv).
    Reads KEY=VALUE pairs from .env in project root if present.
    Existing OS env vars take precedence over .env values."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()

def _env_int(name, default):
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        print(f"⚠️  {name} bukan angka — pakai default {default}")
        return default


def _env_float(name, default):
    try:
        return float(os.environ.get(name, "").strip() or default)
    except ValueError:
        print(f"⚠️  {name} bukan angka — pakai default {default}")
        return default


SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "").strip()
SILICONFLOW_BASE    = os.environ.get("SILICONFLOW_BASE", "https://api.siliconflow.com/v1")
TEXT_MODEL          = os.environ.get("TEXT_MODEL", "Qwen/Qwen2.5-72B-Instruct")
VISION_MODEL        = os.environ.get("VISION_MODEL", "Qwen/Qwen3-VL-32B-Instruct")
IMAGE_MODEL         = os.environ.get("IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")

# DB: kalau ada Railway Volume, default otomatis ke dalam volume
# (env DB_PATH tetap menang kalau di-set manual).
_vol = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
_default_db = str(Path(_vol) / "aura.db") if _vol else "aura.db"
DB_PATH = os.environ.get("DB_PATH", _default_db)

# ── AI cost controls ──────────────────────────────────────────────────────
# Semua bisa dioverride via env / tab Variables di Railway.
# Default di bawah SENGAJA lebih hemat daripada perilaku v1.0.
# Interval dalam MENIT.
AI_POST_INTERVAL_MIN  = _env_int("AI_POST_INTERVAL_MIN", 10)    # v1.0: 8
AI_POST_INTERVAL_MAX  = _env_int("AI_POST_INTERVAL_MAX", 20)    # v1.0: 15
AI_STORY_INTERVAL_MIN = _env_int("AI_STORY_INTERVAL_MIN", 30)   # v1.0: 15
AI_STORY_INTERVAL_MAX = _env_int("AI_STORY_INTERVAL_MAX", 60)   # v1.0: 25
# Peluang post AI menyertakan gambar FLUX (v1.0: 0.30).
AI_POST_IMAGE_PROB    = _env_float("AI_POST_IMAGE_PROB", 0.15)
# Peluang satu siklus story benar-benar generate (v1.0: selalu / 1.0).
AI_STORY_PROB         = _env_float("AI_STORY_PROB", 0.5)
# Kuota gambar FLUX per hari, semua sumber. 0 = tanpa gambar AI sama sekali.
AI_IMAGE_DAILY_LIMIT  = _env_int("AI_IMAGE_DAILY_LIMIT", 20)
# Scheduler hanya jalan kalau app dibuka dalam N menit terakhir. 0 = 24/7.
AI_ACTIVE_WINDOW_MIN  = _env_int("AI_ACTIVE_WINDOW_MIN", 240)
# Maks persona yang komentar per post (target balasan tidak kena cap).
AI_COMMENT_MAX        = _env_int("AI_COMMENT_MAX", 3)
# Peredam obrolan AI↔AI: pengali reply_prob saat yang posting bukan 'me'.
AI_COMMENT_ON_AI_SCALE = _env_float("AI_COMMENT_ON_AI_SCALE", 0.5)

# Sanity clamps
AI_POST_INTERVAL_MIN  = max(1, AI_POST_INTERVAL_MIN)
AI_POST_INTERVAL_MAX  = max(AI_POST_INTERVAL_MIN, AI_POST_INTERVAL_MAX)
AI_STORY_INTERVAL_MIN = max(1, AI_STORY_INTERVAL_MIN)
AI_STORY_INTERVAL_MAX = max(AI_STORY_INTERVAL_MIN, AI_STORY_INTERVAL_MAX)
AI_POST_IMAGE_PROB    = min(max(AI_POST_IMAGE_PROB, 0.0), 1.0)
AI_STORY_PROB         = min(max(AI_STORY_PROB, 0.0), 1.0)
AI_COMMENT_ON_AI_SCALE = min(max(AI_COMMENT_ON_AI_SCALE, 0.0), 1.0)

if not SILICONFLOW_API_KEY:
    print(
        "\n⚠️  WARNING: SILICONFLOW_API_KEY is not set.\n"
        "   AI features (comments, DMs, image generation) will fail silently.\n"
        "   Copy .env.example to .env and set your key, then restart.\n"
    )
