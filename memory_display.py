from __future__ import annotations


def preference_lines(items: list[dict[str, str]], query: str) -> list[str]:
    visible = [item for item in items if visible_preference(item)]
    if query:
        visible = [item for item in visible if query in f"{item['key']} {item['value']}".lower()]
    return [
        f"1) Preference: {item['value']} | source: {item['source']} | confidence: high"
        for item in visible[:5]
    ]


def visible_preference(item: dict[str, str]) -> bool:
    key = str(item.get("key", "")).lower()
    source = str(item.get("source", "")).lower()
    value = " ".join(str(item.get("value", "")).split())
    if "chat_id" in key:
        return False
    if source in {"workflow", "harness", "document", "screen", "vision", "skill", "travel"}:
        return False
    if value.startswith(("{", "[")):
        return False
    if value.startswith("1970-01-01"):
        return False
    if value.lower().startswith("visible:"):
        return False
    return not key.startswith((
        "maya_browser_workflow",
        "maya_pending_browser_click",
        "maya_harness_choices:",
        "maya_last_document_path",
        "maya_last_app_project_path",
        "maya_last_maker_project_path",
    ))


def canonical_lines(items: list[str]) -> list[str]:
    return [
        f"0) Canonical memory: {item} | source: canonical | confidence: high"
        for item in items[:5]
    ]


def lesson_lines(items: list[dict[str, str]]) -> list[str]:
    return [
        f"2) Lesson: {item['normalized_rule']} | source: {item['source']} | confidence: {item['confidence']}"
        for item in items[:5]
    ]


def summary_lines(items: list[dict[str, str | int]]) -> list[str]:
    lines = []
    for item in items[:2]:
        preview = " ".join(str(item["summary"]).split())[:120]
        lines.append(f"3) Context summary: {preview} | source: {item['source']} | confidence: medium")
    return lines
