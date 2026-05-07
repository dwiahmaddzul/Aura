"""
Aura Social — Utility Helpers
Time labels follow diary-app conventions: "tadi pagi", "semalam", etc.
The aim is to feel like the way humans recall time, not a stopwatch.
"""
import time
from datetime import datetime, timedelta


def time_ago(ts):
    """Convert timestamp to Indonesian relative-time string with diary feel.

    Examples:
      < 1 min        → "baru saja"
      < 60 min       → "5 mnt lalu"
      Today, morning → "tadi pagi"
      Today, noon    → "tadi siang"
      Today, evening → "tadi sore"
      Today, night   → "tadi malam"
      Yesterday      → "kemarin pagi/siang/sore/malam"
      2-6 days       → "3 hari lalu"
      < 4 weeks      → "2 minggu lalu"
      < 12 months    → "5 bulan lalu"
      Older          → "1 tahun lalu"
    """
    now = time.time()
    d = now - ts
    if d < 0:
        return "baru saja"
    if d < 60:
        return "baru saja"
    if d < 3600:
        return f"{int(d // 60)} mnt lalu"

    # Same-day labels — anchor to "today" calendar boundary, not just hours
    now_dt = datetime.fromtimestamp(now)
    then_dt = datetime.fromtimestamp(ts)
    days_diff = (now_dt.date() - then_dt.date()).days

    if days_diff == 0:
        # Today — describe by part-of-day
        return f"tadi {_part_of_day(then_dt.hour)}"
    if days_diff == 1:
        return f"kemarin {_part_of_day(then_dt.hour)}"
    if days_diff < 7:
        return f"{days_diff} hari lalu"
    if days_diff < 30:
        weeks = days_diff // 7
        return f"{weeks} minggu lalu"
    if days_diff < 365:
        months = days_diff // 30
        return f"{months} bulan lalu"
    years = days_diff // 365
    return f"{years} tahun lalu"


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
    return _part_of_day(datetime.now().hour)


def greeting_for_now():
    """Soft greeting matching part-of-day. Used for onboarding/empty states."""
    h = datetime.now().hour
    if 4 <= h < 11:
        return "Selamat pagi"
    if 11 <= h < 15:
        return "Selamat siang"
    if 15 <= h < 19:
        return "Selamat sore"
    return "Selamat malam"
