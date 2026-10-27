"""
Aura Social — Rem biaya AI

Satu tempat untuk memutuskan apakah AI boleh bekerja sekarang. Semua angka
dibaca dari settings_rt (dashboard /kelola), jadi berlaku tanpa restart.

- auto_block_reason()        : untuk aktivitas yang AI lakukan sendiri
                               (post, story, komentar di post AI).
- interactive_block_reason() : untuk respons atas tindakanmu (DM, komentar
                               di post-mu, balasan komentar).
- try_consume_image()        : ambil 1 jatah gambar hari ini (atomik).

Activity gate: scheduler cuma jalan kalau app dibuka dalam N menit terakhir.
Setelah restart, status mulai "idle" (fail-closed: tidak membakar kuota diam-diam).
"""
import sqlite3
import threading
import time

import settings_rt as S
from ai_engine import usage
from config import DB_PATH
from utils import local_day, now_local

# Detak loop scheduler (detik). Perubahan setting terasa dalam ≤ 1 detak.
IDLE_RECHECK_SEC = 30

_last_seen = [0.0]
_budget_lock = threading.Lock()


def mark_activity():
    """Dipanggil dari before_request untuk tiap hit /api/* dari browser user."""
    _last_seen[0] = time.time()


def last_seen():
    return _last_seen[0]


def user_is_active():
    w = S.get("active_window_min")
    if w <= 0:
        return True
    return (time.time() - _last_seen[0]) < w * 60


def in_quiet_hours():
    if not S.get("quiet_enabled"):
        return False
    start, end = S.get("quiet_start"), S.get("quiet_end")
    if start == end:
        return False
    h = now_local().hour
    if start < end:
        return start <= h < end
    return h >= start or h < end


def budget_exceeded():
    b = S.get("daily_budget_usd")
    return b > 0 and usage.cost_today() >= b


def auto_block_reason():
    """None kalau boleh jalan, atau alasan singkat kenapa ditahan."""
    if not S.get("ai_enabled"):
        return "AI dimatikan"
    if in_quiet_hours():
        return "jam tenang"
    if not user_is_active():
        return "app sedang tidak dibuka"
    if usage.auto_calls_today() >= S.get("auto_call_daily_limit"):
        return "batas panggilan otomatis hari ini tercapai"
    if budget_exceeded():
        return "anggaran harian habis"
    return None


def auto_ok():
    return auto_block_reason() is None


def interactive_block_reason():
    if not S.get("ai_enabled"):
        return "AI dimatikan"
    if usage.interactive_calls_today() >= S.get("interactive_daily_limit"):
        return "batas balasan harian tercapai"
    return None


def interactive_ok():
    return interactive_block_reason() is None


def _usage_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS ai_usage(day TEXT PRIMARY KEY, images INTEGER DEFAULT 0)")


def try_consume_image(persona_username=None):
    """Ambil 1 jatah gambar hari ini. True kalau masih ada kuota.
    Dihitung per PERCOBAAN generate (bukan per sukses), sengaja ke arah hemat."""
    limit = S.get("image_daily_limit")
    if limit <= 0:
        return False
    if persona_username and not S.persona(persona_username, "can_image"):
        return False
    if budget_exceeded():
        return False
    day = local_day()
    with _budget_lock:
        conn = sqlite3.connect(DB_PATH, timeout=15)
        try:
            _usage_table(conn)
            conn.execute("INSERT OR IGNORE INTO ai_usage(day, images) VALUES(?, 0)", (day,))
            used = conn.execute("SELECT images FROM ai_usage WHERE day=?", (day,)).fetchone()[0]
            if used >= limit:
                return False
            conn.execute("UPDATE ai_usage SET images=images+1 WHERE day=?", (day,))
            conn.commit()
            return True
        except Exception as e:
            print(f"[Budget] error: {e}")
            return False  # kalau ragu, jangan generate (hemat)
        finally:
            conn.close()


def images_used_today():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=15)
        try:
            _usage_table(conn)
            row = conn.execute("SELECT images FROM ai_usage WHERE day=?", (local_day(),)).fetchone()
        finally:
            conn.close()
        return row[0] if row else 0
    except Exception:
        return 0


def status():
    """Ringkasan rem untuk /kelola dan /api/health."""
    seen = _last_seen[0]
    return {
        "ai_enabled": S.get("ai_enabled"),
        "user_active": user_is_active(),
        "last_seen_sec": int(time.time() - seen) if seen else None,
        "quiet_now": in_quiet_hours(),
        "auto_block": auto_block_reason(),
        "interactive_block": interactive_block_reason(),
        "images_today": images_used_today(),
        "image_daily_limit": S.get("image_daily_limit"),
        "auto_calls_today": usage.auto_calls_today(),
        "auto_call_daily_limit": S.get("auto_call_daily_limit"),
        "interactive_calls_today": usage.interactive_calls_today(),
        "interactive_daily_limit": S.get("interactive_daily_limit"),
        "cost_today": round(usage.cost_today(), 5),
        "daily_budget_usd": S.get("daily_budget_usd"),
    }
