"""
Aura Social — Utility Helpers
"""
import time


def time_ago(ts):
    """Convert timestamp to Indonesian relative time string."""
    d = time.time() - ts
    if d < 60:
        return f"{int(d)}d lalu"
    if d < 3600:
        return f"{int(d // 60)} mnt lalu"
    if d < 86400:
        return f"{int(d // 3600)} jam lalu"
    return f"{int(d // 86400)} hari lalu"
