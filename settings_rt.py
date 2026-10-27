"""
Aura Social — Runtime settings (diatur dari dashboard /kelola)

Disimpan di tabel SQLite `app_settings(key, value JSON, updated_at)`, jadi
berlaku tanpa restart dan tidak hilang saat container dibangun ulang.
Jalur panas (scheduler, request) membaca lewat cache kecil di memori yang
disegarkan tiap CACHE_SEC detik atau langsung setelah disimpan dari proses ini.

Setiap nilai yang masuk divalidasi dan di-clamp terhadap SCHEMA, jadi isian
form yang aneh tidak pernah bisa merusak scheduler.
"""
import json
import re
import secrets
import sqlite3
import threading
import time

from config import APP_TZ, DB_PATH, ENV_AI_OVERRIDES
from personas import PERSONAS, PMAP

CACHE_SEC = 5

# ── Preset mode cepat ─────────────────────────────────────────────────────
# Angka per hari kira-kira saat app dibuka terus-menerus (activity gate aktif).
PRESETS = {
    "hemat": {
        "post_enabled": True, "post_interval_min": 60, "post_interval_max": 120,
        "post_image_prob": 0.0,
        "story_enabled": True, "story_interval_min": 240, "story_interval_max": 480,
        "story_prob": 0.4, "image_daily_limit": 2,
        "comment_max": 2, "comment_on_ai_scale": 0.15, "vision_enabled": False,
        "active_window_min": 60, "auto_call_daily_limit": 120,
    },
    "normal": {
        "post_enabled": True, "post_interval_min": 25, "post_interval_max": 50,
        "post_image_prob": 0.1,
        "story_enabled": True, "story_interval_min": 90, "story_interval_max": 180,
        "story_prob": 0.5, "image_daily_limit": 8,
        "comment_max": 3, "comment_on_ai_scale": 0.35, "vision_enabled": True,
        "active_window_min": 120, "auto_call_daily_limit": 300,
    },
    "ramai": {
        "post_enabled": True, "post_interval_min": 10, "post_interval_max": 20,
        "post_image_prob": 0.25,
        "story_enabled": True, "story_interval_min": 30, "story_interval_max": 60,
        "story_prob": 0.8, "image_daily_limit": 25,
        "comment_max": 4, "comment_on_ai_scale": 0.6, "vision_enabled": True,
        "active_window_min": 240, "auto_call_daily_limit": 800,
    },
}

# Harga perkiraan SiliconFlow (USD per 1 juta token: [input, output]).
# Diverifikasi Okt 2026 untuk Qwen2.5-72B, DeepSeek-V3, Qwen3-32B,
# Qwen3-VL-32B, Kimi-K2; sisanya perkiraan. Bisa diubah dari dashboard.
DEFAULT_PRICES = {
    "Qwen/Qwen2.5-72B-Instruct": [0.59, 0.59],
    "deepseek-ai/DeepSeek-V3": [0.25, 1.00],
    "Qwen/Qwen3-32B": [0.14, 0.57],
    "Qwen/Qwen3-14B": [0.07, 0.28],
    "Qwen/Qwen3-8B": [0.06, 0.06],
    "Qwen/Qwen2.5-7B-Instruct": [0.05, 0.05],
    "Qwen/Qwen3-VL-32B-Instruct": [0.20, 0.60],
    "Qwen/Qwen3-VL-8B-Instruct": [0.14, 0.14],
    "Qwen/Qwen2.5-VL-72B-Instruct": [0.59, 0.59],
    "moonshotai/Kimi-K2-Instruct": [0.58, 2.29],
}
FALLBACK_PRICE = [0.5, 1.0]

# Saran model di dashboard (bebas diketik model lain, lalu dites).
SUGGESTED_TEXT_MODELS = [
    "Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3", "Qwen/Qwen3-32B",
    "Qwen/Qwen3-14B", "Qwen/Qwen3-8B", "Qwen/Qwen2.5-7B-Instruct",
]
SUGGESTED_VISION_MODELS = ["Qwen/Qwen3-VL-32B-Instruct", "Qwen/Qwen3-VL-8B-Instruct"]


def _env_or(key, default):
    return ENV_AI_OVERRIDES.get(key, default)


_N = PRESETS["normal"]

# key: (type, default, min, max)
GLOBAL_SCHEMA = {
    # master
    "ai_enabled":            ("bool", True),
    # posting otomatis
    "post_enabled":          ("bool", _N["post_enabled"]),
    "post_interval_min":     ("int", _env_or("post_interval_min", _N["post_interval_min"]), 5, 1440),
    "post_interval_max":     ("int", _env_or("post_interval_max", _N["post_interval_max"]), 5, 2880),
    "post_image_prob":       ("float", _env_or("post_image_prob", _N["post_image_prob"]), 0.0, 1.0),
    # story otomatis
    "story_enabled":         ("bool", _N["story_enabled"]),
    "story_interval_min":    ("int", _env_or("story_interval_min", _N["story_interval_min"]), 10, 2880),
    "story_interval_max":    ("int", _env_or("story_interval_max", _N["story_interval_max"]), 10, 4320),
    "story_prob":            ("float", _env_or("story_prob", _N["story_prob"]), 0.0, 1.0),
    "story_caption":         ("bool", True),
    # gambar
    "image_daily_limit":     ("int", _env_or("image_daily_limit", _N["image_daily_limit"]), 0, 500),
    # komentar / reaksi
    "comment_max":           ("int", _env_or("comment_max", _N["comment_max"]), 0, 6),
    "comment_on_ai_scale":   ("float", _env_or("comment_on_ai_scale", _N["comment_on_ai_scale"]), 0.0, 1.0),
    "ai_likes_enabled":      ("bool", True),
    "vision_enabled":        ("bool", _N["vision_enabled"]),
    "describe_uploads":      ("bool", True),
    "reply_to_user_prob":    ("float", 0.4, 0.0, 1.0),
    "thread_reply_prob":     ("float", 0.6, 0.0, 1.0),
    "dm_enabled":            ("bool", True),
    # kapan AI boleh jalan
    "active_window_min":     ("int", _env_or("active_window_min", _N["active_window_min"]), 0, 1440),
    "quiet_enabled":         ("bool", False),
    "quiet_start":           ("int", 23, 0, 23),
    "quiet_end":             ("int", 6, 0, 23),
    # rem biaya
    "auto_call_daily_limit": ("int", _N["auto_call_daily_limit"], 10, 5000),
    "interactive_daily_limit": ("int", 400, 10, 5000),
    "daily_budget_usd":      ("float", 0.0, 0.0, 100.0),
    "price_image_usd":       ("float", 0.0014, 0.0, 1.0),
    "usd_idr":               ("int", 16500, 1000, 100000),
    "model_prices":          ("prices", DEFAULT_PRICES),
    # lain-lain
    "app_tz":                ("tz", APP_TZ),
}

PERSONA_FIELDS = ("active", "can_image", "reply_prob", "text_model", "vision_model")

_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/:]{1,119}$")

_lock = threading.Lock()
_cache = {"t": 0.0, "vals": {}}
_version = [0]


# ── storage ───────────────────────────────────────────────────────────────
def init(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY, "
        "value TEXT, updated_at REAL)"
    )


def _connect():
    c = sqlite3.connect(DB_PATH, timeout=15)
    init(c)
    return c


def _load_all():
    try:
        c = _connect()
        try:
            rows = c.execute("SELECT key, value FROM app_settings").fetchall()
        finally:
            c.close()
    except Exception as e:
        print(f"[Settings] load error: {e}")
        return dict(_cache["vals"])
    out = {}
    for k, v in rows:
        try:
            out[k] = json.loads(v)
        except Exception:
            continue
    return out


def _vals():
    now = time.time()
    if now - _cache["t"] > CACHE_SEC:
        with _lock:
            if now - _cache["t"] > CACHE_SEC:
                _cache["vals"] = _load_all()
                _cache["t"] = now
    return _cache["vals"]


def invalidate():
    _cache["t"] = 0.0


def version():
    """Naik tiap kali ada perubahan dari dashboard (dipakai scheduler)."""
    return _version[0]


def _write(pairs):
    c = _connect()
    try:
        now = time.time()
        c.executemany(
            "INSERT INTO app_settings(key, value, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            [(k, json.dumps(v), now) for k, v in pairs.items()],
        )
        c.commit()
    finally:
        c.close()
    invalidate()
    _version[0] += 1


def _delete(keys):
    c = _connect()
    try:
        c.executemany("DELETE FROM app_settings WHERE key=?", [(k,) for k in keys])
        c.commit()
    finally:
        c.close()
    invalidate()
    _version[0] += 1


# ── validation ────────────────────────────────────────────────────────────
def _to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "ya", "on", "yes"):
            return True
        if s in ("0", "false", "tidak", "off", "no", ""):
            return False
    raise ValueError("harus ya/tidak")


def _coerce(spec, v):
    typ = spec[0]
    if typ == "bool":
        return _to_bool(v)
    if typ == "int":
        n = int(round(float(v)))
        return max(spec[2], min(spec[3], n))
    if typ == "float":
        f = float(v)
        if f != f:  # NaN
            raise ValueError("bukan angka")
        return round(max(spec[2], min(spec[3], f)), 4)
    if typ == "tz":
        from utils import valid_tz
        s = str(v).strip()
        if not valid_tz(s):
            raise ValueError("zona waktu tidak dikenal")
        return s
    if typ == "prices":
        if not isinstance(v, dict) or len(v) > 60:
            raise ValueError("format harga tidak valid")
        out = {}
        for m, pair in v.items():
            if not _MODEL_RE.match(str(m)):
                raise ValueError(f"nama model tidak valid: {m}")
            a, b = (pair + [0, 0])[:2] if isinstance(pair, list) else (0, 0)
            a, b = float(a), float(b)
            if not (0 <= a <= 100 and 0 <= b <= 100):
                raise ValueError("harga harus 0-100 USD per 1M token")
            out[str(m)] = [round(a, 4), round(b, 4)]
        return out
    raise ValueError("tipe tidak dikenal")


def _persona_spec(username, field):
    p = PMAP[username]
    if field in ("active", "can_image"):
        return ("bool", True)
    if field == "reply_prob":
        return ("float", float(p.get("reply_prob", 0.4)), 0.0, 1.0)
    if field == "text_model":
        return ("model", p["text_model"])
    if field == "vision_model":
        return ("vmodel", p.get("vision_model") or "")
    raise KeyError(field)


def _coerce_persona(spec, v):
    if spec[0] == "model":
        s = str(v).strip()
        if not _MODEL_RE.match(s):
            raise ValueError("nama model tidak valid")
        return s
    if spec[0] == "vmodel":
        s = str(v or "").strip()
        if s and not _MODEL_RE.match(s):
            raise ValueError("nama model tidak valid")
        return s
    return _coerce(spec, v)


# ── public API ────────────────────────────────────────────────────────────
def get(key):
    spec = GLOBAL_SCHEMA[key]
    v = _vals().get(key, None)
    if v is None:
        return spec[1]
    try:
        return _coerce(spec, v)
    except Exception:
        return spec[1]


def persona(username, field):
    spec = _persona_spec(username, field)
    v = _vals().get(f"p.{username}.{field}", None)
    if v is None:
        return spec[1]
    try:
        return _coerce_persona(spec, v)
    except Exception:
        return spec[1]


def active_personas():
    return [p for p in PERSONAS if persona(p["username"], "active")]


def text_model(p):
    return persona(p["username"], "text_model") or p["text_model"]


def vision_model(p):
    """'' / None = persona tidak 'melihat' gambar."""
    return persona(p["username"], "vision_model") or None


def price_for(model):
    prices = get("model_prices") or {}
    return prices.get(model) or DEFAULT_PRICES.get(model) or FALLBACK_PRICE


def snapshot():
    """Semua nilai efektif + default, untuk dashboard."""
    glob = {k: get(k) for k in GLOBAL_SCHEMA}
    defaults = {k: spec[1] for k, spec in GLOBAL_SCHEMA.items()}
    bounds = {k: [spec[2], spec[3]] for k, spec in GLOBAL_SCHEMA.items() if spec[0] in ("int", "float")}
    personas = []
    for p in PERSONAS:
        un = p["username"]
        personas.append({
            "username": un,
            "display": p["display"],
            "avatar": p["avatar"],
            "color": p["color"],
            **{f: persona(un, f) for f in PERSONA_FIELDS},
            "default_text_model": p["text_model"],
            "default_vision_model": p.get("vision_model") or "",
        })
    return {
        "settings": glob,
        "defaults": defaults,
        "bounds": bounds,
        "personas": personas,
        "presets": PRESETS,
        "suggested_text_models": SUGGESTED_TEXT_MODELS,
        "suggested_vision_models": SUGGESTED_VISION_MODELS,
        "version": version(),
    }


def save(changes):
    """changes: {key: value} untuk global, atau {"p.<username>.<field>": value}.
    Return (tersimpan: dict, error: dict)."""
    saved, errors = {}, {}
    if not isinstance(changes, dict):
        return saved, {"_": "format salah"}
    for k, v in list(changes.items())[:80]:
        try:
            if k in GLOBAL_SCHEMA:
                saved[k] = _coerce(GLOBAL_SCHEMA[k], v)
            elif k.startswith("p.") and k.count(".") >= 2:
                # username boleh mengandung titik (bimo.plays) → ambil field dari belakang
                un, field = k[2:].rsplit(".", 1)
                if un not in PMAP or field not in PERSONA_FIELDS:
                    raise KeyError
                saved[k] = _coerce_persona(_persona_spec(un, field), v)
            else:
                raise KeyError
        except KeyError:
            errors[k] = "pengaturan tidak dikenal"
        except (ValueError, TypeError) as e:
            errors[k] = str(e) or "nilai tidak valid"
    # Pasangan min/max harus konsisten (min ≤ max).
    merged = {k: get(k) for k in GLOBAL_SCHEMA}
    merged.update({k: v for k, v in saved.items() if k in GLOBAL_SCHEMA})
    for a, b in (("post_interval_min", "post_interval_max"),
                 ("story_interval_min", "story_interval_max")):
        if merged[a] > merged[b]:
            if a in saved and b not in saved:
                saved[b] = merged[a]
            else:
                saved[a] = merged[b]
    if saved:
        _write(saved)
    return saved, errors


def apply_preset(name):
    preset = PRESETS.get(name)
    if not preset:
        return None
    saved, _ = save(dict(preset))
    return saved


def reset_defaults():
    """Hapus semua override global + persona (balik ke default)."""
    c = _connect()
    try:
        keys = [r[0] for r in c.execute("SELECT key FROM app_settings").fetchall()
                if not r[0].startswith("_")]
    finally:
        c.close()
    if keys:
        _delete(keys)


# ── nilai internal (bukan knob dashboard) ─────────────────────────────────
def get_raw(key, default=None):
    v = _vals().get(key)
    return default if v is None else v


def set_raw(key, value):
    _write({key: value})


def secret_key():
    """Kunci cookie sesi yang persisten (dibuat sekali, disimpan di DB)."""
    k = get_raw("_secret")
    if not k:
        k = secrets.token_hex(32)
        set_raw("_secret", k)
    return k
