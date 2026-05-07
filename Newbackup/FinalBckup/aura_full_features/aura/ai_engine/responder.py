"""
Aura Social — AI Response Engine
Schedules likes + comments from AI personas in response to posts.
"""
import random
import sqlite3
import threading
import time

from config import DB_PATH
from personas import PERSONAS
from llm.generators import comment_image, comment_text


def schedule_responses(pid, content, img=None, poster="me"):
    """Schedule AI persona reactions to a post.

    Args:
        pid: post id
        content: post text (or image description fallback)
        img: optional base64 image string
        poster: username of the poster — skip self-reply.
                MUST be set when an AI is the poster, otherwise infinite self-reply.
    """
    is_img = bool(img)
    for p in PERSONAS:
        if p["username"] == poster:
            continue  # don't reply to own post

        # ── AI LIKE: independent 40-65% chance ──
        like_prob = 0.50 if is_img else 0.40
        if random.random() < like_prob:
            delay_like = random.randint(5, max(10, p["delay_range"][0]))

            def _like(p=p, d=delay_like, pid=pid):
                time.sleep(d)
                try:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute(
                        "INSERT INTO likes(post_id,username) VALUES(?,?)",
                        (pid, p["username"]),
                    )
                    conn.execute(
                        "UPDATE posts SET likes=likes+1 WHERE id=?", (pid,)
                    )
                    conn.commit()
                    conn.close()
                    print(f"[AI-Like] {p['username']} liked post#{pid}")
                except sqlite3.IntegrityError:
                    pass  # already liked
                except Exception as e:
                    print(f"[AI-Like] error: {e}")

            threading.Thread(target=_like, daemon=True).start()

        # ── AI COMMENT: probabilistic ──
        prob = p["reply_prob"]
        if is_img and p.get("image_bias"):
            prob = min(prob + 0.25, 0.85)
        if is_img and not p.get("vision_model"):
            prob *= 0.25
        if random.random() > prob:
            continue

        delay = random.randint(*p["delay_range"])

        def _run(p=p, d=delay, pid=pid, txt=content, i=img):
            time.sleep(d)
            print(f"[AI:{p['username']}] commenting post#{pid}")
            c = comment_image(i, p) if i and p.get("vision_model") else comment_text(txt, p)
            if not c:
                return
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO comments(post_id,username,content,is_ai,created_at) VALUES(?,?,?,1,?)",
                (pid, p["username"], c, time.time()),
            )
            conn.commit()
            conn.close()
            print(f"  → {c[:55]}")

        threading.Thread(target=_run, daemon=True).start()
        print(f"[Sched] {p['username']} → {delay}s for post#{pid}")
