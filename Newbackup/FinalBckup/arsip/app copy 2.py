"""
Aura Social — POC
Social media dengan AI personas yang respon secara natural (delayed).
Mendukung VLM untuk analisis foto/selfie.

Requirements:
    pip install flask requests pillow

Run:
    python app.py

Lalu buka: http://localhost:5000
"""

import os
import json
import time
import random
import base64
import sqlite3
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, g
from io import BytesIO

# ─── CONFIG ────────────────────────────────────────────────────────────────
SILICONFLOW_API_KEY = "sk-yaluviakgcbvoxtgbgxysgwucjwjebpmbwxrsihakmwuagou"
SILICONFLOW_BASE    = "https://api.siliconflow.com/v1"

TEXT_MODEL   = "Qwen/Qwen2.5-72B-Instruct"
VISION_MODEL = "Qwen/Qwen3-VL-32B-Instruct"

DB_PATH = "aura.db"

# ─── AI PERSONAS ────────────────────────────────────────────────────────────
PERSONAS = [
    {
        "username": "maya_art",
        "display":  "Maya ✨",
        "avatar":   "M",
        "color":    "linear-gradient(135deg,#ff6b6b,#ffa500)",
        "personality": (
            "Kamu adalah Maya, seniman digital 24 tahun dari Bandung. "
            "Kamu komentar di social media kayak orang beneran — singkat, kadang gak nyambung, "
            "kadang nge-roast dikit, kadang relate, tapi gak lebay. "
            "JANGAN memuji atau menyemangati secara berlebihan. Reaksi natural aja, "
            "kayak temen yang scroll sambil rebahan. Pakai bahasa gaul, kadang emot, max 1-2 kalimat. "
            "Contoh gaya: 'wkwk relate banget', 'lah kok gitu', 'ih beneran?', 'gw juga ngerasain itu', "
            "'anjay', 'emang sih'. Jangan pake kata 'keren', 'semangat', 'hebat'."
        ),
        "delay_range": (30, 120),
    },
    {
        "username": "rizky_dev",
        "display":  "Rizky 💻",
        "avatar":   "R",
        "color":    "linear-gradient(135deg,#667eea,#764ba2)",
        "personality": (
            "Kamu adalah Rizky, developer 27 tahun Jakarta. "
            "Komentar di medsos singkat dan jujur, gak perlu puji-pujian. "
            "Sering nge-roast ringan, bercanda, atau nyeletuk hal random yang lucu. "
            "Kadang gak usah bahas topiknya langsung, bisa melenceng dikit. "
            "Gaya: 'wkwk gw juga', 'anjir iya juga ya', 'lol', 'ngapain sih', "
            "'bro ini literally gw kemarin', 'yha emang'. Max 1-2 kalimat pendek."
        ),
        "delay_range": (60, 200),
    },
    {
        "username": "nadiafood",
        "display":  "Nadia 🍜",
        "avatar":   "N",
        "color":    "linear-gradient(135deg,#11998e,#38ef7d)",
        "personality": (
            "Kamu adalah Nadia, food blogger 22 tahun Surabaya. "
            "Aslinya positif tapi bukan tipe yang menjilat atau lebay. "
            "Komentar natural, kadang nanya balik, kadang share pengalaman sendiri yang related. "
            "Gak harus setuju sama postingan. Bisa bilang 'eh iya bener juga' atau "
            "'lah gw malah sebaliknya'. Bahasa Indonesia santai. Max 1-2 kalimat, "
            "sesekali pakai tanda seru tapi jangan tiap kalimat."
        ),
        "delay_range": (20, 90),
    },
    {
        "username": "bimo.plays",
        "display":  "Bimo 🎮",
        "avatar":   "B",
        "color":    "linear-gradient(135deg,#fc4a1a,#f7b733)",
        "personality": (
            "Kamu adalah Bimo, gamer 25 tahun Yogyakarta. "
            "Komentar di medsos pendek dan sering gak nyambung atau relate ke game. "
            "Gak perlu pujian, langsung aja reaksi natural. "
            "Gaya: 'skill issue', 'gg', 'bruh moment', 'lol', 'ngga relate', 'wkwkwk', "
            "'bro ini kayak di game', 'ez clap'. Kadang asal nyeletuk hal random. Max 1 kalimat."
        ),
        "delay_range": (90, 240),
    },
]

# ─── DATABASE ────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL,
            content     TEXT,
            image_b64   TEXT,
            image_desc  TEXT,
            post_type   TEXT    DEFAULT 'text',
            likes       INTEGER DEFAULT 0,
            created_at  REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id     INTEGER NOT NULL,
            username    TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            is_ai       INTEGER DEFAULT 0,
            created_at  REAL    NOT NULL,
            FOREIGN KEY (post_id) REFERENCES posts(id)
        );

        CREATE TABLE IF NOT EXISTS likes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id  INTEGER NOT NULL,
            username TEXT    NOT NULL,
            UNIQUE(post_id, username)
        );
    """)
    conn.commit()
    conn.close()

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

# ─── SILICONFLOW API ─────────────────────────────────────────────────────────
def call_llm(messages: list, model: str = TEXT_MODEL, max_tokens: int = 200) -> str:
    """
    Panggil SiliconFlow API dengan auto-fallback antar endpoint.
    Kalau endpoint pertama gagal (timeout/error), otomatis coba berikutnya.
    """
    if SILICONFLOW_API_KEY.startswith("sk-GANTI"):
        print("[ERROR] API key belum diisi! Edit SILICONFLOW_API_KEY di app.py")
        return None

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.9,
        "top_p": 0.95,
    }

    last_error = None
    for endpoint in [SILICONFLOW_BASE]:
        try:
            resp = requests.post(
                f"{endpoint}/chat/completions",
                headers=headers,
                json=payload,
                timeout=25,
            )
            # 401 = key salah, gak perlu coba endpoint lain
            if resp.status_code == 401:
                print(f"[LLM Error] 401 Unauthorized — cek API key kamu!")
                return None
            resp.raise_for_status()
            data = resp.json()
            result = data["choices"][0]["message"]["content"].strip()
            if endpoint != SILICONFLOW_BASE:
                print(f"[LLM] Berhasil via fallback: {endpoint}")
            return result
        except requests.exceptions.Timeout:
            print(f"[LLM] Timeout di {endpoint}, coba endpoint berikutnya...")
            last_error = "Timeout"
        except requests.exceptions.ConnectionError as e:
            print(f"[LLM] Connection error di {endpoint}: {e}")
            last_error = str(e)
        except Exception as e:
            print(f"[LLM Error] {endpoint} → {e}")
            last_error = str(e)

    print(f"[LLM] Semua endpoint gagal. Error terakhir: {last_error}")
    return None


def analyze_image_vlm(image_b64: str, persona: dict) -> str:
    """Gunakan VLM untuk analisis gambar/selfie, lalu buat komentar sesuai persona."""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}",
                        "detail": "low",
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"{persona['personality']}\n\n"
                        "Teman kamu baru posting gambar ini di social media. "
                        "Tulis komentar SATU kalimat singkat sesuai karaktermu. "
                        "Jangan memuji berlebihan. Reaksi natural aja, kayak orang scroll medsos beneran. "
                        "Langsung komentarnya, tanpa pembuka apapun."
                    ),
                },
            ],
        }
    ]
    return call_llm(messages, model=VISION_MODEL, max_tokens=150)


def generate_text_comment(post_content: str, persona: dict) -> str:
    """Generate komentar AI untuk postingan teks."""
    messages = [
        {
            "role": "system",
            "content": persona["personality"],
        },
        {
            "role": "user",
            "content": (
                f"Postingan teman di social media:\n\"{post_content}\"\n\n"
                "Tulis SATU komentar singkat (max 1 kalimat) sesuai karaktermu. "
                "Jangan memuji, jangan lebay, jangan kasih semangat kecuali emang fit banget sama konteks. "
                "Reaksi natural aja — bisa setuju, gak setuju, nanya, nyeletuk, atau relate. "
                "Langsung komentarnya, tanpa kata pembuka."
            ),
        },
    ]
    return call_llm(messages, model=TEXT_MODEL, max_tokens=100)


# ─── BACKGROUND AI SCHEDULER ─────────────────────────────────────────────────
def schedule_ai_responses(post_id: int, post_content: str, image_b64: str = None):
    """
    Pilih 1-2 AI persona secara acak. Ada juga chance gak ada yang balas
    (kayak medsos beneran, gak semua post dikomentarin).
    """
    # 20% chance gak ada yang balas sama sekali
    if random.random() < 0.20:
        print(f"[Scheduler] Post #{post_id} — tidak ada yang balas (natural)")
        return

    # Pilih hanya 1-2 persona
    count = random.choices([1, 2], weights=[60, 40])[0]
    selected = random.sample(PERSONAS, k=count)

    for persona in selected:
        delay = random.randint(*persona["delay_range"])

        def make_commenter(p, d, pid, content, img):
            def commenter():
                time.sleep(d)
                print(f"[AI] {p['username']} mulai nulis komentar untuk post #{pid}...")

                if img:
                    comment_text = analyze_image_vlm(img, p)
                else:
                    comment_text = generate_text_comment(content, p)

                if not comment_text:
                    print(f"[AI] {p['username']} gagal generate komentar.")
                    return

                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "INSERT INTO comments (post_id, username, content, is_ai, created_at) VALUES (?,?,?,1,?)",
                    (pid, p["username"], comment_text, time.time()),
                )
                conn.commit()
                conn.close()
                print(f"[AI] {p['username']} komentar di post #{pid}: {comment_text[:50]}...")

            return commenter

        t = threading.Thread(
            target=make_commenter(persona, delay, post_id, post_content, image_b64),
            daemon=True,
        )
        t.start()
        print(f"[Scheduler] {persona['username']} akan komentar dalam {delay}s")


# ─── FLASK APP ────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


# ── Helper ──
def persona_map():
    return {p["username"]: p for p in PERSONAS}


def time_ago(ts: float) -> str:
    diff = time.time() - ts
    if diff < 60:
        return f"{int(diff)}d lalu"
    elif diff < 3600:
        return f"{int(diff//60)} mnt lalu"
    elif diff < 86400:
        return f"{int(diff//3600)} jam lalu"
    return f"{int(diff//86400)} hari lalu"


# ── Routes ──
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/posts", methods=["GET"])
def get_posts():
    db = get_db()
    posts = db.execute(
        "SELECT * FROM posts ORDER BY created_at DESC LIMIT 20"
    ).fetchall()

    result = []
    pmap = persona_map()
    for p in posts:
        p = dict(p)
        # Get comments
        comments = db.execute(
            "SELECT * FROM comments WHERE post_id=? ORDER BY created_at ASC",
            (p["id"],),
        ).fetchall()
        p["comments"] = []
        for c in comments:
            c = dict(c)
            persona = pmap.get(c["username"], {})
            c["display"]  = persona.get("display", c["username"])
            c["avatar"]   = persona.get("avatar", c["username"][0].upper())
            c["color"]    = persona.get("color", "linear-gradient(135deg,#555,#777)")
            c["time_ago"] = time_ago(c["created_at"])
            p["comments"].append(c)

        # Poster info
        if p["username"] == "me":
            p["display"] = "Kamu 👤"
            p["avatar"]  = "K"
            p["color"]   = "linear-gradient(135deg,#c8a96e,#7b61ff)"
        else:
            persona = pmap.get(p["username"], {})
            p["display"] = persona.get("display", p["username"])
            p["avatar"]  = persona.get("avatar", "?")
            p["color"]   = persona.get("color", "linear-gradient(135deg,#555,#777)")

        p["time_ago"]      = time_ago(p["created_at"])
        p["comment_count"] = len(p["comments"])
        # Jangan kirim raw base64 ke list (berat), kirim flag saja
        p["has_image"] = bool(p.get("image_b64"))
        p.pop("image_b64", None)
        result.append(p)

    return jsonify(result)


@app.route("/api/posts/<int:post_id>/image")
def get_image(post_id):
    db = get_db()
    row = db.execute("SELECT image_b64 FROM posts WHERE id=?", (post_id,)).fetchone()
    if not row or not row["image_b64"]:
        return "", 404
    img_data = base64.b64decode(row["image_b64"])
    from flask import Response
    return Response(img_data, mimetype="image/jpeg")


@app.route("/api/posts", methods=["POST"])
def create_post():
    db   = get_db()
    data = request.get_json() or {}

    content   = data.get("content", "").strip()
    image_b64 = data.get("image_b64")
    post_type = "image" if image_b64 else "text"

    if not content and not image_b64:
        return jsonify({"error": "Konten atau gambar wajib ada"}), 400

    # Post LANGSUNG ke DB tanpa tunggu VLM
    post_id = db.execute(
        "INSERT INTO posts (username, content, image_b64, image_desc, post_type, created_at) VALUES (?,?,?,?,?,?)",
        ("me", content, image_b64, None, post_type, time.time()),
    ).lastrowid
    db.commit()

    # VLM + AI schedule jalan di background (tidak blocking UI)
    def background_tasks(pid, img, cap):
        desc = None
        if img:
            print(f"[VLM] Background: menganalisis gambar post #{pid}...")
            desc_messages = [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img}", "detail": "low"},
                    },
                    {"type": "text", "text": "Deskripsikan gambar ini dalam 1-2 kalimat singkat dalam bahasa Indonesia."},
                ],
            }]
            desc = call_llm(desc_messages, model=VISION_MODEL, max_tokens=100)
            if desc:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("UPDATE posts SET image_desc=? WHERE id=?", (desc, pid))
                conn.commit()
                conn.close()
                print(f"[VLM] Deskripsi post #{pid}: {desc[:60]}...")

        context = cap or desc or "foto baru"
        schedule_ai_responses(pid, context, img)

    threading.Thread(target=background_tasks, args=(post_id, image_b64, content), daemon=True).start()

    return jsonify({
        "id": post_id,
        "message": "Post berhasil! AI personas akan merespon sebentar lagi... 🤖"
    }), 201


@app.route("/api/posts/<int:post_id>/like", methods=["POST"])
def like_post(post_id):
    db = get_db()
    try:
        db.execute("INSERT INTO likes (post_id, username) VALUES (?,?)", (post_id, "me"))
        db.execute("UPDATE posts SET likes = likes + 1 WHERE id=?", (post_id,))
        db.commit()
        liked = True
    except sqlite3.IntegrityError:
        db.execute("DELETE FROM likes WHERE post_id=? AND username=?", (post_id, "me"))
        db.execute("UPDATE posts SET likes = MAX(0, likes - 1) WHERE id=?", (post_id,))
        db.commit()
        liked = False
    row = db.execute("SELECT likes FROM posts WHERE id=?", (post_id,)).fetchone()
    return jsonify({"liked": liked, "likes": row["likes"]})


@app.route("/api/posts/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    db   = get_db()
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Komentar kosong"}), 400

    db.execute(
        "INSERT INTO comments (post_id, username, content, is_ai, created_at) VALUES (?,?,?,0,?)",
        (post_id, "me", text, time.time()),
    )
    db.commit()

    # AI bisa balas komentar juga (50% chance, delay lebih pendek)
    if random.random() < 0.5:
        persona = random.choice(PERSONAS)
        delay   = random.randint(20, 60)

        def reply_comment(p, d, pid, comment_text):
            def _reply():
                time.sleep(d)
                post_row = sqlite3.connect(DB_PATH).execute(
                    "SELECT content, image_b64 FROM posts WHERE id=?", (pid,)
                ).fetchone()
                ctx = f"[Konteks post: {post_row[0]}]\n\nAda yang komentar: \"{comment_text}\""
                reply = generate_text_comment(ctx, p)
                if reply:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute(
                        "INSERT INTO comments (post_id, username, content, is_ai, created_at) VALUES (?,?,?,1,?)",
                        (pid, p["username"], reply, time.time()),
                    )
                    conn.commit()
                    conn.close()
                    print(f"[AI Reply] {p['username']} balas komentar di post #{pid}")
            return _reply

        threading.Thread(
            target=reply_comment(persona, delay, post_id, text),
            daemon=True,
        ).start()

    return jsonify({"message": "Komentar ditambahkan"}), 201


# ─── HTML TEMPLATE ────────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aura Social — POC</title>
<link href="https://fonts.googleapis.com/css2?family=Clash+Display:wght@600;700&family=Sora:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root{--bg:#0a0a0f;--surf:#13131a;--surf2:#1c1c27;--bdr:#2a2a3a;--acc:#c8a96e;--acc2:#7b61ff;--text:#f0eee8;--muted:#7a7a90;--danger:#ff5c7a;}
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:var(--bg);color:var(--text);font-family:'Sora',sans-serif;max-width:480px;margin:0 auto;min-height:100vh;}
  
  .topbar{position:sticky;top:0;z-index:99;background:rgba(10,10,15,.9);backdrop-filter:blur(20px);border-bottom:1px solid var(--bdr);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;}
  .logo{font-family:'Clash Display',sans-serif;font-size:24px;background:linear-gradient(135deg,#c8a96e,#e8c89a,#7b61ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
  .badge{background:var(--surf2);border:1px solid var(--bdr);border-radius:20px;padding:4px 12px;font-size:12px;color:var(--muted);}

  .compose{background:var(--surf);border-bottom:1px solid var(--bdr);padding:16px 20px;}
  .compose-row{display:flex;gap:12px;align-items:flex-start;}
  .av{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;font-family:'Clash Display',sans-serif;flex-shrink:0;}
  .av-me{background:linear-gradient(135deg,#c8a96e,#7b61ff);}
  textarea{flex:1;background:none;border:none;color:var(--text);font-family:'Sora',sans-serif;font-size:15px;line-height:1.6;resize:none;outline:none;min-height:60px;}
  textarea::placeholder{color:var(--muted);}
  .compose-footer{display:flex;align-items:center;gap:10px;margin-top:10px;padding-top:10px;border-top:1px solid var(--bdr);}
  .tool-btn{background:none;border:none;color:var(--acc);cursor:pointer;padding:6px;border-radius:8px;font-size:18px;transition:.2s;}
  .tool-btn:hover{background:var(--surf2);}
  .img-preview{position:relative;margin-top:10px;}
  .img-preview img{width:100%;border-radius:12px;max-height:300px;object-fit:cover;}
  .remove-img{position:absolute;top:8px;right:8px;background:rgba(0,0,0,.6);border:none;color:#fff;border-radius:50%;width:28px;height:28px;cursor:pointer;font-size:16px;}
  .post-btn{margin-left:auto;background:var(--acc);color:var(--bg);border:none;border-radius:20px;padding:8px 20px;font-size:13px;font-weight:600;font-family:'Sora',sans-serif;cursor:pointer;transition:.2s;}
  .post-btn:hover{opacity:.85;}
  .post-btn:disabled{opacity:.5;cursor:not-allowed;}

  .feed{padding-bottom:40px;}
  .post-card{border-bottom:1px solid var(--bdr);animation:fadeUp .4s ease both;}
  @keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
  .post-head{display:flex;align-items:center;gap:10px;padding:14px 20px 8px;}
  .post-meta{flex:1;}
  .uname{font-size:14px;font-weight:600;font-family:'Clash Display',sans-serif;}
  .utime{font-size:12px;color:var(--muted);}
  .post-img{width:100%;display:block;}
  .post-body{padding:8px 20px 4px;font-size:15px;line-height:1.65;}
  .post-body.image-caption{font-size:14px;color:var(--muted);}
  .post-image-desc{padding:4px 20px;font-size:13px;color:var(--acc);font-style:italic;}
  .post-actions{display:flex;gap:4px;padding:6px 12px;}
  .act{display:flex;align-items:center;gap:5px;background:none;border:none;color:var(--muted);font-size:13px;font-family:'Sora',sans-serif;cursor:pointer;padding:7px 10px;border-radius:10px;transition:.2s;}
  .act:hover{background:var(--surf2);color:var(--text);}
  .act.liked{color:var(--danger);}
  .act svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.8;}
  .act.liked svg{fill:var(--danger);}

  .comments-section{background:var(--surf);border-top:1px solid var(--bdr);padding:10px 20px;}
  .comment-item{display:flex;gap:10px;margin-bottom:12px;}
  .comment-av{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;}
  .comment-body{flex:1;}
  .comment-user{font-size:13px;font-weight:600;display:inline-block;margin-right:6px;}
  .comment-text{font-size:13px;color:var(--text);line-height:1.5;display:inline;}
  .comment-time{font-size:11px;color:var(--muted);margin-top:2px;}
  .ai-badge{background:var(--acc2);color:#fff;font-size:9px;padding:1px 5px;border-radius:4px;margin-left:4px;vertical-align:middle;}
  .comment-input-row{display:flex;gap:8px;align-items:center;margin-top:8px;}
  .comment-input{flex:1;background:var(--surf2);border:1px solid var(--bdr);border-radius:20px;padding:8px 14px;color:var(--text);font-family:'Sora',sans-serif;font-size:13px;outline:none;transition:.2s;}
  .comment-input:focus{border-color:var(--acc);}
  .comment-input::placeholder{color:var(--muted);}
  .comment-send{background:var(--acc);border:none;color:var(--bg);border-radius:50%;width:32px;height:32px;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;}

  .empty{text-align:center;padding:60px 20px;color:var(--muted);}
  .empty-icon{font-size:48px;margin-bottom:12px;}
  .loading{text-align:center;padding:40px;color:var(--muted);font-size:14px;}
  .ai-typing{display:inline-flex;align-items:center;gap:4px;color:var(--muted);font-size:12px;font-style:italic;}
  .dot{width:4px;height:4px;background:var(--acc);border-radius:50%;animation:blink 1.4s infinite;}
  .dot:nth-child(2){animation-delay:.2s;}
  .dot:nth-child(3){animation-delay:.4s;}
  @keyframes blink{0%,80%,100%{opacity:.3}40%{opacity:1}}

  .toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--surf2);border:1px solid var(--bdr);border-radius:12px;padding:10px 20px;font-size:14px;opacity:0;transition:.3s;z-index:999;white-space:nowrap;}
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0);}
  
  input[type=file]{display:none;}
  ::-webkit-scrollbar{width:0;}
</style>
</head>
<body>

<div class="topbar">
  <div class="logo">Aura</div>
  <div class="badge">🤖 AI POC · SiliconFlow</div>
</div>

<!-- COMPOSE -->
<div class="compose">
  <div class="compose-row">
    <div class="av av-me">K</div>
    <textarea id="compose-text" placeholder="Apa yang lagi kamu pikirin? Atau upload foto kamu! 📸" rows="2"></textarea>
  </div>
  <div id="img-preview-wrap" style="display:none" class="img-preview">
    <img id="img-preview-el" src="" alt="preview">
    <button class="remove-img" onclick="removeImage()">×</button>
  </div>
  <div class="compose-footer">
    <button class="tool-btn" onclick="document.getElementById('file-input').click()" title="Upload foto">📷</button>
    <input type="file" id="file-input" accept="image/*" onchange="handleFileSelect(event)">
    <span id="char-left" style="font-size:12px;color:var(--muted)">280</span>
    <button class="post-btn" id="post-btn" onclick="submitPost()">Post ✦</button>
  </div>
</div>

<!-- FEED -->
<div class="feed" id="feed">
  <div class="loading">Memuat feed...</div>
</div>

<div class="toast" id="toast"></div>

<script>
let currentImageB64 = null;
let likedPosts = new Set();
let refreshInterval;

// ── Image handling ──
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) { showToast('⚠️ Ukuran file max 5MB'); return; }
  const reader = new FileReader();
  reader.onload = (ev) => {
    const full = ev.target.result;
    currentImageB64 = full.split(',')[1]; // ambil base64 saja
    document.getElementById('img-preview-el').src = full;
    document.getElementById('img-preview-wrap').style.display = 'block';
  };
  reader.readAsDataURL(file);
}

function removeImage() {
  currentImageB64 = null;
  document.getElementById('img-preview-wrap').style.display = 'none';
  document.getElementById('img-preview-el').src = '';
  document.getElementById('file-input').value = '';
}

// ── Post ──
document.getElementById('compose-text').addEventListener('input', function() {
  document.getElementById('char-left').textContent = 280 - this.value.length;
});

async function submitPost() {
  const text = document.getElementById('compose-text').value.trim();
  if (!text && !currentImageB64) { showToast('⚠️ Tulis sesuatu atau upload foto dulu!'); return; }
  
  const btn = document.getElementById('post-btn');
  btn.disabled = true;
  btn.textContent = 'Posting...';

  try {
    const res = await fetch('/api/posts', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ content: text, image_b64: currentImageB64 })
    });
    const data = await res.json();
    if (res.ok) {
      document.getElementById('compose-text').value = '';
      document.getElementById('char-left').textContent = '280';
      removeImage();
      showToast('🚀 ' + data.message);
      loadFeed();
    } else {
      showToast('❌ ' + data.error);
    }
  } catch(err) {
    showToast('❌ Gagal posting: ' + err.message);
  }
  btn.disabled = false;
  btn.textContent = 'Post ✦';
}

// ── Feed ──
async function loadFeed() {
  try {
    const res = await fetch('/api/posts');
    const posts = await res.json();
    renderFeed(posts);
  } catch(e) {
    document.getElementById('feed').innerHTML = '<div class="empty"><div class="empty-icon">⚡</div>Gagal memuat feed</div>';
  }
}

function renderFeed(posts) {
  const feed = document.getElementById('feed');
  if (posts.length === 0) {
    feed.innerHTML = '<div class="empty"><div class="empty-icon">🌱</div><div>Belum ada postingan.</div><div style="margin-top:8px;font-size:13px">Jadilah yang pertama posting!</div></div>';
    return;
  }
  feed.innerHTML = posts.map((p, i) => postCard(p, i)).join('');
}

function postCard(p, i) {
  const isLiked = likedPosts.has(p.id);
  
  let mediaHTML = '';
  if (p.has_image) {
    mediaHTML = `<img src="/api/posts/${p.id}/image" class="post-img" alt="post image" loading="lazy">`;
    if (p.image_desc) mediaHTML += `<div class="post-image-desc">🤖 "${p.image_desc}"</div>`;
  }
  if (p.content) {
    mediaHTML += `<div class="post-body ${p.has_image ? 'image-caption' : ''}">${escHtml(p.content)}</div>`;
  }

  const commentsHTML = p.comments.map(c => `
    <div class="comment-item">
      <div class="comment-av" style="background:${c.color}">${c.avatar}</div>
      <div class="comment-body">
        <span class="comment-user">${c.display}</span>
        ${c.is_ai ? '<span class="ai-badge">AI</span>' : ''}
        <span class="comment-text">${escHtml(c.content)}</span>
        <div class="comment-time">${c.time_ago}</div>
      </div>
    </div>
  `).join('');

  return `
  <div class="post-card" style="animation-delay:${i * 0.05}s" id="post-${p.id}">
    <div class="post-head">
      <div class="av" style="background:${p.color}">${p.avatar}</div>
      <div class="post-meta">
        <div class="uname">${p.display}</div>
        <div class="utime">${p.time_ago}</div>
      </div>
    </div>
    ${mediaHTML}
    <div class="post-actions">
      <button class="act ${isLiked ? 'liked' : ''}" onclick="toggleLike(${p.id}, this)">
        <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        <span id="likes-${p.id}">${p.likes}</span>
      </button>
      <button class="act" onclick="toggleComments(${p.id})">
        <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span>${p.comment_count}</span>
      </button>
      <button class="act" onclick="showToast('🔁 Repost coming soon!')">
        <svg viewBox="0 0 24 24"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
      </button>
    </div>
    <div class="comments-section" id="comments-${p.id}" style="display:${p.comments.length > 0 ? 'block' : 'none'}">
      <div id="comments-list-${p.id}">${commentsHTML}</div>
      <div class="comment-input-row">
        <input class="comment-input" id="cinput-${p.id}" placeholder="Tulis komentar..." onkeydown="if(event.key==='Enter')sendComment(${p.id})">
        <button class="comment-send" onclick="sendComment(${p.id})">➤</button>
      </div>
    </div>
  </div>`;
}

function toggleComments(postId) {
  const el = document.getElementById(`comments-${postId}`);
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
  if (el.style.display === 'block') {
    document.getElementById(`cinput-${postId}`)?.focus();
  }
}

async function toggleLike(postId, btn) {
  const res = await fetch(`/api/posts/${postId}/like`, { method: 'POST' });
  const data = await res.json();
  btn.classList.toggle('liked', data.liked);
  document.getElementById(`likes-${postId}`).textContent = data.likes;
  if (data.liked) {
    likedPosts.add(postId);
    btn.style.transform = 'scale(1.3)';
    setTimeout(() => btn.style.transform = '', 200);
  } else {
    likedPosts.delete(postId);
  }
}

async function sendComment(postId) {
  const input = document.getElementById(`cinput-${postId}`);
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  // Tampilkan komentar kita langsung
  const list = document.getElementById(`comments-list-${postId}`);
  list.insertAdjacentHTML('beforeend', `
    <div class="comment-item">
      <div class="comment-av" style="background:linear-gradient(135deg,#c8a96e,#7b61ff)">K</div>
      <div class="comment-body">
        <span class="comment-user">Kamu 👤</span>
        <span class="comment-text">${escHtml(text)}</span>
        <div class="comment-time">Baru saja</div>
      </div>
    </div>
  `);

  // Indikator AI sedang mengetik (kalau ada AI yg bakal balas)
  const typingId = `typing-${postId}-${Date.now()}`;
  if (Math.random() < 0.5) {
    list.insertAdjacentHTML('beforeend', `
      <div id="${typingId}" class="comment-item">
        <div class="comment-av" style="background:linear-gradient(135deg,#667eea,#764ba2)">?</div>
        <div class="comment-body">
          <div class="ai-typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
        </div>
      </div>
    `);
    setTimeout(() => document.getElementById(typingId)?.remove(), 65000);
  }

  await fetch(`/api/posts/${postId}/comment`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ text })
  });
}

// ── Utils ──
function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

let toastTimer;
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2500);
}

// ── Auto-refresh setiap 15 detik (supaya AI comments muncul) ──
loadFeed();
refreshInterval = setInterval(loadFeed, 15000);
</script>
</body>
</html>
"""

# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("=" * 55)
    print("  🚀 Aura Social POC — SiliconFlow AI")
    print("=" * 55)
    print(f"  Text model  : {TEXT_MODEL}")
    key_ok = not SILICONFLOW_API_KEY.startswith("sk-GANTI")
    print(f"  Text model  : {TEXT_MODEL}")
    print(f"  Vision model: {VISION_MODEL}")
    print(f"  Database    : {DB_PATH}")
    print(f"  API Key     : {'✅ Set' if key_ok else '❌ BELUM DIISI — edit SILICONFLOW_API_KEY!'}")
    print(f"  Endpoint    : {SILICONFLOW_BASE}")
    print("=" * 55)
    if not key_ok:
        print("  ⚠️  STOP! Isi dulu API key di baris SILICONFLOW_API_KEY")
        print("=" * 55)
    print("  Buka: http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, threaded=True, port=5000)