"""
Aura Social — Profiles API Blueprint
Endpoints: /api/personas, /api/profile/<username>
"""
import time

from flask import Blueprint, jsonify

from db import get_db
from personas import PERSONAS, PMAP
from utils import time_ago

bp = Blueprint("profiles", __name__)


@bp.route("/api/personas")
def api_personas():
    return jsonify(
        [
            {
                "username": p["username"],
                "display": p["display"],
                "avatar": p["avatar"],
                "color": p["color"],
                "bio": p.get("bio", ""),
            }
            for p in PERSONAS
        ]
    )


@bp.route("/api/profile/<username>")
def api_profile(username):
    p = PMAP.get(username)
    if not p:
        return jsonify({"error": "not found"}), 404
    db = get_db()
    posts = db.execute(
        "SELECT * FROM posts WHERE username=? ORDER BY created_at DESC LIMIT 20",
        (username,),
    ).fetchall()
    post_list = []
    for row in posts:
        row = dict(row)
        row["has_image"] = bool(row.get("image_b64"))
        row["time_ago"] = time_ago(row["created_at"])
        row.pop("image_b64", None)
        row.pop("image_desc", None)
        post_list.append(row)
    comment_count = db.execute(
        "SELECT COUNT(*) as cnt FROM comments WHERE username=?", (username,)
    ).fetchone()["cnt"]

    # Highlights (Sorotan) — permanent, not time-limited
    highlight_rows = db.execute(
        "SELECT id, caption, created_at FROM stories "
        "WHERE username=? AND is_highlight=1 ORDER BY created_at DESC LIMIT 8",
        (username,),
    ).fetchall()
    highlight_list = [
        {
            "id": s["id"],
            "caption": s["caption"],
            "time_ago": time_ago(s["created_at"]),
        }
        for s in highlight_rows
    ]

    # Active stories (last 24h) — for story viewer trigger
    cutoff = time.time() - 86400
    story_rows = db.execute(
        "SELECT id, caption, created_at FROM stories "
        "WHERE username=? AND created_at>? ORDER BY created_at DESC",
        (username, cutoff),
    ).fetchall()
    story_list = [
        {
            "id": s["id"],
            "caption": s["caption"],
            "time_ago": time_ago(s["created_at"]),
        }
        for s in story_rows
    ]

    return jsonify(
        {
            "username": p["username"],
            "display": p["display"],
            "avatar": p["avatar"],
            "color": p["color"],
            "bio": p.get("bio", ""),
            "posts": post_list,
            "post_count": len(post_list),
            "comment_count": comment_count,
            "highlights": highlight_list,
            "stories": story_list,
        }
    )
