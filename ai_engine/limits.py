"""
Aura Social — AI Cost Limits
Central gate untuk semua generasi AI otomatis. Dua mekanisme:

1. Activity gate  — scheduler cuma jalan kalau user baru saja membuka app
                    (AI_ACTIVE_WINDOW_MIN menit terakhir). App yang nggak
                    dibuka = nggak ada biaya API. Setelah restart, state
                    mulai "idle" (fail-closed: nggak bakar kuota diam-diam).
2. Image budget   — kuota gambar FLUX per hari (AI_IMAGE_DAILY_LIMIT),
                    disimpan di tabel ai_usage (SQLite) supaya restart
                    container tidak mereset hitungan.

Semua knob dibaca dari config.py (env / Railway Variables).
"""
import sqlite3
import threading
import time

from config import AI_ACTIVE_WINDOW_MIN, AI_IMAGE_DAILY_LIMIT, DB_PATH

# Berapa lama scheduler tidur sebelum ngecek ulang saat user idle.
IDLE_RECHECK_SEC = 300

_last_seen = 0.0
_budget_lock = threading.Lock()


def mark_activity():
    """Panggil dari before_request untuk tiap hit /api/* dari browser user."""
    global _last_seen
    _last_seen = time.time()


def user_is_active():
    """True kalau user membuka app dalam AI_ACTIVE_WINDOW_MIN menit terakhir.
    AI_ACTIVE_WINDOW_MIN=0 mematikan gate ini (perilaku lama: 24/7)."""
    if AI_ACTIVE_WINDOW_MIN <= 0:
        return True
    return (time.time() - _last_seen) < AI_ACTIVE_WINDOW_MIN * 60


def _today():
    # Tanggal lokal server (di Railway = UTC). Cukup untuk kuota harian.
    return time.strftime("%Y-%m-%d")


def try_consume_image():
    """Ambil 1 jatah gambar hari ini. Return True kalau masih ada kuota.
    Dihitung per PERCOBAAN generate (bukan per sukses) — sengaja, biar
    aman ke arah hemat. AI_IMAGE_DAILY_LIMIT=0 mematikan gambar AI total."""
    if AI_IMAGE_DAILY_LIMIT <= 0:
        return False
    day = _today()
    with _budget_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO ai_usage(day, images) VALUES(?, 0)", (day,)
            )
            row = conn.execute(
                "SELECT images FROM ai_usage WHERE day=?", (day,)
            ).fetchone()
            used = row[0] if row else 0
            if used >= AI_IMAGE_DAILY_LIMIT:
                return False
            conn.execute(
                "UPDATE ai_usage SET images=images+1 WHERE day=?", (day,)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[Budget] error: {e}")
            return False  # kalau ragu, jangan generate (hemat)
        finally:
            conn.close()


def images_used_today():
    """Untuk /api/health: berapa gambar sudah terpakai hari ini."""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT images FROM ai_usage WHERE day=?", (_today(),)
        ).fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return 0
