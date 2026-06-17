from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import re
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOTS = (
    "maya_core",
    "maya_browser",
    "maya_voice",
    "maya_documents",
    "maya_telegram",
    "harness_helpers",
    "office_drafter_helpers",
    "office_pptx_helpers",
    "pptx_helpers",
    "word_helpers",
)

COMMAND_PATTERNS = (
    re.compile(r"\bsubprocess\.run\("),
    re.compile(r"\basyncio\.create_subprocess_(?:exec|shell)\("),
    re.compile(r"\bsubprocess\.Popen\("),
    re.compile(r"\bos\.system\("),
    re.compile(r"\bos\.remove\("),
    re.compile(r"\bshutil\.rmtree\("),
    re.compile(r"runner\s*=\s*subprocess\.run"),
    re.compile(r"asyncio\.to_thread\(\s*subprocess\.run"),
)
DELETE_PATTERN = re.compile(r"\.unlink\b")

ALLOWED_COMMAND_CALLS = {
    ("maya_core/execution_broker.py", "run_command"): "broker implementation",
    ("maya_core/execution_broker.py", "run_command_async"): "broker implementation",
    ("maya_core/speech_input.py", "MacOSMicTranscriber._record_clip"): "interactive ffmpeg capture until broker streaming mode exists",
    ("maya_voice/voice_agent_audio.py", "VoiceAgentAudioCapture._record_pcm"): "interactive ffmpeg capture until broker streaming mode exists",
    ("maya_core/utils.py", "OSBridge._run_applescript"): "explicit GUI AppleScript; governed, not OS-contained",
    ("maya_core/utils.py", "OSBridge._launch_app"): "explicit GUI app launch; governed, not OS-contained",
    ("maya_core/utils.py", "OSBridge.open_file"): "explicit GUI file open; governed, not OS-contained",
    ("maya_core/service_install.py", "ensure_running"): "explicit launchd service install path",
    ("maya_core/service_install.py", "status"): "explicit launchd service status path",
    ("maya_core/service_install.py", "is_loaded"): "explicit launchd service status path",
    ("maya_core/service_install.py", "status_weekly_memory"): "explicit launchd service status path",
    ("maya_core/service_install.py", "status_nightly_memory"): "explicit launchd service status path",
    ("maya_core/service_install.py", "restart"): "explicit launchd service restart path",
    ("maya_core/service_install.py", "restart_weekly_memory"): "explicit launchd service restart path",
    ("maya_core/service_install.py", "restart_nightly_memory"): "explicit launchd service restart path",
    ("maya_core/service_install.py", "bootout"): "explicit launchd service stop path",
    ("maya_core/service_install.py", "bootout_weekly_memory"): "explicit launchd service stop path",
    ("maya_core/service_install.py", "bootout_nightly_memory"): "explicit launchd service stop path",
    ("maya_core/maya_eye_preview.py", "start_preview"): "persistent GUI preview process",
}

ALLOWED_DELETE_CALLS = {
    ("maya_core/artisan_maker_quality.py", "_render_preview"): "temporary generated Blender preview script cleanup",
    ("maya_core/camera_adapter.py", "ExternalCameraAdapter._process"): "Maya-owned camera event queue cleanup",
    ("maya_core/mudra_adapter.py", "MudraAdapter._process"): "Maya-owned Mudra event queue cleanup",
    ("maya_core/maya_eye_overlay.py", "clear_preview_target"): "Maya-owned overlay PID cleanup",
    ("maya_core/maya_eye_preview.py", "start_preview"): "Maya-owned preview PID cleanup",
    ("maya_core/maya_eye_preview.py", "stop_preview"): "Maya-owned preview PID cleanup",
    ("maya_core/maya_eye_preview.py", "run_preview"): "Maya-owned preview PID cleanup",
    ("maya_core/rehearsal.py", "main"): "temporary rehearsal database cleanup",
    ("maya_core/screen_service.py", "MacScreenService.capture_once"): "temporary screen capture file cleanup",
    ("maya_core/service_install.py", "uninstall"): "explicit launchd plist uninstall path",
    ("maya_core/service_install.py", "uninstall_weekly_memory"): "explicit launchd plist uninstall path",
    ("maya_core/service_install.py", "uninstall_nightly_memory"): "explicit launchd plist uninstall path",
    ("maya_core/sieve.py", "SieveNode.process_file"): "contained Omi watch-directory event cleanup",
    ("maya_documents/document_actions_word.py", "DocumentWordMixin._edit_latest_document"): "Maya-owned failed Word edit copy cleanup",
    ("maya_documents/document_actions_word.py", "DocumentWordMixin._simple_word_edit"): "Maya-owned failed Word edit copy cleanup",
    ("maya_documents/document_actions_office.py", "DocumentOfficeMixin._restore_failed_edit"): "Maya-owned failed Office edit copy cleanup",
    ("maya_telegram/telegram_delivery.py", "send_text"): "Maya-owned generated image cleanup",
    ("maya_telegram/telegram_delivery.py", "send_speech"): "Maya-owned generated voice-note cleanup",
    ("maya_voice/voice.py", "VoiceNode._render_with_xai"): "Maya-owned generated speech file cleanup",
    ("maya_voice/voice.py", "VoiceNode._remove_file"): "Maya-owned generated speech file cleanup",
    ("maya_voice/xai_voice_agent.py", "XaiRealtimeVoiceAgentTransport._play_pcm_audio"): "Maya-owned generated speech file cleanup",
}


def main() -> None:
    command_violations: list[str] = []
    delete_violations: list[str] = []
    for rel_path, line_no, line, function_name in _iter_runtime_lines():
        if any(pattern.search(line) for pattern in COMMAND_PATTERNS):
            if (rel_path, function_name) not in ALLOWED_COMMAND_CALLS:
                command_violations.append(f"{rel_path}:{line_no}:{function_name}: {line.strip()}")
        if DELETE_PATTERN.search(line):
            if (rel_path, function_name) not in ALLOWED_DELETE_CALLS:
                delete_violations.append(f"{rel_path}:{line_no}:{function_name}: {line.strip()}")
    if command_violations or delete_violations:
        detail = "\n".join(command_violations + delete_violations)
        raise AssertionError(f"Execution broker bypasses found:\n{detail}")
    print("execution_broker_static_smoke: ok")


def _iter_runtime_lines():
    for root in RUNTIME_ROOTS:
        folder = ROOT / root
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            function_ranges = _function_ranges(path)
            for line_no, line in enumerate(path.read_text("utf-8", errors="replace").splitlines(), 1):
                function_name = next((name for start, end, name in function_ranges if start <= line_no <= end), "<module>")
                yield rel, line_no, line, function_name


def _function_ranges(path: Path) -> list[tuple[int, int, str]]:
    tree = ast.parse(path.read_text("utf-8", errors="replace"))
    ranges: list[tuple[int, int, str]] = []

    def visit(node: ast.AST, prefix: str = "") -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ranges.append((node.lineno, getattr(node, "end_lineno", node.lineno), prefix + node.name))
            return
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                visit(child, prefix + node.name + ".")
            return
        for child in ast.iter_child_nodes(node):
            visit(child, prefix)

    visit(tree)
    return ranges


if __name__ == "__main__":
    main()
