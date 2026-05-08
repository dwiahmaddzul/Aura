"""
Aura Social — Test Suite
Run: pytest -v
"""
import os
import sys
import time
import pytest

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Fresh test client with isolated DB per test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    # Reload config + db modules with new DB_PATH
    for mod in ("config", "db", "app", "api", "api.posts", "api.dm",
                "api.me", "api.profiles", "api.stories", "api.notif_search"):
        sys.modules.pop(mod, None)
    from app import create_app
    app = create_app()
    return app.test_client()


# ── Health & basics ────────────────────────────────────────────────
def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Aura" in r.data


def test_health_no_key(client, monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "")
    r = client.get("/api/health")
    body = r.get_json()
    assert "api_key_present" in body


def test_personas_list(client):
    r = client.get("/api/personas")
    data = r.get_json()
    assert len(data) == 6
    # Defense-in-depth: text_model never leaks
    assert all("text_model" not in p for p in data)


# ── Profile ────────────────────────────────────────────────────────
def test_me_profile_default(client):
    r = client.get("/api/me/profile")
    data = r.get_json()
    assert data["is_first_time"] is True
    assert data["greeting"]
    assert data["part_of_day"] in {"pagi", "siang", "sore", "malam"}


def test_me_profile_update(client):
    client.post("/api/me/profile",
                json={"display_name": "Tester", "bio": "hi", "avatar": "T"})
    r = client.get("/api/me/profile")
    assert r.get_json()["display_name"] == "Tester"


def test_me_profile_empty_name_rejected(client):
    r = client.post("/api/me/profile",
                    json={"display_name": "", "bio": "", "avatar": ""})
    assert r.status_code == 400


# ── Posts ──────────────────────────────────────────────────────────
def test_create_post(client):
    r = client.post("/api/posts",
                    json={"content": "halo dunia", "mood": "senang"})
    assert r.status_code == 201
    pid = r.get_json()["id"]
    r = client.get("/api/posts")
    posts = r.get_json()
    assert any(p["id"] == pid for p in posts)


def test_post_with_mood_appears_in_timeline(client):
    client.post("/api/posts", json={"content": "test", "mood": "tenang"})
    r = client.get("/api/me/mood-timeline")
    days = r.get_json()
    assert len(days) == 30
    assert any(d["mood"] == "tenang" for d in days)


def test_streak_increments_after_post(client):
    assert client.get("/api/me/streak").get_json()["current"] == 0
    client.post("/api/posts", json={"content": "first"})
    assert client.get("/api/me/streak").get_json()["current"] == 1


def test_first_time_flag_flips(client):
    assert client.get("/api/me/profile").get_json()["is_first_time"]
    client.post("/api/posts", json={"content": "first post"})
    assert not client.get("/api/me/profile").get_json()["is_first_time"]


# ── Bookmarks ──────────────────────────────────────────────────────
def test_bookmark_toggle(client):
    pid = client.post("/api/posts", json={"content": "x"}).get_json()["id"]
    r = client.post(f"/api/posts/{pid}/bookmark")
    assert r.get_json()["bookmarked"] is True
    r = client.post(f"/api/posts/{pid}/bookmark")
    assert r.get_json()["bookmarked"] is False


def test_bookmarks_listing(client):
    pid = client.post("/api/posts", json={"content": "save me"}).get_json()["id"]
    client.post(f"/api/posts/{pid}/bookmark")
    r = client.get("/api/me/bookmarks")
    assert len(r.get_json()) == 1


# ── Reposts ────────────────────────────────────────────────────────
def test_repost_creates_new_post_with_reference(client):
    orig_id = client.post("/api/posts",
                          json={"content": "original"}).get_json()["id"]
    r = client.post(f"/api/posts/{orig_id}/repost",
                    json={"content": "my take"})
    assert r.status_code == 201
    repost_id = r.get_json()["id"]
    posts = client.get("/api/posts").get_json()
    repost = next(p for p in posts if p["id"] == repost_id)
    assert repost["repost_of"] == orig_id
    assert repost["original"]["id"] == orig_id


def test_repost_nonexistent_404(client):
    r = client.post("/api/posts/99999/repost", json={"content": ""})
    assert r.status_code == 404


# ── DM ─────────────────────────────────────────────────────────────
def test_dm_list_returns_six(client):
    r = client.get("/api/dm")
    data = r.get_json()
    assert len(data) == 6
    assert all("online" in d for d in data)


def test_dm_thread_persona_with_dot(client):
    """bimo.plays has a dot in username — verify URL routing handles it."""
    r = client.get("/api/dm/bimo.plays")
    assert r.status_code == 200
    assert r.get_json()["persona"]["username"] == "bimo.plays"


def test_dm_send_persists(client):
    client.post("/api/dm/maya_art", json={"content": "halo"})
    msgs = client.get("/api/dm/maya_art").get_json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["is_me"] is True
    assert msgs[0]["content"] == "halo"


def test_dm_unknown_persona_404(client):
    r = client.get("/api/dm/notexist")
    assert r.status_code == 404


def test_dm_empty_content_rejected(client):
    r = client.post("/api/dm/maya_art", json={"content": "   "})
    assert r.status_code == 400


# ── Stories ────────────────────────────────────────────────────────
def test_story_user_upload(client):
    import base64
    fake = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
    r = client.post("/api/stories",
                    json={"image_b64": fake, "caption": "tes"})
    assert r.status_code == 201
    stories = client.get("/api/stories").get_json()
    assert any(s["username"] == "me" for s in stories)


def test_story_no_image_rejected(client):
    r = client.post("/api/stories", json={"caption": "no img"})
    assert r.status_code == 400


# ── Search ─────────────────────────────────────────────────────────
def test_search_empty_query(client):
    r = client.get("/api/search")
    body = r.get_json()
    assert body == {"posts": [], "personas": [], "dms": []}


def test_search_finds_post(client):
    client.post("/api/posts", json={"content": "kucing oren imut"})
    r = client.get("/api/search?q=kucing")
    assert any("kucing" in p["content"] for p in r.get_json()["posts"])


def test_search_finds_persona_by_handle(client):
    r = client.get("/api/search?q=maya")
    assert any(p["username"] == "maya_art" for p in r.get_json()["personas"])


# ── Throwback & insights ───────────────────────────────────────────
def test_throwback_empty_db_returns_null(client):
    assert client.get("/api/me/throwback").get_json()["throwback"] is None


def test_mood_timeline_shape(client):
    days = client.get("/api/me/mood-timeline").get_json()
    assert len(days) == 30
    assert all({"date", "label", "mood"} <= set(d) for d in days)


# ── Notifications ──────────────────────────────────────────────────
def test_notifications_endpoint(client):
    r = client.get("/api/notifications")
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


# ── Time labels ────────────────────────────────────────────────────
def test_time_ago_recent():
    from utils import time_ago
    assert time_ago(time.time() - 30) == "baru saja"


def test_time_ago_minutes():
    from utils import time_ago
    assert "mnt" in time_ago(time.time() - 600)


def test_part_of_day():
    from utils import part_of_day_now
    assert part_of_day_now() in {"pagi", "siang", "sore", "malam"}
