from __future__ import annotations

import re


def proposal_prompt_notes(topic: str) -> tuple[str, ...]:
    if "proposal" not in topic.lower():
        return ()
    return (
        "If the proposal includes Out of Scope, provide concrete excluded items.",
        "If the proposal names a numbered or tiered framework, complete every tier or step named.",
    )


def proposal_consistency_issues(paragraphs: list[str]) -> list[str]:
    issues: list[str] = []
    lowered = [_normalize(item) for item in paragraphs]
    for index, text in enumerate(lowered):
        if text == "out of scope" and _next_is_heading_or_empty(lowered, index):
            issues.append("proposal has empty Out of Scope section")
    joined = " ".join(lowered)
    if "three tier" in joined and "tier 3" not in joined:
        issues.append("proposal names a three-tier process but omits Tier 3")
    if any(item.strip() in {"***", "---"} for item in paragraphs):
        issues.append("proposal contains raw markdown divider artifact")
    return issues


def _next_is_heading_or_empty(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return True
    return lines[index + 1] in {
        "recommended approach",
        "deliverables",
        "timeline",
        "risks",
        "next steps",
        "sources",
    }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip(" :")
