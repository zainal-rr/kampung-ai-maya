from __future__ import annotations

import os

from maya_core.cost_tracker import record_usage
from maya_core.language_policy import language_instruction
from maya_core.models import TheSenses


async def answer_with_gemini(db_path: str, question: str) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "Malay quality answering is not available right now."
    prompt = [
        {"role": "system", "content": "You are Maya. Answer in natural Malay or Manglish for iMac voice."},
        {"role": "system", "content": language_instruction(question)},
        {"role": "system", "content": "Use 2 to 5 spoken sentences. Do not use exclamation marks. Avoid dash symbols."},
        {"role": "user", "content": question},
    ]
    reply = await TheSenses(api_key).chat(prompt)
    await record_usage(db_path, "gemini_flash_text_calls", 1, "imac voice Malay or Manglish tool")
    return reply.strip() or "Saya tak dapat susun jawapan elok tadi."
