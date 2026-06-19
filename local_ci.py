from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from maya_core.code_health import collect_code_health, format_code_health
from scored_eval_suite import DEFAULT_OUTPUT, format_eval_summary, run_eval_suite


ROOT = Path(__file__).resolve().parent
FAST_VOICE_TELEGRAM_REPLAY_LIMIT = 250
# Fast CI uses representative canaries for expensive matrix checks. Full
# matrix coverage stays in the additive --extended tier.


@dataclass(frozen=True)
class CheckSpec:
    name: str
    command: tuple[str, ...] = ()
    tier: str = "fast"
    required: bool = True
    timeout: int = 180
    kind: str = "command"
    eval_categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckResult:
    name: str
    tier: str
    passed: bool
    output: str
    required: bool = True
    elapsed_s: float = 0.0


CHECKS: tuple[CheckSpec, ...] = (
    CheckSpec("python compile", kind="compile", timeout=240),
    CheckSpec("code health", kind="code_health"),
    CheckSpec("scored eval suite canary", kind="eval", timeout=90, eval_categories=("routing", "safety", "hardening")),
    CheckSpec("scored eval suite full", kind="eval", tier="extended", timeout=180),
    CheckSpec("document request parser", ("tests/smokes/document_request_parser_smoke.py",)),
    CheckSpec("natural artifact parser", ("tests/smokes/document_natural_artifact_parser_smoke.py",)),
    CheckSpec("confirmation decision", ("tests/smokes/confirmation_decision_smoke.py",)),
    CheckSpec("semantic artifact resolver", ("tests/smokes/artifact_semantic_resolver_smoke.py",)),
    CheckSpec("artifact clarification continuity canary", ("tests/smokes/artifact_clarification_continuity_smoke.py", "--mode", "canary")),
    CheckSpec("artifact clarification continuity full", ("tests/smokes/artifact_clarification_continuity_smoke.py",), tier="extended"),
    CheckSpec("artifact session continuity canary", ("tests/smokes/artifact_session_continuity_smoke.py", "--channel", "imac", "--mode", "canary")),
    CheckSpec("artifact session continuity full", ("tests/smokes/artifact_session_continuity_smoke.py",), tier="extended"),
    CheckSpec("artifact naming", ("tests/smokes/artifact_naming_smoke.py",)),
    CheckSpec("artifact delivery gate", ("tests/smokes/artifact_delivery_gate_smoke.py",)),
    CheckSpec("artifact retry loop", ("tests/smokes/artifact_retry_loop_smoke.py",)),
    CheckSpec("office edit workflow", ("tests/smokes/document_edit_office_smoke.py",)),
    CheckSpec("household budget", ("tests/smokes/household_budget_smoke.py",)),
    CheckSpec("word technical repair", ("tests/smokes/word_technical_repair_smoke.py",)),
    CheckSpec("semantic telegram fresh canary", ("tests/replays/semantic_telegram_fresh_500.py", "--limit", "20")),
    CheckSpec("semantic telegram fresh 500", ("tests/replays/semantic_telegram_fresh_500.py",), tier="extended", timeout=240),
    CheckSpec("voice document transcript", ("tests/smokes/voice_document_transcript_smoke.py",)),
    CheckSpec("voice semantic seam manifest", ("tests/smokes/voice_semantic_seam_manifest_smoke.py",)),
    CheckSpec("voice browser steering", ("tests/smokes/xai_realtime_browser_supervisor_smoke.py",)),
    CheckSpec("voice artifact transcript replay canary", ("tests/replays/voice_artifact_transcript_replay_500.py", "--limit", "50")),
    CheckSpec("voice artifact transcript replay 500", ("tests/replays/voice_artifact_transcript_replay_500.py",), tier="extended"),
    CheckSpec(
        "voice telegram transcript replay canary",
        ("tests/replays/voice_telegram_transcript_replay_10000.py", "--limit", str(FAST_VOICE_TELEGRAM_REPLAY_LIMIT)),
    ),
    CheckSpec("voice telegram transcript replay 10000", ("tests/replays/voice_telegram_transcript_replay_10000.py",), tier="extended", timeout=240),
    CheckSpec("artifact parameter resolver", ("tests/smokes/artifact_parameter_resolver_smoke.py",)),
    CheckSpec("artifact parameters", ("tests/smokes/artifact_parameters_smoke.py",)),
    CheckSpec("word travel destination", ("tests/smokes/word_travel_destination_smoke.py",)),
    CheckSpec("untrusted input boundary", ("tests/smokes/untrusted_input_boundary_smoke.py",)),
    CheckSpec("security reliability matrix", ("tests/smokes/security_reliability_matrix_smoke.py",)),
    CheckSpec("W7 provenance authorization", ("tests/smokes/w7_provenance_authorization_smoke.py",)),
    CheckSpec("clearance map planner quarantine", ("tests/smokes/clearance_map_planner_quarantine_smoke.py",)),
    CheckSpec("router clearance conformance", ("tests/smokes/router_clearance_conformance_smoke.py",)),
    CheckSpec("whole-loop harness", ("tests/smokes/whole_loop_harness_smoke.py",)),
    CheckSpec("Maya harness SDK", ("tests/smokes/maya_harness_sdk_smoke.py",)),
    CheckSpec("Meet artifact handoff", ("tests/smokes/meet_artifact_handoff_smoke.py",)),
    CheckSpec("Meet M1 Recall foundation", ("tests/smokes/meet_m1_recall_foundation_smoke.py",)),
    CheckSpec("Meet join orchestrator", ("tests/smokes/meet_join_orchestrator_smoke.py",)),
    CheckSpec("Meet voiceprint policy", ("tests/smokes/meet_voiceprint_policy_smoke.py",)),
    CheckSpec("Meet voiceprint live scoring", ("tests/smokes/meet_voiceprint_live_smoke.py",)),
    CheckSpec("untrusted live path", ("tests/smokes/untrusted_live_path_smoke.py",)),
    CheckSpec("browser untrusted action guard", ("tests/smokes/browser_untrusted_action_guard_smoke.py",)),
    CheckSpec("canonical memory", ("tests/smokes/canonical_memory_smoke.py",)),
    CheckSpec("canonical memory embeddings", ("tests/smokes/canonical_memory_embeddings_smoke.py",)),
    CheckSpec("memory paraphrase canaries (W2-B)", ("tests/smokes/memory_paraphrase_canaries_smoke.py",)),
    CheckSpec("voice memory tools", ("tests/smokes/xai_realtime_memory_tools_smoke.py",)),
    CheckSpec("nightly consolidation", ("tests/smokes/nightly_consolidation_smoke.py",)),
    CheckSpec("memory time audit", ("tests/smokes/memory_time_audit_smoke.py",)),
    CheckSpec("context window canaries", ("tests/smokes/context_window_canaries_smoke.py",)),
    CheckSpec("memory relayed content provenance", ("tests/smokes/memory_relayed_content_provenance_smoke.py",)),
    CheckSpec("memory recall eval", ("tests/evals/memory_recall_eval.py",)),
    CheckSpec("memory recall compare", ("tests/evals/memory_recall_eval_compare.py",), tier="extended", timeout=240),
    CheckSpec("runtime config", ("tests/smokes/runtime_config_smoke.py",)),
    CheckSpec("secret provider", ("tests/smokes/secret_provider_smoke.py",)),
    CheckSpec("secret migration", ("tests/smokes/secret_migration_smoke.py",)),
    CheckSpec("tool sandbox policy", ("tests/smokes/tool_sandbox_policy_smoke.py",)),
    CheckSpec("reversibility predicates", ("tests/smokes/reversibility_predicates_smoke.py",)),
    CheckSpec("reversibility gate wiring", ("tests/smokes/reversibility_gate_wiring_smoke.py",)),
    CheckSpec("blast-radius canaries (W5-1)", ("tests/smokes/blast_radius_canaries_smoke.py",)),
    CheckSpec("execution broker (W5-2)", ("tests/smokes/execution_broker_smoke.py",)),
    CheckSpec("execution broker static guard (W5-2)", ("tests/smokes/execution_broker_static_smoke.py",)),
    CheckSpec("delete quarantine (W5-2)", ("tests/smokes/delete_quarantine_smoke.py",)),
    CheckSpec("memory supersede canaries (W2-A)", ("tests/smokes/memory_supersede_canaries_smoke.py",)),
    CheckSpec("self-heal execution", ("tests/smokes/self_heal_execution_smoke.py",)),
    CheckSpec("voice command aliases", ("tests/smokes/voice_command_aliases_smoke.py",)),
    CheckSpec("OSBridge test mode", ("tests/smokes/osbridge_test_mode_smoke.py",)),
    CheckSpec("telegram conversation contract", ("tests/smokes/telegram_conversation_contract_smoke.py",)),
    CheckSpec("telegram text alias", ("tests/smokes/telegram_text_alias_smoke.py",)),
    CheckSpec("telegram voice input", ("tests/smokes/telegram_voice_input_smoke.py",)),
    CheckSpec("telegram photo input", ("tests/smokes/telegram_photo_input_smoke.py",)),
    CheckSpec("browser semantic scrape canary", ("tests/replays/browser_semantic_scrape_500.py", "--limit", "50")),
    CheckSpec("browser semantic scrape 500", ("tests/replays/browser_semantic_scrape_500.py",), tier="extended", timeout=240),
    CheckSpec("browser run evidence", ("tests/smokes/browser_run_evidence_smoke.py",)),
    CheckSpec("browser lane validators", ("tests/smokes/browser_lane_validators_smoke.py",)),
    CheckSpec("operational incident ledger", ("tests/smokes/reliability_incident_ledger_smoke.py",)),
    CheckSpec("browser reliability dry night", ("tests/smokes/live_browser_reliability_smoke.py",)),
    CheckSpec("browser extension bridge", ("tests/smokes/browser_extension_bridge_smoke.py",)),
    CheckSpec("browser driver mode", ("tests/smokes/browser_driver_mode_smoke.py",)),
    CheckSpec("workflow document bypass", ("tests/smokes/workflow_document_bypass_smoke.py",)),
    CheckSpec("recent questions document", ("tests/smokes/recent_questions_document_smoke.py",)),
    CheckSpec("metacognition taxonomy", ("tests/smokes/metacognition_taxonomy_smoke.py",)),
    CheckSpec("agentic verifier deep", ("tests/smokes/harness_agentic_deep_smoke.py",)),
    CheckSpec("agentic reliability harness", ("tests/smokes/live_agentic_reliability_smoke.py",), tier="extended"),
    CheckSpec("flight deep link", ("tests/smokes/flight_deeplink_smoke.py",), tier="extended"),
    CheckSpec("legacy architecture removed", ("tests/smokes/legacy_architecture_removed_smoke.py",)),
    CheckSpec("memory perspective", ("tests/smokes/memory_perspective_smoke.py",)),
    CheckSpec("hardening audit", ("tests/smokes/hardening_audit_smoke.py",)),
    CheckSpec("latest demo evidence", ("demo_evidence.py", "--check")),
    CheckSpec("maya UI read API", ("KAMPUNG_AI_UI/ui_read_api_smoke.py",)),
    CheckSpec("provider live text", ("tests/smokes/provider_smoke.py", "--stage", "text", "--strict"), tier="live"),
)


def run_local_ci(*, extended: bool = False, live_providers: bool = False) -> list[CheckResult]:
    tiers = {"fast"}
    if extended:
        tiers.add("extended")
    if live_providers:
        tiers.add("live")
    results = []
    for spec in CHECKS:
        if spec.tier not in tiers:
            continue
        print(f"RUN [{spec.tier}]: {spec.name}", flush=True)
        started = time.perf_counter()
        result = _run_check(spec)
        results.append(CheckResult(
            result.name,
            result.tier,
            result.passed,
            result.output,
            result.required,
            round(time.perf_counter() - started, 2),
        ))
    return results


def format_ci(results: list[CheckResult]) -> str:
    lines = ["Kampung AI local CI:"]
    for index, result in enumerate(results, start=1):
        status = "PASS" if result.passed else ("WARN" if not result.required else "FAIL")
        lines.append(f"{index}) {status} [{result.tier} {result.elapsed_s:.2f}s]: {result.name}")
        if not result.passed:
            lines.append(result.output[-1200:])
    blocking = [result for result in results if result.required and not result.passed]
    lines.append(f"blocking failures: {len(blocking)}")
    return "\n".join(lines)


def _run_check(spec: CheckSpec) -> CheckResult:
    if spec.kind == "compile":
        return _compile_check(spec)
    if spec.kind == "code_health":
        return _code_health_check(spec)
    if spec.kind == "eval":
        return _eval_check(spec)
    return _command_check(spec)


def _compile_check(spec: CheckSpec) -> CheckResult:
    excluded = {".git", ".venv", "venv", "__pycache__", ".claude", "backups"}
    files = sorted(
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*.py")
        if not any(part in excluded for part in path.parts)
    )
    return _command_check(CheckSpec(spec.name, ("-m", "py_compile", *files), spec.tier, spec.required, spec.timeout))


def _code_health_check(spec: CheckSpec) -> CheckResult:
    health = collect_code_health(ROOT)
    return CheckResult(spec.name, spec.tier, health.ok, format_code_health(health), spec.required)


def _eval_check(spec: CheckSpec) -> CheckResult:
    payload = run_eval_suite(DEFAULT_OUTPUT, set(spec.eval_categories) or None)
    return CheckResult(spec.name, spec.tier, payload["failed"] == 0, format_eval_summary(payload), spec.required)


def _command_check(
    spec: CheckSpec | str,
    command: tuple[str, ...] | None = None,
    required: bool = True,
) -> CheckResult:
    if isinstance(spec, str):
        spec = CheckSpec(spec, command or (), required=required)
    env = os.environ.copy()
    env["MAYA_TEST_MODE"] = "1"
    if spec.tier != "live":
        # Fast and extended CI must be deterministic and token-free. A user's
        # desktop may have API keys loaded, so explicitly disable live memory
        # embedding paths unless the check is in the live tier.
        env["MEMORY_EMBED_RERANK_LIVE"] = "0"
        env["MEMORY_DIRECT_SEMANTIC_LIVE"] = "0"
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not current_pythonpath else f"{ROOT}{os.pathsep}{current_pythonpath}"
    try:
        proc = subprocess.run(
            [sys.executable, *spec.command],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=spec.timeout,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        output += f"\ntimed out after {spec.timeout}s"
        return CheckResult(spec.name, spec.tier, False, output.strip(), spec.required)
    return CheckResult(spec.name, spec.tier, proc.returncode == 0, (proc.stdout + proc.stderr).strip(), spec.required)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extended", action="store_true", help="Add extended deterministic replay/eval checks.")
    parser.add_argument("--live-providers", action="store_true", help="Add live provider checks.")
    args = parser.parse_args()
    results = run_local_ci(extended=args.extended, live_providers=args.live_providers)
    print(format_ci(results))
    failed = [result for result in results if result.required and not result.passed]
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
