from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from code_health import collect_code_health, format_code_health
from scored_eval_suite import DEFAULT_OUTPUT, format_eval_summary, run_eval_suite


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    output: str
    required: bool = True


def run_local_ci(*, live_providers: bool = False) -> list[CheckResult]:
    results = [
        _compile_check(),
        _code_health_check(required=True),
        _eval_check(),
        _command_check("hardening audit", ("hardening_audit_smoke.py",)),
        _command_check("latest demo evidence", ("demo_evidence.py", "--check")),
    ]
    if live_providers:
        results.append(_command_check("provider live text", ("provider_smoke.py", "--stage", "text", "--strict")))
    return results


def format_ci(results: list[CheckResult]) -> str:
    lines = ["Kampung AI local CI:"]
    for index, result in enumerate(results, start=1):
        status = "PASS" if result.passed else ("WARN" if not result.required else "FAIL")
        lines.append(f"{index}) {status}: {result.name}")
        if not result.passed:
            lines.append(result.output[-1200:])
    blocking = [result for result in results if result.required and not result.passed]
    lines.append(f"blocking failures: {len(blocking)}")
    return "\n".join(lines)


def _compile_check() -> CheckResult:
    files = sorted(str(path.name) for path in ROOT.glob("*.py"))
    return _command_check("python compile", ("-m", "py_compile", *files))


def _code_health_check(required: bool) -> CheckResult:
    health = collect_code_health(ROOT)
    return CheckResult("code health", health.ok, format_code_health(health), required=required)


def _eval_check() -> CheckResult:
    payload = run_eval_suite(DEFAULT_OUTPUT)
    return CheckResult("scored eval suite", payload["failed"] == 0, format_eval_summary(payload))


def _command_check(name: str, command: tuple[str, ...], required: bool = True) -> CheckResult:
    proc = subprocess.run([sys.executable, *command], cwd=ROOT, capture_output=True, text=True, timeout=180)
    return CheckResult(name, proc.returncode == 0, (proc.stdout + proc.stderr).strip(), required=required)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-providers", action="store_true")
    args = parser.parse_args()
    results = run_local_ci(live_providers=args.live_providers)
    print(format_ci(results))
    failed = [result for result in results if result.required and not result.passed]
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
