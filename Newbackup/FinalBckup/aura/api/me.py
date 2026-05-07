"""
Aura Social — Me (User) Blueprint
User-centric endpoints: profile edit, throwback, streak, mood timeline,
liked posts, bookmarks, daily check-in prompt.
"""
import random
import time
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from db import get_db
from personas import PERSONAS, PMAP
from utils import time_ago

bp = Blueprint("me", __name__)


# ── PROFILE: GET / UPDATE ─────────────────────────────────────────────────
@bp.route("/api/me/profile")
def api_me_profile():
    db = get_db()
    row = db.execute("SELECT * FROM me_profile WHERE id=1").fetchone()
    if not row:
        return jsonify({"display_name": "Kamu 👤", "bio": "", "avatar": "K"})
    return jsonify(
        {
            "display_name": row["display_name"],
            "bio": row["bio"],
            "avatar": row["avatar"],
        }
    )


@bp.route("/api/me/profile", methods=["POST"])
def api_me_profile_update():
    data = request.get_json() or {}
    name = (data.get("display_name") or "").strip()[:40]
    bio = (data.get("bio") or "").strip()[:200]
    avatar = (data.get("avatar") or "").strip()[:4] or "K"
    if not name:
        return jsonify({"error": "nama kosong"}), 400
    db = get_db()
    db.execute(
        "UPDATE me_profile SET display_name=?, bio=?, avatar=? WHERE id=1",
        (name, bio, avatar),
    )
    db.commit()
    return jsonify({"ok": True})


# ── DAILY CHECK-IN PROMPT ─────────────────────────────────────────────────
@bp.route("/api/me/daily-prompt")
def api_daily_prompt():
    """Return a check-in prompt if user hasn't posted in last 12h, else null."""
    db = get_db()
    cutoff = time.time() - 12 * 3600
    recent = db.execute(
        "SELECT id FROM posts WHERE username='me' AND created_at>? LIMIT 1",
        (cutoff,),
    ).fetchone()
    if recent:
        return jsonify({"prompt": None})
    # Pick random persona that has daily_prompts
    candidates = [p for p in PERSONAS if p.get("daily_prompts")]
    if not candidates:
        return jsonify({"prompt": None})
    p = random.choice(candidates)
    prompt_text = random.choice(p["daily_prompts"])
    return jsonify(
        {
            "prompt": {
                "text": prompt_text,
                "persona": {
                    "username": p["username"],
                    "display": p["display"],
                    "avatar": p["avatar"],
                    "color": p["color"],
                },
            }
        }
    )


# ── ON THIS DAY (THROWBACK) ───────────────────────────────────────────────
@bp.route("/api/me/throwback")
def api_throwback():
    """Return a 'me' post from ~7/14/30/90/365 days ago, if exists."""
    db = get_db()
    now = time.time()
    candidates = []
    for days in [7, 14, 30, 90, 365]:
        target = now - days * 86400
        # Window: ±12h
        rows = db.execute(
            "SELECT id, content, mood, image_b64, created_at FROM posts "
            "WHERE username='me' AND created_at BETWEEN ? AND ? LIMIT 5",
            (target - 12 * 3600, target + 12 * 3600),
        ).fetchall()
        for r in rows:
            candidates.append({"days_ago": days, "row": r})
    if not candidates:
        return jsonify({"throwback": None})
    pick = random.choice(candidates)
    r = pick["row"]
    return jsonify(
        {
            "throwback": {
                "id": r["id"],
                "content": r["content"],
                "mood": r["mood"],
                "has_image": bool(r["image_b64"]),
                "days_ago": pick["days_ago"],
                "label": _days_label(pick["days_ago"]),
            }
        }
    )


def _days_label(days):
    if days == 7:
        return "1 minggu lalu"
    if days == 14:
        return "2 minggu lalu"
    if days == 30:
        return "1 bulan lalu"
    if days == 90:
        return "3 bulan lalu"
    if days == 365:
        return "1 tahun lalu"
    return f"{days} hari lalu"


# ── STREAK ────────────────────────────────────────────────────────────────
@bp.route("/api/me/streak")
def api_streak():
    """Compute current consecutive-day posting streak for 'me'."""
    db = get_db()
    rows = db.execute(
        "SELECT created_at FROM posts WHERE username='me' ORDER BY created_at DESC"
    ).fetchall()
    if not rows:
        return jsonify({"current": 0, "total_posts": 0})
    # Build set of unique date strings (YYYY-MM-DD) when user posted
    date_set = set()
    for r in rows:
        d = datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d")
        date_set.add(d)
    today = datetime.now().date()
    current = 0
    cursor = today
    # Allow today OR yesterday as starting anchor (haven't posted today yet)
    if cursor.strftime("%Y-%m-%d") not in date_set:
        cursor = cursor - timedelta(days=1)
        if cursor.strftime("%Y-%m-%d") not in date_set:
            return jsonify({"current": 0, "total_posts": len(rows)})
    while cursor.strftime("%Y-%m-%d") in date_set:
        current += 1
        cursor = cursor - timedelta(days=1)
    return jsonify({"current": current, "total_posts": len(rows)})


# ── MOOD TIMELINE (last 30 days) ──────────────────────────────────────────
@bp.route("/api/me/mood-timeline")
def api_mood_timeline():
    """Return last 30 days of mood data — one entry per day."""
    db = get_db()
    cutoff = time.time() - 30 * 86400
    rows = db.execute(
        "SELECT mood, created_at FROM posts WHERE username='me' AND mood IS NOT NULL "
        "AND created_at>? ORDER BY created_at ASC",
        (cutoff,),
    ).fetchall()
    # Bucket by day: pick most recent mood that day
    by_day = {}
    for r in rows:
        d = datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d")
        by_day[d] = r["mood"]  # later overwrites earlier — keeps latest of day
    # Build 30-day array (oldest → newest)
    today = datetime.now().date()
    out = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        out.append({"date": ds, "mood": by_day.get(ds), "label": d.strftime("%d/%m")})
    return jsonify(out)


# ── LIKED POSTS ───────────────────────────────────────────────────────────
@bp.route("/api/me/liked")
def api_liked():
    """Posts user has liked — joined with post data."""
    db = get_db()
    rows = db.execute(
        """SELECT p.id, p.username, p.content, p.image_b64, p.mood, p.created_at, p.likes
           FROM likes l JOIN posts p ON p.id = l.post_id
           WHERE l.username = 'me' ORDER BY l.id DESC LIMIT 30"""
    ).fetchall()
    out = []
    for r in rows:
        r = dict(r)
        un = r["username"]
        if un == "me":
            r["display"] = "Kamu 👤"
            r["avatar"] = "K"
            r["color"] = "linear-gradient(135deg,#c9aa72,#7b61ff)"
        else:
            pers = PMAP.get(un, {})
            r["display"] = pers.get("display", un)
            r["avatar"] = pers.get("avatar", "?")
            r["color"] = pers.get("color", "#555")
        r["has_image"] = bool(r.get("image_b64"))
        r["time_ago"] = time_ago(r["created_at"])
        r.pop("image_b64", None)
        out.append(r)
    return jsonify(out)


# ── BOOKMARKS ─────────────────────────────────────────────────────────────
@bp.route("/api/me/bookmarks")
def api_bookmarks():
    db = get_db()
    rows = db.execute(
        """SELECT p.id, p.username, p.content, p.image_b64, p.mood, p.created_at, p.likes
           FROM bookmarks b JOIN posts p ON p.id = b.post_id
           WHERE b.username = 'me' ORDER BY b.id DESC LIMIT 30"""
    ).fetchall()
    out = []
    for r in rows:
        r = dict(r)
        un = r["username"]
        if un == "me":
            r["display"] = "Kamu 👤"
            r["avatar"] = "K"
            r["color"] = "linear-gradient(135deg,#c9aa72,#7b61ff)"
        else:
            pers = PMAP.get(un, {})
            r["display"] = pers.get("display", un)
            r["avatar"] = pers.get("avatar", "?")
            r["color"] = pers.get("color", "#555")
        r["has_image"] = bool(r.get("image_b64"))
        r["time_ago"] = time_ago(r["created_at"])
        r.pop("image_b64", None)
        out.append(r)
    return jsonify(out)
