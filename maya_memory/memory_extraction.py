from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from maya_memory.canonical_memory_text import is_temporary_memory, memory_tokens, subject_key_from_text, value_from_text
from permission_policy import contains_sensitive_info

ProviderCall = Callable[[str], Awaitable[str]]

ALLOWED_KINDS = {"preference", "lesson", "profile_fact", "project_fact", "style"}
_SCOPE_RE = re.compile(r"^(?:global|[a-z]+:[a-z0-9_\-]+|[a-z_]+)$")


@dataclass(frozen=True)
class ExtractionResult:
    subject: str
    value: str
    kind: str
    scope: str
    durable: bool
    sensitive: bool
    source: str  # "provider" or "deterministic"


def deterministic_extraction(text: str) -> ExtractionResult:
    """No-key fallback: the same regex pipeline canonical memory already uses.

    This is the contract: provider extraction may refine these fields, but the
    system must behave identically to today when no provider is configured.
    """
    subject = subject_key_from_text(text)
    return ExtractionResult(
        subject=subject,
        value=value_from_text(text),
        kind="preference",
        scope="global",
        durable=not is_temporary_memory(text, subject),
        sensitive=contains_sensitive_info(text),
        source="deterministic",
    )


async def extract_memory_fields(text: str, agent: ProviderCall | None = None) -> ExtractionResult:
    """Structured extraction with strict validation and deterministic fallback.

    Any provider failure, malformed JSON, schema violation, or hallucinated
    subject (no token overlap with the source text) falls back silently to the
    deterministic path. Provider output never widens what gets saved; the
    sensitive flag is OR-ed with the local check, never replaced by it.
    """
    fallback = deterministic_extraction(text)
    if agent is None:
        return fallback
    result, _reason = await _provider_extraction(text, agent, fallback)
    return result if result else fallback


async def extract_for_save(
    db_path: str,
    text: str,
    agent: ProviderCall | None,
    *,
    live: bool,
) -> ExtractionResult:
    """Extraction for the real save path, with a divergence audit trail.

    Shadow mode (live=False, agent set): the provider runs, the divergence
    between deterministic and provider parses is recorded, and the
    deterministic result is what gets saved. This makes extraction quality
    measurable before any behavior changes. Live mode saves the validated
    provider result and still records the divergence.
    """
    fallback = deterministic_extraction(text)
    if agent is None:
        return fallback
    result, reason = await _provider_extraction(text, agent, fallback)
    await _record_divergence(db_path, text, fallback, result, reason, live=live)
    return result if (live and result) else fallback


async def _provider_extraction(
    text: str,
    agent: ProviderCall,
    fallback: ExtractionResult,
) -> tuple[ExtractionResult | None, str]:
    try:
        raw = await agent(_extraction_prompt(text))
    except Exception as exc:
        return None, f"provider_error:{type(exc).__name__}"
    parsed = _parse_extraction(raw)
    if parsed is None:
        return None, "no_json"
    validated = _validate(parsed, text, fallback)
    if validated is None:
        return None, "validation_failed"
    return validated, "accepted"


async def _record_divergence(
    db_path: str,
    text: str,
    fallback: ExtractionResult,
    provider: ExtractionResult | None,
    reason: str,
    *,
    live: bool,
) -> None:
    from maya_memory.memory_audit import record_memory_audit_event

    provider_part = (
        f"prov={provider.subject}->{provider.value[:30]}" if provider else "prov=none"
    )
    # Per-dimension disagreement flags so the shadow review can measure
    # subject, value, sensitivity, and durability divergence separately.
    flags = "div=none"
    if provider:
        flags = (
            f"subj_div={int(provider.subject != fallback.subject)} "
            f"val_div={int(provider.value != fallback.value)} "
            f"sens_div={int(provider.sensitive != fallback.sensitive)} "
            f"dur_div={int(provider.durable != fallback.durable)}"
        )
    diverged = bool(
        provider and (provider.subject != fallback.subject or provider.value != fallback.value)
    )
    await record_memory_audit_event(
        db_path,
        event_type="extraction_divergence",
        subject_key=fallback.subject,
        status_after="diverged" if diverged else "agreed",
        source_channel="memory_extraction",
        source_ref=(
            f"det={fallback.subject}->{fallback.value[:30]} | {provider_part} | "
            f"outcome={reason} | mode={'live' if live else 'shadow'} | {flags}"
        ),
        content=text,
    )


def _extraction_prompt(text: str) -> str:
    return "\n".join((
        "Extract one memory record from the user's statement.",
        'Return JSON only: {"subject":"...","value":"...","kind":"preference|lesson|profile_fact|project_fact|style","scope":"global","durable":true,"sensitive":false}',
        "subject: short noun phrase naming what the fact is about, using words from the statement.",
        "value: the fact's value, verbatim where possible.",
        "durable: false for test/temporary/throwaway facts.",
        "sensitive: true for credentials, identity numbers, financial or medical details.",
        f"Statement: {text}",
    ))


def _parse_extraction(raw: str) -> dict[str, object] | None:
    match = re.search(r"\{[\s\S]*\}", str(raw).strip())
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _validate(data: dict[str, object], text: str, fallback: ExtractionResult) -> ExtractionResult | None:
    subject = " ".join(str(data.get("subject", "")).strip().split())
    value = " ".join(str(data.get("value", "")).strip().split())
    kind = str(data.get("kind", "")).strip().lower()
    scope = str(data.get("scope", "")).strip().lower() or "global"
    if not subject or not value:
        return None
    if kind not in ALLOWED_KINDS:
        return None
    if not _SCOPE_RE.match(scope):
        return None
    # Anti-hallucination: the extracted subject and value must overlap the
    # source text. A provider inventing fields fails closed to deterministic.
    source_tokens = memory_tokens(text)
    if not (memory_tokens(subject) & source_tokens):
        return None
    if not (memory_tokens(value) & source_tokens):
        return None
    durable = bool(data.get("durable", True)) and fallback.durable
    sensitive = bool(data.get("sensitive", False)) or fallback.sensitive
    subject_key = subject_key_from_text(subject) or fallback.subject
    return ExtractionResult(
        subject=subject_key,
        value=value[:1000],
        kind=kind,
        scope=scope[:60],
        durable=durable,
        sensitive=sensitive,
        source="provider",
    )


def live_extraction_enabled() -> bool:
    from maya_core.config import get_env

    return get_env("MEMORY_EXTRACTION_LIVE", "0") == "1"


def shadow_extraction_enabled() -> bool:
    from maya_core.config import get_env

    return get_env("MEMORY_EXTRACTION_SHADOW", "0") == "1"


def default_extraction_agent() -> ProviderCall | None:
    """Env-gated extraction agent. Off by default. Activates for either
    MEMORY_EXTRACTION_LIVE=1 (provider result is saved) or
    MEMORY_EXTRACTION_SHADOW=1 (provider runs, divergence is audited,
    deterministic result is saved). Both require GOOGLE_API_KEY. Heavy
    imports stay lazy so no-key environments never load provider SDKs.
    """
    from maya_core.config import get_env

    if not (live_extraction_enabled() or shadow_extraction_enabled()):
        return None
    api_key = get_env("GOOGLE_API_KEY")
    if not api_key:
        return None
    from maya_core.models import TheSenses

    model = get_env("GEMINI_FLASH_MODEL", "gemini-3.1-flash")

    async def _call(prompt: str) -> str:
        senses = TheSenses(api_key, model=model)
        return await senses.chat([
            {"role": "system", "content": "You extract structured memory records. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ])

    return _call
