from __future__ import annotations

import re


def strip_wake_prefix(text: str) -> str:
    return re.sub(r"^\s*(?:hey|hi|hello)?\s*maya\s*[,:\-]?\s*", "", text.strip(), flags=re.IGNORECASE)


def extract_user_text(content: str) -> str:
    marker = "[user]\n"
    index = content.lower().rfind(marker)
    if index >= 0:
        return content[index + len(marker):].strip()
    return content.strip()


def clean_model_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\[channel:[^\]]+\]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"^\[(?:artisan|sight|pulse|library context)\]:?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^Maya:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def normalize_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    cleaned = []
    for item in history:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role == "user":
            content = extract_user_text(content)
        content = clean_model_text(content)
        if content:
            cleaned.append({"role": role, "content": content})
    return cleaned
