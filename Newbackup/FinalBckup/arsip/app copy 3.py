"""
Aura Social v2 — Full UI + Cross-Model AI Personas
6 persona, masing2 punya text_model + vision_model sendiri.
Run: python app.py → http://localhost:5000
"""
import time, random, base64, sqlite3, threading, requests, re
from flask import Flask, request, jsonify, render_template_string, g, Response

SILICONFLOW_API_KEY = "sk-yaluviakgcbvoxtgbgxysgwucjwjebpmbwxrsihakmwuagou"
SILICONFLOW_BASE    = "https://api.siliconflow.com/v1"
DB_PATH             = "aura.db"

PERSONAS = [
    {"username":"maya_art","display":"Maya ✨","avatar":"M","color":"linear-gradient(135deg,#ff6b6b,#ffa500)",
     "text_model":"Qwen/Qwen3-32B","vision_model":"Qwen/Qwen2.5-VL-32B-Instruct",
     "reply_prob":0.55,"delay_range":(25,110),
     "personality":"Kamu Maya, seniman digital 24th Bandung. Komentar singkat, kadang roast, kadang relate. Gak lebay. Max 1 kalimat. Contoh: 'anjay relate','emang sih'. JANGAN: keren, semangat, hebat."},
    {"username":"rizky_dev","display":"Rizky 💻","avatar":"R","color":"linear-gradient(135deg,#667eea,#764ba2)",
     "text_model":"deepseek-ai/DeepSeek-V3","vision_model":"Qwen/Qwen3-VL-32B-Instruct",
     "reply_prob":0.40,"delay_range":(60,200),
     "personality":"Kamu Rizky, developer 27th Jakarta. Jujur, sering roast ringan, nyeletuk. Jaksel-style. Max 1 kalimat. Gaya: 'wkwk gw juga','bro ini literally gw','yha emang'."},
    {"username":"nadiafood","display":"Nadia 🍜","avatar":"N","color":"linear-gradient(135deg,#11998e,#38ef7d)",
     "text_model":"Qwen/Qwen2.5-72B-Instruct","vision_model":"Qwen/Qwen2.5-VL-72B-Instruct",
     "reply_prob":0.60,"delay_range":(20,85),
     "personality":"Kamu Nadia, food blogger 22th Surabaya. Positif tapi gak menjilat. Kadang nanya balik, share pengalaman. Bisa gak setuju. Max 1-2 kalimat santai."},
    {"username":"bimo.plays","display":"Bimo 🎮","avatar":"B","color":"linear-gradient(135deg,#fc4a1a,#f7b733)",
     "text_model":"Qwen/Qwen3-14B","vision_model":None,
     "reply_prob":0.30,"delay_range":(90,240),
     "personality":"Kamu Bimo, gamer 25th Jogja. Komentar pendek, relate ke game. Max 1 kalimat. Gaya: 'skill issue','gg','bruh','ez clap'."},
    {"username":"ara_style","display":"Ara 🌸","avatar":"A","color":"linear-gradient(135deg,#f953c6,#b91d73)",
     "text_model":"moonshotai/Kimi-K2-Instruct","vision_model":"Qwen/Qwen3-VL-32B-Instruct",
     "reply_prob":0.45,"delay_range":(40,150),
     "personality":"Kamu Ara, fashion content creator 23th. Stylish, opinionated. Kadang skeptis. Max 1 kalimat. Gak pernah bilang 'keren'. Bisa bilang 'hmm nah','itu beda cerita'."},
    {"username":"dimas_photo","display":"Dimas 📸","avatar":"D","color":"linear-gradient(135deg,#1a1a2e,#16213e,#0f3460)",
     "text_model":"deepseek-ai/DeepSeek-V3","vision_model":"Qwen/Qwen2.5-VL-72B-Instruct",
     "reply_prob":0.35,"delay_range":(70,180),"image_bias":True,
     "personality":"Kamu Dimas, fotografer jalanan 28th. Komentar dari sudut pandang visual/komposisi. Max 1 kalimat. Gak lebay. Bisa bilang 'foreground-nya kurang','lighting oke sih'."},
]

PMAP = {p["username"]: p for p in PERSONAS}

def init_db():
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,content TEXT,image_b64 TEXT,image_desc TEXT,
            post_type TEXT DEFAULT 'text',likes INTEGER DEFAULT 0,created_at REAL);
        CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,username TEXT,content TEXT,is_ai INTEGER DEFAULT 0,created_at REAL);
        CREATE TABLE IF NOT EXISTS likes(id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,username TEXT,UNIQUE(post_id,username));
    """)
    c.commit(); c.close()

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH); g.db.row_factory = sqlite3.Row
    return g.db

def call_llm(messages, model, max_tokens=90):
    try:
        r = requests.post(f"{SILICONFLOW_BASE}/chat/completions",
            headers={"Authorization":f"Bearer {SILICONFLOW_API_KEY}","Content-Type":"application/json"},
            json={"model":model,"messages":messages,"max_tokens":max_tokens,"temperature":0.93,"top_p":0.95},
            timeout=28)
        if r.status_code==401: print("[401] cek API key"); return None
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"].strip()
        txt = re.sub(r"<think>.*?</think>","",txt,flags=re.DOTALL).strip()
        return txt or None
    except Exception as e: print(f"[LLM] {model.split('/')[-1]}: {e}"); return None

def comment_text(content, p):
    return call_llm([
        {"role":"system","content":p["personality"]},
        {"role":"user","content":f"Post: \"{content}\"\nTulis 1 komentar singkat. Langsung."}
    ], p["text_model"])

def comment_image(img_b64, p):
    if not p.get("vision_model"): return None
    return call_llm([{"role":"user","content":[
        {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_b64}","detail":"low"}},
        {"type":"text","text":f"{p['personality']}\nFoto ini dipost teman. 1 komentar singkat. Langsung."}
    ]}], p["vision_model"])

def describe_image(img_b64):
    return call_llm([{"role":"user","content":[
        {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_b64}","detail":"low"}},
        {"type":"text","text":"Deskripsikan gambar ini 1 kalimat, bahasa Indonesia."}
    ]}], "Qwen/Qwen3-VL-32B-Instruct", max_tokens=70)

def schedule_responses(pid, content, img=None):
    is_img = bool(img)
    for p in PERSONAS:
        prob = p["reply_prob"]
        if is_img and p.get("image_bias"): prob = min(prob+0.25, 0.85)
        if is_img and not p.get("vision_model"): prob *= 0.25
        if random.random() > prob: continue
        delay = random.randint(*p["delay_range"])
        def _run(p=p, d=delay, pid=pid, txt=content, i=img):
            time.sleep(d)
            print(f"[AI:{p['username']}] model={p['text_model'].split('/')[-1][:14]} post#{pid}")
            c = comment_image(i, p) if i else comment_text(txt, p)
            if not c: return
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO comments(post_id,username,content,is_ai,created_at) VALUES(?,?,?,1,?)",
                         (pid, p["username"], c, time.time()))
            conn.commit(); conn.close()
            print(f"  → {c[:55]}")
        threading.Thread(target=_run, daemon=True).start()
        print(f"[Sched] {p['username']} ({p['text_model'].split('/')[-1][:14]}) → {delay}s")

def time_ago(ts):
    d = time.time()-ts
    if d<60: return f"{int(d)}d lalu"
    if d<3600: return f"{int(d//60)} mnt lalu"
    if d<86400: return f"{int(d//3600)} jam lalu"
    return f"{int(d//86400)} hari lalu"

app = Flask(__name__)

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

@app.route("/api/posts")
def api_get_posts():
    db = get_db()
    rows = db.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 30").fetchall()
    out = []
    for p in rows:
        p = dict(p)
        comms = db.execute("SELECT * FROM comments WHERE post_id=? ORDER BY created_at",(p["id"],)).fetchall()
        p["comments"] = []
        for c in comms:
            c = dict(c); pers = PMAP.get(c["username"],{})
            c["display"]  = pers.get("display", c["username"])
            c["avatar"]   = pers.get("avatar", c["username"][0].upper())
            c["color"]    = pers.get("color","linear-gradient(135deg,#555,#777)")
            c["time_ago"] = time_ago(c["created_at"])
            p["comments"].append(c)
        p["comment_count"] = len(p["comments"])
        if p["username"]=="me":
            p["display"]="Kamu 👤"; p["avatar"]="K"; p["color"]="linear-gradient(135deg,#c9aa72,#7b61ff)"
        else:
            pers = PMAP.get(p["username"],{})
            p["display"] = pers.get("display",p["username"])
            p["avatar"]  = pers.get("avatar","?")
            p["color"]   = pers.get("color","#555")
        p["time_ago"] = time_ago(p["created_at"])
        p["has_image"] = bool(p.get("image_b64"))
        p.pop("image_b64",None)
        out.append(p)
    return jsonify(out)

@app.route("/api/posts/<int:pid>/image")
def api_image(pid):
    row = get_db().execute("SELECT image_b64 FROM posts WHERE id=?",(pid,)).fetchone()
    if not row or not row["image_b64"]: return "",404
    return Response(base64.b64decode(row["image_b64"]), mimetype="image/jpeg")

@app.route("/api/posts",methods=["POST"])
def api_create():
    data = request.get_json() or {}
    content = data.get("content","").strip()
    img = data.get("image_b64")
    if not content and not img: return jsonify({"error":"kosong"}),400
    db = get_db()
    pid = db.execute(
        "INSERT INTO posts(username,content,image_b64,image_desc,post_type,created_at) VALUES(?,?,?,?,?,?)",
        ("me",content,img,None,"image" if img else "text",time.time())
    ).lastrowid
    db.commit()
    def bg(pid=pid,i=img,cap=content):
        desc=None
        if i:
            desc = describe_image(i)
            if desc:
                conn=sqlite3.connect(DB_PATH)
                conn.execute("UPDATE posts SET image_desc=? WHERE id=?",(desc,pid))
                conn.commit(); conn.close()
        schedule_responses(pid, cap or desc or "foto", i)
    threading.Thread(target=bg,daemon=True).start()
    return jsonify({"id":pid}),201

@app.route("/api/posts/<int:pid>/like",methods=["POST"])
def api_like(pid):
    db=get_db()
    try:
        db.execute("INSERT INTO likes(post_id,username) VALUES(?,?)",(pid,"me"))
        db.execute("UPDATE posts SET likes=likes+1 WHERE id=?",(pid,))
        db.commit(); liked=True
    except sqlite3.IntegrityError:
        db.execute("DELETE FROM likes WHERE post_id=? AND username=?",(pid,"me"))
        db.execute("UPDATE posts SET likes=MAX(0,likes-1) WHERE id=?",(pid,))
        db.commit(); liked=False
    row=db.execute("SELECT likes FROM posts WHERE id=?",(pid,)).fetchone()
    return jsonify({"liked":liked,"likes":row["likes"]})

@app.route("/api/posts/<int:pid>/comment",methods=["POST"])
def api_comment(pid):
    data=request.get_json() or {}; txt=data.get("text","").strip()
    if not txt: return jsonify({"error":"kosong"}),400
    db=get_db()
    db.execute("INSERT INTO comments(post_id,username,content,is_ai,created_at) VALUES(?,?,?,0,?)",
               (pid,"me",txt,time.time()))
    db.commit()
    if random.random()<0.40:
        p=random.choice(PERSONAS); d=random.randint(15,55)
        def reply(p=p,d=d,pid=pid,t=txt):
            time.sleep(d)
            row=sqlite3.connect(DB_PATH).execute("SELECT content FROM posts WHERE id=?",(pid,)).fetchone()
            ctx=f"[post: {row[0] or 'foto'}] ada komentar: \"{t}\""
            r=comment_text(ctx,p)
            if r:
                conn=sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO comments(post_id,username,content,is_ai,created_at) VALUES(?,?,?,1,?)",
                             (pid,p["username"],r,time.time()))
                conn.commit(); conn.close()
        threading.Thread(target=reply,daemon=True).start()
    return jsonify({"ok":True}),201

@app.route("/api/personas")
def api_personas():
    return jsonify([{"username":p["username"],"display":p["display"],"avatar":p["avatar"],
                     "color":p["color"],"text_model":p["text_model"].split("/")[-1]} for p in PERSONAS])

@app.route("/")
def index(): return render_template_string(HTML)

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
.si{display:flex;flex-direction:column;align-items:center;gap:5px;cursor:pointer;flex-shrink:0;}
.sr{width:62px;height:62px;border-radius:50%;padding:2.5px;
  background:linear-gradient(135deg,var(--acc),var(--a2),var(--a3));transition:transform .18s;}
.sr:hover{transform:scale(1.06);}.sr.seen{background:var(--s3);}
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
.pm{flex:1;}.pu{font-size:13.5px;font-weight:600;font-family:'Clash Display',sans-serif;}
.pt{font-size:11.5px;color:var(--mu);margin-top:1px;}
.pimg{width:100%;display:block;max-height:480px;object-fit:cover;}
.pvlm{padding:5px 18px 3px;font-size:12px;color:var(--acc);font-style:italic;line-height:1.5;}
.pbody{padding:7px 18px 4px;font-size:14.5px;line-height:1.65;}
.pbody.cap{font-size:13.5px;color:var(--mu);}
.pacts{display:flex;gap:2px;padding:5px 10px;}
.ab{display:flex;align-items:center;gap:5px;background:none;border:none;color:var(--mu);font-size:12.5px;
  font-family:'Sora',sans-serif;cursor:pointer;padding:6px 9px;border-radius:9px;transition:.18s;}
.ab:hover{background:var(--s2);color:var(--tx);}.ab.liked{color:var(--red);}
.ab.liked svg{fill:var(--red);stroke:var(--red);}.ab.saved svg{fill:var(--acc);stroke:var(--acc);}
.ab svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.8;}
.sp{flex:1;}
/* comments */
.cw{background:var(--s1);border-top:1px solid var(--bd);padding:10px 18px;}
.ci{display:flex;gap:9px;margin-bottom:11px;}
.cav{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:700;flex-shrink:0;}
.cb{flex:1;}.cu{font-size:12.5px;font-weight:600;margin-right:5px;}
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
.egrid{display:grid;grid-template-columns:repeat(3,1fr);gap:2px;}
.eg{aspect-ratio:1;background:var(--s2);display:flex;align-items:center;justify-content:center;
  font-size:30px;cursor:pointer;transition:opacity .18s;}.eg:hover{opacity:.75;}
.eg:nth-child(4){grid-column:span 2;aspect-ratio:2;}.eg:nth-child(7){grid-column:span 2;aspect-ratio:2;}
.sl{padding:0 18px;}
.sit{display:flex;align-items:center;gap:11px;padding:11px 0;border-bottom:1px solid var(--bd);}
.sav2{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:17px;font-weight:700;font-family:'Clash Display',sans-serif;flex-shrink:0;}
.sm{flex:1;}.sn{font-size:13.5px;font-weight:600;}.ss{font-size:11.5px;color:var(--mu);}
.mono{font-size:10px;background:var(--s3);padding:1px 4px;border-radius:3px;font-family:monospace;}
.fb{background:none;border:1px solid var(--acc);color:var(--acc);border-radius:18px;
  padding:5px 13px;font-size:12px;font-weight:600;font-family:'Sora',sans-serif;cursor:pointer;transition:.18s;}
.fb:hover,.fb.on{background:var(--acc);color:var(--bg);}
/* profile */
.prh{padding:20px 18px 16px;}
.prt{display:flex;align-items:center;gap:18px;margin-bottom:14px;}
.prpic{width:82px;height:82px;border-radius:50%;background:linear-gradient(135deg,var(--acc),var(--a2));
  display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:700;
  font-family:'Clash Display',sans-serif;border:3px solid var(--bg);box-shadow:0 0 0 2px var(--acc);}
.prs{display:flex;gap:22px;flex:1;justify-content:center;}
.st{text-align:center;}.stn{font-family:'Clash Display',sans-serif;font-size:19px;font-weight:700;display:block;}
.stl2{font-size:11.5px;color:var(--mu);}
.prn{font-family:'Clash Display',sans-serif;font-size:19px;font-weight:700;margin-bottom:2px;}
.prh2{font-size:12.5px;color:var(--mu);margin-bottom:8px;}
.prb{font-size:13.5px;line-height:1.55;margin-bottom:13px;}
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
.svf{height:100%;background:#fff;width:0%;transition:width linear;}.svf.done{width:100%;}
.svt{display:flex;align-items:center;gap:9px;padding:9px 14px;}
.svav{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;font-family:'Clash Display',sans-serif;}
.svu{font-size:13.5px;font-weight:600;flex:1;}
.svti{font-size:11.5px;color:rgba(255,255,255,.55);}
.svcl{background:none;border:none;color:#fff;font-size:22px;cursor:pointer;}
.svc{flex:1;display:flex;align-items:center;justify-content:center;font-size:72px;
  background:linear-gradient(145deg,#1a0f35,#0d1f40,#121a0a);}
.svbot{padding:18px 14px 28px;display:flex;gap:9px;align-items:center;}
.svrep{flex:1;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);
  border-radius:22px;padding:9px 14px;color:#fff;font-family:'Sora',sans-serif;font-size:13.5px;outline:none;}
.svrep::placeholder{color:rgba(255,255,255,.45);}
.svh{background:none;border:none;font-size:26px;cursor:pointer;transition:transform .18s;}
.svh:hover{transform:scale(1.2);}
/* toast + misc */
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
  <div class="stop">
    <div class="sw2">
      <svg class="sic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input class="sinp" placeholder="Cari persona, topik…" oninput="doSearch(this.value)">
    </div>
  </div>
  <div id="sr">
    <div class="stit">Explore</div>
    <div class="egrid">
      <div class="eg" onclick="showToast('🎨')">🎨</div><div class="eg" onclick="showToast('🏔️')">🏔️</div>
      <div class="eg" onclick="showToast('🍜')">🍜</div><div class="eg" onclick="showToast('🎵')">🎵</div>
      <div class="eg" onclick="showToast('💻')">💻</div><div class="eg" onclick="showToast('📸')">📸</div>
      <div class="eg" onclick="showToast('🌃')">🌃</div><div class="eg" onclick="showToast('🎮')">🎮</div>
      <div class="eg" onclick="showToast('🌸')">🌸</div>
    </div>
    <div class="stit" style="margin-top:10px">AI Personas</div>
    <div class="sl" id="pl"></div>
  </div>
</div>

<!-- NOTIF -->
<div class="page" id="page-notif">
  <div style="padding:18px 18px 14px;font-family:'Clash Display',sans-serif;font-size:20px;font-weight:700">Notifikasi</div>
  <div class="sl" id="nl"></div>
</div>

<!-- PROFILE -->
<div class="page" id="page-profile">
  <div class="prh">
    <div class="prt">
      <div class="prpic">K</div>
      <div class="prs">
        <div class="st"><span class="stn" id="sp">0</span><span class="stl2">Posts</span></div>
        <div class="st"><span class="stn">1.2K</span><span class="stl2">Followers</span></div>
        <div class="st"><span class="stn">384</span><span class="stl2">Following</span></div>
      </div>
    </div>
    <div class="prn">Kamu 👤</div>
    <div class="prh2">@kamu · Aura</div>
    <div class="prb">✨ Living, learning, creating.<br>🎨 Design & tech. Jakarta 🇮🇩</div>
    <div class="pra">
      <button class="prbt" onclick="showToast('✏️ Edit coming soon')">Edit Profil</button>
      <button class="prbt" onclick="showToast('📤 Share')">Bagikan</button>
    </div>
  </div>
  <div class="ptabs">
    <div class="ptab active" onclick="switchPT(this,'grid')">
      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
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
    <div class="np">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
    </div>
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

<!-- STORY VIEWER -->
<div class="sv" id="sv">
  <div class="svb">
    <div class="svbr"><div class="svf done"></div></div>
    <div class="svbr"><div class="svf" id="svf"></div></div>
    <div class="svbr"><div class="svf"></div></div>
  </div>
  <div class="svt">
    <div class="svav" id="svav"></div>
    <div class="svu" id="svun">...</div>
    <div class="svti">baru saja</div>
    <button class="svcl" onclick="closeSV()">×</button>
  </div>
  <div class="svc" id="sve">✨</div>
  <div class="svbot">
    <input class="svrep" placeholder="Balas story…">
    <button class="svh" onclick="showToast('❤️')">🤍</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const EMOJIS={maya_art:'🌅',rizky_dev:'💻',nadiafood:'🍜','bimo.plays':'🎮',ara_style:'🌸',dimas_photo:'📷'};
let imgB64=null,liked=new Set(),personas=[],svT;

(async()=>{
  try{ const r=await fetch('/api/personas'); personas=await r.json(); renderStories(); renderPL(); renderNotifs(); }catch{}
  loadFeed(); setInterval(loadFeed,15000);
})();

function renderStories(){
  const w=document.getElementById('sw');
  let h=`<div class="si" onclick="showToast('📸 soon')">
    <div class="sr seen"><div class="sav" style="background:var(--s2);font-size:22px">+</div></div>
    <div class="slbl">Kamu</div></div>`;
  personas.forEach((p,i)=>{
    h+=`<div class="si" onclick="openSV('${p.avatar}','${p.display}','${p.color}','${EMOJIS[p.username]||'✨'}')">
      <div class="sr ${i>3?'seen':''}"><div class="sav" style="background:${p.color}">${p.avatar}</div></div>
      <div class="slbl">${p.username}</div></div>`;
  });
  w.innerHTML=h;
}
function openSV(av,un,col,em){
  document.getElementById('svav').textContent=av;
  document.getElementById('svav').style.background=col;
  document.getElementById('svun').textContent=un;
  document.getElementById('sve').textContent=em;
  document.getElementById('sv').classList.add('open');
  const f=document.getElementById('svf');
  f.style.transition='none';f.style.width='0%';
  setTimeout(()=>{f.style.transition='width 5s linear';f.style.width='100%';},30);
  svT=setTimeout(closeSV,5100);
}
function closeSV(){clearTimeout(svT);document.getElementById('sv').classList.remove('open');}

function renderPL(){
  document.getElementById('pl').innerHTML=personas.map(p=>`
    <div class="sit">
      <div class="sav2" style="background:${p.color}">${p.avatar}</div>
      <div class="sm"><div class="sn">${p.display}</div>
        <div class="ss"><span class="mono">${p.text_model}</span></div></div>
      <button class="fb" onclick="tgFollow(this)">Follow</button>
    </div>`).join('');
}
function renderNotifs(){
  const acts=['menyukai postinganmu','mengomentari fotomu','me-repost tweetmu','mulai mengikutimu','melihat storymu'];
  const ems=['❤️','💬','🔁','✨','👀'];
  document.getElementById('nl').innerHTML=personas.slice(0,5).map((p,i)=>`
    <div class="sit">
      <div class="sav2" style="background:${p.color}">${p.avatar}</div>
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
      <div class="sav2" style="background:${p.color}">${p.avatar}</div>
      <div class="sm"><div class="sn">${p.display}</div><div class="ss">${p.text_model}</div></div>
      <button class="fb" onclick="tgFollow(this)">Follow</button>
    </div>`).join('')||'<div style="padding:20px;color:var(--mu)">Tidak ditemukan</div>';
}
function tgFollow(b){b.classList.toggle('on');b.textContent=b.classList.contains('on')?'Following':'Follow';showToast(b.classList.contains('on')?'✅ Following!':'👋 Unfollow');}

async function loadFeed(){
  try{
    const r=await fetch('/api/posts');const posts=await r.json();
    renderFeed(posts);
    document.getElementById('sp').textContent=posts.filter(p=>p.username==='me').length;
    renderPG(posts);
  }catch{}
}
function renderFeed(posts){
  const el=document.getElementById('feed');
  if(!posts.length){el.innerHTML='<div class="empty"><span>🌱</span>Jadilah yang pertama posting!</div>';return;}
  el.innerHTML=posts.map((p,i)=>pCard(p,i)).join('');
}
function pCard(p,i){
  const lk=liked.has(p.id);
  let m='';
  if(p.has_image){
    m+=`<img src="/api/posts/${p.id}/image" class="pimg" loading="lazy" alt="">`;
    if(p.image_desc)m+=`<div class="pvlm">🤖 "${e(p.image_desc)}"</div>`;
  }
  if(p.content)m+=`<div class="pbody ${p.has_image?'cap':''}">${e(p.content)}</div>`;
  const cms=p.comments.map(c=>`
    <div class="ci">
      <div class="cav" style="background:${c.color}">${c.avatar}</div>
      <div class="cb">
        <span class="cu">${e(c.display)}</span>${c.is_ai?'<span class="ait">AI</span>':''}
        <span class="ct">${e(c.content)}</span>
        <div class="ctm">${c.time_ago}</div>
      </div>
    </div>`).join('');
  return `<div class="pc" style="animation-delay:${i*.04}s" id="pc${p.id}">
    <div class="ph">
      <div class="av" style="background:${p.color}">${p.avatar}</div>
      <div class="pm"><div class="pu">${e(p.display)}</div><div class="pt">${p.time_ago}</div></div>
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
    <div class="ci">
      <div class="cav" style="background:linear-gradient(135deg,var(--acc),var(--a2))">K</div>
      <div class="cb"><span class="cu">Kamu 👤</span><span class="ct">${e(txt)}</span><div class="ctm">Baru saja</div></div>
    </div>`);
  if(Math.random()<0.4&&personas.length){
    const rp=personas[Math.floor(Math.random()*personas.length)];
    const tid='ty'+id+Date.now();
    list.insertAdjacentHTML('beforeend',`
      <div id="${tid}" class="ci">
        <div class="cav" style="background:${rp.color}">${rp.avatar}</div>
        <div class="cb"><div class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>
      </div>`);
    setTimeout(()=>document.getElementById(tid)?.remove(),62000);
  }
  await fetch(`/api/posts/${id}/comment`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:txt})});
}
function renderPG(posts){
  const mine=posts.filter(p=>p.username==='me').slice(0,9);
  const el=document.getElementById('pg');
  if(!mine.length){el.innerHTML='<div style="padding:40px;text-align:center;color:var(--mu);grid-column:span 3">Belum ada post</div>';return;}
  el.innerHTML=mine.map(p=>p.has_image
    ?`<div class="pgi" onclick="showToast('🖼️ Post #${p.id}')"><img src="/api/posts/${p.id}/image" loading="lazy" alt=""></div>`
    :`<div class="pgi" style="font-size:12px;padding:8px;align-items:flex-start;color:var(--tx)">${e(p.content||'').slice(0,40)}</div>`
  ).join('');
}
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
    if(r.ok){
      document.getElementById('ct').value='';cntCh();rmImg();closeC();
      showToast('🚀 Posted! AI akan balas...');loadFeed();
    }else showToast('❌ Gagal');
  }catch{showToast('❌ Network error');}
  btn.disabled=false;btn.textContent='Post ✦';
}
function switchPage(n){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.ni').forEach(ni=>ni.classList.remove('active'));
  document.getElementById('page-'+n)?.classList.add('active');
  document.getElementById('nav-'+n)?.classList.add('active');
}
function switchPT(el,t){
  document.querySelectorAll('.ptab').forEach(p=>p.classList.remove('active'));el.classList.add('active');
  if(t==='liked')document.getElementById('pc2').innerHTML='<div class="empty"><span>❤️</span>Belum ada</div>';
  else{document.getElementById('pc2').innerHTML='<div class="pgrid" id="pg"></div>';loadFeed();}
}
function e(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
let tT;function showToast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');clearTimeout(tT);tT=setTimeout(()=>t.classList.remove('show'),2400);}
// Search wrapper fix (missing class)
document.querySelector('.stop')?.querySelector('div')?.classList.add('sw');
</script>
</body></html>"""

if __name__=="__main__":
    init_db()
    print("="*58)
    print("  🚀 Aura Social v2 — Cross-Model AI Personas")
    print("="*58)
    print(f"  Endpoint : {SILICONFLOW_BASE}")
    print(f"  API Key  : {'✅' if not SILICONFLOW_API_KEY.startswith('sk-GANTI') else '❌ BELUM DIISI'}")
    print(f"  Personas : {len(PERSONAS)}")
    for p in PERSONAS:
        vm=p.get('vision_model','').split('/')[-1][:14] if p.get('vision_model') else '— skip'
        print(f"    {p['avatar']} {p['username']:15} txt={p['text_model'].split('/')[-1][:18]:20} prob={p['reply_prob']}")
    print("="*58)
    print("  → http://localhost:5000")
    print("="*58)
    app.run(debug=True,threaded=True,port=5000)