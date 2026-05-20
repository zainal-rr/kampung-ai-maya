from __future__ import annotations

import re


PROVIDER_OR_AI_APP_NAMES = (
    "Anthropic",
    "ChatGPT",
    "Claude",
    "Codex",
    "Gemini",
    "Google",
    "Grok",
    "Kimi",
    "Moonshot",
    "Mistral",
    "OpenAI",
    "xAI",
)
EXTERNAL_DESTINATIONS = (
    "github",
    "email",
    "mail",
    "whatsapp",
    "slack",
    "discord",
    "webhook",
    "public",
    "external",
)
PERSONAL_DESTINATIONS = ("telegram", "imac", "local", "screen", "voice", "maya")


def redact_for_delivery(text: str, destination: str) -> str:
    if not requires_external_redaction(destination):
        return text
    return redact_provider_or_ai_app_names(text)


def requires_external_redaction(destination: str) -> bool:
    lowered = destination.lower().strip()
    if any(item in lowered for item in PERSONAL_DESTINATIONS):
        return False
    return any(item in lowered for item in EXTERNAL_DESTINATIONS)


def redact_provider_or_ai_app_names(text: str) -> str:
    names = sorted(PROVIDER_OR_AI_APP_NAMES, key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(name) for name in names) + r")\b", re.IGNORECASE)
    return pattern.sub("[REDACTED]", text)
