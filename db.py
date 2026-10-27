"""
Aura Social — Database Layer
SQLite schema, connection helpers, and migrations.
"""
import sqlite3
from flask import g

from config import DB_PATH


def _add_column(c, table, coldef):
    try:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
        return True
    except sqlite3.OperationalError:
        return False


def init_db():
    """Initialize schema. Idempotent — safe to call multiple times."""
    c = sqlite3.connect(DB_PATH, timeout=30)
    # WAL: penulis (scheduler threads) tidak memblok pembaca (request Flask).
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
    # ── kolom tambahan (migrasi untuk DB lama) ──
    _add_column(c, "stories", "is_highlight INTEGER DEFAULT 0")
    _add_column(c, "posts", "mood TEXT")
    _add_column(c, "posts", "repost_of INTEGER")
    _add_column(c, "comments", "parent_id INTEGER")
    # Gambar dipindah ke file (media.py). has_img/img_w/img_h dipakai feed
    # supaya tidak perlu menyentuh kolom image_b64 yang besar.
    new_post_flag = _add_column(c, "posts", "has_img INTEGER")
    _add_column(c, "posts", "img_w INTEGER")
    _add_column(c, "posts", "img_h INTEGER")
    new_story_flag = _add_column(c, "stories", "has_img INTEGER")
    _add_column(c, "stories", "img_w INTEGER")
    _add_column(c, "stories", "img_h INTEGER")
    _add_column(c, "stories", "prompt TEXT")
    _add_column(c, "likes", "created_at REAL")
    if new_post_flag:
        c.execute("UPDATE posts SET has_img = (image_b64 IS NOT NULL) WHERE has_img IS NULL")
    if new_story_flag:
        c.execute("UPDATE stories SET has_img = (image_b64 IS NOT NULL) WHERE has_img IS NULL")
    # Like lama tidak punya waktu: pakai waktu post-nya (lebih jujur daripada "baru").
    c.execute(
        "UPDATE likes SET created_at = (SELECT created_at FROM posts WHERE posts.id = likes.post_id) "
        "WHERE created_at IS NULL"
    )
    # ── index (dulu tidak ada sama sekali) ──
    c.executescript("""
        CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at);
        CREATE INDEX IF NOT EXISTS idx_posts_user_created ON posts(username, created_at);
        CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_stories_created ON stories(created_at);
        CREATE INDEX IF NOT EXISTS idx_stories_user ON stories(username, created_at);
        CREATE INDEX IF NOT EXISTS idx_messages_persona ON messages(persona, created_at);
        CREATE INDEX IF NOT EXISTS idx_likes_user ON likes(username, post_id);
        CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON bookmarks(username, post_id);
    """)
    # Tabel pengaturan dashboard + catatan pemakaian AI.
    import settings_rt
    from ai_engine import usage
    settings_rt.init(c)
    usage.init(c)
    # Seed default profile if empty
    cur = c.execute("SELECT COUNT(*) FROM me_profile").fetchone()
    if cur[0] == 0:
        c.execute(
            "INSERT INTO me_profile(id, display_name, bio, avatar) VALUES(1, ?, ?, ?)",
            ("Kamu 👤", "✨ Living, learning, creating.\n🎨 Design & tech. Jakarta 🇮🇩", "K"),
        )
    c.commit()
    c.close()


def connect():
    """Koneksi untuk thread latar (bukan request)."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def get_db():
    """Request-scoped DB connection. Use within Flask request context."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=15)
        g.db.execute("PRAGMA synchronous=NORMAL")
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Teardown function — register in app via app.teardown_appcontext(close_db)."""
    db = g.pop("db", None)
    if db:
        db.close()
