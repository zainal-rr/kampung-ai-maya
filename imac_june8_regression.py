from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dependency_manifest import dependency_statuses


@dataclass(frozen=True)
class RegressionCheck:
    name: str
    status: str
    evidence: str


def june8_regression_checks() -> list[RegressionCheck]:
    return [
        _file_check("shared assistant router", "assistant_routes.py"),
        _file_check("document action router", "document_actions.py"),
        _file_check("Word/Excel/PPT edit workflow", "document_actions_word.py"),
        _file_check("workflow desk", "workflow_desk.py"),
        _file_check("weekly memory", "weekly_memory.py"),
        _file_check("voice handoff store", "xai_voice_handoff.py"),
        _file_check("hotkey voice channel", "hotkey_voice_channel.py"),
        _dependency_check("Microsoft Word", "app.word"),
        _dependency_check("Microsoft Excel", "app.excel"),
        _dependency_check("Microsoft PowerPoint", "app.powerpoint"),
        RegressionCheck(
            "iMac live voice architecture",
            "manual-live-required",
            "Run on iMac: hotkey/Mudra trigger -> Grok voice -> long-work handoff -> Maya worker completion.",
        ),
        RegressionCheck(
            "native app continuity",
            "manual-live-required",
            "Run on iMac: open last document, open named document, summarize document, focus correct native app.",
        ),
    ]


def format_june8_regression() -> str:
    lines = ["June 8 iMac regression preflight:"]
    for index, check in enumerate(june8_regression_checks(), start=1):
        lines.append(f"{index}) {check.status}: {check.name} | {check.evidence}")
    lines.append("")
    lines.append("Manual prompts to run on June 8:")
    lines.extend(_manual_prompts())
    return "\n".join(lines)


def _manual_prompts() -> list[str]:
    return [
        "- iMac voice: make me a Word document about router setup.",
        "- iMac voice: make me an Excel budget tracker for a Seoul food trip.",
        "- iMac voice: make me a PowerPoint deck about Seoul food trip.",
        "- iMac voice: open the last document.",
        "- iMac voice: summarize the current document.",
        "- iMac voice: make a document that will take a while; confirm voice parks and worker continues.",
    ]


def _file_check(name: str, relative: str) -> RegressionCheck:
    path = Path(relative)
    return RegressionCheck(name, "pass" if path.exists() else "missing", relative)


def _dependency_check(name: str, dependency_id: str) -> RegressionCheck:
    statuses = {item.id: item for item in dependency_statuses()}
    item = statuses.get(dependency_id)
    if not item:
        return RegressionCheck(name, "missing", dependency_id)
    return RegressionCheck(name, item.status, item.detail)


def main() -> None:
    print(format_june8_regression())


if __name__ == "__main__":
    main()
