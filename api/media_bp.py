"""
Aura Social — Media files
GET /media/<kind>/<id>-<v>.webp   kind: p (post) / s (story), v: t (thumb) / f (full)

Images never change once written and ids are never reused, so responses are
cacheable forever. AI images are `public` (Cloudflare may cache them at the
edge, so they stop travelling over the home uplink). Your own photos are
`private`: only your browser keeps a copy.
"""
import re

from flask import Blueprint, abort, send_file

import media
from db import get_db

bp = Blueprint("media", __name__)

_NAME = re.compile(r"^(\d{1,12})-([tf])\.webp$")
YEAR = 31536000


def serve(kind, mid, v):
    if kind not in media.KINDS:
        abort(404)
    table = media.KINDS[kind]
    row = get_db().execute(f"SELECT username FROM {table} WHERE id=?", (int(mid),)).fetchone()
    if not row:
        abort(404)
    path, mime = media.ensure_variant(kind, mid, v)
    if not path:
        abort(404)
    resp = send_file(path, mimetype=mime, conditional=True, etag=True, max_age=YEAR)
    scope = "private" if row["username"] == "me" else "public"
    resp.headers["Cache-Control"] = f"{scope}, max-age={YEAR}, immutable"
    return resp


@bp.route("/media/<kind>/<name>")
def media_file(kind, name):
    m = _NAME.match(name)
    if not m:
        abort(404)
    return serve(kind, int(m.group(1)), m.group(2))
