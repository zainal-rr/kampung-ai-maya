from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import aiosqlite

from maya_voice.voice_session_store import (
    latest_voice_session,
    list_today_voice_sessions,
    search_voice_sessions,
    voice_session_turns,
    _voice_session_by_id,
)
from maya_core.workspace_paths import workspace_dir


async def export_voice_session_markdown(db_path: str, session_id: int) -> str:
    session = await _voice_session_by_id(db_path, session_id)
    if not session:
        return ""
    turns = await voice_session_turns(db_path, session_id, limit=500)
    path = _next_export_path(session)
    lines = [
        f"# Maya Voice Session {session_id}",
        "",
        "## Diagnostics",
        "",
        f"- Started: {session.get('started_at') or ''}",
        f"- Ended: {session.get('ended_at') or ''}",
        f"- Close reason: {session.get('close_reason') or ''}",
        f"- Duration seconds: {session.get('duration_seconds') or 0}",
        f"- Input device: {session.get('input_device') or ''}",
        f"- Output device: {session.get('output_device') or ''}",
        f"- Model: {session.get('model') or ''}",
        f"- Voice: {session.get('voice') or ''}",
        f"- Audio errors: {session.get('audio_error_count') or 0}",
        f"- Output resets: {session.get('output_reset_count') or 0}",
        f"- Input chunks captured: {session.get('input_chunks_captured') or 0}",
        f"- Input chunks sent: {session.get('input_chunks_sent') or 0}",
        f"- Input bytes sent: {session.get('input_bytes_sent') or 0}",
        f"- Last input audio at: {session.get('last_input_audio_at') or 0}",
        f"- Last local mic RMS: {session.get('last_local_mic_rms') or 0}",
        f"- Peak local mic RMS: {session.get('peak_local_mic_rms') or 0}",
        f"- Peak local mic RMS since response: {session.get('peak_local_mic_rms_since_response') or 0}",
        f"- Peak local mic RMS since response at: {session.get('peak_local_mic_rms_since_response_at') or 0}",
        f"- Last xAI speech started at: {session.get('last_xai_speech_started_at') or 0}",
        f"- Last user transcript at: {session.get('last_user_transcript_at') or 0}",
        f"- Last response done at: {session.get('last_response_done_at') or 0}",
        "",
        "## Transcript",
        "",
    ]
    if not turns:
        lines.append("_No transcript turns recorded._")
    for turn in turns:
        marker = " interrupted" if turn.get("interrupted") else ""
        role = str(turn["role"]).capitalize()
        timestamp = turn.get("created_at") or ""
        tool = f" [{turn['tool_name']}]" if turn.get("tool_name") else ""
        lines.extend([
            f"### {timestamp} {role}{tool}{marker}",
            "",
            str(turn["content"]).strip(),
            "",
        ])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return str(path)


async def format_last_voice_session(db_path: str) -> str:
    session = await latest_voice_session(db_path)
    if not session:
        return "No iMac voice sessions have been logged yet."
    turns = await voice_session_turns(db_path, int(session["id"]), limit=24)
    header = _session_header(session)
    if not turns:
        return header + "\nTranscript: no turns recorded."
    lines = [header, "Transcript:"]
    for turn in turns[-16:]:
        role = _role_label(turn)
        content = " ".join(str(turn["content"]).split())
        lines.append(f"{role}: {content[:320]}")
    return "\n".join(lines)


async def format_today_voice_sessions(db_path: str) -> str:
    sessions = await list_today_voice_sessions(db_path)
    if not sessions:
        return "No iMac voice sessions logged today."
    lines = ["Today's iMac voice sessions:"]
    for idx, session in enumerate(sessions, start=1):
        lines.append(
            f"{idx}) Session {session['id']} at {session['started_at']} "
            f"reason={session.get('close_reason') or 'running'} "
            f"turns={session.get('turn_count') or 0} "
            f"duration={round(float(session.get('duration_seconds') or 0), 1)}s"
        )
    return "\n".join(lines)


async def format_voice_session_diagnostics(db_path: str) -> str:
    session = await latest_voice_session(db_path)
    if not session:
        return "No iMac voice session diagnostics are available yet."
    return "\n".join(
        [
            f"Voice session diagnostics for session {session['id']}:",
            f"1) close reason: {session.get('close_reason') or 'running'}",
            f"2) duration: {round(float(session.get('duration_seconds') or 0), 1)}s",
            f"3) input device: {session.get('input_device') or 'unknown'}",
            f"4) output device: {session.get('output_device') or 'unknown'}",
            f"5) audio errors: {session.get('audio_error_count') or 0}",
            f"6) output resets: {session.get('output_reset_count') or 0}",
            f"7) transcript count: {session.get('transcript_count') or 0}",
            f"8) export: {session.get('export_path') or 'not exported yet'}",
            f"9) input chunks captured: {session.get('input_chunks_captured') or 0}",
            f"10) input chunks sent: {session.get('input_chunks_sent') or 0}",
            f"11) input bytes sent: {session.get('input_bytes_sent') or 0}",
            f"12) last local mic RMS: {session.get('last_local_mic_rms') or 0}",
            f"13) peak local mic RMS: {session.get('peak_local_mic_rms') or 0}",
            f"14) peak local mic RMS since response: {session.get('peak_local_mic_rms_since_response') or 0}",
            f"15) peak local mic RMS since response at: {session.get('peak_local_mic_rms_since_response_at') or 0}",
            f"16) last xAI speech started at: {session.get('last_xai_speech_started_at') or 0}",
            f"17) last user transcript at: {session.get('last_user_transcript_at') or 0}",
            f"18) last response done at: {session.get('last_response_done_at') or 0}",
        ]
    )


async def format_voice_session_search(db_path: str, query: str) -> str:
    rows = await search_voice_sessions(db_path, query)
    if not rows:
        return f"No iMac voice session transcript matched {query}."
    lines = [f"Voice session search for {query}:"]
    for idx, row in enumerate(rows, start=1):
        role = _role_label(row)
        content = " ".join(str(row["content"]).split())[:260]
        lines.append(f"{idx}) session {row['session_id']} {role}: {content}")
    return "\n".join(lines)


async def export_latest_voice_session(db_path: str) -> str:
    session = await latest_voice_session(db_path)
    if not session:
        return "No iMac voice sessions have been logged yet."
    path = await export_voice_session_markdown(db_path, int(session["id"]))
    if not path:
        return "I could not export the last voice session."
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE voice_sessions SET export_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (path, session["id"]),
        )
        await db.commit()
    return f"Exported last iMac voice session:\n{path}"


def _next_export_path(session: dict) -> Path:
    folder = workspace_dir("voice_sessions", create=True)
    raw = str(session.get("started_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    slug = re.sub(r"[^0-9A-Za-z]+", "-", raw).strip("-")[:18] or datetime.now().strftime("%Y-%m-%d-%H%M")
    base = f"voice-session-{slug}"
    version = 1
    while True:
        path = folder / f"{base}-v{version}.md"
        if not path.exists():
            return path
        version += 1


def _session_header(session: dict) -> str:
    return (
        f"Voice session {session['id']} "
        f"started={session.get('started_at') or ''} "
        f"ended={session.get('ended_at') or ''} "
        f"reason={session.get('close_reason') or 'running'} "
        f"duration={round(float(session.get('duration_seconds') or 0), 1)}s"
    )


def _role_label(turn: dict) -> str:
    label = str(turn.get("role") or "").capitalize() or "System"
    if turn.get("tool_name"):
        label += f" [{turn['tool_name']}]"
    if turn.get("interrupted"):
        label += " interrupted"
    return label
