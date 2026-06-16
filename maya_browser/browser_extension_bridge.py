from __future__ import annotations

"""Local WebSocket bridge between Maya and the Maya Chrome extension."""

import asyncio
import json
import os
import secrets
import threading
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from maya_browser.extension_controller import ExtensionBrowserController
from maya_browser.extension_state import (
    extension_last_open_result,
    remember_extension_open_result,
    reset_extension_last_open_result,
)
from maya_browser.bridge_status import now_iso


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = _env_int("MAYA_BROWSER_BRIDGE_PORT", 8975)
BRIDGE_HEALTH_PORT = _env_int("MAYA_BROWSER_BRIDGE_HEALTH_PORT", 8976)
TOKEN_PATH = Path("logs") / "extension" / "maya_extension_token.txt"
REQUEST_TIMEOUT = 25.0
HEALTH_BODY = b"maya-extension-bridge-ok\n"


def ensure_bridge_token(path: Path = TOKEN_PATH) -> str:
    if path.exists():
        token = path.read_text("utf-8").strip()
        if token:
            return token
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    path.write_text(token + "\n", "utf-8")
    return token


class ExtensionBridgeServer:
    """Runs the WebSocket server on a background thread; sync `request` API."""

    def __init__(
        self,
        host: str = BRIDGE_HOST,
        port: int = BRIDGE_PORT,
        token: str | None = None,
        health_port: int | None = None,
        owner_kind: str | None = None,
    ):
        self.host = host
        self.port = port
        self.health_port = health_port if health_port is not None else (BRIDGE_HEALTH_PORT if port == BRIDGE_PORT else 0)
        self.token = token if token is not None else ensure_bridge_token()
        self.owner_kind = owner_kind or os.getenv("MAYA_BROWSER_BRIDGE_OWNER_KIND", "codex")
        self.server_started_at = now_iso()
        self.client_connected_at = ""
        self.last_client_seen_at = ""
        self.last_ping_ok_at = ""
        self.last_ping_error = ""
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = None
        self._pending: dict[str, asyncio.Future] = {}
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._startup_error: BaseException | None = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    @property
    def is_running(self) -> bool:
        return bool(self._loop and self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._run_loop, name="maya-extension-bridge", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=10):
            raise RuntimeError("extension bridge server did not start in time")
        if self._startup_error is not None:
            raise RuntimeError(f"extension bridge server failed to start: {self._startup_error}") from self._startup_error

    def request(
        self,
        op: str,
        args: dict | None = None,
        *,
        timeout: float = REQUEST_TIMEOUT,
        reset_on_timeout: bool = True,
    ) -> dict:
        if not self._loop:
            raise RuntimeError("extension bridge server is not running")
        future = asyncio.run_coroutine_threadsafe(
            self._send_request(op, args or {}, timeout, reset_on_timeout=reset_on_timeout),
            self._loop,
        )
        return future.result(timeout=timeout + 5)

    def ping_client(self, *, timeout: float = 1.0, close_on_failure: bool = True) -> bool:
        try:
            ok = bool(self.request("ping", timeout=timeout, reset_on_timeout=close_on_failure).get("pong"))
        except Exception as exc:
            self.last_ping_error = str(exc)
            if close_on_failure:
                self.close_client()
            return False
        if ok:
            self.last_ping_ok_at = now_iso()
            self.last_ping_error = ""
        return ok

    def status(self) -> dict:
        return {
            "owner_kind": self.owner_kind,
            "server_pid": os.getpid(),
            "server_started_at": self.server_started_at,
            "started": self.is_running,
            "running": self.is_running,
            "server_running": self.is_running,
            "connected": self.is_connected,
            "client_connected": self.is_connected,
            "client_connected_at": self.client_connected_at,
            "last_client_seen_at": self.last_client_seen_at,
            "last_ping_ok_at": self.last_ping_ok_at,
            "last_ping_error": self.last_ping_error,
            "port": self.port,
            "health_port": self.health_port,
            "reason_code": "connected" if self.is_connected else "client_disconnected",
        }

    def close_client(self) -> None:
        if not self._loop:
            self._client = None
            self.client_connected_at = ""
            return
        future = asyncio.run_coroutine_threadsafe(self._close_client(), self._loop)
        try:
            future.result(timeout=2)
        except Exception:
            self._client = None
            self.client_connected_at = ""

    def stop(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    # --- internals -------------------------------------------------------

    def _run_loop(self) -> None:
        import websockets

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def boot():
            server = await websockets.serve(self._handler, self.host, self.port)
            health_server = await asyncio.start_server(self._handle_health, self.host, self.health_port)
            if self.port == 0:
                self.port = server.sockets[0].getsockname()[1]
            if self.health_port == 0:
                self.health_port = health_server.sockets[0].getsockname()[1]
            self._ready.set()

        try:
            self._loop.run_until_complete(boot())
            self._loop.run_forever()
        except Exception as exc:
            self._startup_error = exc
            self._ready.set()

    def _request_path(self, websocket) -> str:
        request = getattr(websocket, "request", None)
        if request is not None and getattr(request, "path", ""):
            return request.path
        return getattr(websocket, "path", "")

    async def _handle_health(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await asyncio.wait_for(reader.read(2048), timeout=1)
            first_line = raw.splitlines()[0].decode("latin1", "ignore") if raw else ""
            if first_line.startswith("GET /health"):
                status = b"200 OK"
                content_type = b"text/plain; charset=utf-8"
                body = HEALTH_BODY
            elif first_line.startswith("GET /status"):
                status = b"200 OK"
                content_type = b"application/json; charset=utf-8"
                body = (json.dumps(self.status(), sort_keys=True) + "\n").encode("utf-8")
            else:
                status = b"404 Not Found"
                content_type = b"text/plain; charset=utf-8"
                body = b"not-found\n"
            writer.write(
                b"HTTP/1.1 " + status + b"\r\n"
                b"Content-Type: " + content_type + b"\r\n"
                b"Access-Control-Allow-Origin: *\r\n"
                b"Cache-Control: no-store\r\n"
                b"Connection: close\r\n"
                b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def _handler(self, websocket) -> None:
        query = parse_qs(urlparse(self._request_path(websocket)).query)
        token = (query.get("token") or [""])[0]
        if token != self.token:
            await websocket.close(code=4401, reason="bad token")
            return
        self._client = websocket
        self.client_connected_at = now_iso()
        self.last_client_seen_at = self.client_connected_at
        try:
            async for raw in websocket:
                self.last_client_seen_at = now_iso()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if "id" in message and ("ok" in message or "error" in message):
                    future = self._pending.pop(str(message["id"]), None)
                    if future and not future.done():
                        future.set_result(message)
        finally:
            if self._client is websocket:
                self._client = None
                self.client_connected_at = ""

    async def _send_request(self, op: str, args: dict, timeout: float, *, reset_on_timeout: bool = True) -> dict:
        client = self._client
        if client is None:
            raise ConnectionError("Maya extension is not connected to the bridge")
        request_id = uuid.uuid4().hex[:12]
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await client.send(json.dumps({"id": request_id, "op": op, "args": args}))
        except Exception:
            self._pending.pop(request_id, None)
            if self._client is client:
                self._client = None
            raise
        try:
            message = await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError as exc:
            self._pending.pop(request_id, None)
            if reset_on_timeout and self._client is client:
                self._client = None
                try:
                    await client.close()
                except Exception:
                    pass
            raise TimeoutError(f"extension did not answer op {op!r} in {timeout}s") from exc
        if not message.get("ok"):
            raise RuntimeError(f"extension op {op!r} failed: {message.get('error', 'unknown error')}")
        return message.get("result") or {}

    async def _close_client(self) -> None:
        client = self._client
        self._client = None
        self.client_connected_at = ""
        for request_id, future in list(self._pending.items()):
            if not future.done():
                future.set_exception(ConnectionError("Maya extension connection was reset"))
            self._pending.pop(request_id, None)
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass


def main() -> None:
    from browser_extension_cli import run_bridge_cli

    run_bridge_cli(
        server_cls=ExtensionBridgeServer,
        controller_cls=ExtensionBrowserController,
        token_path=TOKEN_PATH,
    )


if __name__ == "__main__":
    main()
