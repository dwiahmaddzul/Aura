"""
Aura Social — Background AI Schedulers

One loop (daemon thread) ticks every IDLE_RECHECK_SEC and decides whether an
AI post or story is due. Intervals, chances and switches are read from
settings_rt each tick, so changes from /kelola apply within ~30 s without a
restart. Every run passes the cost brakes in ai_engine/limits.py first.
"""
import random
import threading
import time

import media
import settings_rt as S
from ai_engine import limits, usage
from ai_engine.responder import schedule_responses
from db import connect
from llm.client import generate_image
from llm.generators import photo_caption, post_text, story_caption
from llm.memory import (get_persona_memory, pick_fresh_story_prompt,
                        pick_fresh_topic, recent_story_prompts)

IMAGE_STYLE = ", realistic smartphone photo, natural light, no text"

STATE = {
    "started_at": None,
    "next_post": None, "next_story": None,
    "last_post": None, "last_story": None,
    "blocked": None, "tick": None,
}
_lock = threading.Lock()


def _rand_wait(kind):
    lo, hi = S.get(f"{kind}_interval_min"), S.get(f"{kind}_interval_max")
    return random.randint(lo * 60, max(lo, hi) * 60)


def _result(kind, ok, info, persona=None):
    STATE[f"last_{kind}"] = {"at": time.time(), "ok": ok, "info": info, "persona": persona}
    print(f"[AI-{kind}] {'✅' if ok else '—'} {persona or ''} {info}", flush=True)
    return STATE[f"last_{kind}"]


def ai_post_once():
    """Satu post AI (kadang dengan gambar). Dipanggil scheduler atau dashboard."""
    pers = S.active_personas()
    if not pers:
        return _result("post", False, "tidak ada persona aktif")
    p = random.choice(pers)
    un = p["username"]
    memory = get_persona_memory(un)
    img, text = None, None
    if random.random() < S.get("post_image_prob") and limits.try_consume_image(un):
        scene = pick_fresh_story_prompt(p, recent_story_prompts(un))
        img = generate_image(scene + IMAGE_STYLE, persona=un, kind="post_image")
        if img:
            # Caption ditulis DARI deskripsi gambar → caption dan foto nyambung.
            text = photo_caption(p, scene, memory) or ""
    if not img:
        text = post_text(p, pick_fresh_topic(p), memory)
        if not text:
            return _result("post", False, "model tidak memberi teks yang layak", un)
    conn = connect()
    try:
        pid = conn.execute(
            "INSERT INTO posts(username,content,image_b64,image_desc,post_type,has_img,created_at) "
            "VALUES(?,?,NULL,NULL,?,?,?)",
            (un, text, "image" if img else "text", 1 if img else 0, time.time()),
        ).lastrowid
        conn.commit()
        if img:
            w, h = media.save("p", pid, img)
            if w:
                conn.execute("UPDATE posts SET img_w=?, img_h=? WHERE id=?", (w, h, pid))
            else:
                conn.execute("UPDATE posts SET has_img=0, post_type='text' WHERE id=?", (pid,))
            conn.commit()
    finally:
        conn.close()
    schedule_responses(pid, text or "foto", img, poster=un)
    return _result("post", True, f"post #{pid}{' + gambar' if img else ''}", un)


def ai_story_once():
    """Satu story AI (selalu 1 gambar). Peluang & kuota dicek di sini."""
    if random.random() >= S.get("story_prob"):
        return _result("story", False, "dilewati (peluang story)")
    pers = [p for p in S.active_personas() if S.persona(p["username"], "can_image")]
    if not pers:
        return _result("story", False, "tidak ada persona yang boleh membuat gambar")
    p = random.choice(pers)
    un = p["username"]
    if not limits.try_consume_image(un):
        return _result("story", False, "kuota gambar hari ini habis", un)
    scene = pick_fresh_story_prompt(p, recent_story_prompts(un))
    img = generate_image(scene + IMAGE_STYLE, persona=un, kind="story_image")
    if not img:
        return _result("story", False, "gagal membuat gambar", un)
    caption = (story_caption(p, scene) or "") if S.get("story_caption") else ""
    is_highlight = 1 if random.random() < 0.35 else 0
    conn = connect()
    try:
        sid = conn.execute(
            "INSERT INTO stories(username,image_b64,caption,prompt,is_highlight,has_img,created_at) "
            "VALUES(?,NULL,?,?,?,1,?)",
            (un, caption, scene, is_highlight, time.time()),
        ).lastrowid
        conn.commit()
        w, h = media.save("s", sid, img)
        conn.execute("UPDATE stories SET img_w=?, img_h=? WHERE id=?", (w, h, sid))
        conn.commit()
    finally:
        conn.close()
    return _result("story", True, f"story #{sid}{' ✨sorotan' if is_highlight else ''}", un)


def scheduler_loop():
    """Satu loop untuk post + story."""
    STATE["started_at"] = time.time()
    now = time.time()
    STATE["next_post"] = now + 120
    STATE["next_story"] = now + 300
    seen_version = S.version()
    time.sleep(20)
    while True:
        try:
            now = time.time()
            STATE["tick"] = now
            # Setting berubah: jadwal berikutnya tidak boleh lebih jauh dari interval max baru.
            if S.version() != seen_version:
                seen_version = S.version()
                for kind in ("post", "story"):
                    cap_at = now + S.get(f"{kind}_interval_max") * 60
                    if STATE[f"next_{kind}"] and STATE[f"next_{kind}"] > cap_at:
                        STATE[f"next_{kind}"] = now + _rand_wait(kind)
            reason = limits.auto_block_reason()
            STATE["blocked"] = reason
            if not reason:
                if S.get("post_enabled") and now >= (STATE["next_post"] or 0):
                    with _lock:
                        try:
                            ai_post_once()
                        finally:
                            STATE["next_post"] = time.time() + _rand_wait("post")
                if S.get("story_enabled") and now >= (STATE["next_story"] or 0) \
                        and not limits.auto_block_reason():
                    with _lock:
                        try:
                            ai_story_once()
                        finally:
                            STATE["next_story"] = time.time() + _rand_wait("story")
        except Exception as e:
            print(f"[Scheduler] error: {e}", flush=True)
        time.sleep(limits.IDLE_RECHECK_SEC)


def cleanup_worker():
    """Periodic DB hygiene. Non-highlight stories only live 24h in the rail;
    past 48h they're invisible, so drop them (plus their image files).
    Highlights are permanent. AI timeline is trimmed to the 300 newest posts;
    the user's own posts are always kept."""
    time.sleep(300)
    while True:
        try:
            conn = connect()
            try:
                cutoff = time.time() - 48 * 3600
                sids = [r[0] for r in conn.execute(
                    "SELECT id FROM stories WHERE is_highlight=0 AND created_at<?", (cutoff,)
                ).fetchall()]
                pids = [r[0] for r in conn.execute(
                    "SELECT id FROM posts WHERE username!='me' AND id NOT IN "
                    "(SELECT id FROM posts WHERE username!='me' ORDER BY created_at DESC LIMIT 300)"
                ).fetchall()]
                if sids:
                    conn.executemany("DELETE FROM stories WHERE id=?", [(i,) for i in sids])
                if pids:
                    conn.executemany("DELETE FROM posts WHERE id=?", [(i,) for i in pids])
                conn.execute("DELETE FROM comments WHERE post_id NOT IN (SELECT id FROM posts)")
                conn.execute("DELETE FROM likes WHERE post_id NOT IN (SELECT id FROM posts)")
                conn.execute("DELETE FROM bookmarks WHERE post_id NOT IN (SELECT id FROM posts)")
                conn.commit()
            finally:
                conn.close()
            for i in sids:
                media.delete("s", i)
            for i in pids:
                media.delete("p", i)
            if sids or pids:
                print(f"[Cleanup] hapus {len(sids)} story kedaluwarsa, {len(pids)} post AI lama")
            usage.prune()
        except Exception as e:
            print(f"[Cleanup] error: {e}")
        time.sleep(3600)  # hourly


_started = [False]


def start_background_workers():
    """Spawn daemon threads. Call once from app entrypoint."""
    if _started[0]:
        return
    _started[0] = True
    threading.Thread(target=scheduler_loop, daemon=True, name="ai-scheduler").start()
    threading.Thread(target=cleanup_worker, daemon=True, name="db-cleanup").start()
    print("  [BG] AI scheduler (post + story) started — atur dari /kelola")
    print("  [BG] DB cleanup worker started (hourly)")
