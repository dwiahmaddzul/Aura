"""
Aura Social v3 — Modular Edition
Single-page social app with 6 cross-model AI personas.

Run dev   : python app.py
Run prod  : gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4

AI behaviour and cost brakes are tuned live from /kelola (password from the
ADMIN_PASSWORD env var); see settings_rt.py.
"""
import hashlib
import os
from datetime import timedelta
from pathlib import Path

from flask import Flask, render_template, request, url_for

from config import (
    COOKIE_SECURE,
    DB_PATH,
    IMAGE_MODEL,
    MEDIA_MIGRATE,
    SECRET_KEY,
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE,
    TEXT_MODEL,
    VISION_MODEL,
)
from db import close_db, init_db
from personas import PERSONAS
from api import register_blueprints
from ai_engine.schedulers import start_background_workers

STATIC_DIR = Path(__file__).resolve().parent / "static"
_ASSET_V = {}


def asset(path):
    """URL static berversi (?v=<hash isi>) supaya bisa di-cache setahun penuh
    tanpa takut versi lama nyangkut setelah deploy."""
    v = _ASSET_V.get(path)
    if v is None:
        try:
            v = hashlib.md5((STATIC_DIR / path).read_bytes()).hexdigest()[:10]
        except OSError:
            v = "0"
        _ASSET_V[path] = v
    return url_for("static", filename=path, v=v)


# Path API yang BUKAN tanda "user sedang membuka app" (tidak menyalakan scheduler).
_NOT_ACTIVITY = ("/api/health", "/api/kelola")


def create_app():
    """Flask app factory. Registers blueprints + teardown + DB init."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.teardown_appcontext(close_db)
    app.config.update(
        SEND_FILE_MAX_AGE_DEFAULT=timedelta(days=365),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=COOKIE_SECURE,
        SESSION_COOKIE_NAME="aura_kelola",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        JSON_SORT_KEYS=False,
    )
    register_blueprints(app)
    with app.app_context():
        init_db()
    import settings_rt
    app.secret_key = SECRET_KEY or settings_rt.secret_key()
    app.jinja_env.globals["asset"] = asset

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.before_request
    def _track_activity():
        p = request.path
        if p.startswith("/api/") and not p.startswith(_NOT_ACTIVITY):
            from ai_engine.limits import mark_activity
            mark_activity()

    @app.after_request
    def _security_headers(resp):
        h = resp.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # CSP minimal yang tidak memutus handler onclick inline di frontend:
        # cegah clickjacking, plugin, dan pembajakan <base>.
        h.setdefault("Content-Security-Policy",
                     "frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
        return resp

    @app.after_request
    def _cache_policy(resp):
        # GET JSON API: boleh disimpan browser tapi wajib divalidasi ulang.
        # ETag → polling yang isinya tidak berubah dijawab 304 tanpa isi
        # (hemat upload internet rumah).
        if (request.method == "GET" and request.path.startswith("/api/")
                and resp.status_code == 200 and resp.mimetype == "application/json"):
            resp.headers["Cache-Control"] = "no-cache"
            resp.add_etag()
            resp.make_conditional(request)
        elif request.path == "/" or request.path.startswith("/kelola"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    return app


def _print_banner():
    import settings_rt as S
    has_key = bool(SILICONFLOW_API_KEY) and not SILICONFLOW_API_KEY.startswith("sk-GANTI")
    print("=" * 58)
    print("  🚀 Aura Social v3 — Modular Edition")
    print("=" * 58)
    print(f"  Endpoint  : {SILICONFLOW_BASE}")
    print(f"  API Key   : {'✅ loaded' if has_key else '❌ MISSING'}")
    print(f"  Text      : {TEXT_MODEL}")
    print(f"  Vision    : {VISION_MODEL}")
    print(f"  ImageGen  : {IMAGE_MODEL}")
    print(f"  DB        : {DB_PATH}")
    print(f"  AI        : {'ON' if S.get('ai_enabled') else 'OFF'} · post {S.get('post_interval_min')}-"
          f"{S.get('post_interval_max')}mnt · gambar/hari {S.get('image_daily_limit')} (atur di /kelola)")
    print(f"  Personas  : {len(PERSONAS)}")
    print("=" * 58, flush=True)


app = create_app()

# Start background workers at module-level so it works under both
# `python app.py` AND `gunicorn app:app`.
# Set RUN_SCHEDULER=0 on extra replicas to prevent duplicate posts.
if os.environ.get("RUN_SCHEDULER", "1") == "1":
    _print_banner()
    start_background_workers()

if MEDIA_MIGRATE:
    import media
    media.start_migration_thread()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"  → http://0.0.0.0:{port}")
    print("=" * 58, flush=True)
    # host=0.0.0.0 required for Railway/Docker
    # use_reloader=False prevents double-spawn of background threads
    app.run(host="0.0.0.0", debug=debug, threaded=True, port=port, use_reloader=False)
