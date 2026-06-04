from __future__ import annotations

import re


def should_use_artisan_path(text: str) -> bool:
    lowered = text.lower().strip()
    if lowered.startswith((
        "remember ", "remember that ", "what is my ", "what's my ",
        "what was my ", "what are my ", "do you remember ",
    )):
        return False
    strong = ("debug", "fix bug", "fix this", "implement", "refactor", "patch", "write code", "generate code", "run tests", "stack trace")
    if _conversational_test(lowered) and not any(marker in lowered for marker in strong):
        return False
    if _code_snippet_request(lowered):
        return False
    targets = (
        "app", "web app", "website", "frontend", "dashboard", "vite", "blender",
        "3d print", "3d-print", "stl", "3mf", "printable", "phone stand",
    )
    code_targets = ("api", "bash", "class", "code", "css", "database", "error", "function", "html", "javascript", "program", "python", "react", "script", "sql", "typescript", "ui")
    verbs = ("add", "build", "change", "code", "create", "debug", "fix", "implement", "make", "modify", "patch", "refactor", "remove", "repair", "run", "update", "write")
    has_verb = any(lowered.startswith(f"{verb} ") or (verb != "code" and f" {verb} " in f" {lowered} ") for verb in verbs)
    has_target = any(_has_word_or_phrase(lowered, marker) for marker in targets)
    has_code = any(_has_word_or_phrase(lowered, marker) for marker in code_targets)
    return any(marker in lowered for marker in strong) or (has_verb and (has_target or has_code))


def _conversational_test(text: str) -> bool:
    return any(marker in text for marker in (
        "testing maya", "test maya", "keep testing", "what should i focus on",
        "what should we test", "what tests should",
    ))


def _has_word_or_phrase(text: str, marker: str) -> bool:
    words = marker.strip().split()
    if not words:
        return False
    pattern = r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b"
    return re.search(pattern, text) is not None


def _code_snippet_request(text: str) -> bool:
    return text.startswith((
        "write a simple sql query", "write simple sql query", "give me a sql query",
        "show me a sql query", "write a sql query", "write an sql query",
    ))
