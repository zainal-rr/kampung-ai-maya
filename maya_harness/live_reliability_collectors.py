from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path


@dataclass(frozen=True)
class InferredReliabilityCounts:
    imac_voice_turns: int = 0
    file_deliveries: int = 0
    browser_workflows: int = 0
    uptime_minutes: int = 0
    voice_timeouts: int = 0
    file_delivery_failures: int = 0
    browser_failures: int = 0


_VOICE_HEADING_RE = re.compile(r"^### \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ([^\n]+)$", re.MULTILINE)
_TOOL_BLOCK_RE = re.compile(r"^### [^\n]* Tool \[(?P<tool>[^\]]+)\]\n+(?P<body>.*?)(?=^### |\Z)", re.MULTILINE | re.DOTALL)
_LOG_TIME_RE = re.compile(r"^(?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<message>.*)$")


def infer_reliability_counts(
    day: date,
    *,
    repo_root: Path,
    maya_root: Path,
    now: datetime | None = None,
) -> InferredReliabilityCounts:
    voice_files = sorted((maya_root / "voice_sessions").glob(f"voice-session-{day.isoformat()}-*.md"))
    voice_turns = 0
    file_deliveries = 0
    browser_workflows = 0
    voice_timeouts = 0
    file_failures = 0
    browser_failures = 0
    for path in voice_files:
        text = _read_text(path)
        voice_turns += _count_user_turns(text)
        browser_workflows += _count_tool_calls(text, "run_browser_skill")
        file_deliveries += _count_tool_calls(text, "start_maya_work")
        browser_failures += _count_tool_failures(text, "run_browser_skill")
        file_failures += _count_tool_failures(text, "start_maya_work")
        voice_timeouts += _count_voice_timeout(text)
    uptime_minutes = _infer_controller_uptime(day, repo_root / "logs" / "kampung_ai_controller.log", now=now)
    return InferredReliabilityCounts(
        imac_voice_turns=voice_turns,
        file_deliveries=file_deliveries,
        browser_workflows=browser_workflows,
        uptime_minutes=uptime_minutes,
        voice_timeouts=voice_timeouts,
        file_delivery_failures=file_failures,
        browser_failures=browser_failures,
    )


def _count_user_turns(text: str) -> int:
    turns = 0
    previous_user = False
    for match in _VOICE_HEADING_RE.finditer(text):
        role = match.group(1).strip()
        is_user = role == "User"
        if is_user and not previous_user:
            turns += 1
        previous_user = is_user
    return turns


def _count_tool_calls(text: str, tool_name: str) -> int:
    return sum(1 for tool, body in _iter_tool_blocks(text) if tool == tool_name and body.lstrip().startswith("call "))


def _count_tool_failures(text: str, tool_name: str) -> int:
    failures = 0
    for tool, body in _iter_tool_blocks(text):
        if tool != tool_name or not body.lstrip().startswith("result "):
            continue
        lowered = body.lower()
        if any(marker in lowered for marker in ("status: failed", "browser_bridge_unavailable", "browser_tool_timeout", "hard_blocked")):
            failures += 1
    return failures


def _iter_tool_blocks(text: str) -> list[tuple[str, str]]:
    return [(match.group("tool"), match.group("body")) for match in _TOOL_BLOCK_RE.finditer(text)]


def _count_voice_timeout(text: str) -> int:
    close_reason = re.search(r"^- Close reason:\s*(.+)$", text, re.MULTILINE)
    if close_reason and close_reason.group(1).strip() not in {"manual_stop", "normal", "completed"}:
        return 1
    audio_errors = re.search(r"^- Audio errors:\s*(\d+)$", text, re.MULTILINE)
    return 1 if audio_errors and int(audio_errors.group(1)) > 0 else 0


def _infer_controller_uptime(day: date, log_path: Path, *, now: datetime | None = None) -> int:
    if not log_path.exists():
        return 0
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)
    if now is not None and now.date() == day:
        end = min(end, now.replace(tzinfo=None))
    running = False
    interval_start: datetime | None = None
    total = timedelta()
    for line in _read_text(log_path).splitlines():
        parsed = _parse_controller_event(line)
        if parsed is None:
            continue
        stamp, event = parsed
        if stamp > end:
            break
        if stamp < start:
            if event == "running":
                running = True
                interval_start = start
            elif event == "quitting":
                running = False
                interval_start = None
            continue
        if event == "running" and not running:
            running = True
            interval_start = stamp
        elif event == "quitting" and running:
            if interval_start is not None:
                total += max(timedelta(), stamp - interval_start)
            running = False
            interval_start = None
    if running and interval_start is not None and end > interval_start:
        total += end - interval_start
    return max(0, min(1440, int(total.total_seconds() // 60)))


def _parse_controller_event(line: str) -> tuple[datetime, str] | None:
    match = _LOG_TIME_RE.match(line)
    if not match:
        return None
    message = match.group("message")
    if "Kampung AI is running" in message:
        event = "running"
    elif "Kampung AI is quitting" in message:
        event = "quitting"
    else:
        return None
    return datetime.strptime(match.group("stamp"), "%Y-%m-%d %H:%M:%S"), event


def _read_text(path: Path) -> str:
    try:
        return path.read_text("utf-8", errors="replace")
    except OSError:
        return ""
