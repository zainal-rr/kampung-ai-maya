from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dependency_manifest import dependency_statuses
from maya_core.repo_paths import repo_root


@dataclass(frozen=True)
class ProofItem:
    name: str
    status: str
    evidence: str


def hardware_live_proof_items() -> list[ProofItem]:
    return [
        _file_item("Mudra adapter prepared", "maya_core/mudra_adapter.py"),
        _file_item("Omi adapter prepared", "maya_core/omi_adapter.py"),
        _file_item("Omi context sieve prepared", "maya_core/omi_context_sieve.py"),
        _file_item("hardware event store prepared", "maya_core/hardware_event_store.py"),
        _file_item("voice handoff prepared", "maya_voice/xai_voice_handoff.py"),
        _provider_item("xAI/Ara key readiness", "env.xai"),
        _provider_item("Gemini readiness", "env.gemini"),
        ProofItem(
            "Mudra physical trigger",
            "manual-live-required",
            "Requires real Mudra Link event and proximity test before gesture actions are enabled.",
        ),
        ProofItem(
            "Omi physical transcript flow",
            "manual-live-required",
            "Requires real Omi transcript sync path before ambient ingestion is trusted.",
        ),
        ProofItem(
            "iMac live Ara/Grok voice loop",
            "manual-live-required",
            "Requires local hotkey/Mudra trigger, microphone, speaker output, and xAI realtime session.",
        ),
    ]


def format_hardware_live_proof() -> str:
    lines = ["Hardware/live proof readiness:"]
    for index, item in enumerate(hardware_live_proof_items(), start=1):
        lines.append(f"{index}) {item.status}: {item.name} | {item.evidence}")
    lines.append("")
    lines.append("Rule: prepared adapters are not live proof. Physical devices and iMac voice must be tested manually.")
    return "\n".join(lines)


def _file_item(name: str, relative: str) -> ProofItem:
    path = repo_root(__file__) / relative
    return ProofItem(name, "pass" if path.exists() else "missing", relative)


def _provider_item(name: str, dependency_id: str) -> ProofItem:
    statuses = {item.id: item for item in dependency_statuses()}
    item = statuses.get(dependency_id)
    if not item:
        return ProofItem(name, "missing", dependency_id)
    return ProofItem(name, item.status, item.detail)


def main() -> None:
    print(format_hardware_live_proof())


if __name__ == "__main__":
    main()
