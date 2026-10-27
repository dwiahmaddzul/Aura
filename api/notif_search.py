"""
Aura Social — Notifications & Search Blueprint
Activity directed at user 'me':
  - AI comments on my posts
  - AI likes on my posts (likes now carry created_at; old likes fall back to
    the post's time instead of being labelled "baru" forever)
  - Recent AI DMs (where last message is from persona)
Plus a search endpoint and a health endpoint.
"""
from flask import Blueprint, jsonify, request

from api.serialize import POST_COLS, author, build_posts, me_identity
from config import SILICONFLOW_API_KEY
from db import get_db
from llm.clean import clean_ai_text
from personas import PMAP

bp = Blueprint("notif_search", __name__)


@bp.route("/api/health")
def api_health():
    """Status kunci API + rem biaya (dipakai banner peringatan di app)."""
    from ai_engine.limits import status
    has_key = bool(SILICONFLOW_API_KEY) and not SILICONFLOW_API_KEY.startswith("sk-GANTI")
    return jsonify({
        "api_key_present": has_key,
        "api_key_format_ok": has_key and SILICONFLOW_API_KEY.startswith("sk-") and len(SILICONFLOW_API_KEY) > 20,
        "ai": status(),
    })


@bp.route("/api/notifications")
def api_notifications():
    """Latest activity directed at me, newest first."""
    db = get_db()
    events = []
    comm_rows = db.execute(
        """SELECT c.id, c.username, c.content, c.created_at, c.post_id, p.content AS post_content
           FROM comments c JOIN posts p ON p.id = c.post_id
           WHERE p.username='me' AND c.username != 'me' AND c.is_ai=1
           ORDER BY c.created_at DESC LIMIT 25"""
    ).fetchall()
    for r in comm_rows:
        pers = PMAP.get(r["username"], {})
        events.append({
            "kind": "comment",
            "ts": r["created_at"] or 0,
            "username": r["username"],
            **author(r["username"], {}),
            "content": clean_ai_text(r["content"], pers, max_len=200),
            "post_id": r["post_id"],
            "post_preview": (r["post_content"] or "")[:60],
        })
    like_rows = db.execute(
        """SELECT l.username, l.post_id, l.created_at AS like_time,
                  p.content AS post_content, p.created_at AS post_time
           FROM likes l JOIN posts p ON p.id = l.post_id
           WHERE p.username='me' AND l.username != 'me'
           ORDER BY COALESCE(l.created_at, p.created_at) DESC LIMIT 20"""
    ).fetchall()
    for r in like_rows:
        events.append({
            "kind": "like",
            "ts": r["like_time"] or r["post_time"] or 0,
            "username": r["username"],
            **author(r["username"], {}),
            "post_id": r["post_id"],
            "post_preview": (r["post_content"] or "")[:60],
        })
    last_rows = db.execute(
        """SELECT persona, sender, content, MAX(created_at) AS created_at
           FROM messages GROUP BY persona"""
    ).fetchall()
    for last in last_rows:
        un = last["persona"]
        pers = PMAP.get(un)
        if pers and last["sender"] != "me":
            events.append({
                "kind": "dm",
                "ts": last["created_at"] or 0,
                "username": un,
                **author(un, {}),
                "content": clean_ai_text(last["content"], pers, max_len=200),
            })
    events.sort(key=lambda e: e["ts"], reverse=True)
    for e in events:
        e["created_at"] = e["ts"]
    return jsonify(events[:40])


@bp.route("/api/search")
def api_search():
    """Search across posts, personas, and DMs. Query param: ?q=..."""
    q = (request.args.get("q") or "").strip()[:80]
    if len(q) < 2:
        return jsonify({"posts": [], "personas": [], "dms": []})
    db = get_db()
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{esc}%"
    rows = db.execute(
        f"SELECT {POST_COLS} FROM posts WHERE content LIKE ? ESCAPE '\\' OR mood LIKE ? ESCAPE '\\' "
        "ORDER BY created_at DESC LIMIT 15",
        (like, like),
    ).fetchall()
    posts = build_posts(db, rows, with_comments=False)
    ql = q.lower()
    personas = [
        {"username": p["username"], "display": p["display"], "avatar": p["avatar"],
         "color": p["color"], "bio": p.get("bio", "")}
        for p in PMAP.values()
        if ql in p["display"].lower() or ql in p["username"].lower() or ql in p.get("bio", "").lower()
    ]
    me = me_identity(db)
    dm_rows = db.execute(
        "SELECT persona, sender, content, created_at FROM messages "
        "WHERE content LIKE ? ESCAPE '\\' ORDER BY created_at DESC LIMIT 15",
        (like,),
    ).fetchall()
    dms = [{"persona": r["persona"], **author(r["persona"], me), "sender": r["sender"],
            "content": r["content"], "created_at": r["created_at"]} for r in dm_rows]
    return jsonify({"posts": posts, "personas": personas, "dms": dms})
