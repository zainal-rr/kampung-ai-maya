from __future__ import annotations

import argparse
import os
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
        _command_check("document request parser", ("document_request_parser_smoke.py",)),
        _command_check("natural artifact parser", ("document_natural_artifact_parser_smoke.py",)),
        _command_check("confirmation decision", ("confirmation_decision_smoke.py",)),
        _command_check("semantic artifact resolver", ("artifact_semantic_resolver_smoke.py",)),
        _command_check("artifact clarification continuity", ("artifact_clarification_continuity_smoke.py",)),
        _command_check("artifact session continuity", ("artifact_session_continuity_smoke.py",)),
        _command_check("artifact naming", ("artifact_naming_smoke.py",)),
        _command_check("artifact delivery gate", ("artifact_delivery_gate_smoke.py",)),
        _command_check("artifact retry loop", ("artifact_retry_loop_smoke.py",)),
        _command_check("office edit workflow", ("document_edit_office_smoke.py",)),
        _command_check("household budget", ("household_budget_smoke.py",)),
        _command_check("word technical repair", ("word_technical_repair_smoke.py",)),
        _command_check("semantic telegram fresh 500", ("semantic_telegram_fresh_500.py",)),
        _command_check("voice document transcript", ("voice_document_transcript_smoke.py",)),
        _command_check("voice artifact transcript replay 500", ("voice_artifact_transcript_replay_500.py",)),
        _command_check("voice telegram transcript replay 10000", ("voice_telegram_transcript_replay_10000.py",)),
        _command_check("artifact parameter resolver", ("artifact_parameter_resolver_smoke.py",)),
        _command_check("artifact parameters", ("artifact_parameters_smoke.py",)),
        _command_check("word travel destination", ("word_travel_destination_smoke.py",)),
        _command_check("untrusted input boundary", ("tests/smokes/untrusted_input_boundary_smoke.py",)),
        _command_check("untrusted live path", ("tests/smokes/untrusted_live_path_smoke.py",)),
        _command_check("browser untrusted action guard", ("tests/smokes/browser_untrusted_action_guard_smoke.py",)),
        _command_check("canonical memory", ("canonical_memory_smoke.py",)),
        _command_check("canonical memory embeddings", ("canonical_memory_embeddings_smoke.py",)),
        _command_check("nightly consolidation", ("nightly_consolidation_smoke.py",)),
        _command_check("memory time audit", ("memory_time_audit_smoke.py",)),
        _command_check("context window canaries", ("context_window_canaries_smoke.py",)),
        _command_check("memory recall eval", ("tests/evals/memory_recall_eval.py",)),
        _command_check("memory recall compare", ("tests/evals/memory_recall_eval_compare.py",)),
        _command_check("runtime config", ("runtime_config_smoke.py",)),
        _command_check("secret provider", ("tests/smokes/secret_provider_smoke.py",)),
        _command_check("secret migration", ("tests/smokes/secret_migration_smoke.py",)),
        _command_check("tool sandbox policy", ("tests/smokes/tool_sandbox_policy_smoke.py",)),
        _command_check("self-heal execution", ("self_heal_execution_smoke.py",)),
        _command_check("voice command aliases", ("voice_command_aliases_smoke.py",)),
        _command_check("OSBridge test mode", ("osbridge_test_mode_smoke.py",)),
        _command_check("telegram conversation contract", ("telegram_conversation_contract_smoke.py",)),
        _command_check("telegram text alias", ("telegram_text_alias_smoke.py",)),
        _command_check("telegram voice input", ("telegram_voice_input_smoke.py",)),
        _command_check("telegram photo input", ("telegram_photo_input_smoke.py",)),
        _command_check("browser semantic scrape 500", ("browser_semantic_scrape_500.py",)),
        _command_check("browser run evidence", ("browser_run_evidence_smoke.py",)),
        _command_check("browser lane validators", ("browser_lane_validators_smoke.py",)),
        _command_check("browser reliability dry night", ("live_browser_reliability_smoke.py",)),
        _command_check("browser extension bridge", ("browser_extension_bridge_smoke.py",)),
        _command_check("browser driver mode", ("browser_driver_mode_smoke.py",)),
        _command_check("workflow document bypass", ("tests/smokes/workflow_document_bypass_smoke.py",)),
        _command_check("recent questions document", ("tests/smokes/recent_questions_document_smoke.py",)),
        _command_check("agentic verifier deep", ("harness_agentic_deep_smoke.py",)),
        _command_check("agentic reliability harness", ("live_agentic_reliability_smoke.py",)),
        _command_check("flight deep link", ("flight_deeplink_smoke.py",)),
        _command_check("legacy architecture removed", ("legacy_architecture_removed_smoke.py",)),
        _command_check("memory perspective", ("memory_perspective_smoke.py",)),
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
    files = sorted(
        str(path.relative_to(ROOT))
        for path in (*ROOT.glob("*.py"), *ROOT.joinpath("tests").rglob("*.py"))
    )
    return _command_check("python compile", ("-m", "py_compile", *files))


def _code_health_check(required: bool) -> CheckResult:
    health = collect_code_health(ROOT)
    return CheckResult("code health", health.ok, format_code_health(health), required=required)


def _eval_check() -> CheckResult:
    payload = run_eval_suite(DEFAULT_OUTPUT)
    return CheckResult("scored eval suite", payload["failed"] == 0, format_eval_summary(payload))


def _command_check(name: str, command: tuple[str, ...], required: bool = True) -> CheckResult:
    env = os.environ.copy()
    env["MAYA_TEST_MODE"] = "1"
    proc = subprocess.run([sys.executable, *command], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
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
