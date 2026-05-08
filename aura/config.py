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
    Existing OS env vars take precedence over .env values.
    Uses utf-8-sig encoding to tolerate BOM (common when editing in
    Windows Notepad)."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()

SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "").strip()
SILICONFLOW_BASE    = os.environ.get("SILICONFLOW_BASE", "https://api.siliconflow.com/v1")
TEXT_MODEL          = os.environ.get("TEXT_MODEL", "Qwen/Qwen2.5-72B-Instruct")
VISION_MODEL        = os.environ.get("VISION_MODEL", "Qwen/Qwen3-VL-32B-Instruct")
IMAGE_MODEL         = os.environ.get("IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
DB_PATH             = os.environ.get("DB_PATH", "aura.db")
PORT                = int(os.environ.get("PORT", "5000"))

if not SILICONFLOW_API_KEY:
    print(
        "\n⚠️  WARNING: SILICONFLOW_API_KEY is not set.\n"
        "   AI features (comments, DMs, image generation) will fail silently.\n"
        "   Copy .env.example to .env and set your key, then restart.\n"
    )
