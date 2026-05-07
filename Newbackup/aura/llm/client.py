"""
Aura Social — SiliconFlow API Client
Raw HTTP layer. No persona awareness. No business logic.
"""
import base64
import re
import requests

from config import SILICONFLOW_API_KEY, SILICONFLOW_BASE, IMAGE_MODEL


def call_llm(messages, model, max_tokens=90):
    """Call SiliconFlow chat completions endpoint. Returns text or None on failure."""
    try:
        r = requests.post(
            f"{SILICONFLOW_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.93,
                "top_p": 0.95,
            },
            timeout=30,
        )
        if r.status_code == 401:
            print("[401] cek API key")
            return None
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"].strip()
        # Strip <think>...</think> blocks (some reasoning models emit these)
        txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip()
        return txt or None
    except Exception as e:
        print(f"[LLM] {model.split('/')[-1][:18]}: {e}")
        return None


def generate_image(prompt):
    """Generate image via FLUX.1-schnell. Returns base64 string or None."""
    try:
        r = requests.post(
            f"{SILICONFLOW_BASE}/images/generations",
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": IMAGE_MODEL, "prompt": prompt, "image_size": "512x512"},
            timeout=60,
        )
        if r.status_code != 200:
            print(f"[ImageGen] {r.status_code}: {r.text[:100]}")
            return None
        data = r.json()
        # Response format: {"images":[{"url":"..."}]} or {"data":[{"b64_json":"..."}]}
        images = data.get("images") or data.get("data") or []
        if not images:
            return None
        img = images[0]
        if "b64_json" in img:
            return img["b64_json"]
        elif "url" in img:
            img_r = requests.get(img["url"], timeout=30)
            if img_r.status_code == 200:
                return base64.b64encode(img_r.content).decode()
        return None
    except Exception as e:
        print(f"[ImageGen] error: {e}")
        return None
