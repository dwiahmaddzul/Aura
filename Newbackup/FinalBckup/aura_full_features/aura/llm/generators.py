"""
Aura Social — Persona-Aware Generators
Wrap the raw LLM client with persona personality + task-specific prompts.
"""
from config import VISION_MODEL
from llm.client import call_llm


def comment_text(content, persona):
    """Generate a text comment from a persona on a (text or image-described) post."""
    return call_llm(
        [
            {"role": "system", "content": persona["personality"]},
            {
                "role": "user",
                "content": f"Post: \"{content}\"\nTulis 1 komentar singkat. Langsung isi komentar, tanpa tanda kutip.",
            },
        ],
        persona["text_model"],
    )


def comment_image(img_b64, persona):
    """Generate a comment on an image post using the persona's vision model."""
    if not persona.get("vision_model"):
        return None
    return call_llm(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}",
                            "detail": "low",
                        },
                    },
                    {
                        "type": "text",
                        "text": f"{persona['personality']}\nFoto ini dipost teman. 1 komentar singkat. Langsung isi, tanpa tanda kutip.",
                    },
                ],
            }
        ],
        persona["vision_model"],
    )


def describe_image(img_b64):
    """Internal-only: describe an image for context. NEVER shown to user."""
    return call_llm(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}",
                            "detail": "low",
                        },
                    },
                    {
                        "type": "text",
                        "text": "Deskripsikan gambar ini 1 kalimat, bahasa Indonesia.",
                    },
                ],
            }
        ],
        VISION_MODEL,
        max_tokens=70,
    )


def dm_reply(persona, history):
    """Generate a DM reply with conversation thread context.
    history: list of {sender, content} oldest→newest, including the latest user message.
    DM is more conversational than public comments — slightly longer (1-3 sentences ok).
    """
    msgs = [
        {
            "role": "system",
            "content": (
                f"{persona['personality']}\n\n"
                f"Kamu lagi DM (chat pribadi) sama temen. Lebih casual & personal dari komen publik. "
                f"Boleh 1-3 kalimat singkat, tetap dalam karakter. JANGAN pakai tanda kutip."
            ),
        }
    ]
    # Map sender → role: 'me' is user, persona username is assistant
    for m in history:
        role = "user" if m["sender"] == "me" else "assistant"
        msgs.append({"role": role, "content": m["content"]})
    return call_llm(msgs, persona["text_model"], max_tokens=120)
