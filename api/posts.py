"""
Aura Social — Posts API Blueprint
Endpoints:
  GET    /api/posts                 list (?limit, ?before=<created_at>, ?mine=1, ?photos=1, ?q=, ?comments=0)
  GET    /api/posts/<id>            one post
  POST   /api/posts                 create (returns the created post)
  DELETE /api/posts/<id>            delete one of YOUR posts
  POST   /api/posts/<id>/{like,comment,bookmark}
  GET    /api/posts/<id>/image      legacy image URL (served from media files)
"""
import random
import threading
import time

from flask import Blueprint, jsonify, request

import media
import settings_rt as S
from ai_engine import limits
from ai_engine.responder import schedule_responses
from api.serialize import POST_COLS, build_posts, comment_dict, me_identity
from db import connect, get_db
from llm.generators import comment_text, describe_image
from personas import PERSONAS, PMAP
from security import MAX_COMMENT, MAX_POST, cap, image_too_big, rate_limit

bp = Blueprint("posts", __name__)


def _int_arg(name, default, lo, hi):
    try:
        return max(lo, min(hi, int(request.args.get(name, default))))
    except (TypeError, ValueError):
        return default


@bp.route("/api/posts")
def api_get_posts():
    limit = _int_arg("limit", 20, 1, 60)
    where, args = [], []
    before = request.args.get("before")
    if before:
        try:
            where.append("created_at < ?")
            args.append(float(before))
        except ValueError:
            pass
    if request.args.get("mine") == "1":
        where.append("username = 'me'")
    if request.args.get("photos") == "1":
        where.append("has_img = 1")
    q = (request.args.get("q") or "").strip()[:80]
    if q:
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("content LIKE ? ESCAPE '\\'")
        args.append(f"%{esc}%")
    sql = f"SELECT {POST_COLS} FROM posts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    db = get_db()
    rows = db.execute(sql, (*args, limit)).fetchall()
    return jsonify(build_posts(db, rows, with_comments=request.args.get("comments") != "0"))


@bp.route("/api/posts/<int:pid>")
def api_get_post(pid):
    db = get_db()
    rows = db.execute(f"SELECT {POST_COLS} FROM posts WHERE id=?", (pid,)).fetchall()
    if not rows:
        return jsonify({"error": "tidak ada"}), 404
    return jsonify(build_posts(db, rows)[0])


@bp.route("/api/posts/<int:pid>/image")
def api_image(pid):
    """URL lama, tetap dilayani (dari file WebP) supaya tab lama tidak rusak."""
    from api.media_bp import serve
    return serve("p", pid, "f")


@bp.route("/api/posts", methods=["POST"])
@rate_limit(max_calls=12, window=60)
def api_create():
    data = request.get_json(silent=True) or {}
    content = cap(data.get("content", ""), MAX_POST)
    img_b64 = data.get("image_b64") or None
    mood = data.get("mood")
    if mood not in (None, "senang", "sedih", "capek", "excited", "bingung", "tenang"):
        mood = None
    ptype = data.get("post_type")
    allow_ai = bool(data.get("allow_ai", True))
    if ptype not in ("text", "image", "gratitude"):
        ptype = None
    if not content and not img_b64:
        return jsonify({"error": "kosong"}), 400
    if image_too_big(img_b64):
        return jsonify({"error": "Gambar terlalu besar (maks ~2MB)"}), 413
    raw = media.decode_b64(img_b64) if img_b64 else None
    if img_b64 and not raw:
        return jsonify({"error": "gambar tidak valid"}), 400
    prompt_persona = data.get("prompt_persona")
    prompt_text = cap(data.get("prompt_text", ""), 200)
    final_type = ptype or ("image" if raw else "text")
    db = get_db()
    pid = db.execute(
        "INSERT INTO posts(username,content,image_b64,image_desc,post_type,mood,has_img,created_at) "
        "VALUES(?,?,NULL,NULL,?,?,?,?)",
        ("me", content, final_type, mood, 1 if raw else 0, time.time()),
    ).lastrowid
    db.commit()
    if raw:
        w, h = media.save("p", pid, raw)
        if w:
            db.execute("UPDATE posts SET img_w=?, img_h=? WHERE id=?", (w, h, pid))
        else:
            db.execute("UPDATE posts SET has_img=0 WHERE id=?", (pid,))
        db.commit()

    skip_ai = final_type == "gratitude" and not allow_ai

    def bg(pid=pid, img=raw, cap_=content, m=mood, skip=skip_ai,
           grat=(final_type == "gratitude"), pp=prompt_persona, pt=prompt_text):
        if skip:
            return  # catatan syukur dengan komentar teman dimatikan
        desc = None
        if img and S.get("describe_uploads") and S.get("vision_enabled") and limits.interactive_ok():
            desc = describe_image(img)
            if desc:
                conn = connect()
                try:
                    conn.execute("UPDATE posts SET image_desc=? WHERE id=?", (desc, pid))
                    conn.commit()
                finally:
                    conn.close()
        prefix = (f"[mood: {m}] " if m else "") + ("[catatan syukur] " if grat else "")
        prioritize = pp if (pp and PMAP.get(pp)) else None
        note = f'[user baru jawab pertanyaan kamu: "{pt}"]' if (prioritize and pt) else ""
        schedule_responses(
            pid, prefix + (cap_ or desc or "foto"), img, poster="me",
            prioritize=prioritize, note=note,
        )

    threading.Thread(target=bg, daemon=True).start()
    rows = db.execute(f"SELECT {POST_COLS} FROM posts WHERE id=?", (pid,)).fetchall()
    post = build_posts(db, rows)[0]
    return jsonify({"id": pid, "post": post}), 201


@bp.route("/api/posts/<int:pid>", methods=["DELETE"])
@rate_limit(max_calls=20, window=60)
def api_delete(pid):
    # App ini publik (gerbang depan hanya kosmetik), jadi menghapus tulisan
    # butuh sesi /kelola yang sudah login di browser yang sama.
    from api.kelola import _authed
    if not _authed():
        return jsonify({"error": "Masuk dulu ke Pengaturan (ikon gerigi di profil) untuk menghapus.",
                        "need_login": True}), 401
    db = get_db()
    row = db.execute("SELECT username FROM posts WHERE id=?", (pid,)).fetchone()
    if not row:
        return jsonify({"error": "tidak ada"}), 404
    if row["username"] != "me":
        return jsonify({"error": "cuma bisa hapus tulisanmu sendiri"}), 403
    db.execute("DELETE FROM comments WHERE post_id=?", (pid,))
    db.execute("DELETE FROM likes WHERE post_id=?", (pid,))
    db.execute("DELETE FROM bookmarks WHERE post_id=?", (pid,))
    db.execute("DELETE FROM posts WHERE id=?", (pid,))
    db.commit()
    media.delete("p", pid)
    return jsonify({"ok": True})


@bp.route("/api/posts/<int:pid>/like", methods=["POST"])
def api_like(pid):
    db = get_db()
    if not db.execute("SELECT 1 FROM posts WHERE id=?", (pid,)).fetchone():
        return jsonify({"error": "tidak ada"}), 404
    cur = db.execute(
        "INSERT OR IGNORE INTO likes(post_id,username,created_at) VALUES(?,?,?)",
        (pid, "me", time.time()),
    )
    if cur.rowcount:
        db.execute("UPDATE posts SET likes=likes+1 WHERE id=?", (pid,))
        liked = True
    else:
        db.execute("DELETE FROM likes WHERE post_id=? AND username=?", (pid, "me"))
        db.execute("UPDATE posts SET likes=MAX(0,likes-1) WHERE id=?", (pid,))
        liked = False
    db.commit()
    row = db.execute("SELECT likes FROM posts WHERE id=?", (pid,)).fetchone()
    return jsonify({"liked": liked, "likes": row["likes"]})


@bp.route("/api/posts/<int:pid>/comment", methods=["POST"])
@rate_limit(max_calls=20, window=60)
def api_comment(pid):
    data = request.get_json(silent=True) or {}
    txt = cap(data.get("text", ""), MAX_COMMENT)
    parent_id = data.get("parent_id")
    if not txt:
        return jsonify({"error": "kosong"}), 400
    db = get_db()
    if not db.execute("SELECT 1 FROM posts WHERE id=?", (pid,)).fetchone():
        return jsonify({"error": "tidak ada"}), 404
    # Normalisasi ke akar thread (balasan 1 tingkat). target_author = persona
    # pemilik akar thread, supaya balasan di thread datang dari teman yang tepat.
    root = None
    target_author = None
    if parent_id:
        prow = db.execute(
            "SELECT id, parent_id FROM comments WHERE id=? AND post_id=?", (parent_id, pid)
        ).fetchone()
        if prow:
            root = prow["parent_id"] or prow["id"]
            rootrow = db.execute(
                "SELECT username, is_ai FROM comments WHERE id=?", (root,)
            ).fetchone()
            if rootrow and rootrow["is_ai"]:
                target_author = rootrow["username"]
    my_id = db.execute(
        "INSERT INTO comments(post_id,username,content,is_ai,parent_id,created_at) "
        "VALUES(?,?,?,0,?,?)",
        (pid, "me", txt, root, time.time()),
    ).lastrowid
    db.commit()
    me = me_identity(db)
    created = comment_dict(db.execute(
        "SELECT id, post_id, username, content, is_ai, parent_id, created_at FROM comments WHERE id=?",
        (my_id,)).fetchone(), me)

    # Siapa yang membalas (kalau ada)?
    p = None
    if target_author:
        p = PMAP.get(target_author)
        if p and not S.persona(p["username"], "active"):
            p = None
        do_reply = p is not None and random.random() < S.get("thread_reply_prob")
    else:
        pool = S.active_personas() or PERSONAS
        do_reply = bool(pool) and random.random() < S.get("reply_to_user_prob")
        p = random.choice(pool) if do_reply else None

    if do_reply and p and limits.interactive_ok():
        d = random.randint(15, 55)
        # Balasan di thread → akar yang sama; balasan atas komentar baru → di bawahnya.
        reply_root = root if target_author else my_id

        def reply(p=p, d=d, pid=pid, t=txt, rr=reply_root):
            time.sleep(d)
            if not limits.interactive_ok():
                return
            conn = connect()
            try:
                row = conn.execute("SELECT content FROM posts WHERE id=?", (pid,)).fetchone()
                ctx = f'[post: {(row[0] if row else "") or "foto"}] ada yang nanggepin: "{t}"'
                r = comment_text(ctx, p, auto=False, kind="reply")
                if r:
                    conn.execute(
                        "INSERT INTO comments(post_id,username,content,is_ai,parent_id,created_at) "
                        "VALUES(?,?,?,1,?,?)",
                        (pid, p["username"], r, rr, time.time()),
                    )
                    conn.commit()
            finally:
                conn.close()

        threading.Thread(target=reply, daemon=True).start()
    return jsonify({"ok": True, "comment": created}), 201


@bp.route("/api/posts/<int:pid>/bookmark", methods=["POST"])
def api_bookmark(pid):
    """Toggle bookmark for 'me'."""
    db = get_db()
    cur = db.execute(
        "INSERT OR IGNORE INTO bookmarks(post_id,username,created_at) VALUES(?,?,?)",
        (pid, "me", time.time()),
    )
    if cur.rowcount:
        db.commit()
        return jsonify({"bookmarked": True})
    db.execute("DELETE FROM bookmarks WHERE post_id=? AND username=?", (pid, "me"))
    db.commit()
    return jsonify({"bookmarked": False})
