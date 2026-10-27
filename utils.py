"""
Aura Social — Utility Helpers
Time labels follow diary-app conventions: "tadi pagi", "semalam", etc.
The aim is to feel like the way humans recall time, not a stopwatch.

All calendar math (today / yesterday / part of day / month) runs in the app's
local time zone (default Asia/Jakarta, changeable from /kelola), NOT the
server clock. Containers run in UTC, which used to label a 21:00 WIB post as
"tadi siang".
"""
import time
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

_TZ_CACHE = {}
_WIB = timezone(timedelta(hours=7), "WIB")


def _tz_name():
    try:
        from settings_rt import get as sget
        return sget("app_tz")
    except Exception:
        from config import APP_TZ
        return APP_TZ


def local_tz():
    """tzinfo for the configured zone. Falls back to fixed UTC+7 (WIB)."""
    name = _tz_name() or "Asia/Jakarta"
    tz = _TZ_CACHE.get(name)
    if tz is None:
        try:
            tz = ZoneInfo(name) if ZoneInfo else _WIB
        except Exception:
            tz = _WIB
        _TZ_CACHE[name] = tz
    return tz


def valid_tz(name):
    """True if `name` is a usable IANA zone (e.g. 'Asia/Jakarta')."""
    if not name or not ZoneInfo:
        return False
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def now_local():
    return datetime.now(local_tz())


def to_local(ts):
    return datetime.fromtimestamp(ts, local_tz())


def local_day(ts=None):
    """YYYY-MM-DD in local time (used for daily quotas and stats)."""
    d = now_local() if ts is None else to_local(ts)
    return d.strftime("%Y-%m-%d")


def time_ago(ts):
    """Convert timestamp to Indonesian relative-time string with diary feel.

    < 1 min → "baru saja", < 60 min → "5 mnt lalu", today → "tadi pagi/siang/
    sore/malam", yesterday → "kemarin …", then hari / minggu / bulan / tahun.
    """
    if not ts:
        return ""
    now = time.time()
    d = now - ts
    if d < 60:
        return "baru saja"
    if d < 3600:
        return f"{int(d // 60)} mnt lalu"

    now_dt = to_local(now)
    then_dt = to_local(ts)
    days_diff = (now_dt.date() - then_dt.date()).days

    if days_diff == 0:
        return f"tadi {_part_of_day(then_dt.hour)}"
    if days_diff == 1:
        return f"kemarin {_part_of_day(then_dt.hour)}"
    if days_diff < 7:
        return f"{days_diff} hari lalu"
    if days_diff < 30:
        return f"{days_diff // 7} minggu lalu"
    if days_diff < 365:
        return f"{max(1, days_diff // 30)} bulan lalu"
    return f"{days_diff // 365} tahun lalu"


def _part_of_day(hour):
    """Indonesian part-of-day label."""
    if 4 <= hour < 11:
        return "pagi"
    if 11 <= hour < 15:
        return "siang"
    if 15 <= hour < 19:
        return "sore"
    return "malam"


def part_of_day_now():
    """Current part of day label (used for time-aware prompts)."""
    return _part_of_day(now_local().hour)


def greeting_for_now():
    """Soft greeting matching part-of-day. Used for onboarding/empty states."""
    h = now_local().hour
    if 4 <= h < 11:
        return "Selamat pagi"
    if 11 <= h < 15:
        return "Selamat siang"
    if 15 <= h < 19:
        return "Selamat sore"
    return "Selamat malam"
