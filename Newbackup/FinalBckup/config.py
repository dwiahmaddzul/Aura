"""
Aura Social — Configuration
All settings loaded from environment variables with sensible defaults.
For production: copy .env.example to .env and override values.
"""
import os

SILICONFLOW_API_KEY = os.environ.get(
    "SILICONFLOW_API_KEY",
    "sk-yaluviakgcbvoxtgbgxysgwucjwjebpmbwxrsihakmwuagou",
)
SILICONFLOW_BASE = os.environ.get("SILICONFLOW_BASE", "https://api.siliconflow.com/v1")
TEXT_MODEL       = os.environ.get("TEXT_MODEL", "Qwen/Qwen2.5-72B-Instruct")
VISION_MODEL     = os.environ.get("VISION_MODEL", "Qwen/Qwen3-VL-32B-Instruct")
IMAGE_MODEL      = os.environ.get("IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
DB_PATH          = os.environ.get("DB_PATH", "aura.db")
