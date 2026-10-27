"""
Aura Social — Shared JSON shapes for posts / authors.

Every list endpoint selects POST_COLS only: never `SELECT *`, because that
used to drag the base64 image of every row through Python on each feed poll.
Relative time labels are computed in the browser (from created_at, in the
viewer's own time zone), which also keeps responses byte-stable between polls
so ETag/304 works.
"""
import media
from llm.clean import clean_ai_text
from personas import PMAP

POST_COLS = ("id, username, content, post_type, mood, repost_of, likes, "
             "created_at, has_img, img_w, img_h")
ME_COLOR = "linear-gradient(135deg,#c9aa72,#7b61ff)"


def me_identity(db):
    me = db.execute("SELECT display_name, avatar FROM me_profile WHERE id=1").fetchone()
    return {
        "display": me["display_name"] if me else "Kamu",
        "avatar": me["avatar"] if me else "K",
        "color": ME_COLOR,
    }


def author(username, me):
    if username == "me":
        return dict(me)
    p = PMAP.get(username, {})
    return {
        "display": p.get("display", username),
        "avatar": p.get("avatar", (username or "?")[0].upper()),
        "color": p.get("color", "#555"),
    }


def image_fields(kind, row):
    if not row["has_img"]:
        return {"has_image": False}
    return {
        "has_image": True,
        "img": media.url(kind, row["id"], "t"),
        "img_full": media.url(kind, row["id"], "f"),
        "img_w": row["img_w"],
        "img_h": row["img_h"],
    }


def comment_dict(c, me):
    d = {
        "id": c["id"],
        "post_id": c["post_id"],
        "username": c["username"],
        "content": c["content"] if c["username"] == "me"
        else clean_ai_text(c["content"], PMAP.get(c["username"]), max_len=600),
        "is_ai": c["is_ai"],
        "parent_id": c["parent_id"],
        "created_at": c["created_at"],
    }
    d.update(author(c["username"], me))
    return d


def post_dict(row, me, liked=(), bookmarked=(), comments=None):
    un = row["username"]
    content = row["content"] or ""
    if un != "me":
        content = clean_ai_text(content, PMAP.get(un), max_len=600)
    d = {
        "id": row["id"],
        "username": un,
        "content": content,
        "post_type": row["post_type"],
        "mood": row["mood"],
        "repost_of": row["repost_of"],
        "likes": row["likes"] or 0,
        "created_at": row["created_at"],
        "is_liked": row["id"] in liked,
        "bookmarked": row["id"] in bookmarked,
    }
    d.update(author(un, me))
    d.update(image_fields("p", row))
    if comments is not None:
        d["comments"] = comments
        d["comment_count"] = len(comments)
    return d


def ids_in(db, sql_prefix, ids, extra=()):
    """Run `sql_prefix ... IN (?,?,…)` safely for a list of ids."""
    if not ids:
        return []
    q = ",".join("?" * len(ids))
    return db.execute(f"{sql_prefix} ({q})", tuple(extra) + tuple(ids)).fetchall()


def build_posts(db, rows, with_comments=True):
    """rows (POST_COLS) → list of post dicts with comments/likes/bookmarks
    resolved in 3-4 queries total (was 1 + 2N)."""
    me = me_identity(db)
    ids = [r["id"] for r in rows]
    liked = {r["post_id"] for r in ids_in(
        db, "SELECT post_id FROM likes WHERE username='me' AND post_id IN", ids)}
    bms = {r["post_id"] for r in ids_in(
        db, "SELECT post_id FROM bookmarks WHERE username='me' AND post_id IN", ids)}
    by_post = {}
    if with_comments:
        for c in ids_in(
            db,
            "SELECT id, post_id, username, content, is_ai, parent_id, created_at "
            "FROM comments WHERE post_id IN",
            ids,
        ):
            by_post.setdefault(c["post_id"], []).append(comment_dict(c, me))
        for lst in by_post.values():
            lst.sort(key=lambda c: (c["created_at"] or 0, c["id"]))
    # Repost lama (fitur sudah dihapus) tetap tampil read-only.
    orig_ids = [r["repost_of"] for r in rows if r["repost_of"]]
    originals = {o["id"]: o for o in ids_in(db, f"SELECT {POST_COLS} FROM posts WHERE id IN", orig_ids)}
    out = []
    for r in rows:
        d = post_dict(r, me, liked, bms, by_post.get(r["id"], []) if with_comments else None)
        o = originals.get(r["repost_of"]) if r["repost_of"] else None
        if o:
            d["original"] = post_dict(o, me)
        out.append(d)
    return out
