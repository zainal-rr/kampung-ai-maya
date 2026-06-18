from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from aiohttp import web

from maya_meet.config import RecallConfig, recall_config_from_env
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
    ):
        self.db_path = db_path
        self.config = config or recall_config_from_env()
        missing = self.config.missing_fields()
        if missing:
            raise ValueError("Maya Meet config missing: " + ", ".join(missing))
        self.callback_port = callback_port or int(os.getenv("MAYA_MEET_CALLBACK_PORT", "8788"))
        self.output_port = output_port or int(os.getenv("MAYA_MEET_OUTPUT_PORT", "8789"))
        self.output_queue = MeetOutputQueue(token=self.config.output_media_token)
        self.responder = MeetM1Responder(db_path=db_path, output_queue=self.output_queue)
        self.logger = logging.getLogger("maya.meet")

    async def run(self) -> None:
        await init_meet_db(self.db_path)
        app = create_meet_app(
            db_path=self.db_path,
            config=self.config,
            output_queue=self.output_queue,
            responder=self.responder,
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
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()


def create_meet_app(
    *,
    db_path: str,
    config: RecallConfig,
    output_queue: MeetOutputQueue,
    responder: MeetM1Responder | None = None,
) -> web.Application:
    app = web.Application()
    responder = responder or MeetM1Responder(db_path=db_path, output_queue=output_queue)

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
        await update_meet_session(db_path, session_id, output_media_status=reason)
        return web.json_response({"status": "accepted"})

    app.router.add_get("/recall/health", recall_health)
    app.router.add_post("/recall/webhook", webhook)
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
        await update_meet_session(db_path, session_id, output_media_status=reason)


async def _request_json(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
