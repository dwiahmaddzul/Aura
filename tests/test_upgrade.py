"""
Aura — tests for the Oct 2026 upgrade: media files + migration, feed paging,
ETag, notifications, cost brakes, settings, /kelola auth, text cleaner.

Shares the temp DB / env set up by test_smoke.py when run together; works on
its own too (same env bootstrap).
"""
import base64
import io
import os
import sqlite3
import tempfile
import time

if "DB_PATH" not in os.environ:
    _TMP = tempfile.mkdtemp(prefix="aura-test-")
    os.environ.update({
        "RUN_SCHEDULER": "0", "SILICONFLOW_API_KEY": "sk-test-dummy-key-0123456789",
        "DB_PATH": os.path.join(_TMP, "aura.db"), "MEDIA_DIR": os.path.join(_TMP, "media"),
        "MEDIA_MIGRATE": "0", "COOKIE_SECURE": "0", "ADMIN_PASSWORD": "rahasia-uji-123",
    })

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from app import app as flask_app  # noqa: E402
import media  # noqa: E402
import security  # noqa: E402
import settings_rt as S  # noqa: E402
from ai_engine import limits, usage  # noqa: E402
from config import DB_PATH  # noqa: E402
from llm import client as llm_client  # noqa: E402
from llm.clean import clean_ai_text  # noqa: E402
from personas import PMAP  # noqa: E402

PW = os.environ["ADMIN_PASSWORD"]
H = {"X-Kelola": "1"}


def png_b64(w=900, h=600, color=(200, 120, 60)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


class _FakeResp:
    def __init__(self, status=200, data=None, text=""):
        self.status_code, self._d, self.text = status, data or {}, text
        self.content = b""

    def json(self):
        return self._d


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Never hit SiliconFlow from tests: canned chat replies."""
    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/chat/completions"):
            return _FakeResp(200, {"choices": [{"message": {"content": "Post: \"oke sip\""}}],
                                   "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
        return _FakeResp(500, text="no images in tests")
    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    security._hits.clear()
    yield


@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def insert_post(username="maya_art", content="halo", ts=None, b64=None):
    c = db()
    pid = c.execute(
        "INSERT INTO posts(username,content,image_b64,post_type,has_img,created_at) VALUES(?,?,?,?,?,?)",
        (username, content, b64, "image" if b64 else "text", 1 if b64 else 0, ts or time.time()),
    ).lastrowid
    c.commit()
    c.close()
    return pid


# ── text cleaner ──
@pytest.mark.parametrize("raw,expected", [
    ('Post: "fixing bug seharian 😤"', "fixing bug seharian 😤"),
    ("POST: Neon jingga nyala. **Kalo post ada FOTO, komentar soal visual/komposisi.**", "Neon jingga nyala."),
    ('Post: "standup meeting"    atau    Story: laptop screen', "standup meeting"),
    ("Komentar: wkwk gw juga", "wkwk gw juga"),
    ("<think>hmm</think> sabi lightingnya", "sabi lightingnya"),
    ("Makasih komentarnya! **seru** sih", "Makasih komentarnya! seru sih"),
])
def test_clean_ai_text(raw, expected):
    assert clean_ai_text(raw) == expected


def test_clean_signature():
    assert clean_ai_text("api tak punya ruang, Maya", PMAP["maya_art"]) == "api tak punya ruang"


# ── feed paging / filters / etag ──
def test_feed_paging_and_filters(client):
    base = time.time() - 10_000
    ids = [insert_post("me" if i % 2 else "rizky_dev", f"paging-{i}", base + i) for i in range(6)]
    page1 = client.get("/api/posts?limit=2").get_json()
    assert len(page1) == 2
    older = client.get(f"/api/posts?limit=50&before={base + 3}").get_json()
    assert all(p["created_at"] < base + 3 for p in older)
    mine = client.get("/api/posts?mine=1&limit=60").get_json()
    assert mine and all(p["username"] == "me" for p in mine)
    found = client.get("/api/posts?mine=1&q=paging-3").get_json()
    assert [p["id"] for p in found] == [ids[3]]
    # no heavy fields leak out, time is a timestamp (client renders the label)
    p = page1[0]
    assert "image_b64" not in p and "image_desc" not in p and "created_at" in p


def test_etag_304(client):
    r1 = client.get("/api/posts?limit=3")
    et = r1.headers.get("ETag")
    assert et and r1.headers["Cache-Control"] == "no-cache"
    r2 = client.get("/api/posts?limit=3", headers={"If-None-Match": et})
    assert r2.status_code == 304


# ── media ──
def test_upload_creates_webp_files(client):
    r = client.post("/api/posts", json={"content": "foto baru", "image_b64": png_b64()})
    assert r.status_code == 201
    d = r.get_json()
    post = d["post"]
    assert post["has_image"] and post["img"].endswith("-t.webp") and post["img_w"] == 900
    t = client.get(post["img"])
    assert t.status_code == 200 and t.mimetype == "image/webp"
    assert "private" in t.headers["Cache-Control"] and "immutable" in t.headers["Cache-Control"]
    full = client.get(post["img_full"])
    assert full.status_code == 200
    with Image.open(io.BytesIO(t.data)) as im:
        assert max(im.size) <= 640
    # legacy URL still works
    assert client.get(f"/api/posts/{d['id']}/image").status_code == 200
    row = db().execute("SELECT image_b64, has_img FROM posts WHERE id=?", (d["id"],)).fetchone()
    assert row["image_b64"] is None and row["has_img"] == 1


def test_ai_image_is_public_cacheable(client):
    pid = insert_post("dimas_photo", "senja")
    media.save("p", pid, png_b64(512, 512))
    c = db()
    c.execute("UPDATE posts SET has_img=1, img_w=512, img_h=512 WHERE id=?", (pid,))
    c.commit()
    r = client.get(f"/media/p/{pid}-t.webp")
    assert r.status_code == 200 and r.headers["Cache-Control"].startswith("public")


def test_media_404s(client):
    assert client.get("/media/p/999999-t.webp").status_code == 404
    assert client.get("/media/x/1-t.webp").status_code == 404
    assert client.get("/media/p/../../etc-t.webp").status_code == 404


def test_legacy_migration_moves_blobs(client):
    b64 = png_b64(400, 300)
    pid = insert_post("nadiafood", "lama", b64=b64)
    c = db()
    sid = c.execute(
        "INSERT INTO stories(username,image_b64,caption,is_highlight,has_img,created_at) VALUES(?,?,?,?,?,?)",
        ("nadiafood", b64, "delicious ramen bowl with steam rising", 1, 1, time.time()),
    ).lastrowid
    c.commit()
    c.close()
    media.MIGRATION["state"] = "idle"
    res = media.migrate_legacy(pause=0)
    assert res["state"] == "done", res
    assert res["backup"] and os.path.exists(res["backup"])
    row = db().execute("SELECT image_b64, has_img, img_w, img_h FROM posts WHERE id=?", (pid,)).fetchone()
    assert row["image_b64"] is None and row["has_img"] == 1 and (row["img_w"], row["img_h"]) == (400, 300)
    assert media.orig_path("p", pid).exists() and media.variant_path("p", pid, "t").exists()
    assert db().execute("SELECT image_b64 FROM stories WHERE id=?", (sid,)).fetchone()[0] is None
    assert client.get(f"/media/s/{sid}-f.webp").status_code == 200
    # the English image prompt is not shown as a caption
    st = client.get("/api/stories").get_json()
    sl = [s for g in st for s in g["slides"] if s["id"] == sid]
    assert sl and sl[0]["caption"] == ""


# ── delete ──
def test_delete_own_post_only(client):
    mine = client.post("/api/posts", json={"content": "hapus aku"}).get_json()["id"]
    # the app is public → deleting needs the /kelola session
    r = client.delete(f"/api/posts/{mine}")
    assert r.status_code == 401 and r.get_json()["need_login"]
    assert client.post("/api/kelola/login", json={"password": PW}, headers=H).status_code == 200
    assert client.delete(f"/api/posts/{mine}").status_code == 200
    assert client.get(f"/api/posts/{mine}").status_code == 404
    ai = insert_post("bimo.plays", "gg")
    assert client.delete(f"/api/posts/{ai}").status_code == 403


# ── notifications ──
def test_like_times_are_real(client):
    pid = client.post("/api/posts", json={"content": "tulisan lama"}).get_json()["id"]
    c = db()
    c.execute("UPDATE posts SET created_at=? WHERE id=?", (time.time() - 40 * 86400, pid))
    c.execute("INSERT INTO likes(post_id,username,created_at) VALUES(?,?,?)", (pid, "maya_art", None))
    c.commit()
    c.close()
    from db import init_db
    with flask_app.app_context():
        init_db()  # backfills legacy like times
    ev = [e for e in client.get("/api/notifications").get_json() if e["kind"] == "like" and e["post_id"] == pid]
    assert ev and ev[0]["created_at"] < time.time() - 30 * 86400


# ── profile + stats ──
def test_profile_counts_are_real(client):
    for i in range(3):
        insert_post("ara_style", f"ootd {i}")
    d = client.get("/api/profile/ara_style").get_json()
    assert d["post_count"] >= 3 and len(d["posts"]) <= 30
    s = client.get("/api/me/stats").get_json()
    assert {"entries", "this_month", "photos"} <= set(s)
    p1 = client.get("/api/me/daily-prompt").get_json()
    p2 = client.get("/api/me/daily-prompt").get_json()
    assert p1 == p2  # stable within the day


def test_dm_since(client):
    client.post("/api/dm/maya_art", json={"content": "satu"})
    full = client.get("/api/dm/maya_art").get_json()["messages"]
    last = full[-1]["created_at"]
    assert client.get(f"/api/dm/maya_art?since={last}").get_json()["messages"] == []


# ── settings + brakes ──
def test_settings_validation_and_pairs():
    saved, errors = S.save({"post_interval_min": 90, "post_interval_max": 30, "post_image_prob": 7,
                            "nope": 1, "p.bimo.plays.reply_prob": 0.2, "p.ghost.active": False})
    assert saved["post_image_prob"] == 1.0
    assert S.get("post_interval_min") <= S.get("post_interval_max")
    assert "nope" in errors and "p.ghost.active" in errors
    assert S.persona("bimo.plays", "reply_prob") == 0.2
    _, err = S.save({"app_tz": "Mars/Olympus"})
    assert "app_tz" in err
    S.reset_defaults()


def test_image_quota_and_persona_permission():
    S.save({"image_daily_limit": 1})
    c = db()
    c.execute("DELETE FROM ai_usage")
    c.commit()
    c.close()
    S.save({"p.maya_art.can_image": False})
    assert limits.try_consume_image("maya_art") is False
    assert limits.try_consume_image("nadiafood") is True
    assert limits.try_consume_image("nadiafood") is False  # quota used up
    S.reset_defaults()


def test_budget_and_master_switch_block_auto():
    S.reset_defaults()
    limits.mark_activity()
    assert limits.auto_block_reason() is None
    S.save({"daily_budget_usd": 0.01})
    usage.record("post", "Qwen/Qwen2.5-72B-Instruct", "maya_art", pt=20_000_000, ct=0)
    assert limits.auto_block_reason() == "anggaran harian habis"
    S.save({"ai_enabled": False})
    assert limits.auto_block_reason() == "AI dimatikan"
    assert limits.interactive_block_reason() == "AI dimatikan"
    S.reset_defaults()
    c = db()
    c.execute("DELETE FROM ai_calls")
    c.commit()
    c.close()


def test_llm_calls_are_logged_with_cost():
    c = db()
    c.execute("DELETE FROM ai_calls")
    c.commit()
    c.close()
    out = llm_client.call_llm([{"role": "user", "content": "x"}], "Qwen/Qwen3-14B", kind="post", persona="bimo.plays")
    assert out
    t = usage.day_totals()
    assert t["calls"] == 1 and t["tokens_in"] == 100 and t["cost"] > 0


def test_thinking_disabled_for_qwen3(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(json)
        return _FakeResp(200, {"choices": [{"message": {"content": "ok"}}], "usage": {}})
    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    llm_client.call_llm([{"role": "user", "content": "x"}], "Qwen/Qwen3-32B")
    assert seen.get("enable_thinking") is False
    seen.clear()
    llm_client.call_llm([{"role": "user", "content": "x"}], "Qwen/Qwen2.5-72B-Instruct")
    assert "enable_thinking" not in seen


def test_quiet_hours(monkeypatch):
    from datetime import datetime
    S.save({"quiet_enabled": True, "quiet_start": 23, "quiet_end": 6})
    monkeypatch.setattr(limits, "now_local", lambda: datetime(2026, 10, 27, 2, 0))
    assert limits.in_quiet_hours() is True
    monkeypatch.setattr(limits, "now_local", lambda: datetime(2026, 10, 27, 14, 0))
    assert limits.in_quiet_hours() is False
    S.reset_defaults()


# ── /kelola ──
def test_kelola_auth_flow(client):
    assert client.get("/kelola").status_code == 200
    assert client.get("/api/kelola/state").status_code == 401
    assert client.post("/api/kelola/login", json={"password": PW}).status_code == 400  # no header
    assert client.post("/api/kelola/login", json={"password": "salah"}, headers=H).status_code == 401
    assert client.post("/api/kelola/login", json={"password": PW}, headers=H).status_code == 200
    st = client.get("/api/kelola/state").get_json()
    assert st["authed"] and "settings" in st and "usage" in st and len(st["personas"]) == 6
    # save without the header is refused
    assert client.post("/api/kelola/settings", json={"comment_max": 2}).status_code == 400
    r = client.post("/api/kelola/settings", json={"comment_max": 2, "image_daily_limit": 4}, headers=H)
    assert r.status_code == 200 and r.get_json()["settings"]["comment_max"] == 2
    bad = client.post("/api/kelola/settings", json={"app_tz": "Nope/Nope"}, headers=H)
    assert bad.status_code == 422
    r = client.post("/api/kelola/preset", json={"name": "hemat"}, headers=H)
    assert r.status_code == 200 and r.get_json()["settings"]["image_daily_limit"] == S.PRESETS["hemat"]["image_daily_limit"]
    t = client.post("/api/kelola/test-model", json={"model": "Qwen/Qwen2.5-72B-Instruct"}, headers=H).get_json()
    assert t["ok"] is True
    b = client.get("/api/kelola/backup")
    assert b.status_code == 200 and b.data[:15] == b"SQLite format 3"
    assert client.post("/api/kelola/logout", headers=H).status_code == 200
    assert client.get("/api/kelola/state").status_code == 401
    S.reset_defaults()


def test_kelola_page_not_counted_as_activity(client):
    limits._last_seen[0] = 0
    client.get("/api/kelola/state")
    client.get("/api/health")
    assert limits.last_seen() == 0
    client.get("/api/posts?limit=1")
    assert limits.last_seen() > 0


def test_static_assets_are_versioned(client):
    html = client.get("/").get_data(as_text=True)
    assert "/static/css/main.css?v=" in html and "/static/js/feed.js?v=" in html
    r = client.get("/static/css/main.css")
    assert "max-age=31536000" in r.headers.get("Cache-Control", "")
