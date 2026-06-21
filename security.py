"""
Aura Social — Security helpers
Server-side input caps + lightweight in-process per-IP rate limiting.

The client also enforces limits (maxlength, image resize), but the server must
never trust the client — these routes are publicly reachable on the live demo.
"""
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request

# ── input caps ──
MAX_POST = 2000        # chars
MAX_COMMENT = 600
MAX_DM = 1000
MAX_CAPTION = 200
MAX_AVATAR = 4
MAX_NAME = 40
MAX_BIO = 200
MAX_IMAGE_B64 = 2_800_000  # base64 chars ≈ 2.1 MB binary (client resizes to ~1080px)


def cap(text, limit):
    """Trim + clamp user text to a hard limit."""
    return (text or "").strip()[:limit]


def image_too_big(b64):
    """True if a base64 image payload exceeds the size cap."""
    return bool(b64) and len(b64) > MAX_IMAGE_B64


# ── per-IP sliding-window rate limit (single-process app) ──
_hits = defaultdict(deque)
_last_prune = [0.0]


def _client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit(max_calls=20, window=60):
    """Decorator: allow `max_calls` per `window` seconds per client IP.

    Designed for write endpoints on the public demo. Returns HTTP 429 when
    exceeded. Behind a PaaS proxy, honours X-Forwarded-For.
    """
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            now = time.time()
            ip = _client_ip()
            dq = _hits[ip]
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= max_calls:
                retry = int(window - (now - dq[0])) + 1
                return jsonify({"error": "Terlalu cepat, coba lagi sebentar.", "retry_after": retry}), 429
            dq.append(now)
            # Opportunistic prune of empty buckets (keeps memory bounded)
            if now - _last_prune[0] > 300:
                _last_prune[0] = now
                for k in [k for k, v in list(_hits.items()) if not v]:
                    _hits.pop(k, None)
            return fn(*args, **kwargs)
        return wrapped
    return deco
