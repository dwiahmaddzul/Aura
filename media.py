"""
Aura Social — Penyimpanan gambar

Dulu gambar disimpan sebagai base64 di dalam baris posts/stories. Karena
kolom created_at letaknya sesudah kolom gambar, setiap query feed membuat
SQLite menelusuri ratusan MB data gambar, dan gambar 500 KB dikirim mentah
tanpa cache lewat upload internet rumah.

Sekarang:
- File asli disimpan apa adanya:    <MEDIA_DIR>/<kind>/<id>.orig
- Versi tampil (WebP, dibuat sekali): <MEDIA_DIR>/<kind>/<id>-t.webp  (≤ 640 px, feed/grid)
                                      <MEDIA_DIR>/<kind>/<id>-f.webp  (≤ 1280 px, layar penuh)
- URL /media/<kind>/<id>-<v>.webp di-cache browser selamanya (immutable):
  id post/story tidak pernah dipakai ulang (AUTOINCREMENT) dan gambar tidak
  pernah diedit. Gambar AI boleh di-cache Cloudflare (public); foto milikmu
  hanya di-cache browser (private).

kind: "p" = posts, "s" = stories.
"""
import base64
import io
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path

from config import DB_PATH, MEDIA_DIR

try:
    from PIL import Image, ImageOps
    HAVE_PIL = True
except Exception:  # pragma: no cover - Pillow selalu ada di image Docker
    HAVE_PIL = False

KINDS = {"p": "posts", "s": "stories"}
VARIANTS = {"t": (640, 78), "f": (1280, 82)}  # max sisi, kualitas WebP

_dir_lock = threading.Lock()
_gen_lock = threading.Lock()


def root():
    return Path(MEDIA_DIR)


def _kind_dir(kind):
    d = root() / kind
    if not d.exists():
        with _dir_lock:
            d.mkdir(parents=True, exist_ok=True)
    return d


def orig_path(kind, mid):
    return _kind_dir(kind) / f"{int(mid)}.orig"


def variant_path(kind, mid, v):
    return _kind_dir(kind) / f"{int(mid)}-{v}.webp"


def url(kind, mid, v="t"):
    return f"/media/{kind}/{int(mid)}-{v}.webp"


def _atomic_write(path, data):
    tmp = path.with_name(path.name + f".tmp{os.getpid()}_{threading.get_ident()}")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def sniff_mime(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "application/octet-stream"


def decode_b64(b64):
    """base64 (boleh berawalan data:...;base64,) → bytes, atau None."""
    if not b64:
        return None
    s = b64.strip()
    if s.startswith("data:") and "," in s:
        s = s.split(",", 1)[1]
    try:
        return base64.b64decode(s, validate=False)
    except Exception:
        return None


def _render_variant(data, v):
    """bytes gambar → (webp_bytes, w, h) untuk varian v."""
    max_side, q = VARIANTS[v]
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "WEBP", quality=q, method=4)
        return out.getvalue(), im.width, im.height


def image_size(data):
    if not HAVE_PIL:
        return None, None
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.exif_transpose(im)
            return im.width, im.height
    except Exception:
        return None, None


def save(kind, mid, data_or_b64, variants=None):
    """Simpan gambar baru. Return (w, h) asli, atau (None, None) kalau
    bukan gambar valid. Varian WebP dibuat langsung supaya request pertama
    cepat (variants=None → semua; varian lain dibuat saat pertama diminta)."""
    data = data_or_b64 if isinstance(data_or_b64, (bytes, bytearray)) else decode_b64(data_or_b64)
    if not data:
        return None, None
    _atomic_write(orig_path(kind, mid), bytes(data))
    w, h = image_size(data)
    if HAVE_PIL and w:
        for v in (variants or VARIANTS):
            try:
                webp, _, _ = _render_variant(data, v)
                _atomic_write(variant_path(kind, mid, v), webp)
            except Exception as e:
                print(f"[Media] varian {kind}/{mid}-{v} gagal: {e}")
    return w, h


def _legacy_blob(kind, mid):
    table = KINDS[kind]
    try:
        c = sqlite3.connect(DB_PATH, timeout=15)
        try:
            row = c.execute(f"SELECT image_b64 FROM {table} WHERE id=?", (int(mid),)).fetchone()
        finally:
            c.close()
    except Exception:
        return None
    return decode_b64(row[0]) if row and row[0] else None


def ensure_variant(kind, mid, v):
    """Path file yang siap dikirim + mimetype, atau (None, None).
    Urutan: varian WebP → buat dari file asli → buat dari base64 lama di DB."""
    if kind not in KINDS or v not in VARIANTS:
        return None, None
    vp = variant_path(kind, mid, v)
    if vp.exists():
        return vp, "image/webp"
    op = orig_path(kind, mid)
    data = op.read_bytes() if op.exists() else _legacy_blob(kind, mid)
    if not data:
        return None, None
    if HAVE_PIL:
        try:
            with _gen_lock:
                if not vp.exists():
                    webp, _, _ = _render_variant(data, v)
                    _atomic_write(vp, webp)
            return vp, "image/webp"
        except Exception as e:
            print(f"[Media] gagal membuat {kind}/{mid}-{v}: {e}")
    # Tanpa Pillow / gambar aneh: kirim aslinya.
    if not op.exists():
        _atomic_write(op, data)
    return op, sniff_mime(data[:16])


def delete(kind, mid):
    for p in [orig_path(kind, mid)] + [variant_path(kind, mid, v) for v in VARIANTS]:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[Media] hapus {p.name} gagal: {e}")


def dir_size():
    total, n = 0, 0
    r = root()
    if not r.exists():
        return 0, 0
    for p in r.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
            n += 1
    return total, n


# ── Migrasi base64 lama → file ────────────────────────────────────────────
MIGRATION = {"state": "idle", "done": 0, "total": 0, "failed": 0,
             "backup": None, "error": None, "finished_at": None}


def _pending(conn):
    a = conn.execute("SELECT COUNT(*) FROM posts WHERE image_b64 IS NOT NULL").fetchone()[0]
    b = conn.execute("SELECT COUNT(*) FROM stories WHERE image_b64 IS NOT NULL").fetchone()[0]
    return a + b


def _backup_db(conn):
    """Salin DB utuh sebelum dipindah (sekali saja). Return path atau None."""
    import settings_rt as S
    existing = S.get_raw("_media_backup")
    if existing and Path(existing).exists():
        return existing
    db = Path(DB_PATH).resolve()
    bdir = db.parent / "backup"
    bdir.mkdir(parents=True, exist_ok=True)
    size = db.stat().st_size + (Path(str(db) + "-wal").stat().st_size if Path(str(db) + "-wal").exists() else 0)
    free = shutil.disk_usage(bdir).free
    if free < size * 2 + 200 * 1024 * 1024:
        raise RuntimeError(f"ruang disk kurang untuk backup ({free // 2**20} MB bebas)")
    dest = bdir / f"aura-sebelum-media-{time.strftime('%Y%m%d-%H%M%S')}.db"
    target = sqlite3.connect(str(dest))
    try:
        conn.backup(target)
    finally:
        target.close()
    S.set_raw("_media_backup", str(dest))
    return str(dest)


def migrate_legacy(pause=0.25):
    """Pindahkan semua image_b64 lama ke file, lalu kosongkan kolomnya dan
    VACUUM. Idempotent: aman dihentikan di tengah dan diulang."""
    import settings_rt as S
    if MIGRATION["state"] == "running":
        return MIGRATION
    MIGRATION.update(state="running", error=None)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        total = _pending(conn)
        MIGRATION.update(total=total, done=0, failed=0)
        if total == 0:
            MIGRATION.update(state="done", finished_at=time.time())
            return MIGRATION
        MIGRATION["backup"] = _backup_db(conn)
        print(f"[Media] migrasi {total} gambar lama → file (backup: {MIGRATION['backup']})", flush=True)
        failed = set()
        for kind, table in (("p", "posts"), ("s", "stories")):
            while True:
                ids = [r[0] for r in conn.execute(
                    f"SELECT id FROM {table} WHERE image_b64 IS NOT NULL ORDER BY id DESC LIMIT 40"
                ).fetchall() if (kind, r[0]) not in failed]
                if not ids:
                    break
                for mid in ids:
                    row = conn.execute(f"SELECT image_b64 FROM {table} WHERE id=?", (mid,)).fetchone()
                    raw = row[0] if row else None
                    data = decode_b64(raw) if raw else None
                    if not data:
                        # base64 kosong/rusak: tidak ada gambar yang bisa diselamatkan
                        conn.execute(f"UPDATE {table} SET image_b64=NULL, has_img=0 WHERE id=?", (mid,))
                        conn.commit()
                        MIGRATION["failed"] += 1
                        continue
                    try:
                        # Migrasi: buat varian yang paling sering dipakai saja
                        # (feed = thumb, story = full); sisanya dibuat saat diminta.
                        # Hemat CPU di server kecil.
                        w, h = save(kind, mid, data, variants=("t",) if kind == "p" else ("f",))
                    except Exception as e:
                        print(f"[Media] {kind}/{mid} gagal disimpan: {e}")
                        failed.add((kind, mid))
                        MIGRATION["failed"] += 1
                        continue
                    conn.execute(
                        f"UPDATE {table} SET image_b64=NULL, has_img=1, img_w=?, img_h=? WHERE id=?",
                        (w, h, mid))
                    conn.commit()
                    MIGRATION["done"] += 1
                    if pause:
                        time.sleep(pause)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        try:
            conn.execute("VACUUM")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as e:
            print(f"[Media] VACUUM dilewati: {e}")
        S.set_raw("_media_migrated_at", time.time())
        MIGRATION.update(state="done", finished_at=time.time())
        print(f"[Media] migrasi selesai: {MIGRATION['done']} dipindah, {MIGRATION['failed']} gagal", flush=True)
    except Exception as e:
        MIGRATION.update(state="error", error=str(e))
        print(f"[Media] migrasi berhenti: {e}", flush=True)
    finally:
        conn.close()
    return MIGRATION


def start_migration_thread(delay=8):
    def _run():
        time.sleep(delay)
        migrate_legacy()
    threading.Thread(target=_run, daemon=True, name="media-migrate").start()
