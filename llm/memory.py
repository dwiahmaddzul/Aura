"""
Aura Social — Persona Memory & Variety
Builds context strings to avoid repetition. No embeddings — just recent history.

The memory is a plain bullet list WITHOUT "Post:" / "Story:" labels: models
copy whatever format they see, and labelled memory is where the
"Post: …" prefixes in old AI posts came from.
"""
import random
import sqlite3

from config import DB_PATH
from llm.clean import clean_ai_text


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def get_persona_memory(username):
    """Recent post texts of a persona as a bullet list, or None."""
    c = _conn()
    try:
        posts = c.execute(
            "SELECT content FROM posts WHERE username=? AND content IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 6",
            (username,),
        ).fetchall()
    finally:
        c.close()
    lines = []
    for p in posts:
        t = clean_ai_text(p["content"], max_len=90)
        if t:
            lines.append(f"- {t}")
    return "\n".join(lines) if lines else None


def recent_story_prompts(username, limit=6):
    c = _conn()
    try:
        rows = c.execute(
            "SELECT COALESCE(prompt, caption) AS s FROM stories WHERE username=? "
            "ORDER BY created_at DESC LIMIT ?",
            (username, limit),
        ).fetchall()
    finally:
        c.close()
    return " | ".join(r["s"] or "" for r in rows).lower()


def pick_fresh_topic(persona, used_topics_str=""):
    """Random topic; the LLM handles deeper dedup via memory injection."""
    return random.choice(persona["post_topics"])


def pick_fresh_story_prompt(persona, used_str=""):
    """Pick an image scene avoiding recently used ones (keyword filter)."""
    prompts = persona["story_prompts"]
    used = (used_str or "").lower()
    if used:
        fresh = [p for p in prompts if not any(w in used for w in p.lower().split()[:2])]
        if fresh:
            return random.choice(fresh)
    return random.choice(prompts)
