"""
Aura Social — Notifications & Search Blueprint
Real-time aggregation of activity directed at user 'me':
  - AI comments on my posts
  - AI likes on my posts (uses likes.id as time proxy since no timestamp)
  - Recent AI DMs (where last message is from persona, unanswered)
Plus a search endpoint that hits posts, personas, DMs.
Plus a health endpoint reporting API key state.
"""
import time
from flask import Blueprint, jsonify, request

from config import SILICONFLOW_API_KEY
from db import get_db
from personas import PMAP
from utils import time_ago

bp = Blueprint("notif_search", __name__)


@bp.route("/api/health")
def api_health():
    """Report whether the SiliconFlow API key is set & looks valid.
    Frontend uses this to show an in-app warning banner so user
    knows why AI features aren't responding."""
    has_key = bool(SILICONFLOW_API_KEY) and not SILICONFLOW_API_KEY.startswith("sk-GANTI")
    # We don't actually call the API here (would slow every page load).
    # We just check the key is present and not the placeholder value.
    from config import AI_ACTIVE_WINDOW_MIN, AI_IMAGE_DAILY_LIMIT
    from ai_engine.limits import images_used_today, user_is_active
    return jsonify({
        "api_key_present": has_key,
        "api_key_format_ok": has_key and SILICONFLOW_API_KEY.startswith("sk-") and len(SILICONFLOW_API_KEY) > 20,
        "ai": {
            "images_today": images_used_today(),
            "image_daily_limit": AI_IMAGE_DAILY_LIMIT,
            "schedulers_active": user_is_active(),
            "active_window_min": AI_ACTIVE_WINDOW_MIN,
        },
    })


@bp.route("/api/notifications")
def api_notifications():
    """Return latest activity directed at me, sorted by recency."""
    db = get_db()
    events = []

    # 1. AI comments on my posts
    comm_rows = db.execute(
        """SELECT c.id, c.username, c.content, c.created_at, c.post_id, p.content AS post_content
           FROM comments c JOIN posts p ON p.id = c.post_id
           WHERE p.username='me' AND c.username != 'me' AND c.is_ai=1
           ORDER BY c.created_at DESC LIMIT 20"""
    ).fetchall()
    for r in comm_rows:
        pers = PMAP.get(r["username"], {})
        events.append({
            "kind": "comment",
            "ts": r["created_at"],
            "username": r["username"],
            "display": pers.get("display", r["username"]),
            "avatar": pers.get("avatar", "?"),
            "color": pers.get("color", "#555"),
            "content": r["content"],
            "post_id": r["post_id"],
            "post_preview": (r["post_content"] or "")[:60],
            "time_ago": time_ago(r["created_at"]),
        })

    # 2. AI likes on my posts (use likes.id as time proxy)
    like_rows = db.execute(
        """SELECT l.id, l.username, l.post_id, p.content AS post_content, p.created_at AS post_time
           FROM likes l JOIN posts p ON p.id = l.post_id
           WHERE p.username='me' AND l.username != 'me'
           ORDER BY l.id DESC LIMIT 15"""
    ).fetchall()
    for r in like_rows:
        pers = PMAP.get(r["username"], {})
        # Approximate time = post creation time + small offset; not perfect but OK
        events.append({
            "kind": "like",
            "ts": r["post_time"] + r["id"],  # rough proxy
            "username": r["username"],
            "display": pers.get("display", r["username"]),
            "avatar": pers.get("avatar", "?"),
            "color": pers.get("color", "#555"),
            "post_id": r["post_id"],
            "post_preview": (r["post_content"] or "")[:60],
            "time_ago": "baru",
        })

    # 3. Recent AI DMs where last sender is the persona (i.e. they wrote to user)
    for un, pers in PMAP.items():
        last = db.execute(
            "SELECT content, sender, created_at FROM messages WHERE persona=? "
            "ORDER BY created_at DESC LIMIT 1",
            (un,),
        ).fetchone()
        if last and last["sender"] != "me":
            events.append({
                "kind": "dm",
                "ts": last["created_at"],
                "username": un,
                "display": pers["display"],
                "avatar": pers["avatar"],
                "color": pers["color"],
                "content": last["content"],
                "time_ago": time_ago(last["created_at"]),
            })

    # Sort all events by timestamp descending, top 30
    events.sort(key=lambda e: e["ts"], reverse=True)
    return jsonify(events[:30])


@bp.route("/api/search")
def api_search():
    """Search across posts, personas, and DMs. Query param: ?q=..."""
    q = (request.args.get("q") or "").strip()
    if not q or len(q) < 2:
        return jsonify({"posts": [], "personas": [], "dms": []})
    db = get_db()
    like = f"%{q}%"

    # Posts
    post_rows = db.execute(
        "SELECT id, username, content, image_b64, mood, created_at FROM posts "
        "WHERE content LIKE ? OR mood LIKE ? ORDER BY created_at DESC LIMIT 15",
        (like, like),
    ).fetchall()
    posts = []
    for r in post_rows:
        r = dict(r)
        un = r["username"]
        if un == "me":
            me = db.execute("SELECT display_name, avatar FROM me_profile WHERE id=1").fetchone()
            r["display"] = me["display_name"] if me else "Kamu"
            r["avatar"] = me["avatar"] if me else "K"
            r["color"] = "linear-gradient(135deg,#c9aa72,#7b61ff)"
        else:
            p = PMAP.get(un, {})
            r["display"] = p.get("display", un)
            r["avatar"] = p.get("avatar", "?")
            r["color"] = p.get("color", "#555")
        r["has_image"] = bool(r.get("image_b64"))
        r["time_ago"] = time_ago(r["created_at"])
        r.pop("image_b64", None)
        posts.append(r)

    # Personas (match display, username, bio)
    personas = [
        {
            "username": p["username"],
            "display": p["display"],
            "avatar": p["avatar"],
            "color": p["color"],
            "bio": p.get("bio", ""),
        }
        for p in PMAP.values()
        if q.lower() in p["display"].lower()
        or q.lower() in p["username"].lower()
        or q.lower() in p.get("bio", "").lower()
    ]

    # DMs
    dm_rows = db.execute(
        "SELECT persona, sender, content, created_at FROM messages "
        "WHERE content LIKE ? ORDER BY created_at DESC LIMIT 15",
        (like,),
    ).fetchall()
    dms = []
    for r in dm_rows:
        p = PMAP.get(r["persona"], {})
        dms.append({
            "persona": r["persona"],
            "display": p.get("display", r["persona"]),
            "avatar": p.get("avatar", "?"),
            "color": p.get("color", "#555"),
            "sender": r["sender"],
            "content": r["content"],
            "time_ago": time_ago(r["created_at"]),
        })

    return jsonify({"posts": posts, "personas": personas, "dms": dms})
