"""
Aura Social — SiliconFlow API Client
Raw HTTP layer. No persona awareness. No business logic.
Every call is logged to the usage ledger (ai_engine/usage.py) with tokens and
estimated cost, so /kelola can show where the money goes.
"""
import base64
import re
import time

import requests

from config import IMAGE_MODEL, SILICONFLOW_API_KEY, SILICONFLOW_BASE

# Model yang di SiliconFlow default-nya "thinking" (rantai pikir dibayar sebagai
# token output dan sering memakan habis max_tokens). Untuk post/komentar pendek
# kita matikan. Daftar dari dokumentasi chat-completions SiliconFlow (Okt 2026).
THINKING_TOGGLE_MODELS = {
    "Qwen/Qwen3-8B", "Qwen/Qwen3-14B", "Qwen/Qwen3-32B", "Qwen/Qwen3-30B-A3B",
    "Qwen/Qwen3-235B-A22B", "tencent/Hunyuan-A13B-Instruct",
    "zai-org/GLM-4.5V", "zai-org/GLM-4.6V", "zai-org/GLM-5V-Turbo",
    "deepseek-ai/DeepSeek-V3.1", "deepseek-ai/DeepSeek-V3.1-Terminus",
    "deepseek-ai/DeepSeek-V3.2-Exp", "deepseek-ai/DeepSeek-V3.2",
}

_THINK = re.compile(r"<think>.*?</think>", re.S)


def _record(**kw):
    try:
        from ai_engine.usage import record
        record(**kw)
    except Exception as e:  # pragma: no cover
        print(f"[Usage] {e}")


def call_llm(messages, model, max_tokens=90, kind="other", persona=None,
             auto=True, temperature=0.85):
    """Call SiliconFlow chat completions. Returns text or None on failure."""
    t0 = time.time()
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 0.95,
    }
    if model in THINKING_TOGGLE_MODELS:
        body["enable_thinking"] = False
    try:
        r = requests.post(
            f"{SILICONFLOW_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=40,
        )
        ms = int((time.time() - t0) * 1000)
        if r.status_code != 200:
            err = f"HTTP {r.status_code}: {r.text[:180]}"
            print(f"[LLM] {model.split('/')[-1][:24]}: {err}")
            _record(kind=kind, model=model, persona=persona, ok=False, auto=auto, ms=ms, err=err)
            return None
        data = r.json()
        usage = data.get("usage") or {}
        txt = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        txt = _THINK.sub("", txt).strip()
        _record(kind=kind, model=model, persona=persona, ok=True, auto=auto, ms=ms,
                pt=usage.get("prompt_tokens", 0), ct=usage.get("completion_tokens", 0))
        return txt or None
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        print(f"[LLM] {model.split('/')[-1][:24]}: {e}")
        _record(kind=kind, model=model, persona=persona, ok=False, auto=auto, ms=ms,
                err=str(e)[:180])
        return None


def generate_image(prompt, persona=None, kind="post_image", auto=True):
    """Generate image via FLUX. Returns raw image bytes or None."""
    t0 = time.time()
    try:
        r = requests.post(
            f"{SILICONFLOW_BASE}/images/generations",
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": IMAGE_MODEL, "prompt": prompt, "image_size": "512x512"},
            timeout=90,
        )
        if r.status_code != 200:
            err = f"HTTP {r.status_code}: {r.text[:180]}"
            print(f"[ImageGen] {err}")
            _record(kind=kind, model=IMAGE_MODEL, persona=persona, ok=False, auto=auto,
                    ms=int((time.time() - t0) * 1000), err=err)
            return None
        data = r.json()
        # {"images":[{"url":"..."}]} atau {"data":[{"b64_json":"..."}]}
        images = data.get("images") or data.get("data") or []
        raw = None
        if images:
            img = images[0]
            if img.get("b64_json"):
                raw = base64.b64decode(img["b64_json"])
            elif img.get("url"):
                img_r = requests.get(img["url"], timeout=60)
                if img_r.status_code == 200:
                    raw = img_r.content
        # Gambar sudah dibuat (dan ditagih) begitu API menjawab 200.
        _record(kind=kind, model=IMAGE_MODEL, persona=persona, ok=True, auto=auto,
                images=1, ms=int((time.time() - t0) * 1000),
                err=None if raw else "gambar tidak bisa diunduh")
        return raw
    except Exception as e:
        print(f"[ImageGen] error: {e}")
        _record(kind=kind, model=IMAGE_MODEL, persona=persona, ok=False, auto=auto,
                ms=int((time.time() - t0) * 1000), err=str(e)[:180])
        return None


def to_b64(raw):
    return base64.b64encode(raw).decode() if raw else None
