from __future__ import annotations

from assistant_prompts import (
    IMAC_FAST_SYSTEM_PROMPT,
    TELEGRAM_FAST_SYSTEM_PROMPT,
    TELEGRAM_VOICE_SYSTEM_PROMPT,
    delivery_instruction,
)
from language_policy import language_instruction


def prepare_input(
    channel: str,
    text: str,
    memory_context: str,
    skill_context: str,
    input_type: str = "text",
) -> str:
    context_blocks = "\n\n".join(block for block in (memory_context, skill_context) if block)
    prefix = f"[delivery]\n{delivery_instruction(channel, input_type)}\n{language_instruction(text)}"
    user_block = f"[user]\n{text}"
    if context_blocks:
        return f"{prefix}\n\n[support-context]\n{context_blocks}\n\n{user_block}"
    return f"{prefix}\n\n{user_block}"


async def fast_imac_response(responder, text: str, memory_context: str, skill_context: str) -> str:
    support_context = "\n\n".join(block for block in (memory_context, skill_context) if block)
    prompt = [
        {"role": "system", "content": IMAC_FAST_SYSTEM_PROMPT},
        {"role": "system", "content": language_instruction(text)},
        {"role": "system", "content": support_context or "No extra support context."},
        {"role": "user", "content": text},
    ]
    return await responder.chat(prompt)


async def fast_telegram_response(
    responder,
    text: str,
    memory_context: str,
    skill_context: str,
    topic_context: str = "",
    voice_note: bool = False,
) -> str:
    support_context = "\n\n".join(block for block in (memory_context, skill_context) if block)
    prompt = [
        {"role": "system", "content": TELEGRAM_VOICE_SYSTEM_PROMPT if voice_note else TELEGRAM_FAST_SYSTEM_PROMPT},
        {"role": "system", "content": _telegram_length_instruction(text, voice_note)},
        {"role": "system", "content": language_instruction(text)},
        {"role": "system", "content": support_context or "No extra support context."},
        {"role": "system", "content": topic_context or "No recent thread context."},
        {"role": "user", "content": text},
    ]
    return await responder.chat(prompt)


def _telegram_length_instruction(text: str, voice_note: bool) -> str:
    lowered = " ".join(str(text).lower().split())
    if voice_note:
        return "For Telegram voice, keep the reply natural and short unless the user asks for detail."
    if any(marker in lowered for marker in ("shorter", "more practical", "keep it short", "simple answer", "too long")):
        return (
            "The user is asking for a shorter or more practical version. Reply in at most "
            "two short lines. No nested bullets, no explanations, no extra context."
        )
    return "Keep Telegram text concise by default; use structure only when it genuinely helps."
