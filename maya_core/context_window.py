"""Maya's working memory: the token-budgeted raw context window (Tier 1+2).

Design: docs/context_window_design_2026-06-12.md (read it before changing
anything here — especially the staging order and the canary contract).

The five memory layers stay separate. This module owns ONLY:
- the turn store (facts-not-policy metadata, taint included from day one),
- the rolling per-channel summary (session continuity, NEVER a memory write),
- the forget watermark,
- `assemble_recent_context()` — the single assembly point for window content.

Everything is gated by MAYA_CONTEXT_WINDOW (default OFF). While off, recording
and assembly are no-ops and live behavior is byte-identical.

Guarantees (enforced by context_window_canaries_smoke.py):
- C1 forget-into-summary: a forget drops + rebuilds the rolling summary.
- C2 taint persistence: included tainted turns taint the assembled context;
  the summary inherits untrusted_influence (never injection text).
- C4 budget binding: budget is a ceiling, never a fill target.
- C5 watermark: nothing from before the last forget enters assembly.
- C6 summaries rebuild from raw turns only (no summary-of-summary).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiosqlite

_ROUTE_ENV = {
    "voice": ("MAYA_CONTEXT_VOICE_BUDGET", 3000),
    "normal": ("MAYA_CONTEXT_TELEGRAM_BUDGET", 12000),
    "deep": ("MAYA_CONTEXT_DEEP_BUDGET", 32000),
    "complex": ("MAYA_CONTEXT_COMPLEX_BUDGET", 48000),
}

_HEADER = "Recent conversation (working memory):"
_GIST_LABEL = "Session gist (compressed older context):"
_FOOTER = (
    "This recent-conversation block is conversational context only. Durable "
    "facts come from the memory context; authoritative methods come from the "
    "domain knowledge context. Recency never outranks those sources."
)


def context_window_enabled() -> bool:
    return os.getenv("MAYA_CONTEXT_WINDOW", "0") == "1"


def rolling_summary_enabled() -> bool:
    return os.getenv("MAYA_CONTEXT_ROLLING_SUMMARY", "1") == "1"


def route_budget(route: str) -> int:
    env, default = _ROUTE_ENV.get(route, _ROUTE_ENV["normal"])
    try:
        return max(0, int(os.getenv(env, str(default))))
    except ValueError:
        return default


def per_turn_cap() -> int:
    try:
        return max(50, int(os.getenv("MAYA_CONTEXT_PER_TURN_CAP", "800")))
    except ValueError:
        return 800


def summary_cap() -> int:
    try:
        return max(100, int(os.getenv("MAYA_CONTEXT_SUMMARY_CAP", "1000")))
    except ValueError:
        return 1000


def estimate_tokens(text: str) -> int:
    return max(1, len(str(text)) // 4)


def resolve_route(channel: str, *, complex_route: bool = False, deep: bool = False) -> str:
    if complex_route:
        return "complex"
    if deep:
        return "deep"
    if "voice" in str(channel).lower():
        return "voice"
    return "normal"


@dataclass(frozen=True)
class AssembledContext:
    text: str = ""
    untrusted_influence: bool = False
    injection_detected: bool = False
    manifest: dict = field(default_factory=dict)


async def init_context_window_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS context_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tokens INTEGER NOT NULL,
                source TEXT DEFAULT 'user',
                untrusted_influence INTEGER DEFAULT 0,
                injection_detected INTEGER DEFAULT 0,
                signals TEXT DEFAULT '[]',
                folded INTEGER DEFAULT 0,
                run_id TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS context_rolling_summary (
                channel TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                tokens INTEGER NOT NULL,
                untrusted_influence INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS context_watermarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_turn_id INTEGER NOT NULL,
                reason TEXT DEFAULT 'canonical_forget',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def record_context_turn(
    db_path: str,
    *,
    channel: str,
    role: str,
    content: str,
    source: str | None = None,
    untrusted_influence: bool = False,
    injection_detected: bool = False,
    signals: tuple[str, ...] = (),
    run_id: str = "",
) -> None:
    """Store one turn with facts-only metadata. No-op while the switch is off.

    Policy (what taint MEANS for an action) is never stored — the permission
    kernel derives it at action time. Per-turn cap applies at write so one
    giant reply cannot evict an entire window at assembly time.
    """
    if not context_window_enabled():
        return
    text = " ".join(str(content or "").split())
    if not text:
        return
    cap_chars = per_turn_cap() * 4
    if len(text) > cap_chars:
        text = text[: cap_chars - 3].rstrip() + "..."
    await init_context_window_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO context_turns
                (channel, role, content, tokens, source, untrusted_influence,
                 injection_detected, signals, run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(channel or "unknown"),
                "user" if role == "user" else "maya",
                text,
                estimate_tokens(text),
                source or ("user" if role == "user" else "maya"),
                1 if untrusted_influence else 0,
                1 if injection_detected else 0,
                json.dumps(list(signals)),
                run_id,
            ),
        )
        await db.commit()
    if rolling_summary_enabled():
        await _compact_overflow(db_path, channel=str(channel or "unknown"))


async def on_canonical_forget(db_path: str) -> None:
    """Forget honesty across the window tiers (canary C1/C5).

    Watermark: nothing recorded before this moment may enter assembly again.
    Rolling summaries are DROPPED (never surgically edited — paraphrase
    defeats string matching) and rebuild naturally from surviving raw turns
    on the next compaction pass.
    """
    await init_context_window_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        # The watermark is the LAST TURN ID at forget time, not a timestamp:
        # SQLite's second-resolution clock cannot order a forget against turns
        # recorded in the same second (canary C5 caught exactly this leak).
        # Turn ids are monotonic and deterministic.
        cursor = await db.execute("SELECT COALESCE(MAX(id), 0) AS last_id FROM context_turns")
        last_id = int((await cursor.fetchone())[0])
        await db.execute(
            "INSERT INTO context_watermarks (last_turn_id, reason) VALUES (?, 'canonical_forget')",
            (last_id,),
        )
        await db.execute("DELETE FROM context_rolling_summary")
        # Pre-watermark turns are excluded by the watermark; clearing folded
        # flags on the (post-watermark) survivors lets the next compaction
        # rebuild the summary from raw turns only (canary C6).
        await db.execute("UPDATE context_turns SET folded = 0 WHERE folded = 1")
        await db.commit()


async def assemble_recent_context(
    db_path: str,
    *,
    channel: str,
    route: str = "normal",
) -> AssembledContext:
    """THE single assembly point for window content (chokepoint, canary C3).

    Both cross-tier filters run here, once: the forget watermark and the
    union taint over everything included. Returns the rendered block, the
    taint flags for the permission kernel, and the audit manifest that the
    /context view (Stage 3) will render.
    """
    if not context_window_enabled():
        return AssembledContext()
    budget = route_budget(route)
    if budget <= 0:
        return AssembledContext()
    await init_context_window_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT COALESCE(MAX(last_turn_id), 0) AS wm FROM context_watermarks")
        watermark = int((await cursor.fetchone())["wm"])
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM context_turns WHERE id <= ?",
            (watermark,),
        )
        excluded_watermarked = int((await cursor.fetchone())["n"])
        cursor = await db.execute(
            """
            SELECT role, content, tokens, untrusted_influence, injection_detected, created_at
            FROM context_turns
            WHERE folded = 0 AND id > ?
            ORDER BY id DESC
            """,
            (watermark,),
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        summary_row = None
        if rolling_summary_enabled():
            cursor = await db.execute(
                "SELECT summary, tokens, untrusted_influence FROM context_rolling_summary WHERE channel = ?",
                (str(channel or "unknown"),),
            )
            fetched = await cursor.fetchone()
            summary_row = dict(fetched) if fetched else None

    used = estimate_tokens(_HEADER) + estimate_tokens(_FOOTER)
    summary_block = ""
    summary_taint = False
    if summary_row and summary_row["summary"].strip():
        summary_tokens = int(summary_row["tokens"])
        if used + summary_tokens <= budget:
            summary_block = f"{_GIST_LABEL}\n{summary_row['summary'].strip()}"
            summary_taint = bool(summary_row["untrusted_influence"])
            used += summary_tokens

    included: list[dict] = []
    excluded_overbudget = 0
    for row in rows:  # newest first
        if used + int(row["tokens"]) <= budget:
            included.append(row)
            used += int(row["tokens"])
        else:
            excluded_overbudget += 1

    if not included and not summary_block:
        return AssembledContext(
            manifest={
                "included_turns": 0,
                "tokens_used": 0,
                "budget": budget,
                "route": route,
                "excluded_watermarked": excluded_watermarked,
                "excluded_overbudget": excluded_overbudget,
                "summary_included": False,
            }
        )

    untrusted = summary_taint or any(bool(r["untrusted_influence"]) for r in included)
    injection = any(bool(r["injection_detected"]) for r in included)
    lines = [_HEADER]
    if summary_block:
        lines.append(summary_block)
    for row in reversed(included):  # render oldest-first, newest last
        speaker = "Zainal" if row["role"] == "user" else "Maya"
        lines.append(f"[{_age_label(row['created_at'])}] {speaker}: {row['content']}")
    lines.append(_FOOTER)
    manifest = {
        "included_turns": len(included),
        "tokens_used": used,
        "budget": budget,
        "route": route,
        "excluded_watermarked": excluded_watermarked,
        "excluded_overbudget": excluded_overbudget,
        "summary_included": bool(summary_block),
        "untrusted_influence": untrusted,
        "injection_detected": injection,
    }
    return AssembledContext(
        text="\n".join(lines),
        untrusted_influence=untrusted,
        injection_detected=injection,
        manifest=manifest,
    )


async def _compact_overflow(db_path: str, *, channel: str) -> None:
    """Fold turns that no longer fit the channel's own budget into the
    rolling summary (Tier 2). Deterministic gist for now: an LLM summarizer
    can be injected later without changing the contract.

    Invariants: summaries are built from RAW TURN content only (C6); the
    summary inherits untrusted_influence from folded turns but never their
    raw injected text (C2) — folding stores a short content gist, which is
    why compaction is also decontamination.
    """
    budget = route_budget(resolve_route(channel))
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT COALESCE(MAX(last_turn_id), 0) AS wm FROM context_watermarks")
        watermark = int((await cursor.fetchone())["wm"])
        cursor = await db.execute(
            """
            SELECT id, role, content, tokens, untrusted_influence
            FROM context_turns
            WHERE folded = 0 AND id > ?
            ORDER BY id DESC
            """,
            (watermark,),
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        used = 0
        keep_ids: set[int] = set()
        overflow: list[dict] = []
        for row in rows:
            if used + int(row["tokens"]) <= budget:
                keep_ids.add(int(row["id"]))
                used += int(row["tokens"])
            else:
                overflow.append(row)
        if not overflow:
            return
        cursor = await db.execute(
            "SELECT summary, untrusted_influence FROM context_rolling_summary WHERE channel = ?",
            (channel,),
        )
        existing = await cursor.fetchone()
        prior_lines = str(existing["summary"]).splitlines() if existing else []
        prior_taint = bool(existing["untrusted_influence"]) if existing else False
        new_lines = []
        for row in reversed(overflow):  # oldest first into the gist
            speaker = "Zainal" if row["role"] == "user" else "Maya"
            gist = row["content"][:120].rstrip()
            new_lines.append(f"- {speaker}: {gist}")
        merged = [*prior_lines, *new_lines]
        cap = summary_cap()
        while merged and sum(estimate_tokens(line) for line in merged) > cap:
            merged.pop(0)  # oldest gist lines decay first — graceful forgetting
        summary_text = "\n".join(merged)
        taint = prior_taint or any(bool(r["untrusted_influence"]) for r in overflow)
        await db.execute(
            """
            INSERT INTO context_rolling_summary (channel, summary, tokens, untrusted_influence, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(channel) DO UPDATE SET
                summary = excluded.summary,
                tokens = excluded.tokens,
                untrusted_influence = excluded.untrusted_influence,
                updated_at = CURRENT_TIMESTAMP
            """,
            (channel, summary_text, estimate_tokens(summary_text), 1 if taint else 0),
        )
        await db.executemany(
            "UPDATE context_turns SET folded = 1 WHERE id = ?",
            [(int(r["id"]),) for r in overflow],
        )
        await db.commit()


def _age_label(created_at: str) -> str:
    try:
        stamp = datetime.fromisoformat(str(created_at)).replace(tzinfo=timezone.utc)
    except ValueError:
        return "earlier"
    minutes = max(0, int((datetime.now(timezone.utc) - stamp).total_seconds() // 60))
    if minutes < 2:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    if minutes < 60 * 24:
        return f"{minutes // 60}h ago"
    return f"{minutes // (60 * 24)}d ago"
