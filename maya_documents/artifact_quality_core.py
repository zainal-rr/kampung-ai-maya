from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from maya_documents.artifact_qa_governance import (
    QAIssue,
    blocker_issues,
    blocker_messages,
    legacy_blocker,
    warning_messages,
)


SKILL_IDS = {
    "docx": "word_artifact_quality",
    "xlsx": "excel_artifact_quality",
    "pptx": "powerpoint_artifact_quality",
    "html": "html_app_artifact_quality",
}

EXTRA_SKILL_IDS = {
    "pptx": ("powerpoint_design_taste",),
}


@dataclass
class ArtifactQualityResult:
    artifact_type: str
    path: str = ""
    passed: bool = True
    summary: str = ""
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    draft_model: str = ""
    review_model: str = ""
    validation_steps: list[str] = field(default_factory=list)
    repair_attempted: bool = False
    delivery_ready: bool = True
    issue_details: list[QAIssue] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.issue_details:
            self.issues = blocker_messages(self.issue_details)
            for message in warning_messages(self.issue_details):
                if message not in self.warnings:
                    self.warnings.append(message)
        elif self.issues:
            self.issue_details = [legacy_blocker(message) for message in self.issues]
        if self.issues:
            self.passed = False
            self.delivery_ready = False

    @property
    def blocker_issue_details(self) -> list[QAIssue]:
        return blocker_issues(self.issue_details)

    def merge(self, other: "ArtifactQualityResult") -> "ArtifactQualityResult":
        return ArtifactQualityResult(
            artifact_type=self.artifact_type,
            path=self.path or other.path,
            passed=self.passed and other.passed,
            summary=other.summary or self.summary,
            issues=[*self.issues, *other.issues],
            warnings=[*self.warnings, *other.warnings],
            draft_model=self.draft_model or other.draft_model,
            review_model=other.review_model or self.review_model,
            validation_steps=[*self.validation_steps, *other.validation_steps],
            repair_attempted=self.repair_attempted or other.repair_attempted,
            delivery_ready=self.delivery_ready and other.delivery_ready,
            issue_details=[*self.issue_details, *other.issue_details],
        )

    def short_issue_text(self) -> str:
        return "; ".join(self.issues[:4]) or self.summary or "quality review did not pass"


def artifact_skill_context(artifact_type: str) -> str:
    artifact_type = artifact_type.lower()
    skill_ids = [SKILL_IDS.get(artifact_type, ""), *EXTRA_SKILL_IDS.get(artifact_type, ())]
    skill_ids = [skill_id for skill_id in skill_ids if skill_id]
    if not skill_ids:
        return ""
    chunks = []
    for skill_id in skill_ids:
        text = _skill_text(skill_id)
        if text:
            chunks.append(text)
    return "\n\n".join(chunks)[:16000]


def _skill_text(skill_id: str) -> str:
    for folder in ("active", "proposed"):
        path = Path("maya_skills") / folder / f"{skill_id}.md"
        if path.exists():
            return path.read_text("utf-8")[:12000]
    return ""
