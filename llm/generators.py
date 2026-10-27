"""
Aura Social — Persona-Aware Generators
Wrap the raw LLM client with persona personality + task-specific prompts.

Two distinct voices per persona:
- persona["voice"]       → their OWN posts, story captions, DMs
- persona["personality"] → short comments on someone else's post
(Using the comment rules for posting is what used to leak lines like
"Kalo post ada FOTO, komentar soal visual…" into the timeline.)
"""
import base64
import io

import settings_rt as S
from config import VISION_MODEL
from llm.clean import clean_ai_text, looks_usable
from llm.client import call_llm

_POST_RULES = (
    "Aturan: bahasa Indonesia santai sehari-hari (boleh selipan bahasa Inggris "
    "kalau memang gayamu). 1-2 kalimat, maksimal 200 karakter. Tulis isinya saja: "
    "tanpa label seperti 'Post:', tanpa tanda kutip, tanpa tanda tangan nama, "
    "tanpa menjelaskan aturan ini."
)


def _voice(p):
    return p.get("voice") or p["personality"]


def _memory_block(memory):
    if not memory:
        return ""
    return ("\n\nBeberapa postinganmu sebelumnya (JANGAN diulang, cari hal lain):\n"
            + memory)


def _finish(raw, persona, max_len=320):
    t = clean_ai_text(raw, persona, max_len=max_len)
    return t if looks_usable(t) else None


def post_text(persona, topic, memory=None, auto=True):
    """Text-only status post about `topic`."""
    raw = call_llm(
        [
            {"role": "system", "content": f"{_voice(persona)}\n\nKamu lagi bikin postingan di "
             f"medsos pribadimu (bukan komentar). Topik bebas seputar: {topic}.\n{_POST_RULES}"
             f"{_memory_block(memory)}"},
            {"role": "user", "content": "Tulis satu postingan singkat sekarang."},
        ],
        S.text_model(persona), max_tokens=110, kind="post",
        persona=persona["username"], auto=auto, temperature=0.9,
    )
    return _finish(raw, persona, max_len=280)


def photo_caption(persona, scene, memory=None, auto=True):
    """Caption for a photo the persona is posting. `scene` is the (English)
    description used to generate the image, so caption and image match."""
    raw = call_llm(
        [
            {"role": "system", "content": f"{_voice(persona)}\n\nKamu baru upload foto ke medsos. "
             f"Isi fotonya: {scene}. (Itu deskripsi isi foto untukmu, bukan teks untuk disalin.) "
             f"Tulis caption yang nyambung dengan foto itu.\n{_POST_RULES}{_memory_block(memory)}"},
            {"role": "user", "content": "Tulis caption-nya."},
        ],
        S.text_model(persona), max_tokens=90, kind="post",
        persona=persona["username"], auto=auto, temperature=0.85,
    )
    return _finish(raw, persona, max_len=220)


def story_caption(persona, scene, auto=True):
    raw = call_llm(
        [
            {"role": "system", "content": f"{_voice(persona)}\n\nTulis caption story super singkat "
             f"(maksimal 8 kata) untuk foto berisi: {scene}. Bahasa Indonesia santai. "
             "Tanpa tanda kutip, tanpa label, tanpa hashtag."},
            {"role": "user", "content": "Caption-nya?"},
        ],
        S.text_model(persona), max_tokens=30, kind="story_caption",
        persona=persona["username"], auto=auto, temperature=0.8,
    )
    return _finish(raw, persona, max_len=80)


def comment_text(content, persona, auto=True, kind="comment"):
    """Generate a text comment from a persona on a (text or image-described) post."""
    raw = call_llm(
        [
            {"role": "system", "content": persona["personality"]},
            {"role": "user", "content": f"Post: \"{content}\"\nTulis 1 komentar singkat. "
             "Langsung isi komentar, tanpa tanda kutip."},
        ],
        S.text_model(persona), max_tokens=80, kind=kind,
        persona=persona["username"], auto=auto,
    )
    return _finish(raw, persona, max_len=240)


def _vision_url(img):
    """bytes/base64 → data URL kecil (≤ 512 px JPEG). Token vision dihitung
    dari resolusi, jadi foto 1080 px dikecilkan dulu supaya ~4x lebih murah."""
    raw = img if isinstance(img, (bytes, bytearray)) else base64.b64decode(img)
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(raw)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((512, 512))
            out = io.BytesIO()
            im.save(out, "JPEG", quality=80)
            raw = out.getvalue()
            mime = "image/jpeg"
    except Exception:
        from media import sniff_mime
        mime = sniff_mime(bytes(raw[:16]))
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def comment_image(img, persona, auto=True):
    """Comment on an image post using the persona's vision model."""
    vm = S.vision_model(persona)
    if not vm:
        return None
    raw = call_llm(
        [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _vision_url(img), "detail": "low"}},
                    {"type": "text", "text": f"{persona['personality']}\nFoto ini dipost teman. "
                     "1 komentar singkat. Langsung isi, tanpa tanda kutip."},
                ],
            }
        ],
        vm, max_tokens=80, kind="vision_comment", persona=persona["username"], auto=auto,
    )
    return _finish(raw, persona, max_len=240)


def describe_image(img):
    """Internal-only: describe an image for context. NEVER shown to user."""
    return call_llm(
        [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _vision_url(img), "detail": "low"}},
                    {"type": "text", "text": "Deskripsikan gambar ini 1 kalimat, bahasa Indonesia."},
                ],
            }
        ],
        VISION_MODEL, max_tokens=70, kind="describe", auto=False,
    )


def dm_reply(persona, history):
    """Generate a DM reply with conversation thread context.
    history: list of {sender, content} oldest→newest, including the latest user message.
    """
    msgs = [
        {
            "role": "system",
            "content": (
                f"{_voice(persona)}\n\nKamu lagi DM (chat pribadi) sama temen. Lebih santai dan "
                "personal dari komentar publik. 1-3 kalimat singkat, tetap jadi dirimu. "
                "Jangan pakai tanda kutip atau label."
            ),
        }
    ]
    for m in history:
        role = "user" if m["sender"] == "me" else "assistant"
        msgs.append({"role": role, "content": m["content"]})
    raw = call_llm(msgs, S.text_model(persona), max_tokens=140, kind="dm",
                   persona=persona["username"], auto=False)
    return _finish(raw, persona, max_len=600)
