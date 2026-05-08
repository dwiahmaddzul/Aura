"""
Aura Social v3 — Modular Edition
Single-page social app with 6 cross-model AI personas.

Run: python app.py → http://localhost:5000
"""
from flask import Flask, render_template

from config import (
    DB_PATH,
    IMAGE_MODEL,
    PORT,
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
    # Initialize DB inside app context (idempotent — CREATE IF NOT EXISTS)
    with app.app_context():
        init_db()

    @app.route("/")
    def index():
        return render_template("index.html")

    return app


app = create_app()


def _print_banner():
    has_key = bool(SILICONFLOW_API_KEY) and not SILICONFLOW_API_KEY.startswith("sk-GANTI")
    print("=" * 58)
    print("  🚀 Aura Social v3 — Modular Edition")
    print("=" * 58)
    print(f"  Endpoint  : {SILICONFLOW_BASE}")
    print(f"  API Key   : {'✅ loaded' if has_key else '❌ MISSING'}")
    if not has_key:
        print(f"              → Bikin file .env dulu (copy dari .env.example)")
        print(f"              → Set SILICONFLOW_API_KEY=sk-xxx")
        print(f"              → Restart app")
    print(f"  Text      : {TEXT_MODEL}")
    print(f"  Vision    : {VISION_MODEL}")
    print(f"  ImageGen  : {IMAGE_MODEL}")
    print(f"  DB        : {DB_PATH}")
    print(f"  Personas  : {len(PERSONAS)}")
    for p in PERSONAS:
        print(f"    {p['avatar']} {p['username']:<15} txt={p['text_model'].split('/')[-1][:20]:<20} prob={p['reply_prob']}")
    print("=" * 58)


if __name__ == "__main__":
    _print_banner()
    start_background_workers()
    print("=" * 58)
    print(f"  → http://localhost:{PORT}")
    print("=" * 58)
    # use_reloader=False is CRITICAL — reloader would double-spawn background threads
    app.run(debug=True, threaded=True, port=PORT, use_reloader=False)
