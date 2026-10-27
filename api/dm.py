"""
Aura Social — DM (Direct Message) Blueprint
1-on-1 chat threads with each AI persona. Threaded memory.
Endpoints:
  GET  /api/dm                  — list of threads (one per persona)
  GET  /api/dm/<persona>        — message history (?since=<created_at> → only newer)
  POST /api/dm/<persona>        — send a message; AI replies async (if allowed)
"""
import random
import threading
import time

from flask import Blueprint, jsonify, request

import settings_rt as S
from ai_engine import limits
from db import connect, get_db
from llm.clean import clean_ai_text
from llm.generators import dm_reply
from personas import PERSONAS, PMAP, is_online
from security import MAX_DM, cap, rate_limit

bp = Blueprint("dm", __name__)


def _msg(r, persona):
    is_me = r["sender"] == "me"
    return {
        "id": r["id"],
        "sender": r["sender"],
        "content": r["content"] if is_me else clean_ai_text(r["content"], persona, max_len=600),
        "created_at": r["created_at"],
        "is_me": is_me,
    }


@bp.route("/api/dm")
def api_dm_list():
    """Daftar thread + pesan terakhir (1 query, dulu 6)."""
    db = get_db()
    last = {r["persona"]: r for r in db.execute(
        "SELECT persona, sender, content, MAX(created_at) AS created_at FROM messages GROUP BY persona"
    ).fetchall()}
    out = []
    for p in PERSONAS:
        l = last.get(p["username"])
        out.append({
            "username": p["username"],
            "display": p["display"],
            "avatar": p["avatar"],
            "color": p["color"],
            "online": is_online(p["username"]),
            "last_message": (l["content"] if l["sender"] == "me"
                             else clean_ai_text(l["content"], p, max_len=200)) if l else None,
            "last_sender": l["sender"] if l else None,
            "last_at": l["created_at"] if l else None,
            "has_thread": bool(l),
        })
    out.sort(key=lambda x: (0 if x["has_thread"] else 1, -(x["last_at"] or 0), x["display"]))
    return jsonify(out)


@bp.route("/api/dm/<persona>")
def api_dm_thread(persona):
    p = PMAP.get(persona)
    if not p:
        return jsonify({"error": "not found"}), 404
    db = get_db()
    since = request.args.get("since")
    if since:
        try:
            rows = db.execute(
                "SELECT id, sender, content, created_at FROM messages WHERE persona=? AND created_at>? "
                "ORDER BY created_at ASC LIMIT 200",
                (persona, float(since)),
            ).fetchall()
        except ValueError:
            rows = []
    else:
        rows = db.execute(
            "SELECT * FROM (SELECT id, sender, content, created_at FROM messages WHERE persona=? "
            "ORDER BY created_at DESC LIMIT 200) ORDER BY created_at ASC",
            (persona,),
        ).fetchall()
    return jsonify({
        "persona": {
            "username": p["username"], "display": p["display"], "avatar": p["avatar"],
            "color": p["color"], "bio": p.get("bio", ""), "online": is_online(p["username"]),
        },
        "messages": [_msg(r, p) for r in rows],
    })


@bp.route("/api/dm/<persona>", methods=["POST"])
@rate_limit(max_calls=20, window=60)
def api_dm_send(persona):
    """Kirim pesan dari 'me'. Balasan AI di thread latar (kalau rem mengizinkan)."""
    p = PMAP.get(persona)
    if not p:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    txt = cap(data.get("content", ""), MAX_DM)
    if not txt:
        return jsonify({"error": "kosong"}), 400
    db = get_db()
    now = time.time()
    mid = db.execute(
        "INSERT INTO messages(persona,sender,content,created_at) VALUES(?,?,?,?)",
        (persona, "me", txt, now),
    ).lastrowid
    db.commit()

    will_reply = S.get("dm_enabled") and limits.interactive_ok() and S.persona(persona, "active")

    def _reply(pers=p, persona_un=persona):
        time.sleep(random.randint(3, 15))
        if not limits.interactive_ok():
            return
        conn = connect()
        try:
            rows = conn.execute(
                "SELECT sender, content FROM messages WHERE persona=? ORDER BY created_at DESC LIMIT 12",
                (persona_un,),
            ).fetchall()
            history = [{"sender": r[0], "content": r[1]} for r in reversed(rows)]
            reply = dm_reply(pers, history)
            if reply:
                conn.execute(
                    "INSERT INTO messages(persona,sender,content,created_at) VALUES(?,?,?,?)",
                    (persona_un, persona_un, reply, time.time()),
                )
                conn.commit()
                print(f"[DM:{persona_un}] {reply[:50]}")
        finally:
            conn.close()

    if will_reply:
        threading.Thread(target=_reply, daemon=True).start()
    return jsonify({"ok": True, "id": mid, "created_at": now, "will_reply": bool(will_reply)}), 201
