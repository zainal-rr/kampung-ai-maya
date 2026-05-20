from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapability:
    lane: str
    model_env: str
    default_model: str
    owner: str
    allowed_tools: tuple[str, ...]
    disallowed_tools: tuple[str, ...]
    cost_tier: str
    triggers: tuple[str, ...]
    safety_boundary: str
    can_write_memory: bool
    can_propose_skills: bool
    execution: str


CAPABILITIES = {
    "sight": ProviderCapability(
        "Gemini Flash / Pro",
        "GEMINI_FLASH_MODEL",
        "gemini-3-flash-preview",
        "The Sight",
        ("telegram_text", "research", "screen", "vision", "omi_distillation", "weekly_memory_first_pass"),
        ("payments", "deletes", "deploys", "private_exposure"),
        "low",
        ("research", "summarize", "screen", "camera", "telegram"),
        "Facts and summaries only become durable memory through Maya's memory gates.",
        True,
        True,
        "tool-assisted through Maya",
    ),
    "mind": ProviderCapability(
        "GPT 5.5 xhigh",
        "OPENAI_COMPLEX_MODEL",
        "gpt-5.5",
        "The Mind",
        ("complex_judgement", "architecture", "strategy", "identity_sensitive_memory"),
        ("normal_telegram", "coding_implementation", "voice_presence"),
        "high",
        ("/complex", "complex task", "deep judgement", "important judgement"),
        "Only explicit complex routes can call this lane.",
        True,
        True,
        "judgement only",
    ),
    "steward": ProviderCapability(
        "Claude Sonnet 4.6",
        "CLAUDE_STEWARD_MODEL",
        "claude-sonnet-4-6",
        "The Steward",
        ("review", "critique", "workflow_supervision", "safety_review", "skill_review", "self_heal_review"),
        ("direct_deploy", "direct_restart", "unapproved_skill_install", "private_exposure"),
        "medium",
        ("review", "critique", "audit", "check this plan", "hidden risk", "before acting"),
        "Review and recommend. Maya's gates still own execution.",
        False,
        True,
        "review only",
    ),
    "artisan": ProviderCapability(
        "Kimi K2.6",
        "KIMI_MODEL",
        "kimi-k2.6",
        "The Artisan",
        ("coding", "repo_maintenance", "patch_planning", "technical_implementation"),
        ("payments", "private_exposure", "unapproved_deploy", "identity_rewrite"),
        "medium",
        ("code", "debug", "python", "repo", "test", "implementation"),
        "Code changes, deploys, restarts, and destructive edits require Maya approval gates.",
        False,
        True,
        "tool-assisted through Maya",
    ),
    "pulse": ProviderCapability(
        "Grok + Ara",
        "XAI_TEXT_MODEL",
        "grok-beta",
        "The Pulse",
        ("voice_presence", "news", "weather", "market", "currency", "current_worldview"),
        ("normal_research_notes", "coding_implementation", "memory_shaping"),
        "medium",
        ("hey maya", "latest news", "weather", "market", "currency", "myr", "usd"),
        "Paid voice only starts after local wake and closes after silence.",
        False,
        False,
        "voice/text through Maya",
    ),
}


def capability_context() -> str:
    lines = ["Provider capability registry:"]
    for key, item in CAPABILITIES.items():
        lines.append(
            f"- {item.owner} ({key}): {item.lane}; tools={', '.join(item.allowed_tools)}; "
            f"boundary={item.safety_boundary}"
        )
    return "\n".join(lines)


def review_triggers() -> tuple[str, ...]:
    return CAPABILITIES["steward"].triggers
