from __future__ import annotations

"""Helpers for nightly memory consolidation: prompts, parsing, episode
gathering, decay reporting, run bookkeeping, link recording, and audit.

Split from nightly_consolidation.py to respect the 300-line root-file rule,
mirroring the weekly_memory.py / weekly_memory_helpers.py pattern.
"""

import json
from datetime import datetime, timedelta, timezone

import aiosqlite

from canonical_memory import subject_key_from_text
from cost_tracker import record_usage
from memory_audit import record_memory_audit_event
from memory_links import add_memory_link
from permission_policy import contains_sensitive_info
from weekly_memory_live import ProviderCall, _clean, _json_blob

MAX_EPISODE_ROWS = 400
MAX_EPISODE_CHARS = 280
MAX_PROMPT_CHARS = 12000
MAX_LINKS_PER_RUN = 12
DECAY_REPORT_LIMIT = 20

_INITIALIZED: set[str] = set()


async def init_nightly_db(db_path: str) -> None:
    if db_path in _INITIALIZED:
        return
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS nightly_consolidation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                watermark TEXT DEFAULT '',
                episodes INTEGER DEFAULT 0,
                saved INTEGER DEFAULT 0,
                rejected INTEGER DEFAULT 0,
                links_recorded INTEGER DEFAULT 0,
                provider_calls INTEGER DEFAULT 0,
                skip_reason TEXT DEFAULT '',
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            )
            """
        )
        await db.commit()
    _INITIALIZED.add(db_path)


def distiller_prompt(run_key: str, episodes: list[dict[str, str]]) -> str:
    return "\n".join((
        "You are Maya's nightly memory consolidator. Replay today's episodes and extract durable memories.",
        "Return JSON only:",
        '{"facts":[{"content":"...","kind":"preference|lesson|project_fact|profile_fact","scope":"global","confidence":"high|medium"}],',
        ' "links":[{"source":"<content of one fact or existing memory>","target":"<content of another>","relation":"shared_entity|same_episode|causal"}]}',
        "Facts must be stable and worth keeping for months. No test memories, temporary chatter, sensitive data, guesses, or forgotten facts.",
        "Links connect memories about the same person, place, project, or cause-effect pair.",
        f"Night: {run_key}",
        "Episodes:",
        json.dumps(episodes, ensure_ascii=True)[:MAX_PROMPT_CHARS],
    ))


def parse_links(text: str) -> list[dict[str, str]]:
    blob = _json_blob(text)
    if not blob:
        return []
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return []
    links = data.get("links", []) if isinstance(data, dict) else []
    if not isinstance(links, list):
        return []
    cleaned = []
    for link in links[:MAX_LINKS_PER_RUN]:
        if isinstance(link, dict) and link.get("source") and link.get("target"):
            cleaned.append({
                "source": _clean(str(link["source"])),
                "target": _clean(str(link["target"])),
                "relation": _clean(str(link.get("relation", "related"))) or "related",
            })
    return cleaned


async def record_links(db_path: str, links: list[dict[str, str]]) -> tuple[int, int]:
    """Record links between resolved active memories. Returns (recorded, dropped)."""
    recorded = 0
    dropped = 0
    for link in links:
        source_id = await resolve_active_memory_id(db_path, link["source"])
        target_id = await resolve_active_memory_id(db_path, link["target"])
        if not source_id or not target_id:
            dropped += 1
            continue
        ok = await add_memory_link(
            db_path, source_id, target_id,
            relation=link["relation"] if link["relation"] in ("shared_entity", "same_episode", "causal") else "related",
            source_channel="nightly_consolidation",
        )
        recorded += 1 if ok else 0
        dropped += 0 if ok else 1
    return recorded, dropped


async def resolve_active_memory_id(db_path: str, content: str) -> str:
    subject_key = subject_key_from_text(content)
    if not subject_key:
        return ""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT memory_id FROM canonical_memory_items
            WHERE subject_key = ? AND status = 'active'
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            LIMIT 1
            """,
            (subject_key,),
        )
        row = await cursor.fetchone()
    return str(row[0]) if row else ""


async def gather_episodes(db_path: str, watermark: str) -> tuple[list[dict[str, str]], str]:
    """Day replay: history rows newer than the watermark, sensitive rows excluded."""
    async with aiosqlite.connect(db_path) as db:
        if not await table_exists(db, "history"):
            return [], watermark
        cursor = await db.execute(
            """
            SELECT role, content, timestamp FROM history
            WHERE timestamp > ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (watermark or "", MAX_EPISODE_ROWS),
        )
        rows = await cursor.fetchall()
    episodes = []
    new_watermark = watermark
    for role, content, timestamp in rows:
        new_watermark = max(new_watermark or "", str(timestamp or ""))
        text = " ".join(str(content or "").split())[:MAX_EPISODE_CHARS]
        if not text or contains_sensitive_info(text):
            continue
        episodes.append({"role": str(role or ""), "text": text, "at": str(timestamp or "")})
    return episodes, new_watermark


async def decay_report(db_path: str, decay_days: int) -> tuple[str, ...]:
    """Stale, unused, unpinned active memories. Report only — never mutates."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(decay_days, 1))).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT content FROM canonical_memory_items
            WHERE status = 'active' AND pinned = 0 AND temporary = 0
              AND updated_at < ?
              AND (last_used_at IS NULL OR last_used_at < ?)
            ORDER BY updated_at ASC
            LIMIT ?
            """,
            (cutoff, cutoff, DECAY_REPORT_LIMIT),
        )
        rows = await cursor.fetchall()
    return tuple(str(row[0]) for row in rows)


async def last_watermark(db_path: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT watermark FROM nightly_consolidation_runs WHERE status = 'completed' ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
    return str(row[0]) if row and row[0] else ""


async def finish_run(
    db_path: str, run_key: str, *, status: str, watermark: str, episodes: int = 0,
    saved: int = 0, rejected: int = 0, links_recorded: int = 0, provider_calls: int = 0,
    skip_reason: str = "",
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO nightly_consolidation_runs
                (run_key, status, watermark, episodes, saved, rejected, links_recorded,
                 provider_calls, skip_reason, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (run_key, status, watermark, episodes, saved, rejected, links_recorded, provider_calls, skip_reason),
        )
        await db.commit()


async def record_costs(db_path: str, distiller_agent: ProviderCall, reviewer_agent: ProviderCall | None) -> None:
    try:
        lane = getattr(distiller_agent, "usage_lane", "gemini_flash_text_calls")
        await record_usage(db_path, str(lane), 1, "nightly memory consolidation")
        if reviewer_agent:
            await record_usage(db_path, "claude_steward_calls", 1, "nightly memory review")
    except Exception:
        pass  # cost visibility must never break consolidation


async def audit_nightly(
    db_path: str, event_type: str, run_key: str, fact: dict[str, str],
    *, memory_id: str = "", source_ref: str = "",
) -> None:
    content = _clean(fact.get("content", ""))
    if not content:
        return
    await record_memory_audit_event(
        db_path,
        event_type=event_type,
        memory_id=memory_id,
        subject_key=subject_key_from_text(content),
        status_after="saved" if event_type == "weekly_save" else "candidate",
        source_channel="nightly_consolidation",
        source_ref=source_ref or run_key,
        run_id=run_key,
        content=content,
    )


async def table_exists(db: aiosqlite.Connection, table: str) -> bool:
    cursor = await db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,))
    return bool(await cursor.fetchone())
