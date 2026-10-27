"""
Aura Social — Buku catatan pemakaian AI

Setiap panggilan SiliconFlow (teks, vision, gambar) dicatat beserta token dan
perkiraan biayanya, supaya /kelola bisa menunjukkan uang lari ke mana dan
rem anggaran bisa bekerja.

`auto` = 1 untuk aktivitas yang AI lakukan sendiri (post/story/komentar di post
AI), 0 untuk respons atas tindakanmu (DM, komentar di post-mu, balasan).
"""
import sqlite3
import time

from config import DB_PATH

KIND_LABELS = {
    "post": "Post AI (teks)",
    "post_image": "Gambar post",
    "story_image": "Gambar story",
    "story_caption": "Caption story",
    "comment": "Komentar",
    "vision_comment": "Komentar lihat foto",
    "reply": "Balasan komentarmu",
    "describe": "Baca foto upload",
    "dm": "Balas DM",
    "test": "Tes model",
    "other": "Lainnya",
}


def init(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ai_calls(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, day TEXT, kind TEXT, model TEXT, persona TEXT,
            auto INTEGER DEFAULT 1, ok INTEGER DEFAULT 1,
            pt INTEGER DEFAULT 0, ct INTEGER DEFAULT 0, images INTEGER DEFAULT 0,
            cost REAL DEFAULT 0, ms INTEGER DEFAULT 0, err TEXT);
        CREATE INDEX IF NOT EXISTS idx_ai_calls_day ON ai_calls(day);
        CREATE INDEX IF NOT EXISTS idx_ai_calls_ts ON ai_calls(ts);
    """)


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def _today():
    from utils import local_day
    return local_day()


def estimate_cost(model, pt=0, ct=0, images=0):
    import settings_rt as S
    cost = 0.0
    if images:
        cost += images * float(S.get("price_image_usd"))
    if pt or ct:
        pin, pout = S.price_for(model)
        cost += (pt or 0) / 1e6 * pin + (ct or 0) / 1e6 * pout
    return round(cost, 7)


def record(kind, model, persona=None, ok=True, pt=0, ct=0, images=0,
           auto=True, ms=0, err=None):
    """Catat satu panggilan. Tidak pernah melempar error ke pemanggil."""
    try:
        cost = estimate_cost(model, pt, ct, images) if ok else 0.0
        c = _conn()
        try:
            c.execute(
                "INSERT INTO ai_calls(ts,day,kind,model,persona,auto,ok,pt,ct,images,cost,ms,err) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (time.time(), _today(), kind, model, persona, 1 if auto else 0,
                 1 if ok else 0, int(pt or 0), int(ct or 0), int(images or 0),
                 cost, int(ms or 0), (err or None) and str(err)[:240]),
            )
            c.commit()
        finally:
            c.close()
        return cost
    except Exception as e:
        print(f"[Usage] record error: {e}")
        return 0.0


# ── angka untuk rem (dipanggil sering, query kecil ber-index) ─────────────
def _scalar(sql, args=()):
    try:
        c = _conn()
        try:
            row = c.execute(sql, args).fetchone()
        finally:
            c.close()
        return (row[0] if row else 0) or 0
    except Exception:
        return 0


def cost_today():
    return float(_scalar("SELECT SUM(cost) FROM ai_calls WHERE day=?", (_today(),)))


def auto_calls_today():
    return int(_scalar(
        "SELECT COUNT(*) FROM ai_calls WHERE day=? AND auto=1 AND kind!='test'", (_today(),)))


def interactive_calls_today():
    return int(_scalar(
        "SELECT COUNT(*) FROM ai_calls WHERE day=? AND auto=0 AND kind!='test'", (_today(),)))


# ── ringkasan untuk dashboard ─────────────────────────────────────────────
def day_totals(day=None):
    day = day or _today()
    c = _conn()
    try:
        r = c.execute(
            "SELECT COUNT(*) calls, SUM(auto) auto_calls, SUM(images) images, "
            "SUM(cost) cost, SUM(pt) pt, SUM(ct) ct, SUM(1-ok) fails "
            "FROM ai_calls WHERE day=?", (day,)).fetchone()
        kinds = c.execute(
            "SELECT kind, COUNT(*) calls, SUM(images) images, SUM(cost) cost "
            "FROM ai_calls WHERE day=? GROUP BY kind ORDER BY cost DESC, calls DESC",
            (day,)).fetchall()
    finally:
        c.close()
    calls = r["calls"] or 0
    auto_calls = r["auto_calls"] or 0
    return {
        "day": day,
        "calls": calls,
        "auto_calls": auto_calls,
        "interactive_calls": calls - auto_calls,
        "images": r["images"] or 0,
        "cost": round(r["cost"] or 0.0, 5),
        "tokens_in": r["pt"] or 0,
        "tokens_out": r["ct"] or 0,
        "fails": r["fails"] or 0,
        "by_kind": [
            {"kind": k["kind"], "label": KIND_LABELS.get(k["kind"], k["kind"]),
             "calls": k["calls"], "images": k["images"] or 0,
             "cost": round(k["cost"] or 0.0, 5)}
            for k in kinds
        ],
    }


def history(days=14):
    from datetime import timedelta
    from utils import now_local
    today = now_local().date()
    keys = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    c = _conn()
    try:
        rows = c.execute(
            "SELECT day, COUNT(*) calls, SUM(images) images, SUM(cost) cost, SUM(auto) auto_calls "
            "FROM ai_calls WHERE day>=? GROUP BY day", (keys[0],)).fetchall()
    finally:
        c.close()
    m = {r["day"]: r for r in rows}
    out = []
    for k in keys:
        r = m.get(k)
        out.append({
            "day": k,
            "calls": r["calls"] if r else 0,
            "auto_calls": (r["auto_calls"] or 0) if r else 0,
            "images": (r["images"] or 0) if r else 0,
            "cost": round((r["cost"] or 0.0), 5) if r else 0.0,
        })
    return out


def by_persona(days=7):
    since = time.time() - days * 86400
    c = _conn()
    try:
        rows = c.execute(
            "SELECT COALESCE(persona,'-') persona, COUNT(*) calls, SUM(images) images, SUM(cost) cost "
            "FROM ai_calls WHERE ts>=? GROUP BY persona ORDER BY cost DESC", (since,)).fetchall()
    finally:
        c.close()
    return [{"persona": r["persona"], "calls": r["calls"], "images": r["images"] or 0,
             "cost": round(r["cost"] or 0.0, 5)} for r in rows]


def by_model(days=7):
    since = time.time() - days * 86400
    c = _conn()
    try:
        rows = c.execute(
            "SELECT model, COUNT(*) calls, SUM(ok) ok, SUM(pt) pt, SUM(ct) ct, SUM(cost) cost "
            "FROM ai_calls WHERE ts>=? GROUP BY model ORDER BY cost DESC", (since,)).fetchall()
    finally:
        c.close()
    return [{"model": r["model"], "calls": r["calls"], "ok": r["ok"] or 0,
             "tokens_in": r["pt"] or 0, "tokens_out": r["ct"] or 0,
             "cost": round(r["cost"] or 0.0, 5)} for r in rows]


def recent_errors(hours=24, limit=12):
    since = time.time() - hours * 3600
    c = _conn()
    try:
        rows = c.execute(
            "SELECT model, err, COUNT(*) n, MAX(ts) last FROM ai_calls "
            "WHERE ok=0 AND ts>=? GROUP BY model, err ORDER BY last DESC LIMIT ?",
            (since, limit)).fetchall()
    finally:
        c.close()
    return [{"model": r["model"], "err": r["err"], "count": r["n"], "last": r["last"]} for r in rows]


def prune(days=120):
    try:
        c = _conn()
        try:
            c.execute("DELETE FROM ai_calls WHERE ts<?", (time.time() - days * 86400,))
            c.commit()
        finally:
            c.close()
    except Exception as e:
        print(f"[Usage] prune error: {e}")
