"""
Aura Social — AI Response Engine
Schedules likes + comments from AI personas in response to posts.
All knobs come from settings_rt (dashboard /kelola).
"""
import random
import threading
import time

import settings_rt as S
from ai_engine import limits
from db import connect
from llm.generators import comment_image, comment_text


def schedule_responses(pid, content, img=None, poster="me", prioritize=None, note=""):
    """Schedule AI persona reactions to a post.

    Args:
        pid: post id
        content: post text (or image description fallback)
        img: optional image (raw bytes or base64)
        poster: username of the poster — never replies to itself.
        prioritize: persona forced to comment (e.g. the one whose daily
                    question the user just answered).
        note: context prefix for the prioritized persona's prompt only.
    """
    auto = poster != "me"
    gate = limits.auto_block_reason if auto else limits.interactive_block_reason
    reason = gate()
    if reason:
        print(f"[Sched] post#{pid}: reaksi AI ditahan ({reason})")
        return 0
    is_img = bool(img)
    vision_on = S.get("vision_enabled")
    candidates = [p for p in S.active_personas() if p["username"] != poster]
    random.shuffle(candidates)
    comment_max = S.get("comment_max")
    scheduled = 0
    for p in candidates:
        un = p["username"]

        # ── AI LIKE (gratis, tidak memanggil API) ──
        if S.get("ai_likes_enabled") and random.random() < (0.50 if is_img else 0.40):
            delay_like = random.randint(5, max(10, p["delay_range"][0]))

            def _like(un=un, d=delay_like, pid=pid):
                time.sleep(d)
                try:
                    conn = connect()
                    try:
                        cur = conn.execute(
                            "INSERT OR IGNORE INTO likes(post_id,username,created_at) VALUES(?,?,?)",
                            (pid, un, time.time()),
                        )
                        if cur.rowcount:
                            conn.execute("UPDATE posts SET likes=likes+1 WHERE id=?", (pid,))
                        conn.commit()
                    finally:
                        conn.close()
                except Exception as e:
                    print(f"[AI-Like] error: {e}")

            threading.Thread(target=_like, daemon=True).start()

        # ── AI COMMENT ──
        is_target = prioritize is not None and un == prioritize
        prob = S.persona(un, "reply_prob")
        can_see = is_img and vision_on and bool(S.vision_model(p))
        if is_img and p.get("image_bias"):
            prob = min(prob + 0.25, 0.85)
        if is_img and not can_see:
            prob *= 0.25  # tidak bisa melihat foto → jarang ikut komentar
        if auto:
            prob *= S.get("comment_on_ai_scale")  # redam obrolan AI↔AI
        if is_target:
            prob = 1.0
        elif scheduled >= comment_max:
            continue
        if random.random() > prob:
            continue
        scheduled += 1

        delay = random.randint(*p["delay_range"])
        ctx = f"{note} {content}".strip() if (is_target and note) else content

        def _run(p=p, d=delay, pid=pid, txt=ctx, i=img, see=can_see):
            time.sleep(d)
            # Cek ulang: anggaran bisa habis selama menunggu.
            if gate():
                return
            if see and i:
                c = comment_image(i, p, auto=auto)
            else:
                c = comment_text(txt or "foto", p, auto=auto)
            if not c:
                return
            conn = connect()
            try:
                conn.execute(
                    "INSERT INTO comments(post_id,username,content,is_ai,created_at) VALUES(?,?,?,1,?)",
                    (pid, p["username"], c, time.time()),
                )
                conn.commit()
            finally:
                conn.close()
            print(f"[AI:{p['username']}] komentar post#{pid}: {c[:55]}")

        threading.Thread(target=_run, daemon=True).start()
    return scheduled
