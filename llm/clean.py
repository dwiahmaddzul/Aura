"""
Aura Social — Pembersih teks AI

Model kadang membocorkan prompt ke dalam hasil: label "Post:", instruksi
persona dalam **...**, dua alternatif sekaligus ("... atau Story: ..."),
tanda kutip pembungkus, tanda tangan nama. Fungsi di sini dipakai saat teks
disimpan (post/komentar/DM baru) DAN saat ditampilkan (data lama), dan aman
dipanggil berkali-kali.
"""
import re

_THINK = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)
_LABEL = re.compile(
    r"^\s*[\*_`\"'“”‘’]*\s*(post(ingan)?|caption|status|story|komen(tar)?|balasan|reply|jawaban|"
    r"dm|pesan|tweet|isi)\s*[\*_]*\s*[:：]\s*",
    re.I,
)
# Pemisah dua alternatif: baris "atau" sendirian, atau "... atau Story: ...".
_ALT_LINE = re.compile(r"\n\s*(atau|or)\s*\n", re.I)
_ALT_INLINE = re.compile(r"\s+(atau|or)\s+(?=[\*_\"“]*\s*(post(ingan)?|story|caption|komen(tar)?)\s*[:：])", re.I)
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")

_LEAK_MARKERS = (
    "kalo post", "kalau post", "kalau postingan", "kalo postingan", "komentar soal",
    "max 1 kalimat", "maks 1 kalimat", "maksimal 1 kalimat", "max 1-2 kalimat",
    "langsung isi", "tanpa tanda kutip", "jangan bahas", "jangan pakai label",
    "dalam karakter", "tulis 1 komentar", "tulis isi", "gaya santai:", "contoh:",
    "penting:", "system prompt", "instruksi", "as an ai", "sebagai ai",
    "sebagai model bahasa", "aturan:", "persona",
)


def _leaky(s):
    low = s.lower()
    return any(m in low for m in _LEAK_MARKERS)


def _strip_quotes(t):
    pairs = (('"', '"'), ("“", "”"), ("'", "'"), ("‘", "’"), ("«", "»"))
    for _ in range(2):
        t = t.strip()
        for a, b in pairs:
            if len(t) >= 2 and t.startswith(a) and t.endswith(b) and t.count(a) <= 2:
                t = t[1:-1].strip()
    return t


def _first_name(persona):
    if not persona:
        return None
    disp = persona.get("display") if isinstance(persona, dict) else str(persona)
    if not disp:
        return None
    return re.sub(r"[^\w]", "", disp.split()[0]) or None


def clean_ai_text(text, persona=None, max_len=320):
    if not text:
        return ""
    t = _THINK.sub("", str(text)).replace("\r", "")
    # Ambil alternatif pertama saja.
    t = _ALT_LINE.split(t)[0]
    t = _ALT_INLINE.split(t)[0]
    # Label di depan ("Post:", "POST:", "Komentar:") — bisa bertumpuk.
    for _ in range(3):
        new = _LABEL.sub("", t, count=1)
        if new == t:
            break
        t = new
    # **instruksi yang bocor** dibuang, **penekanan biasa** dipertahankan teksnya.
    t = _BOLD.sub(lambda m: "" if _leaky(m.group(1)) else m.group(1), t)
    # Kalimat yang jelas-jelas instruksi dibuang.
    lines = []
    for line in t.split("\n"):
        sents = [s for s in _SENT_SPLIT.split(line) if s.strip() and not _leaky(s)]
        if sents:
            lines.append(" ".join(sents))
    t = " ".join(l.strip() for l in lines if l.strip())
    t = t.replace("**", "").strip()
    t = _strip_quotes(t)
    # Tanda tangan nama sendiri di akhir: ", Maya" / "— Maya" / "- Maya ✨"
    name = _first_name(persona)
    if name:
        t = re.sub(rf"\s*[,—–-]\s*{re.escape(name)}\W*$", "", t, flags=re.I).strip()
    t = re.sub(r"\s{2,}", " ", t).strip()
    if len(t) > max_len:
        cut = t[:max_len]
        stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        t = (cut[: stop + 1] if stop > max_len * 0.5 else cut.rstrip() + "…").strip()
    return t


def looks_usable(t, min_len=3):
    """False untuk hasil kosong / sisa bocoran yang tidak layak tampil."""
    return bool(t) and len(t.strip()) >= min_len and not _leaky(t)
