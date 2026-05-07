"""
Aura Social v3 — Full Feature Upgrade
Improvements:
  1. VLM deskripsi hidden dari user (internal only)
  2. Story multi-slide + navigation
  3. Profile grid = image only, tweets tab = text only
  4. AI persona profiles viewable + AI bisa posting di timeline
  5. Image generation (FLUX.1-schnell) untuk AI story
  6. AI-to-AI commenting
  7. Probabilistic reply (tidak semua balas)

Run: python app.py → http://localhost:5000
"""
import time, random, base64, sqlite3, threading, requests, re, io
from flask import Flask, request, jsonify, render_template_string, g, Response

# ─── CONFIG ────────────────────────────────────────────────────────────────
SILICONFLOW_API_KEY = "sk-yaluviakgcbvoxtgbgxysgwucjwjebpmbwxrsihakmwuagou"
SILICONFLOW_BASE    = "https://api.siliconflow.com/v1"
TEXT_MODEL          = "Qwen/Qwen2.5-72B-Instruct"
VISION_MODEL        = "Qwen/Qwen3-VL-32B-Instruct"
IMAGE_MODEL         = "black-forest-labs/FLUX.1-schnell"
DB_PATH             = "aura.db"

# ─── PERSONAS ──────────────────────────────────────────────────────────────
PERSONAS = [
    {"username":"maya_art","display":"Maya ✨","avatar":"M",
     "color":"linear-gradient(135deg,#ff6b6b,#ffa500)",
     "text_model":"Qwen/Qwen3-32B","vision_model":"Qwen/Qwen2.5-VL-32B-Instruct",
     "reply_prob":0.55,"delay_range":(25,110),
     "bio":"Seniman digital 24th Bandung. Suka warna, komposisi, dan kopi.\n🎨 Art • Design • Aesthetic",
     "personality":"Kamu Maya, seniman digital 24th Bandung. Komentar singkat, kadang roast, kadang relate. Gak lebay. Max 1 kalimat. Contoh: 'anjay relate','emang sih'. JANGAN: keren, semangat, hebat.",
     "post_topics":["art","sunset","creative process","design tips","color palette"],
     "story_prompts":["dreamy pastel sunset over mountains","abstract watercolor painting with gold accents","cozy art studio with canvas and paint"]},
    {"username":"rizky_dev","display":"Rizky 💻","avatar":"R",
     "color":"linear-gradient(135deg,#667eea,#764ba2)",
     "text_model":"deepseek-ai/DeepSeek-V3","vision_model":"Qwen/Qwen3-VL-32B-Instruct",
     "reply_prob":0.40,"delay_range":(60,200),
     "bio":"Developer 27th Jakarta. Code, coffee, repeat.\n💻 Full-stack • Open source • Memes",
     "personality":"Kamu Rizky, developer 27th Jakarta. Jujur, sering roast ringan, nyeletuk. Jaksel-style. Max 1 kalimat. Gaya: 'wkwk gw juga','bro ini literally gw','yha emang'.",
     "post_topics":["coding","tech","startup life","debugging story","setup"],
     "story_prompts":["dark coding setup with neon monitor lights","futuristic tech workspace aesthetic","coffee cup next to laptop with code on screen"]},
    {"username":"nadiafood","display":"Nadia 🍜","avatar":"N",
     "color":"linear-gradient(135deg,#11998e,#38ef7d)",
     "text_model":"Qwen/Qwen2.5-72B-Instruct","vision_model":"Qwen/Qwen2.5-VL-72B-Instruct",
     "reply_prob":0.60,"delay_range":(20,85),
     "bio":"Food blogger 22th Surabaya. Makan enak gak harus mahal!\n🍜 Kuliner • Review • Resep",
     "personality":"Kamu Nadia, food blogger 22th Surabaya. Positif tapi gak menjilat. Kadang nanya balik, share pengalaman. Bisa gak setuju. Max 1-2 kalimat santai.",
     "post_topics":["food review","recipe","street food","cafe hopping","cooking fail"],
     "story_prompts":["delicious ramen bowl with steam rising","aesthetic cafe interior with latte art","colorful street food market at night"]},
    {"username":"bimo.plays","display":"Bimo 🎮","avatar":"B",
     "color":"linear-gradient(135deg,#fc4a1a,#f7b733)",
     "text_model":"Qwen/Qwen3-14B","vision_model":None,
     "reply_prob":0.30,"delay_range":(90,240),
     "bio":"Gamer 25th Jogja. Rank pusher. Sleep is optional.\n🎮 FPS • MOBA • Indie games",
     "personality":"Kamu Bimo, gamer 25th Jogja. Komentar pendek, relate ke game. Max 1 kalimat. Gaya: 'skill issue','gg','bruh','ez clap'.",
     "post_topics":["gaming moment","rank story","new game","rage quit","late night gaming"],
     "story_prompts":["epic gaming setup with RGB lights","retro arcade machine glowing in dark room","controller on desk with energy drink"]},
    {"username":"ara_style","display":"Ara 🌸","avatar":"A",
     "color":"linear-gradient(135deg,#f953c6,#b91d73)",
     "text_model":"moonshotai/Kimi-K2-Instruct","vision_model":"Qwen/Qwen3-VL-32B-Instruct",
     "reply_prob":0.45,"delay_range":(40,150),
     "bio":"Fashion content creator 23th. Style > trend.\n🌸 OOTD • Thrift • Aesthetic",
     "personality":"Kamu Ara, fashion content creator 23th. Stylish, opinionated. Kadang skeptis. Max 1 kalimat. Gak pernah bilang 'keren'. Bisa bilang 'hmm nah','itu beda cerita'.",
     "post_topics":["fashion","ootd","thrift finds","style tips","aesthetic"],
     "story_prompts":["aesthetic outfit flatlay on marble background","stylish street fashion photography","minimalist wardrobe closet organization"]},
    {"username":"dimas_photo","display":"Dimas 📸","avatar":"D",
     "color":"linear-gradient(135deg,#1a1a2e,#16213e,#0f3460)",
     "text_model":"deepseek-ai/DeepSeek-V3","vision_model":"Qwen/Qwen2.5-VL-72B-Instruct",
     "reply_prob":0.35,"delay_range":(70,180),"image_bias":True,
     "bio":"Fotografer jalanan 28th. Light chaser.\n📸 Street • Portrait • Moody",
     "personality":"Kamu Dimas, fotografer jalanan 28th. PENTING: kalo post ada FOTO, komentar soal visual/komposisi (lighting, angle, framing). Kalo post TEKS biasa tanpa foto, komentar biasa kayak orang normal — relate, roast ringan, atau kasih pendapat. JANGAN bahas fotografi/visual kalo gak ada foto. Max 1 kalimat. Gaya santai: 'sabi','bener juga','anjir relate'.",
     "post_topics":["street photography","golden hour","composition tips","behind the lens","city night"],
     "story_prompts":["golden hour city street photography","moody portrait with dramatic lighting","urban night photography with neon signs"]},
]
PMAP = {p["username"]: p for p in PERSONAS}

# ─── DB ────────────────────────────────────────────────────────────────────
def init_db():
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, content TEXT, image_b64 TEXT, image_desc TEXT,
            post_type TEXT DEFAULT 'text', likes INTEGER DEFAULT 0, created_at REAL);
        CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER, username TEXT, content TEXT, is_ai INTEGER DEFAULT 0, created_at REAL);
        CREATE TABLE IF NOT EXISTS likes(id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER, username TEXT, UNIQUE(post_id, username));
        CREATE TABLE IF NOT EXISTS stories(id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, image_b64 TEXT, caption TEXT, created_at REAL);
    """)
    c.commit(); c.close()

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH); g.db.row_factory = sqlite3.Row
    return g.db

# ─── LLM / VLM / IMAGE GEN ────────────────────────────────────────────────
def call_llm(messages, model, max_tokens=90):
    try:
        r = requests.post(f"{SILICONFLOW_BASE}/chat/completions",
            headers={"Authorization":f"Bearer {SILICONFLOW_API_KEY}","Content-Type":"application/json"},
            json={"model":model,"messages":messages,"max_tokens":max_tokens,"temperature":0.93,"top_p":0.95},
            timeout=30)
        if r.status_code == 401: print("[401] cek API key"); return None
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"].strip()
        txt = re.sub(r"<think>.*?</think>","",txt,flags=re.DOTALL).strip()
        return txt or None
    except Exception as e:
        print(f"[LLM] {model.split('/')[-1][:18]}: {e}")
        return None

def generate_image(prompt):
    """Generate image via FLUX.1-schnell — returns base64 or None"""
    try:
        r = requests.post(f"{SILICONFLOW_BASE}/images/generations",
            headers={"Authorization":f"Bearer {SILICONFLOW_API_KEY}","Content-Type":"application/json"},
            json={"model":IMAGE_MODEL,"prompt":prompt,"image_size":"512x512"},
            timeout=60)
        if r.status_code != 200:
            print(f"[ImageGen] {r.status_code}: {r.text[:100]}")
            return None
        data = r.json()
        # Response format: {"images":[{"url":"..."}]} or {"data":[{"b64_json":"..."}]}
        images = data.get("images") or data.get("data") or []
        if not images: return None
        img = images[0]
        if "b64_json" in img:
            return img["b64_json"]
        elif "url" in img:
            # Download the image and convert to base64
            img_r = requests.get(img["url"], timeout=30)
            if img_r.status_code == 200:
                return base64.b64encode(img_r.content).decode()
        return None
    except Exception as e:
        print(f"[ImageGen] error: {e}")
        return None

def comment_text(content, p):
    return call_llm([
        {"role":"system","content":p["personality"]},
        {"role":"user","content":f"Post: \"{content}\"\nTulis 1 komentar singkat. Langsung isi komentar, tanpa tanda kutip."}
    ], p["text_model"])

def comment_image(img_b64, p):
    if not p.get("vision_model"): return None
    return call_llm([{"role":"user","content":[
        {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_b64}","detail":"low"}},
        {"type":"text","text":f"{p['personality']}\nFoto ini dipost teman. 1 komentar singkat. Langsung isi, tanpa tanda kutip."}
    ]}], p["vision_model"])

def describe_image(img_b64):
    """Internal only — description NOT shown to user"""
    return call_llm([{"role":"user","content":[
        {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_b64}","detail":"low"}},
        {"type":"text","text":"Deskripsikan gambar ini 1 kalimat, bahasa Indonesia."}
    ]}], VISION_MODEL, max_tokens=70)

# ─── AI RESPONSE SCHEDULING ───────────────────────────────────────────────
def schedule_responses(pid, content, img=None, poster="me"):
    """Schedule AI persona responses + likes. poster = who made the post (skip self-reply)"""
    is_img = bool(img)
    for p in PERSONAS:
        if p["username"] == poster: continue  # don't reply to own post
        # AI LIKE: 40-65% chance to like (independent of replying)
        like_prob = 0.50 if is_img else 0.40
        if random.random() < like_prob:
            delay_like = random.randint(5, max(10, p["delay_range"][0]))
            def _like(p=p, d=delay_like, pid=pid):
                time.sleep(d)
                try:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("INSERT INTO likes(post_id,username) VALUES(?,?)", (pid, p["username"]))
                    conn.execute("UPDATE posts SET likes=likes+1 WHERE id=?", (pid,))
                    conn.commit(); conn.close()
                    print(f"[AI-Like] {p['username']} liked post#{pid}")
                except sqlite3.IntegrityError: pass  # already liked
                except Exception as e: print(f"[AI-Like] error: {e}")
            threading.Thread(target=_like, daemon=True).start()
        # AI COMMENT: probabilistic
        prob = p["reply_prob"]
        if is_img and p.get("image_bias"): prob = min(prob + 0.25, 0.85)
        if is_img and not p.get("vision_model"): prob *= 0.25
        if random.random() > prob: continue
        delay = random.randint(*p["delay_range"])
        def _run(p=p, d=delay, pid=pid, txt=content, i=img):
            time.sleep(d)
            print(f"[AI:{p['username']}] commenting post#{pid}")
            c = comment_image(i, p) if i and p.get("vision_model") else comment_text(txt, p)
            if not c: return
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO comments(post_id,username,content,is_ai,created_at) VALUES(?,?,?,1,?)",
                         (pid, p["username"], c, time.time()))
            conn.commit(); conn.close()
            print(f"  → {c[:55]}")
        threading.Thread(target=_run, daemon=True).start()
        print(f"[Sched] {p['username']} → {delay}s for post#{pid}")

# ─── AI AUTONOMOUS POSTING ────────────────────────────────────────────────
def ai_post_scheduler():
    """Background: AI personas post on timeline periodically, sometimes with images"""
    time.sleep(120)  # wait 2min after startup
    while True:
        try:
            p = random.choice(PERSONAS)
            topic = random.choice(p["post_topics"])
            # 30% chance to post with generated image (hemat token)
            do_image = random.random() < 0.30
            print(f"[AI-Post] {p['username']} generating {'image+' if do_image else ''}post about '{topic}'...")
            content = call_llm([
                {"role":"system","content":f"{p['personality']}\nKamu sedang posting di medsos sendiri, bukan komentar. Topik: {topic}. Tulis 1-2 kalimat. Langsung isi post, tanpa tanda kutip."},
                {"role":"user","content":"Buat 1 postingan medsos singkat."}
            ], p["text_model"], max_tokens=80)
            if content:
                img_b64 = None
                if do_image:
                    # Generate image prompt based on topic
                    img_prompt = random.choice(p.get("story_prompts", [topic]))
                    img_b64 = generate_image(img_prompt)
                    if img_b64:
                        print(f"[AI-Post] {p['username']} generated image!")
                    else:
                        print(f"[AI-Post] image gen failed, posting text only")
                conn = sqlite3.connect(DB_PATH)
                pid = conn.execute(
                    "INSERT INTO posts(username,content,image_b64,image_desc,post_type,created_at) VALUES(?,?,?,?,?,?)",
                    (p["username"], content, img_b64, None, "image" if img_b64 else "text", time.time())
                ).lastrowid
                conn.commit(); conn.close()
                print(f"[AI-Post] {p['username']} posted #{pid}: {content[:50]}")
                # Other AIs may comment on this AI post (AI-to-AI interaction!)
                schedule_responses(pid, content, img_b64, poster=p["username"])
        except Exception as e:
            print(f"[AI-Post] error: {e}")
        # Wait 8-15 minutes before next AI post (hemat token!)
        wait = random.randint(480, 900)
        print(f"[AI-Post] next in {wait//60}min")
        time.sleep(wait)

# ─── AI STORY GENERATION ──────────────────────────────────────────────────
def ai_story_scheduler():
    """Background: generate AI stories with FLUX images"""
    time.sleep(60)  # wait 1min
    while True:
        try:
            p = random.choice(PERSONAS)
            prompt = random.choice(p["story_prompts"])
            print(f"[AI-Story] {p['username']} generating story: '{prompt[:40]}...'")
            img_b64 = generate_image(prompt)
            if img_b64:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO stories(username,image_b64,caption,created_at) VALUES(?,?,?,?)",
                             (p["username"], img_b64, prompt, time.time()))
                conn.commit(); conn.close()
                print(f"[AI-Story] {p['username']} story posted!")
            else:
                print(f"[AI-Story] failed to generate image")
        except Exception as e:
            print(f"[AI-Story] error: {e}")
        # Wait 15-25 min between stories (hemat token!)
        wait = random.randint(900, 1500)
        print(f"[AI-Story] next in {wait//60}min")
        time.sleep(wait)

# ─── HELPERS ───────────────────────────────────────────────────────────────
def time_ago(ts):
    d = time.time() - ts
    if d < 60: return f"{int(d)}d lalu"
    if d < 3600: return f"{int(d//60)} mnt lalu"
    if d < 86400: return f"{int(d//3600)} jam lalu"
    return f"{int(d//86400)} hari lalu"

# ─── FLASK APP ─────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

# ── API: Posts ─────────────────────────────────────────────────────────────
@app.route("/api/posts")
def api_get_posts():
    db = get_db()
    rows = db.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 30").fetchall()
    out = []
    for p in rows:
        p = dict(p)
        comms = db.execute("SELECT * FROM comments WHERE post_id=? ORDER BY created_at", (p["id"],)).fetchall()
        p["comments"] = []
        for c in comms:
            c = dict(c); pers = PMAP.get(c["username"], {})
            c["display"]  = pers.get("display", "Kamu 👤" if c["username"]=="me" else c["username"])
            c["avatar"]   = pers.get("avatar", "K" if c["username"]=="me" else c["username"][0].upper())
            c["color"]    = pers.get("color", "linear-gradient(135deg,#c9aa72,#7b61ff)" if c["username"]=="me" else "linear-gradient(135deg,#555,#777)")
            c["time_ago"] = time_ago(c["created_at"])
            p["comments"].append(c)
        p["comment_count"] = len(p["comments"])
        if p["username"] == "me":
            p["display"] = "Kamu 👤"; p["avatar"] = "K"
            p["color"] = "linear-gradient(135deg,#c9aa72,#7b61ff)"
        else:
            pers = PMAP.get(p["username"], {})
            p["display"] = pers.get("display", p["username"])
            p["avatar"]  = pers.get("avatar", "?")
            p["color"]   = pers.get("color", "#555")
        p["time_ago"] = time_ago(p["created_at"])
        p["has_image"] = bool(p.get("image_b64"))
        # FIX #1: Don't send image_desc to frontend (hidden from user)
        p.pop("image_desc", None)
        p.pop("image_b64", None)
        out.append(p)
    return jsonify(out)

@app.route("/api/posts/<int:pid>/image")
def api_image(pid):
    row = get_db().execute("SELECT image_b64 FROM posts WHERE id=?", (pid,)).fetchone()
    if not row or not row["image_b64"]: return "", 404
    return Response(base64.b64decode(row["image_b64"]), mimetype="image/jpeg")

@app.route("/api/posts", methods=["POST"])
def api_create():
    data = request.get_json() or {}
    content = data.get("content", "").strip()
    img = data.get("image_b64")
    if not content and not img: return jsonify({"error": "kosong"}), 400
    db = get_db()
    pid = db.execute(
        "INSERT INTO posts(username,content,image_b64,image_desc,post_type,created_at) VALUES(?,?,?,?,?,?)",
        ("me", content, img, None, "image" if img else "text", time.time())
    ).lastrowid
    db.commit()
    def bg(pid=pid, i=img, cap=content):
        desc = None
        if i:
            desc = describe_image(i)
            if desc:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("UPDATE posts SET image_desc=? WHERE id=?", (desc, pid))
                conn.commit(); conn.close()
        schedule_responses(pid, cap or desc or "foto", i, poster="me")
    threading.Thread(target=bg, daemon=True).start()
    return jsonify({"id": pid}), 201

@app.route("/api/posts/<int:pid>/like", methods=["POST"])
def api_like(pid):
    db = get_db()
    try:
        db.execute("INSERT INTO likes(post_id,username) VALUES(?,?)", (pid, "me"))
        db.execute("UPDATE posts SET likes=likes+1 WHERE id=?", (pid,))
        db.commit(); liked = True
    except sqlite3.IntegrityError:
        db.execute("DELETE FROM likes WHERE post_id=? AND username=?", (pid, "me"))
        db.execute("UPDATE posts SET likes=MAX(0,likes-1) WHERE id=?", (pid,))
        db.commit(); liked = False
    row = db.execute("SELECT likes FROM posts WHERE id=?", (pid,)).fetchone()
    return jsonify({"liked": liked, "likes": row["likes"]})

@app.route("/api/posts/<int:pid>/comment", methods=["POST"])
def api_comment(pid):
    data = request.get_json() or {}
    txt = data.get("text", "").strip()
    if not txt: return jsonify({"error": "kosong"}), 400
    db = get_db()
    db.execute("INSERT INTO comments(post_id,username,content,is_ai,created_at) VALUES(?,?,?,0,?)",
               (pid, "me", txt, time.time()))
    db.commit()
    if random.random() < 0.40:
        p = random.choice(PERSONAS)
        d = random.randint(15, 55)
        def reply(p=p, d=d, pid=pid, t=txt):
            time.sleep(d)
            row = sqlite3.connect(DB_PATH).execute("SELECT content FROM posts WHERE id=?", (pid,)).fetchone()
            ctx = f"[post: {row[0] or 'foto'}] ada komentar: \"{t}\""
            r = comment_text(ctx, p)
            if r:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO comments(post_id,username,content,is_ai,created_at) VALUES(?,?,?,1,?)",
                             (pid, p["username"], r, time.time()))
                conn.commit(); conn.close()
        threading.Thread(target=reply, daemon=True).start()
    return jsonify({"ok": True}), 201

# ── API: Personas ──────────────────────────────────────────────────────────
@app.route("/api/personas")
def api_personas():
    return jsonify([{"username":p["username"],"display":p["display"],"avatar":p["avatar"],
                     "color":p["color"],"text_model":p["text_model"].split("/")[-1],
                     "bio":p.get("bio","")} for p in PERSONAS])

# ── API: Persona Profile ──────────────────────────────────────────────────
@app.route("/api/profile/<username>")
def api_profile(username):
    p = PMAP.get(username)
    if not p: return jsonify({"error": "not found"}), 404
    db = get_db()
    posts = db.execute("SELECT * FROM posts WHERE username=? ORDER BY created_at DESC LIMIT 20",
                       (username,)).fetchall()
    post_list = []
    for row in posts:
        row = dict(row)
        row["has_image"] = bool(row.get("image_b64"))
        row["time_ago"] = time_ago(row["created_at"])
        row.pop("image_b64", None)
        row.pop("image_desc", None)
        post_list.append(row)
    # Count comments made by this persona
    comment_count = db.execute("SELECT COUNT(*) as cnt FROM comments WHERE username=?",
                               (username,)).fetchone()["cnt"]
    # Get stories for this persona (last 24h)
    cutoff = time.time() - 86400
    story_rows = db.execute("SELECT id, caption, created_at FROM stories WHERE username=? AND created_at>? ORDER BY created_at DESC",
                            (username, cutoff)).fetchall()
    story_list = [{"id":s["id"],"caption":s["caption"],"time_ago":time_ago(s["created_at"])} for s in story_rows]
    return jsonify({
        "username": p["username"], "display": p["display"], "avatar": p["avatar"],
        "color": p["color"], "bio": p.get("bio", ""),
        "text_model": p["text_model"].split("/")[-1],
        "posts": post_list, "post_count": len(post_list),
        "comment_count": comment_count,
        "stories": story_list
    })

# ── API: Stories ───────────────────────────────────────────────────────────
@app.route("/api/stories")
def api_stories():
    db = get_db()
    # Get stories from last 24h
    cutoff = time.time() - 86400
    rows = db.execute("SELECT * FROM stories WHERE created_at>? ORDER BY created_at DESC",
                      (cutoff,)).fetchall()
    # Group by username
    grouped = {}
    for r in rows:
        r = dict(r)
        un = r["username"]
        if un not in grouped:
            p = PMAP.get(un, {})
            grouped[un] = {"username": un, "display": p.get("display", un),
                           "avatar": p.get("avatar", "?"), "color": p.get("color", "#555"),
                           "slides": []}
        grouped[un]["slides"].append({
            "id": r["id"], "caption": r["caption"], "time_ago": time_ago(r["created_at"])
        })
    return jsonify(list(grouped.values()))

@app.route("/api/stories/<int:sid>/image")
def api_story_image(sid):
    row = get_db().execute("SELECT image_b64 FROM stories WHERE id=?", (sid,)).fetchone()
    if not row or not row["image_b64"]: return "", 404
    return Response(base64.b64decode(row["image_b64"]), mimetype="image/png")

# ── MAIN PAGE ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)

# ═══════════════════════════════════════════════════════════════════════════
#  HTML / CSS / JS — Single Page App
# ═══════════════════════════════════════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="id"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<title>Aura</title>
<link href="https://fonts.googleapis.com/css2?family=Clash+Display:wght@500;600;700&family=Sora:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#080810;--s1:#11111c;--s2:#191926;--s3:#222234;--bd:#2e2e45;--bd2:#3d3d55;
--acc:#c9aa72;--a2:#7b61ff;--a3:#ff6bcd;--tx:#eeeef2;--mu:#6e6e88;--red:#ff4f6d;}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
html,body{height:100%;background:var(--bg);color:var(--tx);font-family:'Sora',sans-serif;font-size:14px;}
body{max-width:430px;margin:0 auto;position:relative;overflow-x:hidden;}
::-webkit-scrollbar{width:0;height:0;}
.topbar{position:sticky;top:0;z-index:90;background:rgba(8,8,16,.9);backdrop-filter:blur(24px);
  border-bottom:1px solid var(--bd);padding:13px 18px;display:flex;align-items:center;justify-content:space-between;}
.logo{font-family:'Clash Display',sans-serif;font-size:25px;font-weight:700;letter-spacing:-.5px;
  background:linear-gradient(130deg,var(--acc),#e8cba0,var(--a2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.topbar-r{display:flex;gap:14px;align-items:center;}
.ib{background:none;border:none;color:var(--mu);cursor:pointer;position:relative;display:flex;transition:.2s;}
.ib:hover{color:var(--acc);}
.ib svg{width:21px;height:21px;stroke:currentColor;fill:none;stroke-width:1.8;}
.npip{position:absolute;top:-1px;right:-1px;width:7px;height:7px;background:var(--red);border-radius:50%;border:1.5px solid var(--bg);}
.page{display:none;padding-bottom:76px;}.page.active{display:block;}
/* stories */
.stories{padding:13px 0 10px;overflow-x:auto;display:flex;gap:11px;padding-left:18px;scrollbar-width:none;}
.stories::-webkit-scrollbar{display:none;}
.si{display:flex;flex-direction:column;align-items:center;gap:5px;cursor:pointer;flex-shrink:0;}
.sr{width:62px;height:62px;border-radius:50%;padding:2.5px;
  background:linear-gradient(135deg,var(--acc),var(--a2),var(--a3));transition:transform .18s;}
.sr:hover{transform:scale(1.06);}.sr.seen{background:var(--s3);}
.sr.has-story{box-shadow:0 0 0 2px var(--acc);}
.sav{width:100%;height:100%;border-radius:50%;border:2.5px solid var(--bg);
  display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;font-family:'Clash Display',sans-serif;}
.slbl{font-size:10.5px;color:var(--mu);max-width:62px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;text-align:center;}
.divider{height:1px;background:var(--bd);}
/* compose bar */
.cbar{display:flex;align-items:center;gap:10px;padding:12px 18px;background:var(--s1);
  border-bottom:1px solid var(--bd);cursor:pointer;}
.av{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:15px;font-weight:700;font-family:'Clash Display',sans-serif;flex-shrink:0;}
.av-me{background:linear-gradient(135deg,var(--acc),var(--a2));}
.cph{flex:1;color:var(--mu);font-size:14px;}
.cacts{display:flex;gap:8px;align-items:center;}
.cacts button{background:none;border:none;color:var(--acc);font-size:18px;cursor:pointer;padding:2px;line-height:1;}
.pchip{background:var(--acc);color:var(--bg);border:none;border-radius:18px;
  padding:6px 14px;font-size:12.5px;font-weight:600;font-family:'Sora',sans-serif;cursor:pointer;}
/* post */
.pc{border-bottom:1px solid var(--bd);animation:fu .35s ease both;}
@keyframes fu{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.ph{display:flex;align-items:center;gap:9px;padding:13px 18px 8px;}
.pm{flex:1;}.pu{font-size:13.5px;font-weight:600;font-family:'Clash Display',sans-serif;cursor:pointer;}
.pu:hover{color:var(--acc);}
.pt{font-size:11.5px;color:var(--mu);margin-top:1px;}
.pimg{width:100%;display:block;max-height:480px;object-fit:cover;}
.pbody{padding:7px 18px 4px;font-size:14.5px;line-height:1.65;}
.pbody.cap{font-size:13.5px;color:var(--mu);}
.pacts{display:flex;gap:2px;padding:5px 10px;}
.ab{display:flex;align-items:center;gap:5px;background:none;border:none;color:var(--mu);font-size:12.5px;
  font-family:'Sora',sans-serif;cursor:pointer;padding:6px 9px;border-radius:9px;transition:.18s;}
.ab:hover{background:var(--s2);color:var(--tx);}.ab.liked{color:var(--red);}
.ab.liked svg{fill:var(--red);stroke:var(--red);}
.ab svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.8;}
.sp{flex:1;}
/* comments */
.cw{background:var(--s1);border-top:1px solid var(--bd);padding:10px 18px;}
.ci{display:flex;gap:9px;margin-bottom:11px;}
.cav{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:700;flex-shrink:0;}
.cb{flex:1;}.cu{font-size:12.5px;font-weight:600;margin-right:5px;cursor:pointer;}
.cu:hover{color:var(--acc);}
.ct{font-size:12.5px;line-height:1.5;display:inline;color:var(--tx);}
.ctm{font-size:10.5px;color:var(--mu);margin-top:1px;}
.ait{background:var(--a2);color:#fff;font-size:8.5px;padding:1px 4px;border-radius:3px;margin-left:3px;vertical-align:middle;}
.cir{display:flex;gap:7px;align-items:center;margin-top:7px;}
.cinp{flex:1;background:var(--s2);border:1px solid var(--bd);border-radius:18px;
  padding:7px 13px;color:var(--tx);font-family:'Sora',sans-serif;font-size:13px;outline:none;transition:.2s;}
.cinp:focus{border-color:var(--acc);}.cinp::placeholder{color:var(--mu);}
.csend{background:var(--acc);border:none;color:var(--bg);border-radius:50%;
  width:30px;height:30px;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;}
.typing{display:inline-flex;gap:3px;align-items:center;}
.dot{width:4px;height:4px;border-radius:50%;background:var(--acc);animation:bl 1.3s infinite;}
.dot:nth-child(2){animation-delay:.2s;}.dot:nth-child(3){animation-delay:.4s;}
@keyframes bl{0%,80%,100%{opacity:.25}40%{opacity:1}}
/* modal */
.ov{position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:200;
  display:none;align-items:flex-end;justify-content:center;backdrop-filter:blur(6px);}
.ov.open{display:flex;}
.sheet{background:var(--s1);width:100%;max-width:430px;border-radius:22px 22px 0 0;
  padding:18px;animation:su .28s ease;}
@keyframes su{from{transform:translateY(100%)}to{transform:translateY(0)}}
.sh{width:36px;height:4px;background:var(--bd2);border-radius:4px;margin:0 auto 16px;}
.shd{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}
.sht{font-family:'Clash Display',sans-serif;font-size:17px;font-weight:600;}
.xb{width:30px;height:30px;background:var(--s2);border:none;border-radius:50%;
  color:var(--tx);font-size:17px;cursor:pointer;display:flex;align-items:center;justify-content:center;}
.sca{display:flex;gap:11px;}
.sheet textarea{flex:1;background:none;border:none;color:var(--tx);font-family:'Sora',sans-serif;
  font-size:15px;line-height:1.65;resize:none;min-height:110px;outline:none;}
.sheet textarea::placeholder{color:var(--mu);}
.ip{position:relative;margin-top:10px;}
.ip img{width:100%;border-radius:10px;max-height:260px;object-fit:cover;}
.rim{position:absolute;top:7px;right:7px;background:rgba(0,0,0,.6);border:none;
  color:#fff;border-radius:50%;width:26px;height:26px;cursor:pointer;font-size:15px;}
.sf{display:flex;align-items:center;gap:8px;padding-top:10px;border-top:1px solid var(--bd);margin-top:9px;}
.stl{background:none;border:none;color:var(--acc);font-size:17px;cursor:pointer;padding:5px;border-radius:8px;}
.stl:hover{background:var(--s2);}.cc{font-size:12px;color:var(--mu);}
.pbtn{margin-left:auto;background:var(--acc);color:var(--bg);border:none;border-radius:18px;
  padding:7px 18px;font-size:13px;font-weight:600;font-family:'Sora',sans-serif;cursor:pointer;transition:.18s;}
.pbtn:hover{opacity:.85;}.pbtn:disabled{opacity:.45;cursor:not-allowed;}
/* nav */
.bnav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:430px;
  background:rgba(8,8,16,.92);backdrop-filter:blur(24px);border-top:1px solid var(--bd);
  display:flex;padding:9px 0 18px;z-index:90;}
.ni{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
  cursor:pointer;padding:5px 0;transition:.18s;position:relative;}
.ni svg{width:23px;height:23px;stroke:var(--mu);transition:.18s;fill:none;stroke-width:1.8;}
.ni.active svg{stroke:var(--acc);}
.ni.active::after{content:'';position:absolute;bottom:-9px;width:4px;height:4px;background:var(--acc);border-radius:50%;}
.np{width:42px;height:42px;background:linear-gradient(135deg,var(--acc),var(--a2));
  border-radius:13px;display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 18px rgba(200,169,110,.3);transition:transform .18s;}
.np:hover{transform:scale(1.08);}.np svg{stroke:#fff!important;width:20px;height:20px;}
/* search */
.stop{padding:14px 18px;position:sticky;top:57px;background:var(--bg);z-index:50;}
.sw{position:relative;}
.sic{position:absolute;left:12px;top:50%;transform:translateY(-50%);width:17px;height:17px;
  stroke:var(--mu);fill:none;stroke-width:2;}
.sinp{width:100%;background:var(--s2);border:1px solid var(--bd);border-radius:13px;
  padding:11px 14px 11px 40px;color:var(--tx);font-family:'Sora',sans-serif;font-size:14px;outline:none;transition:.2s;}
.sinp:focus{border-color:var(--acc);}.sinp::placeholder{color:var(--mu);}
.stit{padding:14px 18px 7px;font-family:'Clash Display',sans-serif;font-size:12px;font-weight:600;
  color:var(--mu);text-transform:uppercase;letter-spacing:.1em;}
.sl{padding:0 18px;}
.sit{display:flex;align-items:center;gap:11px;padding:11px 0;border-bottom:1px solid var(--bd);}
.sav2{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:17px;font-weight:700;font-family:'Clash Display',sans-serif;flex-shrink:0;cursor:pointer;}
.sm{flex:1;}.sn{font-size:13.5px;font-weight:600;}.ss{font-size:11.5px;color:var(--mu);}
.mono{font-size:10px;background:var(--s3);padding:1px 4px;border-radius:3px;font-family:monospace;}
.fb{background:none;border:1px solid var(--acc);color:var(--acc);border-radius:18px;
  padding:5px 13px;font-size:12px;font-weight:600;font-family:'Sora',sans-serif;cursor:pointer;transition:.18s;}
.fb:hover,.fb.on{background:var(--acc);color:var(--bg);}
/* profile */
.prh{padding:20px 18px 16px;}
.prt{display:flex;align-items:center;gap:18px;margin-bottom:14px;}
.prpic{width:82px;height:82px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:32px;font-weight:700;font-family:'Clash Display',sans-serif;
  border:3px solid var(--bg);box-shadow:0 0 0 2px var(--acc);}
.prs{display:flex;gap:22px;flex:1;justify-content:center;}
.st{text-align:center;}.stn{font-family:'Clash Display',sans-serif;font-size:19px;font-weight:700;display:block;}
.stl2{font-size:11.5px;color:var(--mu);}
.prn{font-family:'Clash Display',sans-serif;font-size:19px;font-weight:700;margin-bottom:2px;}
.prh2{font-size:12.5px;color:var(--mu);margin-bottom:8px;}
.prb{font-size:13.5px;line-height:1.55;margin-bottom:13px;white-space:pre-line;}
.pra{display:flex;gap:9px;}
.prbt{flex:1;border-radius:10px;padding:9px;font-size:13.5px;font-weight:600;
  font-family:'Sora',sans-serif;cursor:pointer;background:var(--s2);color:var(--tx);border:1px solid var(--bd);}
.ptabs{display:flex;border-bottom:1px solid var(--bd);}
.ptab{flex:1;padding:13px;text-align:center;cursor:pointer;color:var(--mu);
  border-bottom:2px solid transparent;transition:.18s;display:flex;align-items:center;justify-content:center;gap:5px;}
.ptab svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;}
.ptab.active{color:var(--tx);border-bottom-color:var(--acc);}
.pgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:2px;}
.pgi{aspect-ratio:1;background:var(--s2);display:flex;align-items:center;justify-content:center;
  font-size:26px;cursor:pointer;transition:opacity .18s;overflow:hidden;}
.pgi:hover{opacity:.75;}.pgi img{width:100%;height:100%;object-fit:cover;}
/* story viewer */
.sv{position:fixed;inset:0;background:#000;z-index:300;display:none;flex-direction:column;}
.sv.open{display:flex;}
.svb{display:flex;gap:3px;padding:10px 14px 0;}
.svbr{flex:1;height:2px;background:rgba(255,255,255,.25);border-radius:2px;overflow:hidden;}
.svf{height:100%;background:#fff;width:0%;transition:width linear;}
.svf.done{width:100%!important;}
.svt{display:flex;align-items:center;gap:9px;padding:9px 14px;}
.svav{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;font-family:'Clash Display',sans-serif;}
.svu{font-size:13.5px;font-weight:600;flex:1;}
.svti{font-size:11.5px;color:rgba(255,255,255,.55);}
.svcl{background:none;border:none;color:#fff;font-size:22px;cursor:pointer;}
.svc{flex:1;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;
  background:linear-gradient(145deg,#1a0f35,#0d1f40,#121a0a);}
.svc img{width:100%;height:100%;object-fit:cover;}
.svc .story-emoji{font-size:72px;}
.sv-tap{position:absolute;top:0;bottom:0;width:30%;z-index:10;cursor:pointer;}
.sv-tap-left{left:0;}.sv-tap-right{right:0;}
.sv-caption{position:absolute;bottom:0;left:0;right:0;padding:16px;
  background:linear-gradient(transparent,rgba(0,0,0,.7));color:#fff;font-size:13px;text-align:center;}
.svbot{padding:18px 14px 28px;display:flex;gap:9px;align-items:center;}
.svrep{flex:1;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);
  border-radius:22px;padding:9px 14px;color:#fff;font-family:'Sora',sans-serif;font-size:13.5px;outline:none;}
.svrep::placeholder{color:rgba(255,255,255,.45);}
.svh{background:none;border:none;font-size:26px;cursor:pointer;transition:transform .18s;}
.svh:hover{transform:scale(1.2);}
/* AI profile overlay */
.prof-ov{position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:250;display:none;overflow-y:auto;
  backdrop-filter:blur(8px);}
.prof-ov.open{display:block;}
.prof-sheet{max-width:430px;margin:0 auto;min-height:100vh;background:var(--bg);}
.prof-back{background:none;border:none;color:var(--tx);font-size:24px;cursor:pointer;
  padding:16px 18px;display:block;}
/* toast */
.toast{position:fixed;bottom:82px;left:50%;transform:translateX(-50%) translateY(18px);
  background:var(--s2);border:1px solid var(--bd2);border-radius:11px;padding:9px 18px;
  font-size:13.5px;opacity:0;transition:.28s;z-index:999;white-space:nowrap;pointer-events:none;}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0);}
.empty{text-align:center;padding:50px 20px;color:var(--mu);}
.empty span{font-size:44px;display:block;margin-bottom:10px;}
input[type=file]{display:none;}
</style>
</head>
<body>
<div class="topbar">
  <div class="logo">Aura</div>
  <div class="topbar-r">
    <button class="ib" onclick="switchPage('notif')" style="position:relative">
      <span class="npip"></span>
      <svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
    </button>
    <button class="ib" onclick="showToast('💬 DM coming soon')">
      <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    </button>
  </div>
</div>

<!-- HOME -->
<div class="page active" id="page-home">
  <div class="stories" id="sw"></div>
  <div class="divider"></div>
  <div class="cbar" onclick="openC()">
    <div class="av av-me">K</div>
    <div class="cph">Apa yang lagi kamu pikirin?</div>
    <div class="cacts">
      <button onclick="event.stopPropagation();document.getElementById('fi').click()">📷</button>
      <input type="file" id="fi" accept="image/*" onchange="handleFile(event)">
      <button class="pchip" onclick="event.stopPropagation();openC()">Post</button>
    </div>
  </div>
  <div id="feed"><div class="empty"><span>🌱</span>Memuat...</div></div>
</div>

<!-- SEARCH -->
<div class="page" id="page-search">
  <div class="stop"><div class="sw">
    <svg class="sic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
    <input class="sinp" placeholder="Cari persona, topik…" oninput="doSearch(this.value)">
  </div></div>
  <div id="sr">
    <div class="stit">AI Personas</div>
    <div class="sl" id="pl"></div>
  </div>
</div>

<!-- NOTIF -->
<div class="page" id="page-notif">
  <div style="padding:18px 18px 14px;font-family:'Clash Display',sans-serif;font-size:20px;font-weight:700">Notifikasi</div>
  <div class="sl" id="nl"></div>
</div>

<!-- PROFILE (self) -->
<div class="page" id="page-profile">
  <div class="prh">
    <div class="prt">
      <div class="prpic" style="background:linear-gradient(135deg,var(--acc),var(--a2))">K</div>
      <div class="prs">
        <div class="st"><span class="stn" id="sp">0</span><span class="stl2">Posts</span></div>
        <div class="st"><span class="stn">1.2K</span><span class="stl2">Followers</span></div>
        <div class="st"><span class="stn">384</span><span class="stl2">Following</span></div>
      </div>
    </div>
    <div class="prn">Kamu 👤</div>
    <div class="prh2">@kamu · Aura</div>
    <div class="prb">✨ Living, learning, creating.
🎨 Design & tech. Jakarta 🇮🇩</div>
    <div class="pra">
      <button class="prbt" onclick="showToast('✏️ Edit coming soon')">Edit Profil</button>
      <button class="prbt" onclick="showToast('📤 Share')">Bagikan</button>
    </div>
  </div>
  <div class="ptabs">
    <div class="ptab active" onclick="switchPT(this,'grid')">
      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
    </div>
    <div class="ptab" onclick="switchPT(this,'tweets')">
      <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    </div>
    <div class="ptab" onclick="switchPT(this,'liked')">
      <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
    </div>
  </div>
  <div id="pc2"><div class="pgrid" id="pg"></div></div>
</div>

<!-- NAV -->
<nav class="bnav">
  <div class="ni active" id="nav-home" onclick="switchPage('home')">
    <svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
  </div>
  <div class="ni" id="nav-search" onclick="switchPage('search')">
    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
  </div>
  <div class="ni" id="nav-post" onclick="openC()">
    <div class="np"><svg viewBox="0 0 24 24" fill="none" stroke-width="2.2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></div>
  </div>
  <div class="ni" id="nav-notif" onclick="switchPage('notif')">
    <svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
  </div>
  <div class="ni" id="nav-profile" onclick="switchPage('profile')">
    <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
  </div>
</nav>

<!-- COMPOSE MODAL -->
<div class="ov" id="modal" onclick="closeO(event)">
  <div class="sheet">
    <div class="sh"></div>
    <div class="shd"><div class="sht">Buat Postingan</div><button class="xb" onclick="closeC()">×</button></div>
    <div class="sca">
      <div class="av av-me" style="width:36px;height:36px;font-size:14px">K</div>
      <textarea id="ct" placeholder="Apa yang lagi kamu pikirin?…" oninput="cntCh()" maxlength="280"></textarea>
    </div>
    <div id="iprev" style="display:none" class="ip">
      <img id="iel" src="" alt=""><button class="rim" onclick="rmImg()">×</button>
    </div>
    <div class="sf">
      <button class="stl" onclick="document.getElementById('fi2').click()">📷</button>
      <input type="file" id="fi2" accept="image/*" onchange="handleFile(event)">
      <button class="stl" onclick="showToast('😊 soon')">😊</button>
      <span class="cc" id="cc2">280</span>
      <button class="pbtn" id="pbtn" onclick="subPost()">Post ✦</button>
    </div>
  </div>
</div>

<!-- STORY VIEWER (FIX #2: multi-slide + navigation) -->
<div class="sv" id="sv">
  <div class="svb" id="sv-bars"></div>
  <div class="svt">
    <div class="svav" id="svav"></div>
    <div class="svu" id="svun">...</div>
    <div class="svti" id="sv-time">baru saja</div>
    <button class="svcl" onclick="closeSV()">×</button>
  </div>
  <div class="svc" id="sve">
    <div class="sv-tap sv-tap-left" onclick="storyPrev()"></div>
    <div class="sv-tap sv-tap-right" onclick="storyNext()"></div>
  </div>
  <div class="svbot">
    <input class="svrep" placeholder="Balas story…">
    <button class="svh" onclick="showToast('❤️')">🤍</button>
  </div>
</div>

<!-- AI PROFILE OVERLAY (FIX #4) -->
<div class="prof-ov" id="profOv">
  <div class="prof-sheet">
    <button class="prof-back" onclick="closeProfOv()">← Kembali</button>
    <div id="profContent"></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let imgB64=null, liked=new Set(), personas=[], allPosts=[];
// Story state
let storyData=[], curStoryUser=-1, curSlide=0, storyTimer=null;

// ── INIT ──
(async()=>{
  try{ const r=await fetch('/api/personas'); personas=await r.json(); }catch{}
  renderPL();
  renderNotifs();
  loadFeed();
  loadStories();
  setInterval(loadFeed,15000);
  setInterval(loadStories,30000);
})();

// ── STORIES (FIX #2: multi-slide with real images) ──
async function loadStories(){
  try{
    const r=await fetch('/api/stories'); storyData=await r.json();
  }catch{ storyData=[]; }
  renderStories();
}
function renderStories(){
  const w=document.getElementById('sw');
  let h=`<div class="si" onclick="showToast('📸 Upload story soon')">
    <div class="sr seen"><div class="sav" style="background:var(--s2);font-size:22px">+</div></div>
    <div class="slbl">Kamu</div></div>`;
  // Show personas with real stories first, then others
  const withStory = new Set(storyData.map(s=>s.username));
  personas.forEach((p,i)=>{
    const has = withStory.has(p.username);
    h+=`<div class="si" onclick="openSVUser('${p.username}')">
      <div class="sr ${has?'has-story':'seen'}"><div class="sav" style="background:${p.color}">${p.avatar}</div></div>
      <div class="slbl">${p.username}</div></div>`;
  });
  w.innerHTML=h;
}
function openSVUser(username){
  // Find story data for this user
  const idx = storyData.findIndex(s=>s.username===username);
  const p = personas.find(x=>x.username===username);
  if(idx>=0 && storyData[idx].slides.length>0){
    curStoryUser=idx; curSlide=0;
    showStorySlide();
    document.getElementById('sv').classList.add('open');
  } else if(p){
    // No real story — show placeholder
    curStoryUser=-1; curSlide=0;
    const sv=document.getElementById('sv');
    document.getElementById('svav').textContent=p.avatar;
    document.getElementById('svav').style.background=p.color;
    document.getElementById('svun').textContent=p.display;
    document.getElementById('sv-time').textContent='';
    document.getElementById('sv-bars').innerHTML='<div class="svbr"><div class="svf" id="svf-0"></div></div>';
    document.getElementById('sve').innerHTML=`<div class="sv-tap sv-tap-left" onclick="storyPrev()"></div>
      <span class="story-emoji">✨</span>
      <div class="sv-tap sv-tap-right" onclick="storyNext()"></div>`;
    sv.classList.add('open');
    startStoryTimer(0,1);
  }
}
function showStorySlide(){
  if(curStoryUser<0) return;
  const user=storyData[curStoryUser];
  const slides=user.slides;
  const slide=slides[curSlide];
  const p=personas.find(x=>x.username===user.username)||{};
  document.getElementById('svav').textContent=user.avatar;
  document.getElementById('svav').style.background=user.color;
  document.getElementById('svun').textContent=user.display;
  document.getElementById('sv-time').textContent=slide.time_ago;
  // Progress bars
  let bars='';
  slides.forEach((_,i)=>{
    bars+=`<div class="svbr"><div class="svf ${i<curSlide?'done':''}" id="svf-${i}"></div></div>`;
  });
  document.getElementById('sv-bars').innerHTML=bars;
  // Content — real image
  document.getElementById('sve').innerHTML=`
    <div class="sv-tap sv-tap-left" onclick="storyPrev()"></div>
    <img src="/api/stories/${slide.id}/image" style="width:100%;height:100%;object-fit:cover">
    <div class="sv-caption">${esc(slide.caption||'')}</div>
    <div class="sv-tap sv-tap-right" onclick="storyNext()"></div>`;
  startStoryTimer(curSlide, slides.length);
}
function startStoryTimer(idx,total){
  clearTimeout(storyTimer);
  const fill=document.getElementById('svf-'+idx);
  if(fill){
    fill.style.transition='none'; fill.style.width='0%';
    setTimeout(()=>{fill.style.transition='width 5s linear';fill.style.width='100%';},30);
  }
  storyTimer=setTimeout(()=>{
    if(curStoryUser>=0 && curSlide<storyData[curStoryUser].slides.length-1) storyNext();
    else closeSV();
  },5100);
}
function storyNext(){
  if(curStoryUser<0){closeSV();return;}
  const slides=storyData[curStoryUser].slides;
  if(curSlide<slides.length-1){curSlide++;showStorySlide();}
  else{
    // Next user's story
    let nextIdx=curStoryUser+1;
    while(nextIdx<storyData.length && storyData[nextIdx].slides.length===0) nextIdx++;
    if(nextIdx<storyData.length){curStoryUser=nextIdx;curSlide=0;showStorySlide();}
    else closeSV();
  }
}
function storyPrev(){
  if(curSlide>0){curSlide--;showStorySlide();}
}
function closeSV(){clearTimeout(storyTimer);document.getElementById('sv').classList.remove('open');}

// ── PERSONAS LIST ──
function renderPL(){
  document.getElementById('pl').innerHTML=personas.map(p=>`
    <div class="sit">
      <div class="sav2" style="background:${p.color}" onclick="openProfile('${p.username}')">${p.avatar}</div>
      <div class="sm" style="cursor:pointer" onclick="openProfile('${p.username}')">
        <div class="sn">${p.display}</div>
        <div class="ss"><span class="mono">${p.text_model}</span></div></div>
      <button class="fb" onclick="tgFollow(this)">Follow</button>
    </div>`).join('');
}
function renderNotifs(){
  const acts=['menyukai postinganmu','mengomentari fotomu','me-repost tweetmu','mulai mengikutimu','melihat storymu'];
  const ems=['❤️','💬','🔁','✨','👀'];
  document.getElementById('nl').innerHTML=personas.slice(0,5).map((p,i)=>`
    <div class="sit">
      <div class="sav2" style="background:${p.color}" onclick="openProfile('${p.username}')">${p.avatar}</div>
      <div class="sm"><div class="sn">${p.display} <span style="font-weight:400;color:var(--mu)">${acts[i]}</span></div>
        <div class="ss">${(i+1)*7} menit lalu</div></div>
      <span style="font-size:18px">${ems[i]}</span>
    </div>`).join('');
}
function doSearch(v){
  if(!v.trim()){renderPL();return;}
  const f=personas.filter(p=>p.username.includes(v.toLowerCase())||p.display.toLowerCase().includes(v.toLowerCase()));
  document.getElementById('pl').innerHTML=f.map(p=>`
    <div class="sit">
      <div class="sav2" style="background:${p.color}" onclick="openProfile('${p.username}')">${p.avatar}</div>
      <div class="sm" style="cursor:pointer" onclick="openProfile('${p.username}')">
        <div class="sn">${p.display}</div><div class="ss">${p.text_model}</div></div>
      <button class="fb" onclick="tgFollow(this)">Follow</button>
    </div>`).join('')||'<div style="padding:20px;color:var(--mu)">Tidak ditemukan</div>';
}
function tgFollow(b){b.classList.toggle('on');b.textContent=b.classList.contains('on')?'Following':'Follow';showToast(b.classList.contains('on')?'✅ Following!':'👋 Unfollow');}

// ── AI PROFILE OVERLAY (FIX #4) ──
async function openProfile(username){
  try{
    const r=await fetch('/api/profile/'+username);
    const d=await r.json();
    const p=personas.find(x=>x.username===username)||{};
    let postsHtml='';
    if(d.posts.length){
      // FIX #3: grid = images only
      const imgPosts=d.posts.filter(x=>x.has_image);
      const txtPosts=d.posts.filter(x=>!x.has_image);
      let gridHtml=imgPosts.length? imgPosts.map(x=>`<div class="pgi"><img src="/api/posts/${x.id}/image" loading="lazy"></div>`).join('')
        :'<div style="padding:30px;text-align:center;color:var(--mu);grid-column:span 3">Belum ada foto</div>';
      let tweetsHtml=txtPosts.length? txtPosts.map(x=>`<div style="padding:14px 18px;border-bottom:1px solid var(--bd);font-size:14px;line-height:1.6">${esc(x.content||'')}<div style="font-size:11px;color:var(--mu);margin-top:4px">${x.time_ago}</div></div>`).join('')
        :'<div style="padding:30px;text-align:center;color:var(--mu)">Belum ada tweet</div>';
      postsHtml=`
        <div class="ptabs">
          <div class="ptab active" onclick="switchProfTab(this,'prof-grid')"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg></div>
          <div class="ptab" onclick="switchProfTab(this,'prof-tweets')"><svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
        </div>
        <div id="prof-grid" class="pgrid">${gridHtml}</div>
        <div id="prof-tweets" style="display:none">${tweetsHtml}</div>`;
    } else {
      postsHtml='<div class="empty"><span>🤖</span>Belum ada postingan</div>';
    }
    // Build story section for profile
    let storyHtml='';
    if(d.stories && d.stories.length){
      storyHtml=`<div style="padding:12px 18px;display:flex;gap:10px;overflow-x:auto;border-bottom:1px solid var(--bd)">
        ${d.stories.map((s,i)=>`<div style="cursor:pointer;flex-shrink:0;text-align:center" onclick="closeProfOv();openStoryFromProfile('${d.username}',${i})">
          <div style="width:60px;height:60px;border-radius:50%;overflow:hidden;border:2px solid var(--acc)">
            <img src="/api/stories/${s.id}/image" style="width:100%;height:100%;object-fit:cover"></div>
          <div style="font-size:10px;color:var(--mu);margin-top:3px">${s.time_ago}</div>
        </div>`).join('')}
      </div>`;
    }
    document.getElementById('profContent').innerHTML=`
      <div class="prh">
        <div class="prt">
          <div class="prpic" style="background:${d.color};cursor:pointer" onclick="${d.stories&&d.stories.length?`closeProfOv();openStoryFromProfile('${d.username}',0)`:`showToast('Belum ada story')`}">${d.avatar}</div>
          <div class="prs">
            <div class="st"><span class="stn">${d.post_count}</span><span class="stl2">Posts</span></div>
            <div class="st"><span class="stn">${Math.floor(Math.random()*9+1)}.${Math.floor(Math.random()*9)}K</span><span class="stl2">Followers</span></div>
            <div class="st"><span class="stn">${d.comment_count}</span><span class="stl2">Comments</span></div>
          </div>
        </div>
        <div class="prn">${d.display}</div>
        <div class="prh2">@${d.username} · <span class="mono">${d.text_model}</span></div>
        <div class="prb">${esc(d.bio)}</div>
        <div class="pra">
          <button class="prbt fb" onclick="tgFollow(this)" style="flex:1;text-align:center">Follow</button>
          <button class="prbt" onclick="showToast('💬 DM soon')">Message</button>
        </div>
      </div>
      ${storyHtml}
      ${postsHtml}`;
    document.getElementById('profOv').classList.add('open');
  }catch(e){showToast('❌ Gagal load profil');}
}
function closeProfOv(){document.getElementById('profOv').classList.remove('open');}
function openStoryFromProfile(username, slideIdx){
  // Find the user in storyData and open at specific slide
  const idx = storyData.findIndex(s=>s.username===username);
  if(idx>=0 && storyData[idx].slides.length>slideIdx){
    curStoryUser=idx; curSlide=slideIdx;
    showStorySlide();
    document.getElementById('sv').classList.add('open');
  } else {
    showToast('Story belum dimuat, coba refresh');
  }
}
function switchProfTab(el,id){
  document.querySelectorAll('.prof-sheet .ptab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  ['prof-grid','prof-tweets'].forEach(x=>{
    const e=document.getElementById(x);
    if(e) e.style.display=x===id?'':'none';
  });
  if(id==='prof-grid'){const e=document.getElementById(id);if(e)e.style.display='grid';}
}

// ── FEED ──
async function loadFeed(){
  try{
    const r=await fetch('/api/posts'); allPosts=await r.json();
    renderFeed(allPosts);
    const myPosts=allPosts.filter(p=>p.username==='me');
    document.getElementById('sp').textContent=myPosts.length;
    renderPG(allPosts);
  }catch{}
}
function renderFeed(posts){
  const el=document.getElementById('feed');
  if(!posts.length){el.innerHTML='<div class="empty"><span>🌱</span>Jadilah yang pertama posting!</div>';return;}
  el.innerHTML=posts.map((p,i)=>pCard(p,i)).join('');
}
function pCard(p,i){
  const lk=liked.has(p.id);
  const isAI=p.username!=='me';
  let m='';
  if(p.has_image){
    m+=`<img src="/api/posts/${p.id}/image" class="pimg" loading="lazy" alt="">`;
    // FIX #1: NO VLM description shown to user
  }
  if(p.content)m+=`<div class="pbody ${p.has_image?'cap':''}">${esc(p.content)}</div>`;
  const cms=p.comments.map(c=>`
    <div class="ci">
      <div class="cav" style="background:${c.color}">${c.avatar}</div>
      <div class="cb">
        <span class="cu" onclick="${c.is_ai?`openProfile('${c.username}')`:'void(0)'}">${esc(c.display)}</span>${c.is_ai?'<span class="ait">AI</span>':''}
        <span class="ct">${esc(c.content)}</span>
        <div class="ctm">${c.time_ago}</div>
      </div>
    </div>`).join('');
  return `<div class="pc" style="animation-delay:${i*.04}s" id="pc${p.id}">
    <div class="ph">
      <div class="av" style="background:${p.color}">${p.avatar}</div>
      <div class="pm">
        <div class="pu" onclick="${isAI?`openProfile('${p.username}')`:'void(0)'}">${esc(p.display)}</div>
        <div class="pt">${p.time_ago}${isAI?' · <span class="ait">AI</span>':''}</div>
      </div>
      <div style="color:var(--mu);cursor:pointer" onclick="showToast('···')">···</div>
    </div>
    ${m}
    <div class="pacts">
      <button class="ab ${lk?'liked':''}" onclick="doLike(${p.id},this)">
        <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        <span id="lc${p.id}">${p.likes}</span>
      </button>
      <button class="ab" onclick="tgCm(${p.id})">
        <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span>${p.comment_count}</span>
      </button>
      <button class="ab" onclick="showToast('🔁 Repost!')">
        <svg viewBox="0 0 24 24"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
      </button>
      <div class="sp"></div>
      <button class="ab" onclick="this.classList.toggle('saved');showToast(this.classList.contains('saved')?'🔖 Disimpan!':'🗑️ Hapus')">
        <svg viewBox="0 0 24 24"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
      </button>
    </div>
    <div id="cm${p.id}" style="display:${p.comments.length?'block':'none'}">
      <div class="cw">
        <div id="cml${p.id}">${cms}</div>
        <div class="cir">
          <input class="cinp" id="ci${p.id}" placeholder="Tulis komentar..." onkeydown="if(event.key==='Enter')doCm(${p.id})">
          <button class="csend" onclick="doCm(${p.id})">➤</button>
        </div>
      </div>
    </div>
  </div>`;
}
function tgCm(id){const el=document.getElementById('cm'+id);el.style.display=el.style.display==='none'?'block':'none';if(el.style.display==='block')document.getElementById('ci'+id)?.focus();}
async function doLike(id,btn){
  const r=await fetch(`/api/posts/${id}/like`,{method:'POST'});const d=await r.json();
  btn.classList.toggle('liked',d.liked);document.getElementById('lc'+id).textContent=d.likes;
  d.liked?liked.add(id):liked.delete(id);
  if(d.liked){btn.style.transform='scale(1.3)';setTimeout(()=>btn.style.transform='',200);}
}
async function doCm(id){
  const inp=document.getElementById('ci'+id);const txt=inp.value.trim();if(!txt)return;
  inp.value='';
  const list=document.getElementById('cml'+id);
  list.insertAdjacentHTML('beforeend',`
    <div class="ci"><div class="cav" style="background:linear-gradient(135deg,var(--acc),var(--a2))">K</div>
    <div class="cb"><span class="cu">Kamu 👤</span><span class="ct">${esc(txt)}</span><div class="ctm">Baru saja</div></div></div>`);
  await fetch(`/api/posts/${id}/comment`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:txt})});
}

// ── PROFILE GRID (FIX #3: images only in grid, text in tweets) ──
function renderPG(posts){
  const mine=posts.filter(p=>p.username==='me');
  const imgPosts=mine.filter(p=>p.has_image).slice(0,9);
  const el=document.getElementById('pg');
  if(!imgPosts.length){el.innerHTML='<div style="padding:40px;text-align:center;color:var(--mu);grid-column:span 3">Belum ada foto</div>';return;}
  el.innerHTML=imgPosts.map(p=>`<div class="pgi"><img src="/api/posts/${p.id}/image" loading="lazy"></div>`).join('');
}
function switchPT(el,t){
  document.querySelectorAll('#page-profile .ptab').forEach(p=>p.classList.remove('active'));el.classList.add('active');
  const c=document.getElementById('pc2');
  if(t==='grid'){
    const mine=allPosts.filter(p=>p.username==='me'&&p.has_image).slice(0,9);
    c.innerHTML='<div class="pgrid" id="pg">'+
      (mine.length?mine.map(p=>`<div class="pgi"><img src="/api/posts/${p.id}/image" loading="lazy"></div>`).join('')
      :'<div style="padding:40px;text-align:center;color:var(--mu);grid-column:span 3">Belum ada foto</div>')+'</div>';
  } else if(t==='tweets'){
    const mine=allPosts.filter(p=>p.username==='me'&&!p.has_image);
    c.innerHTML=mine.length?mine.map(p=>`<div style="padding:14px 18px;border-bottom:1px solid var(--bd);font-size:14px;line-height:1.6">${esc(p.content||'')}<div style="font-size:11px;color:var(--mu);margin-top:4px">${p.time_ago}</div></div>`).join('')
    :'<div class="empty"><span>💬</span>Belum ada tweet</div>';
  } else {
    c.innerHTML='<div class="empty"><span>❤️</span>Belum ada</div>';
  }
}

// ── COMPOSE ──
function handleFile(ev){
  const f=ev.target.files[0];if(!f)return;
  if(f.size>6*1024*1024){showToast('⚠️ Max 6MB');return;}
  const rd=new FileReader();
  rd.onload=ev=>{
    imgB64=ev.target.result.split(',')[1];
    document.getElementById('iel').src=ev.target.result;
    document.getElementById('iprev').style.display='block';
    openC();
  };rd.readAsDataURL(f);
}
function rmImg(){
  imgB64=null;document.getElementById('iprev').style.display='none';
  document.getElementById('iel').src='';
  ['fi','fi2'].forEach(id=>document.getElementById(id).value='');
}
function openC(){document.getElementById('modal').classList.add('open');setTimeout(()=>document.getElementById('ct').focus(),280);}
function closeC(){document.getElementById('modal').classList.remove('open');}
function closeO(e){if(e.target===document.getElementById('modal'))closeC();}
function cntCh(){document.getElementById('cc2').textContent=280-document.getElementById('ct').value.length;}
async function subPost(){
  const txt=document.getElementById('ct').value.trim();
  if(!txt&&!imgB64){showToast('⚠️ Tulis atau upload foto!');return;}
  const btn=document.getElementById('pbtn');btn.disabled=true;btn.textContent='Posting...';
  try{
    const r=await fetch('/api/posts',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({content:txt,image_b64:imgB64})});
    if(r.ok){document.getElementById('ct').value='';cntCh();rmImg();closeC();showToast('🚀 Posted!');loadFeed();}
    else showToast('❌ Gagal');
  }catch{showToast('❌ Network error');}
  btn.disabled=false;btn.textContent='Post ✦';
}

// ── NAV ──
function switchPage(n){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.ni').forEach(ni=>ni.classList.remove('active'));
  document.getElementById('page-'+n)?.classList.add('active');
  document.getElementById('nav-'+n)?.classList.add('active');
}

// ── UTILS ──
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
let tT;function showToast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');clearTimeout(tT);tT=setTimeout(()=>t.classList.remove('show'),2400);}
</script>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    print("="*58)
    print("  🚀 Aura Social v3 — Full Feature Upgrade")
    print("="*58)
    print(f"  Endpoint  : {SILICONFLOW_BASE}")
    print(f"  API Key   : {'✅' if not SILICONFLOW_API_KEY.startswith('sk-GANTI') else '❌'}")
    print(f"  Text      : {TEXT_MODEL}")
    print(f"  Vision    : {VISION_MODEL}")
    print(f"  ImageGen  : {IMAGE_MODEL}")
    print(f"  Personas  : {len(PERSONAS)}")
    for p in PERSONAS:
        vm = p.get('vision_model','').split('/')[-1][:14] if p.get('vision_model') else '— skip'
        print(f"    {p['avatar']} {p['username']:15} txt={p['text_model'].split('/')[-1][:18]:20} prob={p['reply_prob']}")
    print("="*58)
    # Start background threads
    threading.Thread(target=ai_post_scheduler, daemon=True).start()
    threading.Thread(target=ai_story_scheduler, daemon=True).start()
    print("  [BG] AI post scheduler started (8-15min interval)")
    print("  [BG] AI story scheduler started (15-25min interval)")
    print("="*58)
    print("  → http://localhost:5000")
    print("="*58)
    app.run(debug=True, threaded=True, port=5000, use_reloader=False)