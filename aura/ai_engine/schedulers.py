"""
Aura Social — Background AI Schedulers
Two infinite loops that run in daemon threads:
  - ai_post_scheduler: AI personas post to timeline (8-15min interval)
  - ai_story_scheduler: AI personas generate stories (15-25min interval)
"""
import random
import sqlite3
import threading
import time

from config import DB_PATH
from personas import PERSONAS
from llm.client import call_llm, generate_image
from llm.memory import get_persona_memory, pick_fresh_topic, pick_fresh_story_prompt
from ai_engine.responder import schedule_responses


def ai_post_scheduler():
    """Background loop: AI personas post on timeline periodically, with memory."""
    time.sleep(120)  # wait 2min after startup
    while True:
        try:
            p = random.choice(PERSONAS)
            topic = pick_fresh_topic(p, "")
            memory = get_persona_memory(p["username"])
            do_image = random.random() < 0.30
            print(
                f"[AI-Post] {p['username']} {'img+' if do_image else ''}"
                f"post '{topic}' (memory: {bool(memory)})"
            )
            mem_ctx = ""
            if memory:
                mem_ctx = (
                    f"\n\nPOST/STORY TERAKHIR KAMU (JANGAN ulangi topik/isi yg sama!):\n"
                    f"{memory}\nBuat sesuatu BEDA."
                )
            content = call_llm(
                [
                    {
                        "role": "system",
                        "content": (
                            f"{p['personality']}\nKamu posting di medsos. Topik: {topic}. "
                            f"1-2 kalimat. Langsung isi, tanpa tanda kutip.{mem_ctx}"
                        ),
                    },
                    {"role": "user", "content": "Buat 1 postingan medsos singkat."},
                ],
                p["text_model"],
                max_tokens=80,
            )
            if content:
                img_b64 = None
                if do_image:
                    img_prompt = random.choice(p.get("story_prompts", [topic]))
                    img_b64 = generate_image(img_prompt)
                    print(f"[AI-Post] image: {'✅' if img_b64 else '❌'}")
                conn = sqlite3.connect(DB_PATH)
                pid = conn.execute(
                    "INSERT INTO posts(username,content,image_b64,image_desc,post_type,created_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        p["username"],
                        content,
                        img_b64,
                        None,
                        "image" if img_b64 else "text",
                        time.time(),
                    ),
                ).lastrowid
                conn.commit()
                conn.close()
                print(f"[AI-Post] {p['username']} #{pid}: {content[:50]}")
                schedule_responses(pid, content, img_b64, poster=p["username"])
        except Exception as e:
            print(f"[AI-Post] error: {e}")
        wait = random.randint(480, 900)
        print(f"[AI-Post] next in {wait // 60}min")
        time.sleep(wait)


def ai_story_scheduler():
    """Background loop: generate AI stories with FLUX, memory-aware, highlight decision."""
    time.sleep(60)
    while True:
        try:
            p = random.choice(PERSONAS)
            memory = get_persona_memory(p["username"])
            mem_captions = memory if memory else ""
            prompt = pick_fresh_story_prompt(p, mem_captions)
            print(
                f"[AI-Story] {p['username']} story: '{prompt[:40]}...' "
                f"(memory: {bool(memory)})"
            )
            img_b64 = generate_image(prompt)
            if img_b64:
                # 35% chance to mark as highlight (Sorotan)
                is_highlight = 1 if random.random() < 0.35 else 0
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "INSERT INTO stories(username,image_b64,caption,is_highlight,created_at) "
                    "VALUES(?,?,?,?,?)",
                    (p["username"], img_b64, prompt, is_highlight, time.time()),
                )
                conn.commit()
                conn.close()
                print(
                    f"[AI-Story] {p['username']} posted! "
                    f"highlight={'✨' if is_highlight else '—'}"
                )
            else:
                print("[AI-Story] image gen failed")
        except Exception as e:
            print(f"[AI-Story] error: {e}")
        wait = random.randint(900, 1500)
        print(f"[AI-Story] next in {wait // 60}min")
        time.sleep(wait)


def start_background_workers():
    """Spawn both daemon threads. Call once from app entrypoint."""
    threading.Thread(target=ai_post_scheduler, daemon=True).start()
    threading.Thread(target=ai_story_scheduler, daemon=True).start()
    print("  [BG] AI post scheduler started (8-15min interval)")
    print("  [BG] AI story scheduler started (15-25min interval)")
