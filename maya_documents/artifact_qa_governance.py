from __future__ import annotations

from dataclasses import dataclass


BLOCKER = "blocker"
WARNING = "warning"
INFO = "info"

MECHANICAL = "mechanical"
OPEN_WORLD = "open_world"
SEMANTIC = "semantic"


@dataclass(frozen=True)
class QAIssue:
    rule_id: str
    severity: str
    rule_class: str
    message: str
    evidence: str = ""

    @property
    def blocks_delivery(self) -> bool:
        return self.severity == BLOCKER

    def demote_to_warning(self, evidence: str = "") -> "QAIssue":
        note = evidence or self.evidence
        return QAIssue(self.rule_id, WARNING, self.rule_class, self.message, note)


def blocker(rule_id: str, rule_class: str, message: str, evidence: str = "") -> QAIssue:
    return QAIssue(rule_id, BLOCKER, rule_class, message, evidence)


def warning(rule_id: str, rule_class: str, message: str, evidence: str = "") -> QAIssue:
    return QAIssue(rule_id, WARNING, rule_class, message, evidence)


def info(rule_id: str, rule_class: str, message: str, evidence: str = "") -> QAIssue:
    return QAIssue(rule_id, INFO, rule_class, message, evidence)


def legacy_blocker(message: str, rule_id: str = "legacy.local_validation") -> QAIssue:
    return blocker(rule_id, MECHANICAL, message)


def blocker_messages(issues: list[QAIssue]) -> list[str]:
    return [issue.message for issue in issues if issue.blocks_delivery]


def warning_messages(issues: list[QAIssue]) -> list[str]:
    return [issue.message for issue in issues if issue.severity == WARNING]


def blocker_issues(issues: list[QAIssue]) -> list[QAIssue]:
    return [issue for issue in issues if issue.blocks_delivery]


def open_world_or_semantic_blockers(issues: list[QAIssue]) -> list[QAIssue]:
    return [
        issue
        for issue in issues
        if issue.blocks_delivery and issue.rule_class in {OPEN_WORLD, SEMANTIC}
    ]
