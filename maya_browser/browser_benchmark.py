from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from maya_browser.browser_field_tests import BrowserFieldScenario, browser_field_scenarios


BENCHMARK_PATH = Path("logs") / "browser_benchmarks" / "latest.json"


@dataclass(frozen=True)
class BrowserBenchmarkCase:
    id: str
    name: str
    prompt: str
    expected: str
    deterministic_status: str
    deterministic_evidence: str
    pass_criteria: str = ""
    safety_boundary: str = ""
    live_status: str = "not-run"
    live_evidence: str = ""
    updated_at: str = ""


def browser_benchmark_cases(path: Path = BENCHMARK_PATH) -> list[BrowserBenchmarkCase]:
    existing = {item.id: item for item in _load_existing(path)}
    cases = []
    for index, scenario in enumerate(browser_field_scenarios(), 1):
        case_id = _case_id(index, scenario)
        old = existing.get(case_id)
        cases.append(_from_scenario(case_id, scenario, old))
    return cases


def save_browser_benchmark(cases: list[BrowserBenchmarkCase], path: Path = BENCHMARK_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _now(),
        "summary": browser_benchmark_summary(cases),
        "cases": [asdict(case) for case in cases],
    }
    path.write_text(json.dumps(payload, indent=2), "utf-8")


def record_browser_live_result(case_id: str, live_status: str, evidence: str, path: Path = BENCHMARK_PATH) -> bool:
    changed = False
    updated = []
    for case in browser_benchmark_cases(path):
        if case.id == case_id:
            updated.append(
                BrowserBenchmarkCase(
                    case.id,
                    case.name,
                    case.prompt,
                    case.expected,
                    case.deterministic_status,
                    case.deterministic_evidence,
                    case.pass_criteria,
                    case.safety_boundary,
                    live_status,
                    evidence,
                    _now(),
                )
            )
            changed = True
        else:
            updated.append(case)
    if changed:
        save_browser_benchmark(updated, path)
    return changed


def browser_benchmark_summary(cases: list[BrowserBenchmarkCase] | None = None) -> dict[str, float | int]:
    rows = cases or browser_benchmark_cases()
    deterministic_passed = sum(1 for case in rows if case.deterministic_status == "pass")
    live_run = [case for case in rows if case.live_status != "not-run"]
    live_passed = sum(1 for case in live_run if case.live_status == "passed")
    return {
        "total": len(rows),
        "deterministic_passed": deterministic_passed,
        "deterministic_score": round((deterministic_passed / len(rows)) * 100, 1) if rows else 0,
        "live_run": len(live_run),
        "live_passed": live_passed,
        "live_score": round((live_passed / len(live_run)) * 100, 1) if live_run else 0,
    }


def format_browser_benchmark(cases: list[BrowserBenchmarkCase] | None = None) -> str:
    rows = cases or browser_benchmark_cases()
    summary = browser_benchmark_summary(rows)
    lines = [
        "Browser benchmark:",
        f"1) deterministic score: {summary['deterministic_score']}% ({summary['deterministic_passed']}/{summary['total']})",
        f"2) live score: {summary['live_score']}% ({summary['live_passed']}/{summary['live_run']} live runs)",
    ]
    for case in rows:
        lines.append(f"- {case.id}: deterministic={case.deterministic_status}, live={case.live_status}, {case.name}")
        lines.append(f"  pass: {case.pass_criteria or 'live evidence recorded'}")
        lines.append(f"  boundary: {case.safety_boundary or 'standard browser safety boundary'}")
    lines.append("Rule: deterministic pass is not browser maturity; live runs must be recorded separately.")
    return "\n".join(lines)


def _load_existing(path: Path) -> list[BrowserBenchmarkCase]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text("utf-8"))
        return [BrowserBenchmarkCase(**item) for item in payload.get("cases", [])]
    except (json.JSONDecodeError, TypeError):
        return []


def _from_scenario(case_id: str, scenario: BrowserFieldScenario, old: BrowserBenchmarkCase | None) -> BrowserBenchmarkCase:
    return BrowserBenchmarkCase(
        case_id,
        scenario.name,
        scenario.prompt,
        scenario.expected,
        scenario.status,
        scenario.evidence,
        scenario.pass_criteria,
        scenario.safety_boundary,
        old.live_status if old else "not-run",
        old.live_evidence if old else "",
        old.updated_at if old else "",
    )


def _case_id(index: int, scenario: BrowserFieldScenario) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in scenario.name.lower()).strip("_")
    return f"browser_{index}_{slug}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--record", nargs=3, metavar=("CASE_ID", "STATUS", "EVIDENCE"))
    args = parser.parse_args()
    if args.record and not record_browser_live_result(*args.record):
        raise SystemExit(f"Unknown browser benchmark case: {args.record[0]}")
    if args.init or args.record:
        save_browser_benchmark(browser_benchmark_cases())
    print(format_browser_benchmark())


if __name__ == "__main__":
    main()
