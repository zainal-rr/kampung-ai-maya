from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


LIVE_DIR = Path("logs") / "live_tests"
LIVE_STATUS_PATH = LIVE_DIR / "latest.json"


@dataclass(frozen=True)
class LiveEvidence:
    id: str
    area: str
    title: str
    status: str
    evidence: str
    updated_at: str
    notes: str = ""


DEFAULT_CASES = (
    LiveEvidence(
        "telegram_document_memory",
        "telegram",
        "Telegram document, voice-note, memory, route, and file delivery",
        "passed",
        "Manual Telegram regression passed in late May 2026; local smoke coverage remains in CI.",
        "",
    ),
    LiveEvidence(
        "imac_voice_office_pre_may25",
        "imac",
        "iMac voice can create Word, Excel, and PowerPoint through Maya",
        "passed",
        "Zainal reported pre-May-25 iMac live voice Office artifact creation passed.",
        "",
    ),
    LiveEvidence(
        "imac_live_long_handoff",
        "imac",
        "iMac live voice parks paid speech-to-speech while long work continues",
        "manual-live-required",
        "Requires local iMac voice session proof.",
        "",
    ),
    LiveEvidence(
        "imac_native_app_continuity",
        "imac",
        "Open last document, open named document, summarize, and focus native app",
        "manual-live-required",
        "Requires June 8 iMac regression session.",
        "",
    ),
    LiveEvidence(
        "browser_field_workflows",
        "browser",
        "Real browser field workflow reliability",
        "pending-field-test",
        "Use browser_field_tests.py prompts; smoke checks only prove routing and safety boundaries.",
        "",
    ),
    LiveEvidence(
        "omi_hardware",
        "hardware",
        "Omi real transcript sync and ambient memory privacy",
        "manual-live-required",
        "Requires real Omi transcript flow.",
        "",
    ),
    LiveEvidence(
        "mudra_hardware",
        "hardware",
        "Mudra real proximity and gesture trigger",
        "manual-live-required",
        "Requires real Mudra Link event.",
        "",
    ),
)


def load_live_evidence(path: Path = LIVE_STATUS_PATH) -> list[LiveEvidence]:
    defaults = {item.id: _with_time(item) for item in DEFAULT_CASES}
    if path.exists():
        try:
            payload = json.loads(path.read_text("utf-8"))
            for raw in payload.get("items", []):
                item = LiveEvidence(**raw)
                defaults[item.id] = item
        except (json.JSONDecodeError, TypeError):
            pass
    return list(defaults.values())


def save_live_evidence(items: list[LiveEvidence], path: Path = LIVE_STATUS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _now(),
        "items": [asdict(item) for item in items],
    }
    path.write_text(json.dumps(payload, indent=2), "utf-8")


def record_live_evidence(
    case_id: str,
    status: str,
    evidence: str,
    notes: str = "",
    path: Path = LIVE_STATUS_PATH,
) -> bool:
    items = load_live_evidence(path)
    changed = False
    updated = []
    for item in items:
        if item.id == case_id:
            updated.append(LiveEvidence(item.id, item.area, item.title, status, evidence, _now(), notes))
            changed = True
        else:
            updated.append(item)
    if changed:
        save_live_evidence(updated, path)
    return changed


def format_live_evidence(items: list[LiveEvidence] | None = None) -> str:
    rows = items or load_live_evidence()
    lines = ["Live test evidence:"]
    for index, item in enumerate(rows, 1):
        lines.append(f"{index}) {item.status}: {item.area} | {item.title} | {item.evidence}")
    return "\n".join(lines)


def live_evidence_summary(items: list[LiveEvidence] | None = None) -> dict[str, int]:
    rows = items or load_live_evidence()
    summary: dict[str, int] = {}
    for item in rows:
        summary[item.status] = summary.get(item.status, 0) + 1
    return summary


def _with_time(item: LiveEvidence) -> LiveEvidence:
    return LiveEvidence(item.id, item.area, item.title, item.status, item.evidence, item.updated_at or _now(), item.notes)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--record", nargs=3, metavar=("CASE_ID", "STATUS", "EVIDENCE"))
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    if args.init:
        save_live_evidence(load_live_evidence())
    if args.record:
        case_id, status, evidence = args.record
        if not record_live_evidence(case_id, status, evidence, args.notes):
            raise SystemExit(f"Unknown live evidence case: {case_id}")
    print(format_live_evidence())


if __name__ == "__main__":
    main()
