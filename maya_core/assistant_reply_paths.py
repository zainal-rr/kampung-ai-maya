from __future__ import annotations

from maya_core.assistant_prompts import (
    IMAC_FAST_SYSTEM_PROMPT,
    TELEGRAM_FAST_SYSTEM_PROMPT,
    TELEGRAM_VOICE_SYSTEM_PROMPT,
    delivery_instruction,
)
from language_policy import language_instruction
from telegram_context_policy import silent_context_guard
from telegram_rewrite_context import is_rewrite_followup


def prepare_input(
    channel: str,
    text: str,
    memory_context: str,
    skill_context: str,
    input_type: str = "text",
) -> str:
    context_blocks = silent_context_guard("\n\n".join(block for block in (memory_context, skill_context) if block))
    prefix = f"[delivery]\n{delivery_instruction(channel, input_type)}\n{language_instruction(text)}"
    user_block = f"[user]\n{text}"
    if context_blocks:
        return f"{prefix}\n\n[support-context]\n{context_blocks}\n\n{user_block}"
    return f"{prefix}\n\n{user_block}"


async def fast_imac_response(responder, text: str, memory_context: str, skill_context: str) -> str:
    support_context = silent_context_guard("\n\n".join(block for block in (memory_context, skill_context) if block))
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
    support_context = silent_context_guard("\n\n".join(block for block in (memory_context, skill_context) if block))
    prompt = [
        {"role": "system", "content": TELEGRAM_VOICE_SYSTEM_PROMPT if voice_note else TELEGRAM_FAST_SYSTEM_PROMPT},
        {"role": "system", "content": _telegram_length_instruction(text, voice_note)},
        {"role": "system", "content": language_instruction(text)},
        {"role": "system", "content": support_context or "No extra support context."},
        {"role": "system", "content": topic_context or "No recent thread context."},
        {"role": "user", "content": text},
    ]
    response = await responder.chat(prompt)
    if is_rewrite_followup(text) and len(response.splitlines()) > 3:
        response = await responder.chat(
            [
                {"role": "system", "content": TELEGRAM_FAST_SYSTEM_PROMPT},
                {
                    "role": "system",
                    "content": (
                        "Condense this Telegram rewrite into at most two short lines. "
                        "No numbered list, no bullets, no explanation, no file or memory references."
                    ),
                },
                {"role": "system", "content": language_instruction(text)},
                {"role": "user", "content": f"User instruction: {text}\n\nDraft:\n{response}"},
            ]
        )
    return response


def _telegram_length_instruction(text: str, voice_note: bool) -> str:
    lowered = " ".join(str(text).lower().split())
    if voice_note:
        return "For Telegram voice, keep the reply natural and short unless the user asks for detail."
    if is_rewrite_followup(lowered):
        return (
            "The user is asking for a rewrite or tone adjustment. Rewrite only a suitable "
            "immediately previous draft/message from the current thread. If the previous "
            "assistant message was a refusal, safety warning, route/status output, file report, "
            "or unrelated project context, ask what text to rewrite in one short line. Otherwise "
            "reply with only the revised text in at most two short lines. No numbered lists."
        )
    return "Keep Telegram text concise by default; use structure only when it genuinely helps."
