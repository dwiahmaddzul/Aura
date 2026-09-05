"""
Aura Social v3 — Modular Edition
Single-page social app with 6 cross-model AI personas.

Run dev   : python app.py
Run prod  : gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4
"""
import os
from flask import Flask, render_template, request

from config import (
    DB_PATH,
    IMAGE_MODEL,
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE,
    TEXT_MODEL,
    VISION_MODEL,
)
from db import close_db, init_db
from personas import PERSONAS
from api import register_blueprints
from ai_engine.schedulers import start_background_workers


def create_app():
    """Flask app factory. Registers blueprints + teardown + DB init."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.teardown_appcontext(close_db)
    register_blueprints(app)
    with app.app_context():
        init_db()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.before_request
    def _track_activity():
        # Semua hit /api/* datang dari browser user (app single-user).
        # /api/health dikecualikan supaya uptime monitor tidak dihitung
        # sebagai "user aktif".
        p = request.path
        if p.startswith("/api/") and p != "/api/health":
            from ai_engine.limits import mark_activity
            mark_activity()

    return app


def _print_banner():
    has_key = bool(SILICONFLOW_API_KEY) and not SILICONFLOW_API_KEY.startswith("sk-GANTI")
    print("=" * 58)
    print("  🚀 Aura Social v3 — Modular Edition")
    print("=" * 58)
    print(f"  Endpoint  : {SILICONFLOW_BASE}")
    print(f"  API Key   : {'✅ loaded' if has_key else '❌ MISSING'}")
    if not has_key:
        print(f"              → Set SILICONFLOW_API_KEY in environment")
    print(f"  Text      : {TEXT_MODEL}")
    print(f"  Vision    : {VISION_MODEL}")
    print(f"  ImageGen  : {IMAGE_MODEL}")
    print(f"  DB        : {DB_PATH}")
    from config import (
        AI_ACTIVE_WINDOW_MIN, AI_IMAGE_DAILY_LIMIT, AI_POST_IMAGE_PROB,
        AI_POST_INTERVAL_MAX, AI_POST_INTERVAL_MIN, AI_STORY_INTERVAL_MAX,
        AI_STORY_INTERVAL_MIN, AI_STORY_PROB,
    )
    print(f"  AI-Post   : tiap {AI_POST_INTERVAL_MIN}-{AI_POST_INTERVAL_MAX}mnt, img prob {AI_POST_IMAGE_PROB}")
    print(f"  AI-Story  : tiap {AI_STORY_INTERVAL_MIN}-{AI_STORY_INTERVAL_MAX}mnt, prob {AI_STORY_PROB}")
    print(f"  Img/hari  : max {AI_IMAGE_DAILY_LIMIT}")
    print(f"  ActiveWin : {AI_ACTIVE_WINDOW_MIN}mnt {'(24/7)' if AI_ACTIVE_WINDOW_MIN <= 0 else ''}")
    print(f"  Personas  : {len(PERSONAS)}")
    for p in PERSONAS:
        print(f"    {p['avatar']} {p['username']:<15} txt={p['text_model'].split('/')[-1][:20]:<20} prob={p['reply_prob']}")
    print("=" * 58, flush=True)


app = create_app()

# Start background workers at module-level so it works under both
# `python app.py` AND `gunicorn app:app`.
# Set RUN_SCHEDULER=0 on extra replicas to prevent duplicate posts.
if os.environ.get("RUN_SCHEDULER", "1") == "1":
    _print_banner()
    start_background_workers()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"  → http://0.0.0.0:{port}")
    print("=" * 58, flush=True)
    # host=0.0.0.0 required for Railway/Docker
    # use_reloader=False prevents double-spawn of background threads
    app.run(host="0.0.0.0", debug=debug, threaded=True, port=port, use_reloader=False)