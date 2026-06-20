from __future__ import annotations

from maya_core.config import get_env
from maya_core.models import TheSenses, TheSteward
from maya_core.weekly_memory_live import ProviderCall


class WeeklyGeminiDistiller:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.usage_lane = "gemini_flash_text_calls"
        self.last_model = ""

    async def __call__(self, prompt: str) -> str:
        model = _weekly_gemini_model(prompt)
        self.last_model = model
        self.usage_lane = "gemini_premium_text_calls" if _premium_model(model) else "gemini_flash_text_calls"
        senses = TheSenses(self.api_key, model=model)
        return await senses.chat([
            {"role": "system", "content": "You are Maya's weekly memory distiller. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ])


class WeeklyClaudeReviewer:
    usage_lane = "claude_steward_calls"

    def __init__(self, api_key: str):
        self.steward = TheSteward(api_key, get_env("CLAUDE_STEWARD_MODEL", "claude-opus-4-8"))

    async def __call__(self, prompt: str) -> str:
        return await self.steward.chat([
            {"role": "system", "content": "You are Maya's weekly memory steward. Return only approved JSON."},
            {"role": "user", "content": prompt},
        ])


def weekly_distiller_agent() -> ProviderCall | None:
    api_key = get_env("GOOGLE_API_KEY")
    if not api_key:
        return None
    return WeeklyGeminiDistiller(api_key)


def weekly_reviewer_agent() -> ProviderCall | None:
    api_key = get_env("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return WeeklyClaudeReviewer(api_key)


def _weekly_gemini_model(prompt: str) -> str:
    if get_env("WEEKLY_MEMORY_FORCE_PREMIUM", "0") == "1":
        return get_env("GEMINI_PREMIUM_MODEL", "gemini-3.5-flash")
    lowered = prompt.lower()
    dense = len(prompt) > int(get_env("WEEKLY_MEMORY_PREMIUM_CHARS", "9000"))
    ambiguous = any(marker in lowered for marker in ("ambiguous", "conflicting", "contradiction", "unclear"))
    if dense or ambiguous:
        return get_env("GEMINI_PREMIUM_MODEL", "gemini-3.5-flash")
    return get_env("GEMINI_FLASH_MODEL", "gemini-3.1-flash")


def _premium_model(model: str) -> bool:
    return model == get_env("GEMINI_PREMIUM_MODEL", "gemini-3.5-flash")
