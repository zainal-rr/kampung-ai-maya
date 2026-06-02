from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from canonical_memory import is_temporary_memory, subject_key_from_text, upsert_canonical_memory
from cost_tracker import record_usage
from permission_policy import contains_sensitive_info

ProviderCall = Callable[[str], Awaitable[str]]


@dataclass(frozen=True)
class LiveWeeklyMemoryResult:
    saved: int = 0
    rejected: int = 0
    provider_calls: int = 0
    memory_ids: tuple[str, ...] = ()
    confirmation_needed: tuple[str, ...] = ()


async def live_weekly_canonical_distillation(
    db_path: str,
    *,
    run_key: str,
    data: dict[str, list[dict[str, str]]],
    distiller_agent: ProviderCall,
    reviewer_agent: ProviderCall | None = None,
) -> LiveWeeklyMemoryResult:
    prompt = _distiller_prompt(run_key, data)
    raw = await distiller_agent(prompt)
    provider_calls = 1
    facts = _parse_facts(raw)
    confirmation_needed: tuple[str, ...] = ()
    review_rejected = 0
    if reviewer_agent:
        reviewed = await reviewer_agent(_review_prompt(run_key, facts))
        provider_calls += 1
        review = _parse_review(reviewed, proposed_count=len(facts))
        facts = review["facts"]
        review_rejected = int(review["rejected"])
        confirmation_needed = tuple(review["confirmation_needed"])
    saved = 0
    rejected = review_rejected
    memory_ids = []
    for fact in facts:
        content = _clean(fact.get("content", ""))
        kind = _clean(fact.get("kind", "")) or "weekly_fact"
        scope = _clean(fact.get("scope", "")) or "global"
        if not _stable_fact(content, kind=kind, scope=scope):
            rejected += 1
            continue
        memory_id = await upsert_canonical_memory(
            db_path,
            raw_text=content,
            content=content,
            kind=kind,
            scope=scope,
            source_channel="weekly_memory",
            confidence=_clean(fact.get("confidence", "")) or "medium",
            source_ref=f"weekly:{run_key}",
        )
        memory_ids.append(memory_id)
        saved += 1
    if provider_calls:
        await record_usage(db_path, "gemini_premium_text_calls", 1, "weekly memory distillation")
    if reviewer_agent:
        await record_usage(db_path, "claude_steward_calls", 1, "weekly memory review")
    return LiveWeeklyMemoryResult(
        saved=saved,
        rejected=rejected,
        provider_calls=provider_calls,
        memory_ids=tuple(memory_ids),
        confirmation_needed=confirmation_needed,
    )


def _distiller_prompt(run_key: str, data: dict[str, list[dict[str, str]]]) -> str:
    return "\n".join((
        "Extract only durable, stable memories for Maya.",
        "Return JSON only: {\"facts\":[{\"content\":\"...\",\"kind\":\"preference|lesson|project_fact|profile_fact\",\"scope\":\"global\",\"confidence\":\"high|medium\"}]}",
        "Do not include test memories, temporary project chatter, sensitive data, guesses, or forgotten facts.",
        f"Week: {run_key}",
        "Data:",
        json.dumps(data, ensure_ascii=True)[:12000],
    ))


def _review_prompt(run_key: str, facts: list[dict[str, str]]) -> str:
    return "\n".join((
        "Review these proposed weekly memories for safety and durability.",
        "Return JSON only: {\"facts\":[approved facts],\"rejected\":[{\"content\":\"...\",\"reason\":\"...\"}],\"confirmation_needed\":[{\"content\":\"...\",\"reason\":\"...\"}]}",
        "Reject overreach, false assumptions, vague preferences, unsafe memory, test facts, sensitive information, and low-value transient details.",
        "Reject generated-artifact observations and trip-plan details as global memory unless Zainal explicitly asked Maya to remember them.",
        "Use confirmation_needed when the fact may be useful but Zainal should confirm it before Maya saves it.",
        f"Week: {run_key}",
        json.dumps({"facts": facts}, ensure_ascii=True),
    ))


def _parse_facts(text: str) -> list[dict[str, str]]:
    blob = _json_blob(text)
    if not blob:
        return []
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return []
    facts = data.get("facts", data) if isinstance(data, dict) else data
    if not isinstance(facts, list):
        return []
    return [item for item in facts if isinstance(item, dict)]


def _parse_review(text: str, *, proposed_count: int) -> dict[str, object]:
    blob = _json_blob(text)
    if not blob:
        return {"facts": [], "rejected": proposed_count, "confirmation_needed": ()}
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return {"facts": [], "rejected": proposed_count, "confirmation_needed": ()}
    if not isinstance(data, dict):
        approved = [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
        return {"facts": approved, "rejected": max(0, proposed_count - len(approved)), "confirmation_needed": ()}
    approved = data.get("facts") or data.get("approved") or []
    if not isinstance(approved, list):
        approved = []
    approved = [item for item in approved if isinstance(item, dict)]
    rejected = data.get("rejected") or []
    rejected_count = len(rejected) if isinstance(rejected, list) else max(0, proposed_count - len(approved))
    confirm = data.get("confirmation_needed") or []
    confirmation_needed = tuple(_clean(item.get("content", "")) for item in confirm if isinstance(item, dict) and item.get("content"))
    return {"facts": approved, "rejected": rejected_count, "confirmation_needed": confirmation_needed}


def _json_blob(text: str) -> str:
    match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text.strip())
    return match.group(0) if match else ""


def _stable_fact(content: str, *, kind: str = "", scope: str = "") -> bool:
    if not content or contains_sensitive_info(content):
        return False
    subject_key = subject_key_from_text(content)
    if is_temporary_memory(content, subject_key):
        return False
    lowered = content.lower()
    if kind == "project_fact" and scope in {"", "global"}:
        return False
    unstable_markers = (
        "maya is planning",
        "maya's travel strategy",
        "maya uses a dedicated",
        "maya prefers",
        "this week maya",
        "latest document",
        "last document",
        "generated asset",
        "gemini asset",
        "slide deck",
        "presentation deck",
        "budget tracker",
        "food trip",
        "48-hour",
        "one traveler",
        "krw",
    )
    if any(marker in lowered for marker in unstable_markers):
        return False
    return len(content.split()) >= 4


def _clean(value: str) -> str:
    return " ".join(str(value).strip().split())[:1000]
