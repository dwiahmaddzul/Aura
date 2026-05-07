"""
Aura Social — DM (Direct Message) Blueprint
1-on-1 chat threads with each AI persona. Threaded memory.
Endpoints:
  GET  /api/dm                  — list of threads (one per persona)
  GET  /api/dm/<persona>        — full message history of one thread
  POST /api/dm/<persona>        — send a message; AI replies async
"""
import random
import sqlite3
import threading
import time

from flask import Blueprint, jsonify, request

from config import DB_PATH
from db import get_db
from personas import PERSONAS, PMAP, is_online
from utils import time_ago
from llm.generators import dm_reply

bp = Blueprint("dm", __name__)


@bp.route("/api/dm")
def api_dm_list():
    """Return list of all personas with last DM preview + unread proxy."""
    db = get_db()
    out = []
    for p in PERSONAS:
        last = db.execute(
            "SELECT sender, content, created_at FROM messages WHERE persona=? "
            "ORDER BY created_at DESC LIMIT 1",
            (p["username"],),
        ).fetchone()
        out.append(
            {
                "username": p["username"],
                "display": p["display"],
                "avatar": p["avatar"],
                "color": p["color"],
                "online": is_online(p["username"]),
                "last_message": last["content"] if last else None,
                "last_sender": last["sender"] if last else None,
                "last_time": time_ago(last["created_at"]) if last else None,
                "has_thread": bool(last),
            }
        )
    # Sort: with-thread first (by recency), then untouched
    out.sort(key=lambda x: (-1 if x["has_thread"] else 0, x["display"]))
    return jsonify(out)


@bp.route("/api/dm/<persona>")
def api_dm_thread(persona):
    """Return full message history for a persona thread."""
    p = PMAP.get(persona)
    if not p:
        return jsonify({"error": "not found"}), 404
    db = get_db()
    rows = db.execute(
        "SELECT sender, content, created_at FROM messages WHERE persona=? "
        "ORDER BY created_at ASC LIMIT 200",
        (persona,),
    ).fetchall()
    msgs = [
        {
            "sender": r["sender"],
            "content": r["content"],
            "time_ago": time_ago(r["created_at"]),
            "is_me": r["sender"] == "me",
        }
        for r in rows
    ]
    return jsonify(
        {
            "persona": {
                "username": p["username"],
                "display": p["display"],
                "avatar": p["avatar"],
                "color": p["color"],
                "bio": p.get("bio", ""),
                "online": is_online(p["username"]),
            },
            "messages": msgs,
        }
    )


@bp.route("/api/dm/<persona>", methods=["POST"])
def api_dm_send(persona):
    """Send a message from 'me' to persona. AI replies in background thread."""
    p = PMAP.get(persona)
    if not p:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    txt = data.get("content", "").strip()
    if not txt:
        return jsonify({"error": "kosong"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO messages(persona,sender,content,created_at) VALUES(?,?,?,?)",
        (persona, "me", txt, time.time()),
    )
    db.commit()

    # AI reply in background — uses last 12 msgs as context
    def _reply(pers=p, persona_un=persona):
        delay = random.randint(3, 18)
        time.sleep(delay)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT sender, content FROM messages WHERE persona=? "
            "ORDER BY created_at DESC LIMIT 12",
            (persona_un,),
        ).fetchall()
        conn.close()
        history = [{"sender": r["sender"], "content": r["content"]} for r in reversed(rows)]
        reply = dm_reply(pers, history)
        if not reply:
            return
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO messages(persona,sender,content,created_at) VALUES(?,?,?,?)",
            (persona_un, persona_un, reply, time.time()),
        )
        conn.commit()
        conn.close()
        print(f"[DM:{persona_un}] replied: {reply[:50]}")

    threading.Thread(target=_reply, daemon=True).start()
    return jsonify({"ok": True}), 201
