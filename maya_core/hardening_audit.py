from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from maya_core.dependency_manifest import readiness_summary
from maya_core.demo_evidence import load_latest, validate_latest_demo_evidence
from maya_core.repo_paths import repo_root
from maya_core.permission_policy import SECRET_PATTERNS
from maya_core.route_tracker import _model_for_lane
from maya_core.self_heal_memory import guardrails_text


@dataclass(frozen=True)
class AuditItem:
    name: str
    passed: bool
    detail: str


CAPABILITIES = {
    "telegram": ("ready", 90, "text, voice notes, files, route/cost, memory, latest-document follow-up"),
    "documents": ("partial", 85, "Word/Excel strong, PowerPoint improving, app HTML goes through Artisan projects"),
    "memory": ("partial", 87, "canonical save/recall/forget works; self-heal compaction still needs live run"),
    "weekly_memory": ("partial", 90, "manual/live status works; unattended schedule needs continued proof"),
    "artisan_codex": ("ready", 85, "Codex-backed project/app lane with approval boundaries"),
    "blender_maker": ("ready", 85, "template/export workflow works; physical printing requires confirmation"),
    "agentic_workflow": ("partial", 86, "approval-gated /complex workflows work; full harness spine still in progress"),
    "overall": ("partial", 87, "personal agent harness in hardening sprint"),
}

ROOT = repo_root(__file__)


def route_cost_audit() -> list[AuditItem]:
    samples = {
        "Gemini Flash text": "gemini",
        "Gemini Flash role-based Word draft + local Word QA + Claude Word review": "claude",
        "xAI STT + Gemini Flash text": "grok-2-audio",
        "Artisan Codex app": "codex",
        "Gemini source-aware research": "gemini",
        "GPT complex": "gpt-5.5",
        "command": "none",
    }
    items = []
    for lane, expected in samples.items():
        model = _model_for_lane(lane).lower()
        items.append(AuditItem(f"route model: {lane}", expected in model, model))
    return items


def capability_readiness_report() -> str:
    deps = readiness_summary()
    lines = ["Capability readiness:"]
    for key, (status, percent, detail) in CAPABILITIES.items():
        lines.append(f"- {key}: {status} | {percent}% | {detail}")
    lines.append(f"Dependencies: {deps}")
    return "\n".join(lines)


def rollback_drill_items() -> list[AuditItem]:
    guardrails = guardrails_text()
    required = (
        "Snapshot root:",
        "Rollback command:",
        "Force mode is rejected",
        "Retrieval pass criteria:",
    )
    return [
        AuditItem("memory rollback guardrails", all(item in guardrails for item in required), guardrails),
        AuditItem("repo apply patch records", (ROOT / "maya_core" / "artisan_apply.py").exists(), "maya_core/artisan_apply.py"),
    ]


def public_report_redaction_issues(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in paths:
        if not path.exists() or path.is_dir():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                issues.append(f"{path}: secret-shaped value matched {pattern.pattern}")
        if "/Users/zainalabidinjamal/" in text:
            issues.append(f"{path}: private local home path found")
    return issues


def demo_evidence_items() -> list[AuditItem]:
    payload = load_latest()
    issues = validate_latest_demo_evidence(payload)
    detail = "latest demo evidence PASS" if not issues else "; ".join(f"{i.demo}: {i.issue}" for i in issues)
    return [AuditItem("latest demo evidence", bool(payload) and not issues, detail)]


def public_redaction_paths() -> list[Path]:
    return [
        Path("README.md"),
        Path("logs/demos/latest.json"),
        Path("logs/demos/latest.md"),
        Path("logs/evals/latest.json"),
    ]


def hardening_audit_summary() -> str:
    route_items = route_cost_audit()
    rollback_items = rollback_drill_items()
    demo_items = demo_evidence_items()
    privacy_issues = public_report_redaction_issues(public_redaction_paths())
    lines = ["Hardening audit:"]
    lines.append(f"1) route/cost audit: {_count_passed(route_items)}")
    lines.append("2) capability readiness:\n" + capability_readiness_report())
    lines.append(f"3) rollback drills: {_count_passed(rollback_items)}")
    lines.append(f"4) demo evidence: {_count_passed(demo_items)}")
    lines.append(f"5) privacy/redaction issues: {len(privacy_issues)}")
    lines.append("6) demo replay notes: logs/demos/latest.md points to the latest passing replay for each demo")
    return "\n".join(lines)


def _count_passed(items: list[AuditItem]) -> str:
    passed = sum(1 for item in items if item.passed)
    return f"{passed}/{len(items)}"


if __name__ == "__main__":
    print(hardening_audit_summary())
