"""
Aura Social — Dashboard /kelola (kendali AI & biaya)

Dilindungi password dari env ADMIN_PASSWORD. Sesi disimpan di cookie
bertanda tangan (HttpOnly, SameSite=Strict, Secure). Semua POST wajib membawa
header X-Kelola: 1 (tidak bisa dikirim lintas situs tanpa CORS).
"""
import hashlib
import hmac
import os
import sqlite3
import threading
import time
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, send_file, session

import media
import settings_rt as S
from ai_engine import limits, usage
from config import ADMIN_PASSWORD, DB_PATH, IMAGE_MODEL, SILICONFLOW_API_KEY
from db import get_db
from llm.client import call_llm
from security import rate_limit

bp = Blueprint("kelola", __name__)

_storage_cache = {"t": 0.0, "v": None}


def _pw_tag():
    return hashlib.sha256(("aura-kelola:" + ADMIN_PASSWORD).encode()).hexdigest()[:20]


def _authed():
    return bool(ADMIN_PASSWORD) and session.get("kelola") == _pw_tag()


def _guard():
    """None kalau boleh lanjut, atau response error."""
    if not _authed():
        return jsonify({"error": "belum masuk"}), 401
    if request.method == "POST" and request.headers.get("X-Kelola") != "1":
        return jsonify({"error": "header X-Kelola wajib"}), 400
    return None


# ── halaman ───────────────────────────────────────────────────────────────
@bp.route("/kelola")
@bp.route("/kelola/")
def kelola_page():
    return render_template("kelola.html")


@bp.route("/manage")
@bp.route("/admin")
def kelola_alias():
    return redirect("/kelola", code=302)


# ── auth ──────────────────────────────────────────────────────────────────
@bp.route("/api/kelola/login", methods=["POST"])
@rate_limit(max_calls=6, window=300)
def api_login():
    if not ADMIN_PASSWORD:
        return jsonify({"error": "ADMIN_PASSWORD belum di-set di server"}), 503
    if request.headers.get("X-Kelola") != "1":
        return jsonify({"error": "header X-Kelola wajib"}), 400
    pw = str((request.get_json(silent=True) or {}).get("password", ""))
    ok = hmac.compare_digest(
        hashlib.sha256(pw.encode()).digest(), hashlib.sha256(ADMIN_PASSWORD.encode()).digest()
    )
    if not ok:
        time.sleep(0.6)
        return jsonify({"error": "Password salah"}), 401
    session.clear()
    session.permanent = True
    session["kelola"] = _pw_tag()
    return jsonify({"ok": True})


@bp.route("/api/kelola/logout", methods=["POST"])
def api_logout():
    session.pop("kelola", None)
    return jsonify({"ok": True})


# ── state ─────────────────────────────────────────────────────────────────
def _storage():
    now = time.time()
    if _storage_cache["v"] and now - _storage_cache["t"] < 60:
        v = dict(_storage_cache["v"])
    else:
        db = Path(DB_PATH)
        wal = Path(str(db) + "-wal")
        mbytes, mfiles = media.dir_size()
        v = {
            "db_bytes": db.stat().st_size if db.exists() else 0,
            "wal_bytes": wal.stat().st_size if wal.exists() else 0,
            "media_bytes": mbytes,
            "media_files": mfiles,
        }
        _storage_cache.update(t=now, v=v)
        v = dict(v)
    v["migration"] = dict(media.MIGRATION)
    v["backup"] = S.get_raw("_media_backup")
    return v


def _counts():
    db = get_db()
    one = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "posts": one("SELECT COUNT(*) FROM posts"),
        "my_posts": one("SELECT COUNT(*) FROM posts WHERE username='me'"),
        "ai_posts": one("SELECT COUNT(*) FROM posts WHERE username!='me'"),
        "stories": one("SELECT COUNT(*) FROM stories"),
        "comments": one("SELECT COUNT(*) FROM comments"),
        "messages": one("SELECT COUNT(*) FROM messages"),
        "legacy_images": one("SELECT COUNT(*) FROM posts WHERE image_b64 IS NOT NULL")
        + one("SELECT COUNT(*) FROM stories WHERE image_b64 IS NOT NULL"),
    }


def _scheduler():
    from ai_engine.schedulers import STATE
    now = time.time()
    return {
        "running": STATE["started_at"] is not None,
        "blocked": STATE["blocked"],
        "next_post_in": int(STATE["next_post"] - now) if STATE["next_post"] else None,
        "next_story_in": int(STATE["next_story"] - now) if STATE["next_story"] else None,
        "last_post": STATE["last_post"],
        "last_story": STATE["last_story"],
    }


@bp.route("/api/kelola/state")
def api_state():
    if not ADMIN_PASSWORD:
        return jsonify({"authed": False, "configured": False}), 401
    if not _authed():
        return jsonify({"authed": False, "configured": True}), 401
    snap = S.snapshot()
    return jsonify({
        "authed": True,
        **snap,
        "status": limits.status(),
        "scheduler": _scheduler(),
        "usage": {
            "today": usage.day_totals(),
            "history": usage.history(14),
            "by_persona": usage.by_persona(7),
            "by_model": usage.by_model(7),
            "errors": usage.recent_errors(),
        },
        "storage": _storage(),
        "counts": _counts(),
        "image_model": IMAGE_MODEL,
        "api_key_present": bool(SILICONFLOW_API_KEY),
        "server_time": time.time(),
    })


# ── ubah setting ──────────────────────────────────────────────────────────
@bp.route("/api/kelola/settings", methods=["POST"])
def api_settings():
    g = _guard()
    if g:
        return g
    saved, errors = S.save(request.get_json(silent=True) or {})
    return jsonify({"saved": saved, "errors": errors, **S.snapshot()}), (200 if not errors else 422)


@bp.route("/api/kelola/preset", methods=["POST"])
def api_preset():
    g = _guard()
    if g:
        return g
    name = (request.get_json(silent=True) or {}).get("name")
    if S.apply_preset(name) is None:
        return jsonify({"error": "preset tidak dikenal"}), 400
    return jsonify({"ok": True, **S.snapshot()})


@bp.route("/api/kelola/reset", methods=["POST"])
def api_reset():
    g = _guard()
    if g:
        return g
    S.reset_defaults()
    return jsonify({"ok": True, **S.snapshot()})


# ── tes model ─────────────────────────────────────────────────────────────
@bp.route("/api/kelola/test-model", methods=["POST"])
@rate_limit(max_calls=20, window=60)
def api_test_model():
    g = _guard()
    if g:
        return g
    model = str((request.get_json(silent=True) or {}).get("model", "")).strip()
    if not S._MODEL_RE.match(model):
        return jsonify({"ok": False, "error": "nama model tidak valid"}), 400
    t0 = time.time()
    out = call_llm([{"role": "user", "content": "Balas dengan satu kata: oke"}], model,
                   max_tokens=8, kind="test", auto=False, temperature=0.1)
    ms = int((time.time() - t0) * 1000)
    if out:
        return jsonify({"ok": True, "reply": out[:40], "ms": ms})
    errs = [e for e in usage.recent_errors(hours=1, limit=20) if e["model"] == model]
    return jsonify({"ok": False, "ms": ms, "error": errs[0]["err"] if errs else "tidak ada jawaban"})


# ── jalankan sekarang (untuk mencoba) ─────────────────────────────────────
@bp.route("/api/kelola/run", methods=["POST"])
@rate_limit(max_calls=6, window=300)
def api_run():
    g = _guard()
    if g:
        return g
    what = (request.get_json(silent=True) or {}).get("what")
    from ai_engine import schedulers
    fn = {"post": schedulers.ai_post_once, "story": schedulers.ai_story_once}.get(what)
    if not fn:
        return jsonify({"error": "pilih post atau story"}), 400
    if not S.get("ai_enabled"):
        return jsonify({"error": "AI sedang dimatikan"}), 409

    def _go():
        with schedulers._lock:
            try:
                fn()
            except Exception as e:
                print(f"[Kelola] run {what} error: {e}")

    threading.Thread(target=_go, daemon=True).start()
    return jsonify({"ok": True, "started": what})


# ── data ──────────────────────────────────────────────────────────────────
@bp.route("/api/kelola/backup")
def api_backup():
    if not _authed():
        return jsonify({"error": "belum masuk"}), 401
    bdir = Path(DB_PATH).resolve().parent / "backup"
    bdir.mkdir(parents=True, exist_ok=True)
    dest = bdir / f"aura-{time.strftime('%Y%m%d-%H%M%S')}.db"
    src = sqlite3.connect(DB_PATH, timeout=30)
    try:
        tgt = sqlite3.connect(str(dest))
        try:
            src.backup(tgt)
        finally:
            tgt.close()
    finally:
        src.close()
    # Simpan 3 backup manual terakhir saja.
    olds = sorted(bdir.glob("aura-2*.db"))
    for old in olds[:-3]:
        try:
            old.unlink()
        except OSError:
            pass
    return send_file(dest, as_attachment=True, download_name=dest.name,
                     mimetype="application/x-sqlite3", max_age=0)


@bp.route("/api/kelola/maintenance", methods=["POST"])
def api_maintenance():
    g = _guard()
    if g:
        return g
    action = (request.get_json(silent=True) or {}).get("action")
    if action == "migrate_media":
        if media.MIGRATION["state"] == "running":
            return jsonify({"ok": True, "migration": media.MIGRATION})
        threading.Thread(target=media.migrate_legacy, daemon=True).start()
        return jsonify({"ok": True, "started": True})
    if action == "vacuum":
        c = sqlite3.connect(DB_PATH, timeout=30)
        try:
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            c.execute("VACUUM")
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            c.close()
        _storage_cache["t"] = 0
        return jsonify({"ok": True})
    if action == "delete_backup":
        p = S.get_raw("_media_backup")
        if p and Path(p).exists() and media.MIGRATION["state"] != "running":
            os.remove(p)
            S.set_raw("_media_backup", "")
            _storage_cache["t"] = 0
            return jsonify({"ok": True})
        return jsonify({"error": "tidak ada backup migrasi"}), 404
    return jsonify({"error": "aksi tidak dikenal"}), 400
