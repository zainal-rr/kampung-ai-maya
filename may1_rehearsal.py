from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    live: bool = False
    optional: bool = False


BASE_CHECKS = (
    Check("doctor", ("doctor.py",)),
    Check("code health", ("code_health.py",)),
    Check("service install", ("tests/smokes/service_install_smoke.py",)),
    Check("wake and activation", ("tests/smokes/activation_smoke.py",)),
    Check("audio device resolution", ("tests/smokes/audio_device_resolution_smoke.py",)),
    Check("voice agent session", ("tests/smokes/voice_agent_session_smoke.py",)),
    Check("hotkey voice channel", ("tests/smokes/hotkey_voice_channel_smoke.py",)),
    Check("xAI realtime stream", ("xai_realtime_stream_smoke.py",)),
    Check("voice session log", ("tests/smokes/voice_session_log_smoke.py",)),
    Check("iMac voice policy", ("tests/smokes/imac_voice_policy_smoke.py",)),
    Check("xAI voice adapter payload", ("xai_voice_agent_smoke.py",)),
    Check("route ledger", ("tests/smokes/route_tracker_smoke.py",)),
    Check("cost ledger", ("tests/smokes/cost_tracker_smoke.py",)),
    Check("weather lookup", ("tests/smokes/weather_lookup_smoke.py",)),
    Check("provider readiness", ("tests/smokes/provider_readiness_smoke.py",)),
    Check("provider capabilities", ("tests/smokes/provider_capabilities_smoke.py",)),
    Check("complex planning", ("tests/smokes/complex_plan_smoke.py",)),
    Check("delivery redaction", ("tests/smokes/delivery_redaction_smoke.py",)),
    Check("workflow persistence", ("workflow_persistence_smoke.py",)),
    Check("harness store", ("tests/smokes/harness_store_smoke.py",)),
    Check("harness graph", ("tests/smokes/harness_graph_smoke.py",)),
    Check("harness native checkpoint resume", ("tests/smokes/harness_native_checkpoint_resume_smoke.py",)),
    Check("harness idempotency", ("tests/smokes/harness_idempotency_smoke.py",)),
    Check("harness approval checkpoint", ("tests/smokes/harness_approval_checkpoint_smoke.py",)),
    Check("harness multi checkpoint resume", ("tests/smokes/harness_multi_checkpoint_resume_smoke.py",)),
    Check("harness document replay", ("tests/smokes/harness_document_replay_smoke.py",)),
    Check("harness skill replay", ("tests/smokes/harness_skill_replay_smoke.py",)),
    Check("harness self-heal replay", ("tests/smokes/harness_self_heal_replay_smoke.py",)),
    Check("harness background checkpoint", ("tests/smokes/harness_background_checkpoint_smoke.py",)),
    Check("harness resume", ("tests/smokes/harness_resume_smoke.py",)),
    Check("harness resume detail", ("tests/smokes/harness_resume_detail_smoke.py",)),
    Check("harness multi resume", ("tests/smokes/harness_multi_resume_smoke.py",)),
    Check("harness artifacts", ("tests/smokes/harness_artifact_tracking_smoke.py",)),
    Check("harness grounding", ("tests/smokes/harness_grounding_smoke.py",)),
    Check("harness browser", ("tests/smokes/harness_browser_smoke.py",)),
    Check("harness screen", ("tests/smokes/harness_screen_smoke.py",)),
    Check("session compactor", ("tests/smokes/session_compactor_smoke.py",)),
    Check("memory control", ("tests/smokes/memory_control_smoke.py",)),
    Check("canonical memory", ("tests/smokes/canonical_memory_smoke.py",)),
    Check("retention policy", ("tests/smokes/retention_policy_smoke.py",)),
    Check("project mode", ("tests/smokes/project_mode_smoke.py",)),
    Check("hardening flow", ("tests/smokes/hardening_flow_smoke.py",)),
    Check("self healing", ("tests/smokes/self_healing_smoke.py",)),
    Check("self heal loop", ("tests/smokes/self_heal_loop_smoke.py",)),
    Check("self heal report isolation", ("tests/smokes/self_heal_report_isolation_smoke.py",)),
    Check("quantum advisory", ("tests/smokes/quantum_advisory_smoke.py",)),
    Check("quantum leaf boundary", ("tests/smokes/quantum_leaf_smoke.py",)),
    Check("weekly memory dry run", ("weekly_memory_smoke.py",)),
    Check("weekly memory provider path", ("weekly_memory_provider_path_smoke.py",)),
    Check("source-aware Gemini research", ("tests/smokes/source_aware_research_smoke.py",)),
    Check("learning pipeline", ("tests/smokes/learning_smoke.py",)),
    Check("golden conversation eval", ("tests/evals/golden_conversation_eval.py",)),
    Check("Telegram commands", ("tests/smokes/telegram_commands_smoke.py",)),
    Check("Telegram routing", ("tests/smokes/telegram_routing_smoke.py",)),
    Check("Telegram delivery files", ("tests/smokes/telegram_delivery_file_smoke.py",)),
    Check("Telegram voice input", ("tests/smokes/telegram_voice_input_smoke.py",)),
    Check("Telegram voice reply policy", ("tests/smokes/telegram_voice_reply_policy_smoke.py",)),
    Check("camera command gate", ("tests/smokes/vision_command_smoke.py",)),
    Check("screen sight command", ("tests/smokes/screen_command_smoke.py",)),
    Check("app interaction", ("tests/smokes/app_interaction_smoke.py",)),
    Check("app command full path", ("tests/smokes/app_command_fullpath_smoke.py",)),
    Check("browser control", ("tests/smokes/browser_control_smoke.py",)),
    Check("frequent sites", ("tests/smokes/frequent_sites_smoke.py",)),
    Check("browser site skills", ("tests/smokes/browser_site_skills_smoke.py",)),
    Check("browser agent maturity", ("tests/smokes/browser_agent_maturity_smoke.py",)),
    Check("browser field tests", ("tests/smokes/browser_field_tests_smoke.py",)),
    Check("browser benchmark", ("tests/smokes/browser_benchmark_smoke.py",)),
    Check("travel booking safety", ("tests/smokes/travel_booking_safety_smoke.py",)),
    Check("web actions", ("tests/smokes/web_actions_smoke.py",)),
    Check("iMac workflows", ("tests/smokes/imac_workflows_smoke.py",)),
    Check("artifact parameter questions", ("tests/smokes/artifact_parameters_smoke.py",)),
    Check("artifact preflight", ("tests/smokes/artifact_preflight_smoke.py",)),
    Check("document request parser", ("tests/smokes/document_request_parser_smoke.py",)),
    Check("document actions", ("tests/smokes/document_actions_smoke.py",)),
    Check("Office edit actions", ("tests/smokes/document_edit_office_smoke.py",)),
    Check("June 8 iMac regression", ("tests/smokes/imac_june8_regression_smoke.py",)),
    Check("artifact quality", ("tests/smokes/artifact_quality_smoke.py",)),
    Check("Word output quality", ("word_quality_smoke.py",)),
    Check("Word visual QA", ("word_visual_qa_smoke.py",)),
    Check("Word golden artifacts", ("word_golden_artifact_smoke.py",)),
    Check("Word section repair", ("word_section_repair_smoke.py",)),
    Check("HTML render", ("tests/smokes/html_render_smoke.py",)),
    Check("PPTX quality gate", ("tests/smokes/pptx_quality_gate_smoke.py",)),
    Check("PPTX polish review", ("tests/smokes/pptx_polish_review_smoke.py",)),
    Check("Desktop workspace and Excel", ("tests/smokes/desktop_workspace_excel_smoke.py",)),
    Check("waiting-on tracker", ("tests/smokes/waiting_on_smoke.py",)),
    Check("daily cockpit", ("tests/smokes/daily_cockpit_smoke.py",)),
    Check("daily conversation state", ("tests/smokes/daily_conversation_state_smoke.py",)),
    Check("workflow desk", ("workflow_desk_smoke.py",)),
    Check("workflow continue guard", ("workflow_continue_guard_smoke.py",)),
    Check("workspace and drawing actions", ("workspace_drawing_smoke.py",)),
    Check("hardware readiness", ("tests/smokes/hardware_readiness_smoke.py",)),
    Check("hardware/live proof readiness", ("tests/smokes/hardware_live_proof_smoke.py",)),
    Check("live test evidence", ("tests/smokes/live_test_evidence_smoke.py",)),
    Check("live reliability soak", ("tests/smokes/live_reliability_soak_smoke.py",)),
    Check("30-day reliability scorecard", ("tests/smokes/reliability_scorecard_smoke.py",)),
    Check("Mudra prepared only", ("tests/smokes/mudra_prepare_smoke.py",)),
    Check("Omi prepared only", ("tests/smokes/omi_prepare_smoke.py",)),
    Check("Omi context sieve", ("tests/smokes/omi_context_sieve_smoke.py",)),
    Check("permission policy", ("tests/smokes/permission_policy_smoke.py",)),
    Check("safety action commands", ("tests/smokes/safety_action_commands_smoke.py",)),
    Check("security smoke", ("tests/smokes/security_smoke.py",)),
    Check("secret detection", ("tests/smokes/secret_detection_smoke.py",)),
    Check("demo evidence", ("tests/smokes/demo_evidence_smoke.py",)),
    Check("skill usage", ("tests/smokes/skill_usage_smoke.py",)),
    Check("Maya skill creation", ("youtube_skill_creation_maya_smoke.py",)),
    Check("skill learning loop", ("tests/smokes/skill_learning_loop_smoke.py",)),
    Check("skill outcome", ("tests/smokes/skill_outcome_smoke.py",)),
    Check("skill memory", ("tests/smokes/skill_memory_smoke.py",)),
    Check("skill library", ("tests/smokes/skill_library_smoke.py",)),
    Check("weekly skill review", ("weekly_skill_review_smoke.py",)),
    Check("channel adapters", ("tests/smokes/channel_adapter_smoke.py",)),
    Check("honest self improvement", ("tests/smokes/honest_self_improvement_smoke.py",)),
    Check("user model boundary", ("tests/smokes/user_model_boundary_smoke.py",)),
    Check("security manifest", ("tests/smokes/security_manifest_smoke.py",)),
    Check("MCP registry", ("tests/smokes/mcp_registry_smoke.py",)),
    Check("skill import", ("tests/smokes/skill_import_smoke.py",)),
    Check("starter skill catalog", ("tests/smokes/starter_skill_catalog_smoke.py",)),
    Check("skill performance analyzer", ("tests/smokes/skill_performance_analyzer_smoke.py",)),
    Check("Artisan app QA", ("tests/smokes/artisan_app_qa_smoke.py",)),
    Check("Artisan apply-back", ("tests/smokes/artisan_apply_back_smoke.py",)),
    Check("Artisan maker completion", ("tests/smokes/artisan_maker_completion_smoke.py",)),
    Check("Artisan maker template", ("tests/smokes/artisan_maker_template_smoke.py",)),
    Check("Artisan runner", ("tests/smokes/artisan_runner_smoke.py",)),
    Check("Artisan approval gate", ("tests/smokes/artisan_approval_gate_smoke.py",)),
    Check("Maya desk", ("tests/smokes/maya_desk_smoke.py",)),
    Check("memory soak", ("tests/smokes/memory_soak_smoke.py",)),
    Check("screen permission probe", ("tests/smokes/screen_probe.py",), optional=True),
    Check("task lifecycle", ("tests/smokes/task_smoke.py",)),
)
LIVE_CHECKS = (
    Check("live provider text gate", ("tests/smokes/provider_smoke.py", "--stage", "text", "--strict"), live=True),
    Check("live provider vision gate", ("tests/smokes/provider_smoke.py", "--stage", "vision", "--strict"), live=True),
    Check("live provider voice gate", ("tests/smokes/provider_smoke.py", "--stage", "voice", "--strict"), live=True),
)


def main() -> int:
    args = _args()
    checks = list(BASE_CHECKS)
    if args.live_providers:
        checks.extend(LIVE_CHECKS)
    failures = []
    print("== Kampung AI Launch Rehearsal ==")
    for check in checks:
        result = _run(check)
        print(_summary(check, result.returncode))
        if args.verbose or result.returncode != 0 or check.optional:
            _print_tail(result)
        if result.returncode != 0 and not check.optional:
            failures.append(check.name)
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    live_note = "included" if args.live_providers else "skipped"
    print(f"All rehearsal checks passed. Live provider smoke: {live_note}.")
    return 0


def _run(check: Check) -> subprocess.CompletedProcess[str]:
    command = (sys.executable, *check.command)
    env = os.environ.copy()
    env.setdefault("MAYA_TEST_MODE", "1")
    root = Path(__file__).resolve().parent
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(root) if not current_pythonpath else f"{root}{os.pathsep}{current_pythonpath}"
    return subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _summary(check: Check, code: int) -> str:
    status = "ok" if code == 0 else f"needs attention ({code})"
    label = "live " if check.live else ""
    return f"{label}{check.name}: {status}"


def _print_tail(result: subprocess.CompletedProcess[str]) -> None:
    output = "\n".join(part for part in (result.stdout, result.stderr) if part.strip())
    tail = "\n".join(output.splitlines()[-30:])
    if tail:
        print(tail)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Kampung AI launch rehearsal.")
    parser.add_argument("--live-providers", action="store_true", help="Also call live provider APIs.")
    parser.add_argument("--verbose", action="store_true", help="Show output from successful checks.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
