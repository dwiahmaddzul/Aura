"""
Aura Social — Stories API Blueprint
Endpoints: GET /api/stories, GET /api/stories/<id>/image, POST /api/stories
"""
import base64
import time

from flask import Blueprint, Response, jsonify, request

from db import get_db
from personas import PMAP
from utils import time_ago

bp = Blueprint("stories", __name__)


@bp.route("/api/stories")
def api_stories():
    """Return stories from last 24h, grouped by username."""
    db = get_db()
    cutoff = time.time() - 86400
    rows = db.execute(
        "SELECT * FROM stories WHERE created_at>? ORDER BY created_at DESC",
        (cutoff,),
    ).fetchall()
    grouped = {}
    # Resolve user display dynamically (uses me_profile if 'me')
    me = db.execute("SELECT * FROM me_profile WHERE id=1").fetchone()
    me_display = me["display_name"] if me else "Kamu 👤"
    me_avatar = me["avatar"] if me else "K"
    for r in rows:
        r = dict(r)
        un = r["username"]
        if un not in grouped:
            if un == "me":
                grouped[un] = {
                    "username": un,
                    "display": me_display,
                    "avatar": me_avatar,
                    "color": "linear-gradient(135deg,#c9aa72,#7b61ff)",
                    "slides": [],
                }
            else:
                p = PMAP.get(un, {})
                grouped[un] = {
                    "username": un,
                    "display": p.get("display", un),
                    "avatar": p.get("avatar", "?"),
                    "color": p.get("color", "#555"),
                    "slides": [],
                }
        grouped[un]["slides"].append(
            {
                "id": r["id"],
                "caption": r["caption"],
                "time_ago": time_ago(r["created_at"]),
            }
        )
    # Put 'me' first if present
    out = list(grouped.values())
    out.sort(key=lambda x: 0 if x["username"] == "me" else 1)
    return jsonify(out)


@bp.route("/api/stories/<int:sid>/image")
def api_story_image(sid):
    row = get_db().execute(
        "SELECT image_b64 FROM stories WHERE id=?", (sid,)
    ).fetchone()
    if not row or not row["image_b64"]:
        return "", 404
    return Response(base64.b64decode(row["image_b64"]), mimetype="image/png")


@bp.route("/api/stories", methods=["POST"])
def api_story_create():
    """User uploads their own story. Body: {image_b64, caption}."""
    data = request.get_json() or {}
    img = data.get("image_b64")
    caption = (data.get("caption") or "").strip()[:200]
    if not img:
        return jsonify({"error": "foto wajib"}), 400
    db = get_db()
    sid = db.execute(
        "INSERT INTO stories(username,image_b64,caption,is_highlight,created_at) "
        "VALUES(?,?,?,?,?)",
        ("me", img, caption, 0, time.time()),
    ).lastrowid
    db.commit()
    return jsonify({"id": sid}), 201
