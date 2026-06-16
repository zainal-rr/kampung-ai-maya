from __future__ import annotations

import aiosqlite

from maya_voice.voice_session_store import (
    init_voice_session_log_db,
    latest_voice_session,
    list_today_voice_sessions,
    record_voice_turn,
    search_voice_sessions,
    start_voice_session,
    voice_session_turns,
)
from maya_voice.voice_session_format import (
    export_latest_voice_session,
    export_voice_session_markdown,
    format_last_voice_session,
    format_today_voice_sessions,
    format_voice_session_diagnostics,
    format_voice_session_search,
)


async def finish_voice_session(
    db_path: str,
    session_id: int | None,
    *,
    close_reason: str,
    duration_seconds: float,
    input_device: str = "",
    output_device: str = "",
    audio_error_count: int = 0,
    output_reset_count: int = 0,
    input_chunks_captured: int = 0,
    input_chunks_sent: int = 0,
    input_bytes_sent: int = 0,
    last_input_audio_at: float = 0,
    last_local_mic_rms: float = 0,
    peak_local_mic_rms: float = 0,
    peak_local_mic_rms_since_response: float = 0,
    peak_local_mic_rms_since_response_at: float = 0,
    last_xai_speech_started_at: float = 0,
    last_user_transcript_at: float = 0,
    last_response_done_at: float = 0,
    transcript_count: int = 0,
) -> str:
    if not session_id:
        return ""
    await init_voice_session_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE voice_sessions
            SET ended_at = CURRENT_TIMESTAMP,
                close_reason = ?,
                duration_seconds = ?,
                input_device = COALESCE(NULLIF(?, ''), input_device),
                output_device = COALESCE(NULLIF(?, ''), output_device),
                audio_error_count = ?,
                output_reset_count = ?,
                input_chunks_captured = ?,
                input_chunks_sent = ?,
                input_bytes_sent = ?,
                last_input_audio_at = ?,
                last_local_mic_rms = ?,
                peak_local_mic_rms = ?,
                peak_local_mic_rms_since_response = ?,
                peak_local_mic_rms_since_response_at = ?,
                last_xai_speech_started_at = ?,
                last_user_transcript_at = ?,
                last_response_done_at = ?,
                transcript_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                close_reason,
                duration_seconds,
                input_device,
                output_device,
                audio_error_count,
                output_reset_count,
                input_chunks_captured,
                input_chunks_sent,
                input_bytes_sent,
                last_input_audio_at,
                last_local_mic_rms,
                peak_local_mic_rms,
                peak_local_mic_rms_since_response,
                peak_local_mic_rms_since_response_at,
                last_xai_speech_started_at,
                last_user_transcript_at,
                last_response_done_at,
                transcript_count,
                session_id,
            ),
        )
        await db.commit()
    export_path = await export_voice_session_markdown(db_path, session_id)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE voice_sessions SET export_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (export_path, session_id),
        )
        await db.commit()
    return export_path
