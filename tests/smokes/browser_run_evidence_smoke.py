from __future__ import annotations

import tempfile
from pathlib import Path

from browser_run_evidence import (
    BrowserRunRecorder,
    append_run,
    load_runs,
    night_summary,
    redact,
    run_to_dict,
    write_night_markdown,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    recorder = BrowserRunRecorder("flights-01", "smoke_night", "flights", "find flights to Penang on June 24")
    recorder.note_route("flight_search", "flight keyword")
    recorder.note_intent({"destination": "Penang", "depart": "June 24 2026"})
    recorder.record_step("open_url", url="https://www.google.com/travel/flights")
    recorder.record_step("fill", target="Where to?", value="Penang", result="FILLED: where to?")
    recorder.record_step("click_exact_last", target="Search", result="CLICKED: search")
    recorder.record_step("inspect", url="https://www.google.com/travel/flights/search", title="KUL to PEN", text_hash="abc123")
    recorder.add_screenshot("logs/live_tests/reliability/smoke_night/shots/flights-01.png")
    record = recorder.finalize(
        answer="visible price options:\n1) AirAsia MYR 158 contact zainal96bdn@gmail.com",
        final_url="https://www.google.com/travel/flights/search",
        final_title="KUL to PEN",
        final_text="AirAsia\nMYR 158\nKUL-PEN",
        final_text_hash="abc123",
        extracted=("AirAsia MYR 158",),
    )
    record.status = "pass"
    record.reasons = ["partial:example"]

    _require(record.run_id == "flights-01", "run id lost")
    _require(len(record.steps) == 4, "steps not recorded")
    _require(record.parsed_intent["destination"] == "Penang", "intent not recorded")
    _require(record.route_skill == "flight_search", "route not recorded")
    _require(record.screenshots, "screenshot path not recorded")
    _require(record.started_at and record.finished_at, "timestamps missing")

    payload = run_to_dict(record)
    _require("<REDACTED_EMAIL>" in payload["answer"], "email was not redacted")
    _require("zainal96bdn" not in str(payload), "raw email leaked into payload")
    _require(redact("card 4111 1111 1111 1111 used") == "card <REDACTED_CARD> used", "card redaction failed")

    with tempfile.TemporaryDirectory(prefix="maya-evidence-") as tmp:
        jsonl = Path(tmp) / "runs.jsonl"
        append_run(record, jsonl)
        append_run(record, jsonl)
        runs = load_runs(jsonl)
        _require(len(runs) == 2, "JSONL append/load round trip failed")
        eight_fields = ("prompt", "parsed_intent", "steps", "final_url", "extracted", "safety_boundary", "screenshots", "status")
        for field in eight_fields:
            _require(field in runs[0], f"evidence record missing field {field}")
        runs[0]["reasons"] = ["critical:stale-context: osaka leaked"]
        runs[1]["lane"] = "safety"
        runs[1]["status"] = "pass"
        summary = night_summary(runs)
        _require(summary["total"] == 2, "summary total wrong")
        _require(summary["stale_context_criticals"] == 1, "stale critical not counted")
        _require(summary["safety_passed"] == 1 and summary["safety_total"] == 1, "safety lane not counted")
        md_path = Path(tmp) / "night.md"
        write_night_markdown(runs, md_path)
        content = md_path.read_text("utf-8")
        _require("flights-01" in content and "critical:stale-context" in content, "markdown report incomplete")

    print("browser_run_evidence_smoke: ok")


if __name__ == "__main__":
    main()
