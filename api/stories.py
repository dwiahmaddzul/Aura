"""
Aura Social — Stories API Blueprint
Endpoints: GET /api/stories, GET /api/stories/<id>/image (legacy), POST /api/stories
"""
import time

from flask import Blueprint, jsonify, request

import media
from api.serialize import author, me_identity
from db import get_db
from personas import PMAP
from security import MAX_CAPTION, cap, image_too_big, rate_limit

bp = Blueprint("stories", __name__)


_ALL_PROMPTS = {s.strip().lower() for p in PMAP.values() for s in p.get("story_prompts", [])}


def _story_caption(row):
    """Story AI lama menyimpan prompt gambar (bahasa Inggris) sebagai caption.
    Itu bukan caption, jadi disembunyikan."""
    cap_ = (row["caption"] or "").strip()
    if row["username"] != "me" and cap_:
        low = cap_.lower()
        if low in _ALL_PROMPTS or low == (row["prompt"] or "").strip().lower():
            return ""
    return cap_


def slide(row):
    return {
        "id": row["id"],
        "caption": _story_caption(row),
        "created_at": row["created_at"],
        "is_highlight": bool(row["is_highlight"]),
        "img": media.url("s", row["id"], "f"),
        "thumb": media.url("s", row["id"], "t"),
        "img_w": row["img_w"],
        "img_h": row["img_h"],
    }


@bp.route("/api/stories")
def api_stories():
    """Story 24 jam terakhir, dikelompokkan per orang. Dalam satu orang
    urut lama → baru (diputar berurutan); orang dengan story terbaru di depan,
    'me' selalu paling depan."""
    db = get_db()
    cutoff = time.time() - 86400
    rows = db.execute(
        "SELECT id, username, caption, prompt, is_highlight, created_at, img_w, img_h "
        "FROM stories WHERE created_at>? ORDER BY created_at ASC",
        (cutoff,),
    ).fetchall()
    me = me_identity(db)
    grouped = {}
    for r in rows:
        un = r["username"]
        g = grouped.get(un)
        if g is None:
            g = grouped[un] = {"username": un, **author(un, me), "slides": [], "latest": 0}
        g["slides"].append(slide(r))
        g["latest"] = max(g["latest"], r["created_at"] or 0)
    out = sorted(grouped.values(), key=lambda g: (0 if g["username"] == "me" else 1, -g["latest"]))
    return jsonify(out)


@bp.route("/api/stories/<int:sid>/image")
def api_story_image(sid):
    from api.media_bp import serve
    return serve("s", sid, "f")


@bp.route("/api/stories", methods=["POST"])
@rate_limit(max_calls=10, window=60)
def api_story_create():
    """User uploads their own story. Body: {image_b64, caption}."""
    data = request.get_json(silent=True) or {}
    img = data.get("image_b64")
    caption = cap(data.get("caption", ""), MAX_CAPTION)
    if not img:
        return jsonify({"error": "foto wajib"}), 400
    if image_too_big(img):
        return jsonify({"error": "Gambar terlalu besar (maks ~2MB)"}), 413
    raw = media.decode_b64(img)
    if not raw:
        return jsonify({"error": "gambar tidak valid"}), 400
    db = get_db()
    sid = db.execute(
        "INSERT INTO stories(username,image_b64,caption,is_highlight,has_img,created_at) "
        "VALUES(?,NULL,?,0,1,?)",
        ("me", caption, time.time()),
    ).lastrowid
    db.commit()
    w, h = media.save("s", sid, raw)
    db.execute("UPDATE stories SET img_w=?, img_h=? WHERE id=?", (w, h, sid))
    db.commit()
    return jsonify({"id": sid}), 201
