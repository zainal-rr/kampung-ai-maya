from __future__ import annotations

import aiosqlite

from cost_tracker import DEFAULT_RATES, DISPLAY_ORDER


LABELS = {
    "grok_voice_agent_seconds": "Grok Voice Agent",
    "ara_tts_chars": "Ara TTS",
    "xai_stt_seconds": "xAI STT",
    "gemini_flash_text_calls": "Gemini Flash text",
    "gemini_flash_vision_calls": "Gemini Flash sight",
    "gemini_premium_text_calls": "Gemini 3.5 Flash text",
    "gemini_premium_vision_calls": "Gemini 3.5 Flash sight",
    "codex_implementation_jobs": "Artisan Claude Code jobs",
    "kimi_coding_calls": "Kimi coding",
    "gpt_complex_calls": "GPT complex",
    "claude_steward_calls": "Claude steward",
    "grok_text_calls": "Grok text/news",
}

UNITS = {
    "grok_voice_agent_seconds": "seconds",
    "ara_tts_chars": "characters",
    "xai_stt_seconds": "seconds",
}

SAVER_NOTES = {
    "grok_voice_agent_seconds": "Wake phrase only; close after 5 seconds silence.",
    "ara_tts_chars": "Use for Telegram voice replies only when voice is used.",
    "xai_stt_seconds": "Use for voice notes and live voice transcription.",
    "gemini_flash_text_calls": "Default low-cost Telegram and document drafting lane.",
    "gemini_premium_text_calls": "Use only for premium research or careful synthesis.",
    "codex_implementation_jobs": "Local Claude Code execution through Artisan; provider billing is external.",
    "gpt_complex_calls": "Only through /complex or explicit GPT request.",
    "claude_steward_calls": "Review, critique, safety, and document quality checks.",
}


async def kampung_ai_cost_rows(db_path: str) -> tuple[list[str], list[list[str]]]:
    usage = await _usage_totals(db_path)
    headers = ["Lane", "Unit", "Last 30 Days", "Rate USD", "Estimate USD", "Saver Rule"]
    rows = []
    for lane in DISPLAY_ORDER:
        units = usage.get(lane, 0.0)
        rate = DEFAULT_RATES.get(lane, 0.0)
        rows.append([
            LABELS.get(lane, lane),
            UNITS.get(lane, "calls"),
            round(units, 2),
            rate,
            round(units * rate, 4),
            SAVER_NOTES.get(lane, "Use only when the route needs this lane."),
        ])
    rows.append(["Total", "", "", "", round(sum(float(row[4]) for row in rows), 4), "Estimate only. Check provider billing for exact cost."])
    return headers, rows


async def _usage_totals(db_path: str) -> dict[str, float]:
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                """
                SELECT lane, SUM(units)
                FROM usage_events
                WHERE created_at >= datetime('now', '-30 days')
                GROUP BY lane
                """
            )
            return {lane: float(units or 0) for lane, units in await cursor.fetchall()}
    except Exception:
        return {}
