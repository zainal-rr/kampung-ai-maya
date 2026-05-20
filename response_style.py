from __future__ import annotations

import re

from storage import list_preferences


async def apply_reply_preferences(db_path: str, text: str) -> str:
    text = _normalize_outline_markers(text)
    preferences = await list_preferences(db_path, limit=20)
    values = [item["value"] for item in preferences]
    if _wants_no_dash(values):
        text = _strip_dashes(text)
    if _wants_no_exclamation(values):
        text = _strip_exclamations(text)
    return text


def format_grouped_answers(answers: list[str]) -> str:
    blocks = []
    for idx, answer in enumerate(answers, start=1):
        lines = [line.strip() for line in answer.splitlines() if line.strip()]
        if not lines:
            continue
        lines[0] = _strip_number_marker(lines[0])
        blocks.append(f"{idx}) {lines[0]}")
        blocks.extend(f"   {line}" for line in lines[1:])
    return "\n".join(blocks)


def split_telegram_segments(text: str) -> list[str]:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(raw_lines) <= 1:
        return [text.strip()]
    if _has_outline_example(raw_lines):
        return [text.strip()]
    if not all(_numbered_request(line) for line in raw_lines):
        return [text.strip()]
    segments = []
    for line in raw_lines:
        cleaned = _strip_number_marker(line)
        if cleaned:
            segments.append(cleaned)
    return segments or [text.strip()]


def _wants_no_dash(preferences: list[str]) -> bool:
    for value in preferences:
        lowered = value.lower()
        if "dash" in lowered or "hyphen" in lowered:
            return True
    return False


def _wants_no_exclamation(preferences: list[str]) -> bool:
    for value in preferences:
        lowered = value.lower()
        if "!" in value or "exclamation" in lowered or "tanda seru" in lowered:
            return True
    return False


def _normalize_outline_markers(text: str) -> str:
    lines = []
    for line in text.splitlines():
        cleaned = re.sub(r"^(\d+)\.\s+", r"\1) ", line)
        cleaned = re.sub(r"^([a-zA-Z])\.\s+", r"\1) ", cleaned)
        lines.append(cleaned)
    return "\n".join(lines)


def _strip_dashes(text: str) -> str:
    lines = []
    for line in text.splitlines():
        cleaned = re.sub(r"^\s*-\s*", "", line)
        cleaned = re.sub(r"[-–—]", " ", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        lines.append(cleaned)
    output = "\n".join(line for line in lines if line)
    output = re.sub(r"\s+([,.;:!?])", r"\1", output)
    return output.strip()


def _strip_exclamations(text: str) -> str:
    text = re.sub(r"!+", ".", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+\.", ".", text)
    return text.strip()


def _has_outline_example(lines: list[str]) -> bool:
    return any(re.match(r"^(?:\d+[\).]|[a-zA-Z][\).])$", line) for line in lines)


def _numbered_request(line: str) -> bool:
    match = re.match(r"^\s*\d+[\).]\s+(.+)$", line)
    if not match:
        return False
    return _looks_like_request(match.group(1).strip())


def _looks_like_request(text: str) -> bool:
    lowered = text.lower().strip()
    if lowered.endswith("?"):
        return True
    starters = (
        "what", "why", "when", "where", "who", "how", "can", "could",
        "should", "would", "do", "does", "did", "is", "are", "am",
        "will", "have", "has", "tell", "show", "list", "check",
        "explain", "summarize", "remember", "delete", "remove", "add",
        "open", "close", "set", "create", "make", "fix", "update",
        "find", "search", "give", "draft", "send", "save", "remind",
        "book",
    )
    return lowered.startswith(starters)


def _strip_number_marker(line: str) -> str:
    return re.sub(r"^\s*\d+[\).]\s*", "", line).strip()
