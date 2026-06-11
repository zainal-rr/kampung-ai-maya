"""Continuity store for the latest artifact being discussed or edited.

Artifact sessions are the bridge between separate Telegram/iMac turns. When
Maya creates a Word itinerary, this module records the path, artifact type,
short title, extracted parameters such as destination/days/people, and an expiry
time. Later requests like "make an Excel budget for that itinerary" or "change
it to 5 days" resolve through this store instead of relying on brittle wording.

This is not long-term memory. It is a short-lived working context that supports
same-day document collaboration without polluting canonical memory.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from artifact_naming import short_artifact_stem
from travel_parameters import extract_destination
from word_quality_travel import explicit_day_count


ARTIFACT_SESSION_TTL_HOURS = 24


@dataclass(frozen=True)
class ArtifactSession:
    id: int
    channel: str
    artifact_type: str
    path: str
    short_name: str
    title: str
    topic: str
    state: dict
    revision: int
    status: str
    updated_at: str
    expires_at: str


async def init_artifact_sessions_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS artifact_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                path TEXT NOT NULL,
                short_name TEXT NOT NULL,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                state_json TEXT NOT NULL DEFAULT '{}',
                revision INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL
            )
            """
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_artifact_sessions_channel_status ON artifact_sessions(channel, status, updated_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_artifact_sessions_path ON artifact_sessions(path)")
        await db.commit()


async def record_artifact_session(db_path: str, channel: str, artifact_type: str, path: Path, topic: str) -> ArtifactSession:
    await init_artifact_sessions_db(db_path)
    state = artifact_state_from_topic(artifact_type, topic)
    short_name = short_artifact_stem(topic, artifact_type)
    title = _title_from_stem(short_name)
    now = _now()
    expires = _expiry()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE artifact_sessions SET status = 'inactive' WHERE channel = ? AND status = 'active'",
            (channel,),
        )
        cursor = await db.execute(
            """
            INSERT INTO artifact_sessions
                (channel, artifact_type, path, short_name, title, topic, state_json, revision, status, created_at, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'active', ?, ?, ?)
            """,
            (channel, artifact_type, str(path), short_name, title, topic, json.dumps(state, ensure_ascii=False), now, now, expires),
        )
        session_id = int(cursor.lastrowid or 0)
        await db.commit()
    return ArtifactSession(session_id, channel, artifact_type, str(path), short_name, title, topic, state, 0, "active", now, expires)


async def active_artifact_session(db_path: str, channel: str, fallback_path: str | None = None) -> ArtifactSession | None:
    await init_artifact_sessions_db(db_path)
    now = _now()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM artifact_sessions
            WHERE channel = ? AND status = 'active' AND expires_at > ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (channel, now),
        )
        row = await cursor.fetchone()
        if not row and fallback_path:
            cursor = await db.execute(
                """
                SELECT * FROM artifact_sessions
                WHERE path = ? AND status != 'deleted'
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (fallback_path,),
            )
            row = await cursor.fetchone()
    return _row_to_session(row) if row else None


async def cleanup_expired_artifact_sessions(db_path: str, channel: str | None = None) -> None:
    await init_artifact_sessions_db(db_path)
    now = _now()
    query = "UPDATE artifact_sessions SET status = 'inactive' WHERE status = 'active' AND expires_at <= ?"
    params: tuple[object, ...] = (now,)
    if channel:
        query += " AND channel = ?"
        params = (now, channel)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(query, params)
        await db.commit()


async def update_artifact_session_after_edit(
    db_path: str,
    session: ArtifactSession,
    channel: str,
    path: Path,
    instruction: str,
) -> ArtifactSession:
    state = apply_artifact_edit_delta(session.state, instruction)
    topic = _topic_after_edit(session, state, instruction)
    short_name = session.short_name or short_artifact_stem(topic, session.artifact_type)
    title = _title_from_stem(short_name)
    now = _now()
    expires = _expiry()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE artifact_sessions
            SET channel = ?, path = ?, short_name = ?, title = ?, topic = ?, state_json = ?,
                revision = revision + 1, status = 'active', updated_at = ?, expires_at = ?
            WHERE id = ?
            """,
            (channel, str(path), short_name, title, topic, json.dumps(state, ensure_ascii=False), now, expires, session.id),
        )
        await db.commit()
    return ArtifactSession(session.id, channel, session.artifact_type, str(path), short_name, title, topic, state, session.revision + 1, "active", now, expires)


def artifact_state_from_topic(artifact_type: str, topic: str) -> dict:
    destination = extract_destination(topic)
    days = explicit_day_count(topic) or _day_count(topic)
    people = _people_count(topic)
    purpose = _purpose(topic, artifact_type)
    state = {
        "artifact_type": artifact_type,
        "subject": _subject(topic, destination),
        "purpose": purpose,
    }
    if destination:
        state["destination"] = destination
    if days:
        state["days"] = days
    if people:
        state["people"] = people
    return state


def apply_artifact_edit_delta(state: dict, instruction: str) -> dict:
    updated = dict(state)
    days = _day_count(instruction)
    people = _people_count(instruction)
    destination = extract_destination(instruction)
    if days:
        updated["days"] = days
    if people:
        updated["people"] = people
    if destination:
        updated["destination"] = destination
        updated["subject"] = destination
    return updated


def topic_from_state(artifact_type: str, state: dict, fallback: str = "") -> str:
    subject = str(state.get("destination") or state.get("subject") or "").strip()
    purpose = str(state.get("purpose") or "").strip()
    parts: list[str] = []
    if subject:
        parts.append(subject)
    if purpose and purpose.lower() not in subject.lower():
        parts.append(purpose)
    if state.get("days"):
        parts.append(f"{int(state['days'])} days")
    if state.get("people"):
        parts.append(f"{int(state['people'])} people")
    topic = " ".join(parts).strip()
    return topic or fallback or artifact_type


def _topic_after_edit(session: ArtifactSession, state: dict, instruction: str) -> str:
    days = _day_count(instruction)
    if days and session.topic:
        base = re.sub(r"\b\d{1,2}\s+days?\b", " ", session.topic, flags=re.I)
        base = re.sub(r"^\d{1,2}\s*[- ]?\s*day\s+", " ", base, flags=re.I)
        base = " ".join(base.split())
        if base:
            return f"{days}-day {base}"
    return topic_from_state(session.artifact_type, state, fallback=session.topic)


def _row_to_session(row) -> ArtifactSession:
    try:
        state = json.loads(row["state_json"] or "{}")
    except json.JSONDecodeError:
        state = {}
    return ArtifactSession(
        int(row["id"]),
        row["channel"],
        row["artifact_type"],
        row["path"],
        row["short_name"],
        row["title"],
        row["topic"],
        state,
        int(row["revision"] or 0),
        row["status"],
        row["updated_at"],
        row["expires_at"],
    )


def _purpose(topic: str, artifact_type: str) -> str:
    low = topic.lower()
    if any(word in low for word in ("itinerary", "travel plan", "trip", "travel")):
        return "itinerary" if "budget" not in low else "budget tracker"
    if any(word in low for word in ("budget", "expense", "cost", "spend", "tracker")):
        return "budget tracker"
    if any(word in low for word in ("config", "configuration")):
        return "config"
    if "proposal" in low:
        return "proposal"
    if "guide" in low or "setup" in low:
        return "guide"
    if artifact_type == "pptx":
        return "deck"
    if artifact_type == "xlsx":
        return "tracker"
    return "document"


def _subject(topic: str, destination: str) -> str:
    if destination:
        return destination
    words = [word for word in re.findall(r"[A-Za-z0-9]+", topic.lower()) if word not in _STOP_WORDS]
    return " ".join(words[:2]).title() if words else "Maya"


def _day_count(text: str) -> int | None:
    raw = str(text or "").lower()
    pattern = r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*[- ]?\s*(?:day|days)\b"
    match = re.search(pattern, raw)
    return _count_value(match.group(1)) if match else None


def _people_count(text: str) -> int | None:
    raw = str(text or "").lower()
    pattern = r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:people|persons?|travelers?|travellers?|pax|adults?|guests?)\b"
    match = re.search(pattern, raw)
    return _count_value(match.group(1)) if match else None


def _count_value(raw: str) -> int:
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    value = raw.lower()
    return max(1, min(31, int(value) if value.isdigit() else words.get(value, 1)))


def _title_from_stem(stem: str) -> str:
    return " ".join(part.capitalize() for part in stem.replace("-", " ").split())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=ARTIFACT_SESSION_TTL_HOURS)).isoformat()


_STOP_WORDS = {
    "make", "create", "write", "draft", "me", "a", "an", "the", "for", "to", "in", "with", "and",
    "word", "document", "doc", "excel", "sheet", "spreadsheet", "powerpoint", "slides", "deck",
    "days", "day", "people", "person", "two", "three", "four", "one",
}
