from __future__ import annotations

import tempfile
from pathlib import Path

from live_test_evidence import (
    format_live_evidence,
    live_evidence_summary,
    load_live_evidence,
    record_live_evidence,
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-live-evidence-") as tmp:
        path = Path(tmp) / "latest.json"
        items = load_live_evidence(path)
        statuses = {item.status for item in items}
        _require("passed" in statuses, "passed live evidence missing")
        _require("manual-live-required" in statuses, "manual-live-required boundary missing")
        _require(any(item.id == "imac_live_long_handoff" for item in items), "iMac handoff case missing")
        ok = record_live_evidence("browser_field_workflows", "field-test-running", "Started browser field test.", path=path)
        _require(ok, "record did not update known case")
        text = format_live_evidence(load_live_evidence(path))
        _require("field-test-running" in text, "updated status not rendered")
        summary = live_evidence_summary(load_live_evidence(path))
        _require(summary["manual-live-required"] >= 1, "summary lost manual boundary")
    print("live_test_evidence_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
