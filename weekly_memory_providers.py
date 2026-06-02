from __future__ import annotations

from config import get_env
from models import TheSenses, TheSteward
from weekly_memory_live import ProviderCall


def weekly_distiller_agent() -> ProviderCall | None:
    api_key = get_env("GOOGLE_API_KEY")
    if not api_key:
        return None
    model = get_env("GEMINI_FLASH_MODEL", "gemini-3.1-flash")
    senses = TheSenses(api_key, model=model)

    async def call(prompt: str) -> str:
        return await senses.chat([
            {"role": "system", "content": "You are Maya's weekly memory distiller. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ])

    return call


def weekly_reviewer_agent() -> ProviderCall | None:
    api_key = get_env("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    steward = TheSteward(api_key, get_env("CLAUDE_STEWARD_MODEL", "claude-opus-4-8"))

    async def call(prompt: str) -> str:
        return await steward.chat([
            {"role": "system", "content": "You are Maya's weekly memory steward. Return only approved JSON."},
            {"role": "user", "content": prompt},
        ])

    return call
