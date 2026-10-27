"""
Aura Social — Me (User) Blueprint
User-centric endpoints: profile edit, stats, throwback, streak, mood timeline,
liked posts, bookmarks, daily check-in prompt, onboarding state.
All calendar math runs in the app's local time zone (utils.local_tz).
"""
import hashlib
import time
from datetime import timedelta

from flask import Blueprint, jsonify, request

import settings_rt as S
from api.serialize import POST_COLS, build_posts
from db import get_db
from personas import PERSONAS
from utils import greeting_for_now, local_day, now_local, part_of_day_now, to_local

bp = Blueprint("me", __name__)


# ── PROFILE: GET / UPDATE ─────────────────────────────────────────────────
@bp.route("/api/me/profile")
def api_me_profile():
    db = get_db()
    row = db.execute("SELECT * FROM me_profile WHERE id=1").fetchone()
    posts_count = db.execute(
        "SELECT COUNT(*) AS n FROM posts WHERE username='me'"
    ).fetchone()["n"]
    base = {
        "is_first_time": posts_count == 0,
        "greeting": greeting_for_now(),
        "part_of_day": part_of_day_now(),
    }
    if not row:
        return jsonify({"display_name": "Kamu 👤", "bio": "", "avatar": "K", **base})
    return jsonify({"display_name": row["display_name"], "bio": row["bio"],
                    "avatar": row["avatar"], **base})


@bp.route("/api/me/profile", methods=["POST"])
def api_me_profile_update():
    data = request.get_json(silent=True) or {}
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


# ── STATS (profil + jurnal) ───────────────────────────────────────────────
@bp.route("/api/me/stats")
def api_me_stats():
    db = get_db()
    now = now_local()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
    r = db.execute(
        "SELECT COUNT(*) n, SUM(has_img=1) photos, MIN(created_at) first, "
        "SUM(created_at>=?) this_month FROM posts WHERE username='me'",
        (month_start,),
    ).fetchone()
    return jsonify({
        "entries": r["n"] or 0,
        "photos": r["photos"] or 0,
        "this_month": r["this_month"] or 0,
        "first_entry_at": r["first"],
    })


# ── DAILY CHECK-IN PROMPT ─────────────────────────────────────────────────
@bp.route("/api/me/daily-prompt")
def api_daily_prompt():
    """Pertanyaan check-in kalau belum menulis 12 jam terakhir.
    Pilihannya tetap sepanjang hari (dulu berganti tiap kali dimuat)."""
    db = get_db()
    recent = db.execute(
        "SELECT id FROM posts WHERE username='me' AND created_at>? LIMIT 1",
        (time.time() - 12 * 3600,),
    ).fetchone()
    if recent:
        return jsonify({"prompt": None})
    candidates = [p for p in S.active_personas() if p.get("daily_prompts")] or \
                 [p for p in PERSONAS if p.get("daily_prompts")]
    if not candidates:
        return jsonify({"prompt": None})
    day = local_day()
    h = int(hashlib.md5(day.encode()).hexdigest(), 16)
    p = candidates[h % len(candidates)]
    prompt_text = p["daily_prompts"][(h // 7) % len(p["daily_prompts"])]
    return jsonify({
        "prompt": {
            "day": day,
            "text": prompt_text,
            "persona": {"username": p["username"], "display": p["display"],
                        "avatar": p["avatar"], "color": p["color"]},
        }
    })


# ── ON THIS DAY (THROWBACK) ───────────────────────────────────────────────
@bp.route("/api/me/throwback")
def api_throwback():
    """Satu tulisanmu dari ~7/14/30/90/365 hari lalu, kalau ada (tetap per hari)."""
    db = get_db()
    now = time.time()
    candidates = []
    for days in [7, 14, 30, 90, 365]:
        target = now - days * 86400
        rows = db.execute(
            "SELECT id, content, mood, has_img, created_at FROM posts "
            "WHERE username='me' AND created_at BETWEEN ? AND ? ORDER BY id LIMIT 5",
            (target - 12 * 3600, target + 12 * 3600),
        ).fetchall()
        candidates += [{"days_ago": days, "row": r} for r in rows]
    if not candidates:
        return jsonify({"throwback": None})
    h = int(hashlib.md5(local_day().encode()).hexdigest(), 16)
    pick = candidates[h % len(candidates)]
    r = pick["row"]
    return jsonify({
        "throwback": {
            "id": r["id"],
            "content": r["content"],
            "mood": r["mood"],
            "has_image": bool(r["has_img"]),
            "days_ago": pick["days_ago"],
            "label": _days_label(pick["days_ago"]),
        }
    })


def _days_label(days):
    return {7: "1 minggu lalu", 14: "2 minggu lalu", 30: "1 bulan lalu",
            90: "3 bulan lalu", 365: "1 tahun lalu"}.get(days, f"{days} hari lalu")


# ── STREAK (tidak ditampilkan di UI, dipertahankan untuk kompatibilitas) ──
@bp.route("/api/me/streak")
def api_streak():
    db = get_db()
    rows = db.execute(
        "SELECT created_at FROM posts WHERE username='me' ORDER BY created_at DESC"
    ).fetchall()
    if not rows:
        return jsonify({"current": 0, "total_posts": 0})
    dates = {to_local(r["created_at"]).date() for r in rows}
    cursor = now_local().date()
    if cursor not in dates:
        cursor -= timedelta(days=1)
        if cursor not in dates:
            return jsonify({"current": 0, "total_posts": len(rows)})
    current = 0
    while cursor in dates:
        current += 1
        cursor -= timedelta(days=1)
    return jsonify({"current": current, "total_posts": len(rows)})


# ── MOOD TIMELINE (30 hari terakhir) ──────────────────────────────────────
@bp.route("/api/me/mood-timeline")
def api_mood_timeline():
    db = get_db()
    rows = db.execute(
        "SELECT mood, created_at FROM posts WHERE username='me' AND mood IS NOT NULL "
        "AND created_at>? ORDER BY created_at ASC",
        (time.time() - 31 * 86400,),
    ).fetchall()
    by_day = {}
    for r in rows:
        by_day[to_local(r["created_at"]).strftime("%Y-%m-%d")] = r["mood"]
    today = now_local().date()
    out = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        out.append({"date": ds, "mood": by_day.get(ds), "label": d.strftime("%d/%m")})
    return jsonify(out)


# ── LIKED / BOOKMARKS ─────────────────────────────────────────────────────
def _joined(table):
    db = get_db()
    cols = ", ".join(f"p.{c.strip()}" for c in POST_COLS.split(","))
    rows = db.execute(
        f"SELECT {cols} FROM {table} x JOIN posts p ON p.id = x.post_id "
        "WHERE x.username = 'me' ORDER BY x.id DESC LIMIT 40"
    ).fetchall()
    return jsonify(build_posts(db, rows, with_comments=False))


@bp.route("/api/me/liked")
def api_liked():
    return _joined("likes")


@bp.route("/api/me/bookmarks")
def api_bookmarks():
    return _joined("bookmarks")
