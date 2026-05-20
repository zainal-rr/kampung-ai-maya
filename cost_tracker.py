from __future__ import annotations

import os
from dataclasses import dataclass

import aiosqlite


DEFAULT_RATES = {
    "grok_voice_agent_seconds": 0.05 / 60,
    "ara_tts_chars": 4.20 / 1_000_000,
    "xai_stt_seconds": 0.20 / 3600,
    "gemini_flash_vision_calls": 0.001,
    "gemini_pro_vision_calls": 0.01,
    "kimi_coding_calls": 0.02,
    "gpt_complex_calls": 0.05,
    "claude_steward_calls": 0.03,
    "grok_text_calls": 0.01,
}

DISPLAY_ORDER = (
    "grok_voice_agent_seconds",
    "ara_tts_chars",
    "xai_stt_seconds",
    "gemini_flash_vision_calls",
    "gemini_pro_vision_calls",
    "kimi_coding_calls",
    "gpt_complex_calls",
    "claude_steward_calls",
    "grok_text_calls",
)


@dataclass(frozen=True)
class UsageLine:
    lane: str
    units: float
    estimate: float


async def init_cost_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lane TEXT NOT NULL,
                units REAL NOT NULL,
                details TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def record_usage(db_path: str | None, lane: str, units: float = 1, details: str = "") -> None:
    if not db_path or units <= 0:
        return
    await init_cost_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO usage_events (lane, units, details) VALUES (?, ?, ?)",
            (lane, units, details),
        )
        await db.commit()


async def usage_summary_text(db_path: str, days: int = 30) -> str:
    await init_cost_db(db_path)
    rows = await _usage_rows(db_path, days)
    lines = [_usage_line(row[0], float(row[1] or 0)) for row in rows]
    by_lane = {line.lane: line for line in lines}
    total = sum(line.estimate for line in lines)
    output = [f"Usage estimate, last {days} days:"]
    for lane in DISPLAY_ORDER:
        line = by_lane.get(lane, UsageLine(lane, 0, 0))
        output.append(f"{_label(lane)}: {_units(lane, line.units)}  ${line.estimate:.2f}")
    output.append(f"Total estimate: ${total:.2f}")
    output.append("Estimate only. Token-heavy calls still need provider billing to be exact.")
    return "\n".join(output)


async def _usage_rows(db_path: str, days: int) -> list[tuple[str, float]]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT lane, SUM(units)
            FROM usage_events
            WHERE created_at >= datetime('now', ?)
            GROUP BY lane
            """,
            (f"-{days} days",),
        )
        return await cursor.fetchall()


def _usage_line(lane: str, units: float) -> UsageLine:
    return UsageLine(lane=lane, units=units, estimate=units * _rate(lane))


def _rate(lane: str) -> float:
    env_name = f"COST_RATE_{lane.upper()}"
    try:
        return float(os.getenv(env_name, str(DEFAULT_RATES.get(lane, 0))))
    except ValueError:
        return DEFAULT_RATES.get(lane, 0)


def _label(lane: str) -> str:
    labels = {
        "grok_voice_agent_seconds": "Grok Voice Agent",
        "ara_tts_chars": "Ara TTS",
        "xai_stt_seconds": "xAI STT",
        "gemini_flash_vision_calls": "Gemini Flash sight",
        "gemini_pro_vision_calls": "Gemini Pro sight",
        "kimi_coding_calls": "Kimi coding",
        "gpt_complex_calls": "GPT complex",
        "claude_steward_calls": "Claude steward",
        "grok_text_calls": "Grok text/news",
    }
    return labels.get(lane, lane)


def _units(lane: str, units: float) -> str:
    if lane.endswith("_seconds"):
        return f"{units / 60:.1f} min"
    if lane.endswith("_chars"):
        return f"{int(units)} chars"
    return f"{int(units)} calls"
