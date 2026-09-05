"""
Aura Social — Database Layer
SQLite schema, connection helpers, and migrations.
"""
import sqlite3
from flask import g

from config import DB_PATH


def init_db():
    """Initialize schema. Idempotent — safe to call multiple times."""
    c = sqlite3.connect(DB_PATH)
    # WAL: penulis (scheduler threads) tidak memblok pembaca (request Flask).
    # Persistent per-file, cukup di-set sekali di sini.
    try:
        c.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    c.executescript("""
        CREATE TABLE IF NOT EXISTS ai_usage(day TEXT PRIMARY KEY,
            images INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, content TEXT, image_b64 TEXT, image_desc TEXT,
            post_type TEXT DEFAULT 'text', mood TEXT, repost_of INTEGER,
            likes INTEGER DEFAULT 0, created_at REAL);
        CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER, username TEXT, content TEXT, is_ai INTEGER DEFAULT 0, created_at REAL);
        CREATE TABLE IF NOT EXISTS likes(id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER, username TEXT, UNIQUE(post_id, username));
        CREATE TABLE IF NOT EXISTS stories(id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, image_b64 TEXT, caption TEXT, is_highlight INTEGER DEFAULT 0, created_at REAL);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,
            persona TEXT, sender TEXT, content TEXT, created_at REAL);
        CREATE TABLE IF NOT EXISTS bookmarks(id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER, username TEXT, created_at REAL, UNIQUE(post_id, username));
        CREATE TABLE IF NOT EXISTS me_profile(id INTEGER PRIMARY KEY CHECK (id=1),
            display_name TEXT, bio TEXT, avatar TEXT);
    """)
    # Migration: add is_highlight column if missing (for existing DBs)
    try:
        c.execute("ALTER TABLE stories ADD COLUMN is_highlight INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Migration: add mood column to posts (diary feature)
    try:
        c.execute("ALTER TABLE posts ADD COLUMN mood TEXT")
    except sqlite3.OperationalError:
        pass
    # Migration: add repost_of column to posts
    try:
        c.execute("ALTER TABLE posts ADD COLUMN repost_of INTEGER")
    except sqlite3.OperationalError:
        pass
    # Migration: add parent_id to comments (threaded replies — 1 level)
    try:
        c.execute("ALTER TABLE comments ADD COLUMN parent_id INTEGER")
    except sqlite3.OperationalError:
        pass
    # Seed default profile if empty
    cur = c.execute("SELECT COUNT(*) FROM me_profile").fetchone()
    if cur[0] == 0:
        c.execute(
            "INSERT INTO me_profile(id, display_name, bio, avatar) VALUES(1, ?, ?, ?)",
            ("Kamu 👤", "✨ Living, learning, creating.\n🎨 Design & tech. Jakarta 🇮🇩", "K"),
        )
    c.commit()
    c.close()


def get_db():
    """Request-scoped DB connection. Use within Flask request context."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Teardown function — register in app via app.teardown_appcontext(close_db)."""
    db = g.pop("db", None)
    if db:
        db.close()
