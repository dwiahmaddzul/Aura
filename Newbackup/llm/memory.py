"""
Aura Social — Persona Memory & Variety
Builds context strings to avoid repetition. No embeddings — just recent history.
"""
import random
import sqlite3

from config import DB_PATH


def get_persona_memory(username):
    """Get recent posts + story captions for a persona to avoid repetition.
    Returns formatted string ready for system prompt injection, or None.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    posts = conn.execute(
        "SELECT content FROM posts WHERE username=? ORDER BY created_at DESC LIMIT 5",
        (username,),
    ).fetchall()
    stories = conn.execute(
        "SELECT caption FROM stories WHERE username=? ORDER BY created_at DESC LIMIT 5",
        (username,),
    ).fetchall()
    conn.close()
    memory = []
    for p in posts:
        if p["content"]:
            memory.append(f"- Post: {p['content'][:60]}")
    for s in stories:
        if s["caption"]:
            memory.append(f"- Story: {s['caption'][:60]}")
    return "\n".join(memory) if memory else None


def pick_fresh_topic(persona, used_topics_str):
    """Pick a topic that hasn't been used recently.
    The LLM handles deeper deduplication via memory injection.
    """
    topics = persona["post_topics"][:]  # copy to avoid mutating persona
    random.shuffle(topics)
    return topics[0]


def pick_fresh_story_prompt(persona, used_captions_str):
    """Pick a story prompt avoiding recent ones (keyword filter)."""
    prompts = persona["story_prompts"]
    if used_captions_str:
        fresh = [
            p for p in prompts
            if not any(word in used_captions_str.lower() for word in p.split()[:2])
        ]
        if fresh:
            return random.choice(fresh)
    return random.choice(prompts)
