"""
Aura Social — Profiles API Blueprint
Endpoints: /api/personas, /api/profile/<username>
"""
import time

from flask import Blueprint, jsonify

import settings_rt as S
from api.serialize import POST_COLS, build_posts
from api.stories import slide
from db import get_db
from personas import PERSONAS, PMAP

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
                "active": S.persona(p["username"], "active"),
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
    rows = db.execute(
        f"SELECT {POST_COLS} FROM posts WHERE username=? ORDER BY created_at DESC LIMIT 30",
        (username,),
    ).fetchall()
    post_count = db.execute(
        "SELECT COUNT(*) AS n FROM posts WHERE username=?", (username,)
    ).fetchone()["n"]
    comment_count = db.execute(
        "SELECT COUNT(*) AS n FROM comments WHERE username=?", (username,)
    ).fetchone()["n"]
    cols = "id, username, caption, prompt, is_highlight, created_at, img_w, img_h"
    highlights = db.execute(
        f"SELECT {cols} FROM stories WHERE username=? AND is_highlight=1 "
        "ORDER BY created_at DESC LIMIT 12",
        (username,),
    ).fetchall()
    stories = db.execute(
        f"SELECT {cols} FROM stories WHERE username=? AND created_at>? ORDER BY created_at ASC",
        (username, time.time() - 86400),
    ).fetchall()
    return jsonify(
        {
            "username": p["username"],
            "display": p["display"],
            "avatar": p["avatar"],
            "color": p["color"],
            "bio": p.get("bio", ""),
            "posts": build_posts(db, rows, with_comments=False),
            "post_count": post_count,
            "comment_count": comment_count,
            "highlights": [slide(s) for s in highlights],
            "stories": [slide(s) for s in stories],
        }
    )
