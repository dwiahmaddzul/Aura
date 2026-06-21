"""
Aura Social — smoke tests
Fast endpoint coverage via Flask's test client. No external LLM calls are
needed: background AI threads are disabled (RUN_SCHEDULER=0) and any spawned
reply threads fail silently without affecting responses.

Run:  pip install -r requirements-dev.txt && pytest -q
"""
import os
import tempfile

# Must be set BEFORE importing the app (config + workers read these at import).
os.environ["RUN_SCHEDULER"] = "0"
os.environ.setdefault("SILICONFLOW_API_KEY", "sk-test-dummy-key-0123456789")
_fd, _DB = tempfile.mkstemp(suffix=".db")
os.environ["DB_PATH"] = _DB

import pytest  # noqa: E402

from app import app as flask_app  # noqa: E402
import security  # noqa: E402

# A 1x1 transparent PNG, base64 (valid tiny image payload).
TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
PERSONA = "maya_art"


@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Each test starts with a clean rate-limit window."""
    security._hits.clear()
    yield


# ── basics ──
def test_index_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Aura" in r.data


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "api_key_present" in r.get_json()


def test_empty_post_rejected(client):
    assert client.post("/api/posts", json={}).status_code == 400


# ── posts ──
def test_create_and_list_post(client):
    r = client.post("/api/posts", json={"content": "halo dunia"})
    assert r.status_code == 201
    pid = r.get_json()["id"]
    posts = client.get("/api/posts").get_json()
    assert any(p["id"] == pid and p["content"] == "halo dunia" for p in posts)


def test_post_content_is_capped(client):
    long = "x" * 5000
    r = client.post("/api/posts", json={"content": long})
    assert r.status_code == 201
    pid = r.get_json()["id"]
    post = [p for p in client.get("/api/posts").get_json() if p["id"] == pid][0]
    assert len(post["content"]) <= security.MAX_POST


def test_oversized_image_rejected(client):
    huge = "A" * (security.MAX_IMAGE_B64 + 10)
    r = client.post("/api/posts", json={"content": "x", "image_b64": huge})
    assert r.status_code == 413


# ── gratitude (#6) ──
def test_gratitude_entry_type(client):
    r = client.post(
        "/api/posts",
        json={"content": "bersyukur hari ini", "post_type": "gratitude", "allow_ai": False},
    )
    assert r.status_code == 201
    pid = r.get_json()["id"]
    post = [p for p in client.get("/api/posts").get_json() if p["id"] == pid][0]
    assert post["post_type"] == "gratitude"


# ── comments + threaded replies (#5) ──
def test_comment_and_threaded_reply(client):
    pid = client.post("/api/posts", json={"content": "post utama"}).get_json()["id"]
    assert client.post(f"/api/posts/{pid}/comment", json={"text": "komen 1"}).status_code == 201
    post = [p for p in client.get("/api/posts").get_json() if p["id"] == pid][0]
    assert post["comments"], "comment should be stored"
    assert "parent_id" in post["comments"][0]
    cid = post["comments"][0]["id"]
    # reply to that comment
    assert client.post(
        f"/api/posts/{pid}/comment", json={"text": "balasan", "parent_id": cid}
    ).status_code == 201
    post = [p for p in client.get("/api/posts").get_json() if p["id"] == pid][0]
    replies = [c for c in post["comments"] if c.get("parent_id")]
    assert replies and replies[0]["parent_id"] == cid


def test_comment_capped(client):
    pid = client.post("/api/posts", json={"content": "p"}).get_json()["id"]
    client.post(f"/api/posts/{pid}/comment", json={"text": "y" * 3000})
    post = [p for p in client.get("/api/posts").get_json() if p["id"] == pid][0]
    assert all(len(c["content"]) <= security.MAX_COMMENT for c in post["comments"])


# ── likes + bookmarks ──
def test_like_toggle(client):
    pid = client.post("/api/posts", json={"content": "like me"}).get_json()["id"]
    d1 = client.post(f"/api/posts/{pid}/like").get_json()
    assert d1["liked"] is True and d1["likes"] == 1
    d2 = client.post(f"/api/posts/{pid}/like").get_json()
    assert d2["liked"] is False and d2["likes"] == 0


def test_bookmark_toggle(client):
    pid = client.post("/api/posts", json={"content": "save me"}).get_json()["id"]
    assert client.post(f"/api/posts/{pid}/bookmark").get_json()["bookmarked"] is True
    assert client.post(f"/api/posts/{pid}/bookmark").get_json()["bookmarked"] is False


# ── DM ──
def test_dm_flow(client):
    assert client.get("/api/dm").status_code == 200
    assert client.post(f"/api/dm/{PERSONA}", json={"content": "hai"}).status_code == 201
    thread = client.get(f"/api/dm/{PERSONA}").get_json()
    assert any(m["content"] == "hai" and m["is_me"] for m in thread["messages"])


def test_dm_unknown_persona(client):
    assert client.post("/api/dm/nobody", json={"content": "x"}).status_code == 404


# ── stories ──
def test_story_create_and_list(client):
    assert client.post("/api/stories", json={"image_b64": TINY_PNG, "caption": "test"}).status_code == 201
    assert client.get("/api/stories").status_code == 200


# ── profiles + search ──
def test_profile(client):
    r = client.get(f"/api/profile/{PERSONA}")
    assert r.status_code == 200
    d = r.get_json()
    for key in ("post_count", "highlights", "stories", "comment_count"):
        assert key in d
    assert client.get("/api/profile/nobody").status_code == 404


def test_search(client):
    assert client.get("/api/search?q=test").status_code == 200


# ── hardening: rate limit ──
def test_rate_limit_kicks_in(client):
    # api_create allows 12/min; the 13th should be throttled.
    codes = [client.post("/api/posts", json={"content": f"n{i}"}).status_code for i in range(14)]
    assert 429 in codes
    assert codes[:12] == [201] * 12
