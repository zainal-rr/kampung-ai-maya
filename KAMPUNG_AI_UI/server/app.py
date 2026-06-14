"""Maya UI read-only server — Phase 2.

READ-ONLY by doctrine and by construction: no POST/PUT/DELETE routes exist,
and the store is opened with SQLite ?mode=ro. Approvals and commands resolve
in chat/Telegram. Write endpoints arrive only after the internal MayaAppServer
protocol is stable (see maya_text_ui_design_plan.md section 7/10).

Run:  python -m uvicorn server.app:app --port 8765  (from KAMPUNG_AI_UI/)
Auth: MAYA_UI_TOKEN env, or an auto-generated token printed at startup.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .automation_reader import artifact_quality_snapshot, automations_snapshot, memory_audit_snapshot
from .event_reader import latest_cursor, read_after, read_recent
from .proof_reader import proof_snapshot
from .readers_common import DB_PATH, PROTO, connect_ro, table_exists
from .state_reader import artifacts_recent, conversation_recent, desk_snapshot, memory_rows

TOKEN = os.environ.get("MAYA_UI_TOKEN") or secrets.token_urlsafe(16)
POLL_SECONDS = 1.5
HEARTBEAT_EVERY = 10  # polls between heartbeats (~15s)
_STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Maya UI read API", version="0.1.0", docs_url=None, redoc_url=None)


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _authorized(request: Request) -> bool:
    supplied = request.query_params.get("token", "")
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        supplied = supplied or header[7:]
    return secrets.compare_digest(supplied, TOKEN)


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") or path == "/events":
        if not _authorized(request):
            return _error("unauthorized", "missing or wrong token", 401)
    return await call_next(request)


@app.get("/api/health")
def health() -> dict:
    try:
        with connect_ro() as conn:
            tables = sum(
                table_exists(conn, t)
                for t in ("harness_events", "route_events", "harness_runs", "memory_canaries")
            )
        return {"ok": True, "proto": PROTO, "db": str(DB_PATH), "tables": tables, "read_only": True}
    except FileNotFoundError:
        return {"ok": False, "proto": PROTO, "db": str(DB_PATH), "tables": 0, "read_only": True}


@app.get("/api/desk")
def desk():
    try:
        return desk_snapshot()
    except FileNotFoundError:
        return _error("store_unavailable", f"store not found at {DB_PATH}", 503)


@app.get("/api/memory")
def memory(limit: int = 40):
    try:
        return {"items": memory_rows(min(max(limit, 1), 200))}
    except FileNotFoundError:
        return _error("store_unavailable", f"store not found at {DB_PATH}", 503)


@app.get("/api/memory/audit")
def memory_audit(limit: int = 40):
    try:
        return memory_audit_snapshot(min(max(limit, 1), 200))
    except FileNotFoundError:
        return _error("store_unavailable", f"store not found at {DB_PATH}", 503)


@app.get("/api/artifacts")
def artifacts(limit: int = 25):
    try:
        return {"items": artifacts_recent(min(max(limit, 1), 100))}
    except FileNotFoundError:
        return _error("store_unavailable", f"store not found at {DB_PATH}", 503)


@app.get("/api/artifacts/detail")
def artifacts_detail(limit: int = 20):
    try:
        return artifact_quality_snapshot(min(max(limit, 1), 100))
    except FileNotFoundError:
        return _error("store_unavailable", f"store not found at {DB_PATH}", 503)


@app.get("/api/conversation")
def conversation(limit: int = 60):
    try:
        return {"items": conversation_recent(min(max(limit, 1), 160))}
    except FileNotFoundError:
        return _error("store_unavailable", f"store not found at {DB_PATH}", 503)


@app.get("/api/automations")
def automations():
    try:
        return automations_snapshot()
    except FileNotFoundError:
        return _error("store_unavailable", f"store not found at {DB_PATH}", 503)


@app.get("/api/proof")
def proof():
    return proof_snapshot()


@app.get("/api/events/recent")
def recent(limit: int = 30):
    try:
        items, he, re_ = read_recent(min(max(limit, 1), 200))
        return {"items": items, "cursor": {"he": he, "re": re_}}
    except FileNotFoundError:
        return _error("store_unavailable", f"store not found at {DB_PATH}", 503)


def _sse(item: dict) -> str:
    return f"event: {item['type']}\nid: {item['_he']}:{item['_re']}\ndata: {json.dumps(item, default=str)}\n\n"


@app.get("/events")
async def events(request: Request, he: int = 0, re: int = 0):
    last_event_id = request.headers.get("last-event-id", "")
    if last_event_id and ":" in last_event_id:
        try:
            he, re = (int(part) for part in last_event_id.split(":", 1))
        except ValueError:
            pass

    async def stream():
        nonlocal he, re
        yield "retry: 3000\n\n"
        if he == 0 and re == 0:
            he, re = latest_cursor()  # fresh client: start at now
        beats = 0
        while True:
            if await request.is_disconnected():
                return
            try:
                items, he, re = read_after(he, re)
            except FileNotFoundError:
                payload = {"error": {"code": "store_unavailable", "message": str(DB_PATH)}}
                yield f"event: error\ndata: {json.dumps(payload)}\n\n"
                return
            for item in items:
                item["_he"], item["_re"] = he, re
                yield _sse(item)
            beats += 1
            if beats % HEARTBEAT_EVERY == 0:
                yield ":hb\n\n"
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC), name="static")

if not os.environ.get("MAYA_UI_TOKEN"):
    print(f"[maya-ui] generated token: {TOKEN}")
print(f"[maya-ui] store: {DB_PATH} (read-only) · open http://127.0.0.1:8765/?token={TOKEN}")
