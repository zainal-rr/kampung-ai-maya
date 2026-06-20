from __future__ import annotations

import os
from dataclasses import replace
from datetime import date
from pathlib import Path

from maya_core.reliability_scorecard import format_reliability_scorecard
from maya_harness.live_reliability_soak import SOAK_PATH, SoakDay, load_soak, record_soak_day


RELIABILITY_NOTE_FIELDS = {
    "correction": "user_corrections",
    "user_correction": "user_corrections",
    "user_corrections": "user_corrections",
    "missed": "missed_replies",
    "missed_reply": "missed_replies",
    "missed_replies": "missed_replies",
    "route": "wrong_routes",
    "wrong_route": "wrong_routes",
    "wrong_routes": "wrong_routes",
    "voice": "voice_timeouts",
    "voice_timeout": "voice_timeouts",
    "voice_timeouts": "voice_timeouts",
    "memory": "memory_mistakes",
    "memory_mistake": "memory_mistakes",
    "memory_mistakes": "memory_mistakes",
    "delivery": "file_delivery_failures",
    "file_delivery": "file_delivery_failures",
    "file_delivery_failure": "file_delivery_failures",
    "file_delivery_failures": "file_delivery_failures",
    "browser": "browser_failures",
    "browser_failure": "browser_failures",
    "browser_failures": "browser_failures",
    "cost": "cost_spikes",
    "cost_spike": "cost_spikes",
    "cost_spikes": "cost_spikes",
    "false_done": "false_saved_claims",
    "false_saved": "false_saved_claims",
    "false_saved_claim": "false_saved_claims",
    "false_saved_claims": "false_saved_claims",
    "stale_file": "false_saved_claims",
    "artifact": "false_saved_claims",
}


def reliability_text(args: str) -> str:
    cleaned = args.strip()
    if not cleaned or cleaned.lower() in {"status", "scorecard", "show"}:
        return "Reliability:\n" + format_reliability_scorecard()
    head, _, rest = cleaned.partition(" ")
    if head.lower() not in {"note", "log", "failure"}:
        return (
            "Reliability: use /reliability to show the scorecard, or "
            "/reliability note [category] <what happened> to record today's failure note."
        )
    return _record_reliability_note(rest.strip())


def _record_reliability_note(args: str) -> str:
    category, note = _reliability_note_parts(args)
    if not note:
        return (
            "Reliability note: use /reliability note [category] <what happened>.\n"
            "Categories: correction, missed_reply, route, voice, memory, delivery, browser, cost, false_done."
        )
    path = _reliability_soak_path()
    today = date.today().isoformat()
    existing = next((row for row in load_soak(path) if row.day == today), SoakDay(day=today))
    field_name = RELIABILITY_NOTE_FIELDS[category]
    updated = replace(
        existing,
        **{
            field_name: getattr(existing, field_name) + 1,
            "notes": _append_reliability_note(existing.notes, category, note),
        },
    )
    record_soak_day(updated, path=path)
    return (
        "Reliability:\n"
        "Note logged for today.\n"
        f"Category: {category} ({field_name})\n"
        f"Note: {note}"
    )


def _reliability_note_parts(args: str) -> tuple[str, str]:
    cleaned = args.strip()
    if not cleaned:
        return "correction", ""
    first, _, rest = cleaned.partition(" ")
    normalized = first.lower().strip().replace("-", "_")
    if normalized in RELIABILITY_NOTE_FIELDS and rest.strip():
        return normalized, rest.strip()
    return "correction", cleaned


def _append_reliability_note(existing: str, category: str, note: str) -> str:
    entry = f"[telegram:{category}] {note}"
    return entry if not existing.strip() else f"{existing.strip()}; {entry}"


def _reliability_soak_path() -> Path:
    override = os.environ.get("MAYA_RELIABILITY_SOAK_PATH", "").strip()
    return Path(override) if override else SOAK_PATH
