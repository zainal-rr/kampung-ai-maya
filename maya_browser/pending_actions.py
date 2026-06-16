from __future__ import annotations

import json
import re
import time

from maya_core.storage import delete_preference, get_preference, upsert_preference
from maya_browser.query_guard import browser_query_is_incomplete, browser_query_topic


PENDING_BROWSER_ACTION_KEY = "maya_browser_pending_action"
PENDING_BROWSER_CLARIFICATION_KEY = "maya_browser_pending_clarification"
PENDING_BROWSER_ACTION_TTL_SECONDS = 600


def looks_like_pending_browser_confirmation(text: str) -> bool:
    lowered = " ".join(text.lower().strip().split())
    if not lowered:
        return False
    if any(marker in lowered for marker in ("can you hear me", "what are you doing", "status", "what happened")):
        return False
    direct = {
        "yes",
        "yes please",
        "yeah",
        "yep",
        "please",
        "do it",
        "open it",
        "open that",
        "that one",
        "this one",
        "open that one",
        "open this one",
        "go ahead",
    }
    if lowered in direct:
        return True
    return bool(re.search(r"\b(open|click|choose|select)\s+(it|that|this|that one|this one)\b", lowered))


async def remember_pending_browser_action(db_path: str, spec, query: str, options: list[str]) -> None:
    if not options:
        await clear_pending_browser_action(db_path)
        return
    title = " ".join(str(options[0]).split()).strip()
    if not title:
        await clear_pending_browser_action(db_path)
        return
    payload = {
        "created_at": time.time(),
        "provider": str(getattr(spec, "workflow_prefix", "") or ""),
        "skill_id": str(getattr(spec, "skill_id", "") or ""),
        "query": query,
        "rank": 1,
        "title": title[:240],
    }
    await upsert_preference(db_path, PENDING_BROWSER_ACTION_KEY, json.dumps(payload, ensure_ascii=True), source="skill")


async def clear_pending_browser_action(db_path: str) -> None:
    await delete_preference(db_path, PENDING_BROWSER_ACTION_KEY)


async def pending_browser_action(db_path: str) -> dict:
    raw = await get_preference(db_path, PENDING_BROWSER_ACTION_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        age = time.time() - float(data.get("created_at", 0))
    except (TypeError, ValueError, json.JSONDecodeError):
        await clear_pending_browser_action(db_path)
        return {}
    if age > PENDING_BROWSER_ACTION_TTL_SECONDS:
        await clear_pending_browser_action(db_path)
        return {}
    return data


async def pending_browser_request_for_confirmation(db_path: str, text: str) -> tuple[str, str]:
    if not looks_like_pending_browser_confirmation(text):
        return "", ""
    action = await pending_browser_action(db_path)
    if not action:
        return "", ""
    provider = str(action.get("provider") or "")
    if provider == "youtube":
        return "open first video", "browser_youtube"
    if provider == "reddit":
        return "open first thread", "browser_reddit"
    return "open first result", "browser"


async def remember_pending_browser_clarification(db_path: str, provider: str) -> None:
    payload = {"created_at": time.time(), "provider": provider}
    await upsert_preference(db_path, PENDING_BROWSER_CLARIFICATION_KEY, json.dumps(payload), source="skill")


async def clear_pending_browser_clarification(db_path: str) -> None:
    await delete_preference(db_path, PENDING_BROWSER_CLARIFICATION_KEY)


async def pending_browser_request_for_clarification(db_path: str, text: str) -> tuple[str, str]:
    topic = browser_query_topic(text)
    if _looks_like_status_or_dismissal(topic) or browser_query_is_incomplete(topic):
        return "", ""
    raw = await get_preference(db_path, PENDING_BROWSER_CLARIFICATION_KEY)
    if not raw:
        return "", ""
    try:
        data = json.loads(raw)
        age = time.time() - float(data.get("created_at", 0))
    except (TypeError, ValueError, json.JSONDecodeError):
        await clear_pending_browser_clarification(db_path)
        return "", ""
    if age > PENDING_BROWSER_ACTION_TTL_SECONDS:
        await clear_pending_browser_clarification(db_path)
        return "", ""
    provider = str(data.get("provider") or "")
    await clear_pending_browser_clarification(db_path)
    if provider == "google_images":
        return f"google images {topic}", "browser_images"
    if provider == "google_search":
        return f"search {topic}", "browser"
    return "", ""


async def pending_browser_voice_request(db_path: str, text: str) -> tuple[str, str]:
    request, kind = await pending_browser_request_for_confirmation(db_path, text)
    if request:
        return request, kind
    return await pending_browser_request_for_clarification(db_path, text)


def _looks_like_status_or_dismissal(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    if lowered in {"no", "no thanks", "that's okay", "that is okay", "never mind", "nevermind"}:
        return True
    return any(marker in lowered for marker in ("can you hear me", "what are you", "what are you searching", "status", "what happened"))
