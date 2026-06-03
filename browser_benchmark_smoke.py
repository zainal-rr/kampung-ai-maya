from __future__ import annotations

import tempfile
from pathlib import Path

from browser_benchmark import (
    browser_benchmark_cases,
    browser_benchmark_summary,
    format_browser_benchmark,
    record_browser_live_result,
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-browser-bench-") as tmp:
        path = Path(tmp) / "latest.json"
        cases = browser_benchmark_cases(path)
        _require(len(cases) >= 7, "benchmark cases missing")
        _require(browser_benchmark_summary(cases)["deterministic_score"] == 100.0, "deterministic benchmark failed")
        _require(record_browser_live_result(cases[0].id, "passed", "manual test passed", path), "live result not recorded")
        updated = browser_benchmark_cases(path)
        summary = browser_benchmark_summary(updated)
        _require(summary["live_run"] == 1 and summary["live_passed"] == 1, "live summary wrong")
        text = format_browser_benchmark(updated)
        _require("deterministic pass is not browser maturity" in text, "live boundary missing")
    print("browser_benchmark_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
