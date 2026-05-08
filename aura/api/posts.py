"""
Aura Social — Posts API Blueprint
Endpoints: /api/posts (list/create), /api/posts/<id>/{image,like,comment}
"""
import base64
import random
import sqlite3
import threading
import time

from flask import Blueprint, Response, jsonify, request

from config import DB_PATH
from db import get_db
from personas import PERSONAS, PMAP
from utils import time_ago
from llm.generators import comment_text, describe_image
from ai_engine.responder import schedule_responses

bp = Blueprint("posts", __name__)


@bp.route("/api/posts")
def api_get_posts():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM posts ORDER BY created_at DESC LIMIT 30"
    ).fetchall()
    # Bookmarks set for 'me'
    bm_rows = db.execute(
        "SELECT post_id FROM bookmarks WHERE username='me'"
    ).fetchall()
    bookmarked_ids = {r["post_id"] for r in bm_rows}
    # Liked set for 'me'
    lk_rows = db.execute("SELECT post_id FROM likes WHERE username='me'").fetchall()
    liked_ids = {r["post_id"] for r in lk_rows}
    # Editable profile for 'me'
    me = db.execute("SELECT * FROM me_profile WHERE id=1").fetchone()
    me_display = me["display_name"] if me else "Kamu 👤"
    me_avatar = me["avatar"] if me else "K"

    out = []
    for p in rows:
        p = dict(p)
        comms = db.execute(
            "SELECT * FROM comments WHERE post_id=? ORDER BY created_at",
            (p["id"],),
        ).fetchall()
        p["comments"] = []
        for c in comms:
            c = dict(c)
            if c["username"] == "me":
                c["display"] = me_display
                c["avatar"] = me_avatar
                c["color"] = "linear-gradient(135deg,#c9aa72,#7b61ff)"
            else:
                pers = PMAP.get(c["username"], {})
                c["display"] = pers.get("display", c["username"])
                c["avatar"] = pers.get("avatar", c["username"][0].upper())
                c["color"] = pers.get(
                    "color", "linear-gradient(135deg,#555,#777)"
                )
            c["time_ago"] = time_ago(c["created_at"])
            p["comments"].append(c)
        p["comment_count"] = len(p["comments"])
        if p["username"] == "me":
            p["display"] = me_display
            p["avatar"] = me_avatar
            p["color"] = "linear-gradient(135deg,#c9aa72,#7b61ff)"
        else:
            pers = PMAP.get(p["username"], {})
            p["display"] = pers.get("display", p["username"])
            p["avatar"] = pers.get("avatar", "?")
            p["color"] = pers.get("color", "#555")
        p["time_ago"] = time_ago(p["created_at"])
        p["has_image"] = bool(p.get("image_b64"))
        p["bookmarked"] = p["id"] in bookmarked_ids
        p["is_liked"] = p["id"] in liked_ids
        # Resolve repost reference
        if p.get("repost_of"):
            orig = db.execute(
                "SELECT id, username, content, image_b64, mood, created_at "
                "FROM posts WHERE id=?",
                (p["repost_of"],),
            ).fetchone()
            if orig:
                orig = dict(orig)
                if orig["username"] == "me":
                    orig["display"] = me_display
                    orig["avatar"] = me_avatar
                    orig["color"] = "linear-gradient(135deg,#c9aa72,#7b61ff)"
                else:
                    op = PMAP.get(orig["username"], {})
                    orig["display"] = op.get("display", orig["username"])
                    orig["avatar"] = op.get("avatar", "?")
                    orig["color"] = op.get("color", "#555")
                orig["has_image"] = bool(orig.get("image_b64"))
                orig["time_ago"] = time_ago(orig["created_at"])
                orig.pop("image_b64", None)
                p["original"] = orig
        # Don't send image_desc or raw image_b64 to frontend
        p.pop("image_desc", None)
        p.pop("image_b64", None)
        out.append(p)
    return jsonify(out)


@bp.route("/api/posts/<int:pid>/image")
def api_image(pid):
    row = get_db().execute(
        "SELECT image_b64 FROM posts WHERE id=?", (pid,)
    ).fetchone()
    if not row or not row["image_b64"]:
        return "", 404
    return Response(base64.b64decode(row["image_b64"]), mimetype="image/jpeg")


@bp.route("/api/posts", methods=["POST"])
def api_create():
    data = request.get_json() or {}
    content = data.get("content", "").strip()
    img = data.get("image_b64")
    mood = data.get("mood")  # optional: senang/sedih/capek/excited/bingung/tenang
    if not content and not img:
        return jsonify({"error": "kosong"}), 400
    db = get_db()
    pid = db.execute(
        "INSERT INTO posts(username,content,image_b64,image_desc,post_type,mood,created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (
            "me",
            content,
            img,
            None,
            "image" if img else "text",
            mood,
            time.time(),
        ),
    ).lastrowid
    db.commit()

    def bg(pid=pid, i=img, cap=content, m=mood):
        desc = None
        if i:
            desc = describe_image(i)
            if desc:
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "UPDATE posts SET image_desc=? WHERE id=?", (desc, pid)
                )
                conn.commit()
                conn.close()
        # Inject mood marker so AI personas can react with empathy
        mood_prefix = f"[mood: {m}] " if m else ""
        schedule_responses(pid, mood_prefix + (cap or desc or "foto"), i, poster="me")

    threading.Thread(target=bg, daemon=True).start()
    return jsonify({"id": pid}), 201


@bp.route("/api/posts/<int:pid>/like", methods=["POST"])
def api_like(pid):
    db = get_db()
    try:
        db.execute(
            "INSERT INTO likes(post_id,username) VALUES(?,?)", (pid, "me")
        )
        db.execute("UPDATE posts SET likes=likes+1 WHERE id=?", (pid,))
        db.commit()
        liked = True
    except sqlite3.IntegrityError:
        db.execute(
            "DELETE FROM likes WHERE post_id=? AND username=?", (pid, "me")
        )
        db.execute(
            "UPDATE posts SET likes=MAX(0,likes-1) WHERE id=?", (pid,)
        )
        db.commit()
        liked = False
    row = db.execute("SELECT likes FROM posts WHERE id=?", (pid,)).fetchone()
    return jsonify({"liked": liked, "likes": row["likes"]})


@bp.route("/api/posts/<int:pid>/comment", methods=["POST"])
def api_comment(pid):
    data = request.get_json() or {}
    txt = data.get("text", "").strip()
    if not txt:
        return jsonify({"error": "kosong"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO comments(post_id,username,content,is_ai,created_at) "
        "VALUES(?,?,?,0,?)",
        (pid, "me", txt, time.time()),
    )
    db.commit()
    # 40% chance one AI replies to user's comment
    if random.random() < 0.40:
        p = random.choice(PERSONAS)
        d = random.randint(15, 55)

        def reply(p=p, d=d, pid=pid, t=txt):
            time.sleep(d)
            row = sqlite3.connect(DB_PATH).execute(
                "SELECT content FROM posts WHERE id=?", (pid,)
            ).fetchone()
            ctx = f"[post: {row[0] or 'foto'}] ada komentar: \"{t}\""
            r = comment_text(ctx, p)
            if r:
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "INSERT INTO comments(post_id,username,content,is_ai,created_at) "
                    "VALUES(?,?,?,1,?)",
                    (pid, p["username"], r, time.time()),
                )
                conn.commit()
                conn.close()

        threading.Thread(target=reply, daemon=True).start()
    return jsonify({"ok": True}), 201


@bp.route("/api/posts/<int:pid>/bookmark", methods=["POST"])
def api_bookmark(pid):
    """Toggle bookmark for 'me'."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO bookmarks(post_id,username,created_at) VALUES(?,?,?)",
            (pid, "me", time.time()),
        )
        db.commit()
        return jsonify({"bookmarked": True})
    except sqlite3.IntegrityError:
        db.execute(
            "DELETE FROM bookmarks WHERE post_id=? AND username=?", (pid, "me")
        )
        db.commit()
        return jsonify({"bookmarked": False})


@bp.route("/api/posts/<int:pid>/repost", methods=["POST"])
def api_repost(pid):
    """Quote-style repost: creates a new post referencing the original."""
    data = request.get_json() or {}
    extra = (data.get("content") or "").strip()
    db = get_db()
    orig = db.execute("SELECT id FROM posts WHERE id=?", (pid,)).fetchone()
    if not orig:
        return jsonify({"error": "post not found"}), 404
    new_id = db.execute(
        "INSERT INTO posts(username,content,image_b64,image_desc,post_type,repost_of,created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        ("me", extra, None, None, "repost", pid, time.time()),
    ).lastrowid
    db.commit()

    def bg(pid=new_id, ctx=extra):
        schedule_responses(pid, ctx or "repost dari post lain", None, poster="me")

    threading.Thread(target=bg, daemon=True).start()
    return jsonify({"id": new_id}), 201
