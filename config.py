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
# Sejak Okt 2026 semua knob AI diatur dari dashboard /kelola dan disimpan di
# SQLite (settings_rt.py), berlaku tanpa restart. Env var di bawah HANYA
# dipakai sebagai nilai awal kalau di-set eksplisit; begitu disimpan dari
# dashboard, nilai di database yang menang.
_ENV_AI_KEYS = {
    # env var              -> settings key, tipe
    "AI_POST_INTERVAL_MIN":   ("post_interval_min", int),
    "AI_POST_INTERVAL_MAX":   ("post_interval_max", int),
    "AI_STORY_INTERVAL_MIN":  ("story_interval_min", int),
    "AI_STORY_INTERVAL_MAX":  ("story_interval_max", int),
    "AI_POST_IMAGE_PROB":     ("post_image_prob", float),
    "AI_STORY_PROB":          ("story_prob", float),
    "AI_IMAGE_DAILY_LIMIT":   ("image_daily_limit", int),
    "AI_ACTIVE_WINDOW_MIN":   ("active_window_min", int),
    "AI_COMMENT_MAX":         ("comment_max", int),
    "AI_COMMENT_ON_AI_SCALE": ("comment_on_ai_scale", float),
}
ENV_AI_OVERRIDES = {}
for _env, (_key, _typ) in _ENV_AI_KEYS.items():
    _raw = os.environ.get(_env, "").strip()
    if _raw:
        try:
            ENV_AI_OVERRIDES[_key] = _typ(_raw)
        except ValueError:
            print(f"⚠️  {_env} bukan angka, diabaikan")

# ── Dashboard /kelola & misc ──────────────────────────────────────────────
# Password dashboard. Kosong = dashboard terkunci total.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
# Kunci tanda tangan cookie sesi. Kosong = dibuat acak sekali dan disimpan di DB.
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
# Cookie sesi hanya lewat HTTPS (set 0 untuk uji lokal via http).
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1").strip() != "0"
# Zona waktu default (bisa diganti dari dashboard).
APP_TZ = os.environ.get("APP_TZ", "Asia/Jakarta").strip() or "Asia/Jakarta"
# Folder gambar. Default: folder "media" di sebelah file DB (ikut volume).
MEDIA_DIR = os.environ.get("MEDIA_DIR", "").strip() or str(
    Path(DB_PATH).resolve().parent / "media"
)
# Pindahkan gambar lama (base64 di DB) ke file WebP di latar belakang.
MEDIA_MIGRATE = os.environ.get("MEDIA_MIGRATE", "1").strip() != "0"

if not SILICONFLOW_API_KEY:
    print(
        "\n⚠️  WARNING: SILICONFLOW_API_KEY is not set.\n"
        "   AI features (comments, DMs, image generation) will fail silently.\n"
        "   Copy .env.example to .env and set your key, then restart.\n"
    )
