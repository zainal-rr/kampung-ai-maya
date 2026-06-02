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
    Check("service install", ("service_install_smoke.py",)),
    Check("wake and activation", ("activation_smoke.py",)),
    Check("audio device resolution", ("audio_device_resolution_smoke.py",)),
    Check("voice agent session", ("voice_agent_session_smoke.py",)),
    Check("hotkey voice channel", ("hotkey_voice_channel_smoke.py",)),
    Check("xAI realtime stream", ("xai_realtime_stream_smoke.py",)),
    Check("voice session log", ("voice_session_log_smoke.py",)),
    Check("iMac voice policy", ("imac_voice_policy_smoke.py",)),
    Check("xAI voice adapter payload", ("xai_voice_agent_smoke.py",)),
    Check("route ledger", ("route_tracker_smoke.py",)),
    Check("cost ledger", ("cost_tracker_smoke.py",)),
    Check("weather lookup", ("weather_lookup_smoke.py",)),
    Check("provider readiness", ("provider_readiness_smoke.py",)),
    Check("provider capabilities", ("provider_capabilities_smoke.py",)),
    Check("complex planning", ("complex_plan_smoke.py",)),
    Check("delivery redaction", ("delivery_redaction_smoke.py",)),
    Check("workflow persistence", ("workflow_persistence_smoke.py",)),
    Check("harness store", ("harness_store_smoke.py",)),
    Check("harness graph", ("harness_graph_smoke.py",)),
    Check("harness native checkpoint resume", ("harness_native_checkpoint_resume_smoke.py",)),
    Check("harness idempotency", ("harness_idempotency_smoke.py",)),
    Check("harness approval checkpoint", ("harness_approval_checkpoint_smoke.py",)),
    Check("harness multi checkpoint resume", ("harness_multi_checkpoint_resume_smoke.py",)),
    Check("harness document replay", ("harness_document_replay_smoke.py",)),
    Check("harness skill replay", ("harness_skill_replay_smoke.py",)),
    Check("harness self-heal replay", ("harness_self_heal_replay_smoke.py",)),
    Check("harness background checkpoint", ("harness_background_checkpoint_smoke.py",)),
    Check("harness resume", ("harness_resume_smoke.py",)),
    Check("harness resume detail", ("harness_resume_detail_smoke.py",)),
    Check("harness multi resume", ("harness_multi_resume_smoke.py",)),
    Check("harness artifacts", ("harness_artifact_tracking_smoke.py",)),
    Check("harness grounding", ("harness_grounding_smoke.py",)),
    Check("harness browser", ("harness_browser_smoke.py",)),
    Check("harness screen", ("harness_screen_smoke.py",)),
    Check("session compactor", ("session_compactor_smoke.py",)),
    Check("memory control", ("memory_control_smoke.py",)),
    Check("canonical memory", ("canonical_memory_smoke.py",)),
    Check("retention policy", ("retention_policy_smoke.py",)),
    Check("project mode", ("project_mode_smoke.py",)),
    Check("hardening flow", ("hardening_flow_smoke.py",)),
    Check("self healing", ("self_healing_smoke.py",)),
    Check("self heal loop", ("self_heal_loop_smoke.py",)),
    Check("self heal report isolation", ("self_heal_report_isolation_smoke.py",)),
    Check("quantum advisory", ("quantum_advisory_smoke.py",)),
    Check("quantum leaf boundary", ("quantum_leaf_smoke.py",)),
    Check("weekly memory dry run", ("weekly_memory_smoke.py",)),
    Check("weekly memory provider path", ("weekly_memory_provider_path_smoke.py",)),
    Check("learning pipeline", ("learning_smoke.py",)),
    Check("golden conversation eval", ("golden_conversation_eval.py",)),
    Check("Telegram commands", ("telegram_commands_smoke.py",)),
    Check("Telegram routing", ("telegram_routing_smoke.py",)),
    Check("Telegram delivery files", ("telegram_delivery_file_smoke.py",)),
    Check("Telegram voice input", ("telegram_voice_input_smoke.py",)),
    Check("Telegram voice reply policy", ("telegram_voice_reply_policy_smoke.py",)),
    Check("camera command gate", ("vision_command_smoke.py",)),
    Check("screen sight command", ("screen_command_smoke.py",)),
    Check("app interaction", ("app_interaction_smoke.py",)),
    Check("app command full path", ("app_command_fullpath_smoke.py",)),
    Check("browser control", ("browser_control_smoke.py",)),
    Check("frequent sites", ("frequent_sites_smoke.py",)),
    Check("browser site skills", ("browser_site_skills_smoke.py",)),
    Check("browser agent maturity", ("browser_agent_maturity_smoke.py",)),
    Check("web actions", ("web_actions_smoke.py",)),
    Check("iMac workflows", ("imac_workflows_smoke.py",)),
    Check("artifact parameter questions", ("artifact_parameters_smoke.py",)),
    Check("artifact preflight", ("artifact_preflight_smoke.py",)),
    Check("document request parser", ("document_request_parser_smoke.py",)),
    Check("document actions", ("document_actions_smoke.py",)),
    Check("Office edit actions", ("document_edit_office_smoke.py",)),
    Check("artifact quality", ("artifact_quality_smoke.py",)),
    Check("Word output quality", ("word_quality_smoke.py",)),
    Check("Word golden artifacts", ("word_golden_artifact_smoke.py",)),
    Check("Word section repair", ("word_section_repair_smoke.py",)),
    Check("HTML render", ("html_render_smoke.py",)),
    Check("PPTX quality gate", ("pptx_quality_gate_smoke.py",)),
    Check("PPTX polish review", ("pptx_polish_review_smoke.py",)),
    Check("Desktop workspace and Excel", ("desktop_workspace_excel_smoke.py",)),
    Check("waiting-on tracker", ("waiting_on_smoke.py",)),
    Check("daily cockpit", ("daily_cockpit_smoke.py",)),
    Check("daily conversation state", ("daily_conversation_state_smoke.py",)),
    Check("workflow desk", ("workflow_desk_smoke.py",)),
    Check("workflow continue guard", ("workflow_continue_guard_smoke.py",)),
    Check("workspace and drawing actions", ("workspace_drawing_smoke.py",)),
    Check("hardware readiness", ("hardware_readiness_smoke.py",)),
    Check("Mudra prepared only", ("mudra_prepare_smoke.py",)),
    Check("Omi prepared only", ("omi_prepare_smoke.py",)),
    Check("Omi context sieve", ("omi_context_sieve_smoke.py",)),
    Check("permission policy", ("permission_policy_smoke.py",)),
    Check("safety action commands", ("safety_action_commands_smoke.py",)),
    Check("security smoke", ("security_smoke.py",)),
    Check("secret detection", ("secret_detection_smoke.py",)),
    Check("skill usage", ("skill_usage_smoke.py",)),
    Check("skill learning loop", ("skill_learning_loop_smoke.py",)),
    Check("skill outcome", ("skill_outcome_smoke.py",)),
    Check("skill memory", ("skill_memory_smoke.py",)),
    Check("skill library", ("skill_library_smoke.py",)),
    Check("weekly skill review", ("weekly_skill_review_smoke.py",)),
    Check("channel adapters", ("channel_adapter_smoke.py",)),
    Check("honest self improvement", ("honest_self_improvement_smoke.py",)),
    Check("user model boundary", ("user_model_boundary_smoke.py",)),
    Check("security manifest", ("security_manifest_smoke.py",)),
    Check("MCP registry", ("mcp_registry_smoke.py",)),
    Check("skill import", ("skill_import_smoke.py",)),
    Check("starter skill catalog", ("starter_skill_catalog_smoke.py",)),
    Check("skill performance analyzer", ("skill_performance_analyzer_smoke.py",)),
    Check("Artisan app QA", ("artisan_app_qa_smoke.py",)),
    Check("Artisan apply-back", ("artisan_apply_back_smoke.py",)),
    Check("Artisan maker completion", ("artisan_maker_completion_smoke.py",)),
    Check("Artisan maker template", ("artisan_maker_template_smoke.py",)),
    Check("Artisan runner", ("artisan_runner_smoke.py",)),
    Check("Artisan approval gate", ("artisan_approval_gate_smoke.py",)),
    Check("Maya desk", ("maya_desk_smoke.py",)),
    Check("memory soak", ("memory_soak_smoke.py",)),
    Check("screen permission probe", ("screen_probe.py",), optional=True),
    Check("task lifecycle", ("task_smoke.py",)),
)
LIVE_CHECKS = (
    Check("live provider text gate", ("provider_smoke.py", "--stage", "text", "--strict"), live=True),
    Check("live provider vision gate", ("provider_smoke.py", "--stage", "vision", "--strict"), live=True),
    Check("live provider voice gate", ("provider_smoke.py", "--stage", "voice", "--strict"), live=True),
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
    return subprocess.run(
        command,
        cwd=Path(__file__).resolve().parent,
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
