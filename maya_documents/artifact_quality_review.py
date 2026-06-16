from __future__ import annotations

import asyncio
import os
from pathlib import Path

from maya_documents.artifact_quality_core import ArtifactQualityResult, artifact_skill_context
from maya_documents.artifact_qa_governance import (
    SEMANTIC,
    QAIssue,
    blocker,
    open_world_or_semantic_blockers,
)
from maya_documents.artifact_quality_extractors import clip_text
from maya_documents.artifact_review_store import record_artifact_review, record_qa_disagreement
from maya_core.cost_tracker import record_usage
from maya_core.models import TheSenses, TheSteward
from provider_capabilities import CAPABILITIES


async def resolve_quality_disagreement(
    db_path: str,
    *,
    artifact_type: str,
    topic: str,
    path: Path,
    local_qa: ArtifactQualityResult,
    review_qa: ArtifactQualityResult,
    extracted: str,
    attempt_number: int = 1,
) -> ArtifactQualityResult:
    """Demote validator false positives only when semantic review and arbiter agree."""
    disputed = open_world_or_semantic_blockers(local_qa.issue_details)
    if not disputed or not review_qa.passed:
        return local_qa
    adjusted = local_qa
    for issue in disputed:
        verdict, evidence = await _arbitrate_validator_claim(db_path, artifact_type, topic, issue, extracted)
        if verdict == "validator_wrong":
            adjusted = _demote_issue(adjusted, issue, evidence)
            await record_qa_disagreement(
                db_path,
                artifact_type=artifact_type,
                topic=topic,
                artifact_path=str(path),
                rule_id=issue.rule_id,
                rule_class=issue.rule_class,
                severity=issue.severity,
                validator_verdict="fail",
                reviewer_verdict="pass",
                arbiter_verdict="validator_wrong",
                attempt_number=attempt_number,
                final_action="delivered_cleanly_with_audit",
                evidence=evidence,
            )
        else:
            await record_qa_disagreement(
                db_path,
                artifact_type=artifact_type,
                topic=topic,
                artifact_path=str(path),
                rule_id=issue.rule_id,
                rule_class=issue.rule_class,
                severity=issue.severity,
                validator_verdict="fail",
                reviewer_verdict="pass",
                arbiter_verdict=verdict,
                attempt_number=attempt_number,
                final_action="validator_upheld",
                evidence=evidence,
            )
    return adjusted


async def _arbitrate_validator_claim(
    db_path: str,
    artifact_type: str,
    topic: str,
    issue: QAIssue,
    extracted: str,
) -> tuple[str, str]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "arbiter_unavailable", "Gemini arbitration skipped: GOOGLE_API_KEY missing."
    model = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")
    senses = TheSenses(api_key, model)
    prompt = (
        "You are Maya's targeted QA arbiter. Do not judge general quality. "
        "Judge only this validator claim against the provided artifact text.\n\n"
        f"Artifact type: {artifact_type}\n"
        f"User topic: {topic}\n"
        f"Validator rule: {issue.rule_id}\n"
        f"Validator class: {issue.rule_class}\n"
        f"Validator claim: {issue.message}\n"
        f"Validator evidence: {issue.evidence or '(none)'}\n\n"
        "Answer exactly one label first:\n"
        "VALIDATOR_CORRECT - the validator claim is true enough to block or repair.\n"
        "VALIDATOR_WRONG - the validator claim is false or too ambiguous to block.\n"
        "Then add one short reason.\n\n"
        f"Artifact text:\n{extracted[:12000]}"
    )
    try:
        timeout = float(os.getenv("GEMINI_QA_ARBITER_TIMEOUT_SECONDS", "25"))
    except ValueError:
        timeout = 25
    try:
        reply = await asyncio.wait_for(
            senses.chat([
                {"role": "system", "content": "Return VALIDATOR_CORRECT or VALIDATOR_WRONG first."},
                {"role": "user", "content": prompt},
            ]),
            timeout=max(8, timeout),
        )
    except Exception as exc:
        return "arbiter_unavailable", f"Gemini arbitration failed: {type(exc).__name__}"
    await record_usage(db_path, "gemini_flash_text_calls", 1, f"{artifact_type} QA arbiter")
    first = reply.strip().splitlines()[0].strip().upper() if reply.strip() else ""
    if first.startswith("VALIDATOR_WRONG"):
        return "validator_wrong", clip_text(reply, 400)
    if first.startswith("VALIDATOR_CORRECT"):
        return "validator_correct", clip_text(reply, 400)
    lowered = reply.lower()
    if "validator_wrong" in lowered or "validator is wrong" in lowered:
        return "validator_wrong", clip_text(reply, 400)
    return "validator_correct", clip_text(reply or "Gemini did not return a clear label.", 400)


def _demote_issue(result: ArtifactQualityResult, target: QAIssue, evidence: str) -> ArtifactQualityResult:
    details = [
        issue.demote_to_warning(evidence) if issue == target else issue
        for issue in result.issue_details
    ]
    return ArtifactQualityResult(
        artifact_type=result.artifact_type,
        path=result.path,
        passed=True,
        summary=result.summary,
        warnings=[*result.warnings],
        draft_model=result.draft_model,
        review_model=result.review_model,
        validation_steps=[*result.validation_steps, "gemini targeted QA arbitration"],
        repair_attempted=result.repair_attempted,
        delivery_ready=True,
        issue_details=details,
    )


async def review_artifact_quality(
    db_path: str,
    artifact_type: str,
    topic: str,
    extracted: str,
) -> ArtifactQualityResult:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return ArtifactQualityResult(artifact_type, passed=True, summary="Claude review skipped: no Anthropic key.", warnings=["Claude review skipped"])
    model = os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model)
    steward = TheSteward(os.getenv("ANTHROPIC_API_KEY", "dummy"), model)
    skill_context = artifact_skill_context(artifact_type)
    try:
        timeout = float(os.getenv("CLAUDE_ARTIFACT_REVIEW_TIMEOUT_SECONDS", "35"))
    except ValueError:
        timeout = 35
    prompt = _review_prompt(artifact_type, topic, extracted, skill_context)
    try:
        response = await asyncio.wait_for(
            steward.chat([
                {"role": "system", "content": "You are Maya's artifact quality reviewer. Return PASS: or REJECT: with concise reasons."},
                {"role": "user", "content": prompt},
            ]),
            timeout=max(10, timeout),
        )
    except Exception as exc:
        return ArtifactQualityResult(
            artifact_type,
            passed=True,
            summary="Claude review unavailable; local validation is the delivery gate for this artifact.",
            warnings=[f"Claude review failed open: {type(exc).__name__}"],
        )
    await record_usage(db_path, "claude_steward_calls", 1, f"{artifact_type} artifact review")
    first = response.strip().splitlines()[0] if response.strip() else ""
    rejected = first.lower().startswith("reject") or response.lower().startswith("reject")
    await record_artifact_review(db_path, artifact_type, topic, model, not rejected, response)
    return ArtifactQualityResult(
        artifact_type,
        passed=not rejected,
        summary=clip_text(response, 220),
        issues=[clip_text(response, 300)] if rejected else [],
        issue_details=[blocker("review.semantic_reject", SEMANTIC, clip_text(response, 300))] if rejected else [],
        review_model=model,
        validation_steps=["claude artifact skill review"],
        delivery_ready=not rejected,
    )


def _review_prompt(artifact_type: str, topic: str, extracted: str, skill_context: str) -> str:
    return (
        f"Artifact type: {artifact_type}\n"
        f"User topic: {topic}\n\n"
        f"Artifact quality skill:\n{skill_context or 'No skill file found.'}\n\n"
        "Review the artifact against the skill. PASS if it is useful and deliverable. "
        "REJECT only for concrete quality failures that should stop Maya from calling it final. "
        "Do not claim visual styling, rendered layout, sheet count, or chart quality unless those facts are present in the extracted artifact content. "
        "For spreadsheets, distinguish worksheets from sections inside one worksheet.\n\n"
        f"Extracted artifact content:\n{extracted[:16000]}"
    )
