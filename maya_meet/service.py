from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from aiohttp import web

from maya_meet.approval import claim_approved_meeting_actions, mark_meeting_action_execution
from maya_meet.actions import MeetingActionRunner
from maya_meet.audio_wake import RecallAudioWakeState, audio_bytes_from_recall_message, timestamp_from_recall_payload
from maya_meet.config import RecallConfig, recall_config_from_env
from maya_meet.context_answerer import build_meeting_context_answerer
from maya_meet.output_media import MeetOutputQueue
from maya_meet.recall_events import handle_recall_event
from maya_meet.responder import MeetM1Responder
from maya_meet.store import init_meet_db, update_meet_session


class MeetRuntime:
    def __init__(
        self,
        *,
        db_path: str,
        config: RecallConfig | None = None,
        callback_port: int | None = None,
        output_port: int | None = None,
        assistant=None,
        m2_enabled: bool | None = None,
    ):
        self.db_path = db_path
        self.config = config or recall_config_from_env()
        missing = self.config.missing_fields()
        if missing:
            raise ValueError("Maya Meet config missing: " + ", ".join(missing))
        self.callback_port = callback_port or int(os.getenv("MAYA_MEET_CALLBACK_PORT", "8788"))
        self.output_port = output_port or int(os.getenv("MAYA_MEET_OUTPUT_PORT", "8789"))
        self.output_queue = MeetOutputQueue(token=self.config.output_media_token)
        self.audio_wake_state = RecallAudioWakeState.from_env()
        self.m2_enabled = bool(m2_enabled) if m2_enabled is not None else os.getenv("MAYA_MEET_M2_ACTIONS", "0") == "1"
        self.action_runner = MeetingActionRunner(db_path=db_path, assistant=assistant)
        self.responder = MeetM1Responder(
            db_path=db_path,
            output_queue=self.output_queue,
            answerer=build_meeting_context_answerer(db_path),
            audio_wake_state=self.audio_wake_state,
            action_runner=self.action_runner,
            m2_enabled=self.m2_enabled,
        )
        self.logger = logging.getLogger("maya.meet")

    async def run(self) -> None:
        await init_meet_db(self.db_path)
        app = create_meet_app(
            db_path=self.db_path,
            config=self.config,
            output_queue=self.output_queue,
            responder=self.responder,
            audio_wake_state=self.audio_wake_state,
            action_runner=self.action_runner,
            m2_enabled=self.m2_enabled,
        )
        runner = web.AppRunner(app)
        await runner.setup()
        sites = [
            web.TCPSite(runner, "127.0.0.1", self.callback_port),
            web.TCPSite(runner, "127.0.0.1", self.output_port),
        ]
        for site in sites:
            await site.start()
        self.logger.info("Maya Meet service listening on callback=%s output=%s", self.callback_port, self.output_port)
        approval_task = asyncio.create_task(_approved_action_monitor(self.db_path, self.action_runner, self.logger))
        try:
            await asyncio.Event().wait()
        finally:
            approval_task.cancel()
            await runner.cleanup()


def create_meet_app(
    *,
    db_path: str,
    config: RecallConfig,
    output_queue: MeetOutputQueue,
    responder: MeetM1Responder | None = None,
    audio_wake_state: RecallAudioWakeState | None = None,
    action_runner: MeetingActionRunner | None = None,
    m2_enabled: bool = False,
) -> web.Application:
    app = web.Application()
    audio_wake_state = audio_wake_state or RecallAudioWakeState.from_env()
    responder = responder or MeetM1Responder(
        db_path=db_path,
        output_queue=output_queue,
        audio_wake_state=audio_wake_state,
        action_runner=action_runner,
        m2_enabled=m2_enabled,
    )

    async def recall_health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "maya_meet_callback"})

    async def output_health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "maya_meet_output"})

    async def webhook(request: web.Request) -> web.Response:
        raw = await request.read()
        session_id = _session_id_from_request(request, raw)
        result = await handle_recall_event(
            db_path,
            session_id=session_id,
            secret=config.verification_secret,
            headers=request.headers,
            raw_payload=raw,
        )
        if result["status"] == "accepted" and result.get("event_type") == "transcript.data":
            payload = _json_payload(raw)
            asyncio.create_task(_respond_and_record(db_path, session_id, responder, payload))
        status = 202 if result["status"] in {"accepted", "duplicate"} else 401
        return web.json_response(result, status=status)

    async def audio_wake(request: web.Request) -> web.StreamResponse:
        if request.query.get("token", "") != config.output_media_token:
            return web.Response(status=403, text="forbidden")
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            if message.type == web.WSMsgType.BINARY:
                result = audio_wake_state.ingest_pcm_bytes(bytes(message.data))
            elif message.type == web.WSMsgType.TEXT:
                payload = _json_payload(message.data)
                result = audio_wake_state.ingest_pcm_bytes(
                    audio_bytes_from_recall_message(payload or message.data),
                    audio_timestamp=timestamp_from_recall_payload(payload) if payload else None,
                )
            else:
                continue
            if result.get("status") == "accepted":
                logging.getLogger("maya.meet").info("meet audio wake detected result=%s", result)
            await ws.send_json(result)
        return ws

    async def output_page(request: web.Request) -> web.Response:
        token = request.query.get("token", "")
        if token != output_queue.token:
            return web.Response(status=403, text="forbidden")
        return web.Response(text=_output_html(token), content_type="text/html")

    async def next_audio(request: web.Request) -> web.Response:
        if request.query.get("token", "") != output_queue.token:
            return web.Response(status=403, text="forbidden")
        item = await output_queue.next_utterance(request.query.get("token", ""))
        return web.json_response({"utterance": item})

    async def audio(request: web.Request) -> web.StreamResponse:
        path = await output_queue.audio_path(request.match_info.get("utterance_id", ""), request.query.get("token", ""))
        if path is None:
            return web.Response(status=404, text="not found")
        return web.FileResponse(path)

    async def playback(request: web.Request) -> web.Response:
        if request.query.get("token", "") != output_queue.token:
            return web.Response(status=403, text="forbidden")
        session_id = request.query.get("session_id", "") or "recall_default"
        payload = await _request_json(request)
        status = str(payload.get("status") or "unknown")[:80]
        reason = str(payload.get("reason_code") or status)[:120]
        if status == "playback_started":
            audio_wake_state.begin_playback_suppression(max_seconds=120.0)
        elif status in {"playback_ended", "playback_failed"}:
            audio_wake_state.end_playback_suppression(tail_seconds=2.0)
        session_status = "speaking" if status == "playback_started" else "output_media_failed" if status == "playback_failed" else "live"
        await update_meet_session(db_path, session_id, output_media_status=reason, status=session_status)
        return web.json_response({"status": "accepted"})

    app.router.add_get("/recall/health", recall_health)
    app.router.add_post("/recall/webhook", webhook)
    app.router.add_get("/recall/audio-wake", audio_wake)
    app.router.add_get("/meet/output/health", output_health)
    app.router.add_get("/meet/output", output_page)
    app.router.add_get("/meet/output/next", next_audio)
    app.router.add_get("/meet/output/audio/{utterance_id}", audio)
    app.router.add_post("/meet/output/playback", playback)
    return app


def _session_id_from_request(request: web.Request, raw: bytes) -> str:
    if request.query.get("session_id"):
        return request.query["session_id"]
    payload = _json_payload(raw)
    return str(_maya_session_id(payload) or "recall_default")


def _json_payload(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _maya_session_id(payload: dict[str, Any]) -> str:
    candidates: list[dict[str, Any]] = []
    if isinstance(payload.get("metadata"), dict):
        candidates.append(payload["metadata"])
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    for key in ("bot", "recording"):
        nested = data.get(key) if isinstance(data.get(key), dict) else {}
        metadata = nested.get("metadata") if isinstance(nested.get("metadata"), dict) else {}
        candidates.append(metadata)
    for metadata in candidates:
        if metadata.get("maya_session_id"):
            return str(metadata["maya_session_id"])
    return str(payload.get("maya_session_id") or "")


def _output_html(token: str) -> str:
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Maya Meet Output</title></head>
<body>
<script>
const token = {json.dumps(token)};
const params = new URLSearchParams(window.location.search);
const sessionId = params.get('session_id') || 'recall_default';
async function report(status, reason) {{
  try {{
    await fetch('/meet/output/playback?token=' + encodeURIComponent(token) + '&session_id=' + encodeURIComponent(sessionId), {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{status: status, reason_code: reason || status}})
    }});
  }} catch (error) {{
    console.error('maya output report failed', error);
  }}
}}
async function poll() {{
  try {{
    const response = await fetch('/meet/output/next?token=' + encodeURIComponent(token), {{cache: 'no-store'}});
    const data = await response.json();
    if (data.utterance && data.utterance.audio_url) {{
      const audio = new Audio(data.utterance.audio_url);
      audio.addEventListener('ended', () => {{
        report('playback_ended', data.utterance.id || 'playback_ended');
      }}, {{once: true}});
      audio.addEventListener('error', () => {{
        report('playback_failed', data.utterance.id || 'playback_failed');
      }}, {{once: true}});
      await audio.play();
      await report('playback_started', data.utterance.id || 'playback_started');
    }}
  }} catch (error) {{
    await report('playback_failed', String(error));
    console.error('maya output poll failed', error);
  }} finally {{
    setTimeout(poll, 1000);
  }}
}}
poll();
</script>
</body>
</html>"""


async def _respond_and_record(
    db_path: str,
    session_id: str,
    responder: MeetM1Responder,
    payload: dict[str, Any],
) -> None:
    result = await responder.process_verified_event(payload)
    reason = str(result.get("reason_code") or result.get("status") or "")
    if reason:
        status = "response_queued" if result.get("status") == "queued" else "live"
        await update_meet_session(db_path, session_id, output_media_status=reason, status=status)


async def _approved_action_monitor(db_path: str, action_runner: MeetingActionRunner, logger: logging.Logger) -> None:
    while True:
        try:
            for item in await claim_approved_meeting_actions(db_path):
                payload = item["payload"]
                action_id = item["action_id"]
                try:
                    action_class = str(payload.get("action_class") or "unknown_action")
                    if action_class == "private_lookup":
                        action_class = "lookup"
                    executed = await action_runner.run(
                        request=str(payload.get("request") or ""),
                        action_class=action_class,
                        session_id=str(payload.get("session_id") or ""),
                    )
                    status = "executed" if executed.status in {"completed", "needs_clarification"} else "execution_failed"
                    await mark_meeting_action_execution(
                        db_path,
                        action_id,
                        status=status,
                        detail=f"{executed.reason_code}: {executed.spoken}",
                    )
                except Exception as exc:
                    logger.exception("Approved Meet action execution failed for %s", action_id)
                    await mark_meeting_action_execution(
                        db_path,
                        action_id,
                        status="execution_failed",
                        detail=f"{exc.__class__.__name__}: {str(exc)[:300]}",
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Meet approved-action monitor failed")
        await asyncio.sleep(1.0)


async def _request_json(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
