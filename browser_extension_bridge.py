from __future__ import annotations

"""Local WebSocket bridge between Maya and the Maya Chrome extension."""

import asyncio
import base64
import json
import secrets
import threading
import uuid
from pathlib import Path
from urllib.parse import quote_plus
from urllib.parse import parse_qs, urlparse

from browser_control import BrowserClickResult, BrowserElement, BrowserPage, _emit
from browser_control_js import _modal_state, _text_hash


BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8975
BRIDGE_HEALTH_PORT = 8976
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
    ):
        self.host = host
        self.port = port
        self.health_port = health_port if health_port is not None else (BRIDGE_HEALTH_PORT if port == BRIDGE_PORT else 0)
        self.token = token if token is not None else ensure_bridge_token()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = None
        self._pending: dict[str, asyncio.Future] = {}
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._startup_error: BaseException | None = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._run_loop, name="maya-extension-bridge", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=10):
            raise RuntimeError("extension bridge server did not start in time")
        if self._startup_error is not None:
            raise RuntimeError(f"extension bridge server failed to start: {self._startup_error}") from self._startup_error

    def request(self, op: str, args: dict | None = None, *, timeout: float = REQUEST_TIMEOUT) -> dict:
        if not self._loop:
            raise RuntimeError("extension bridge server is not running")
        future = asyncio.run_coroutine_threadsafe(self._send_request(op, args or {}, timeout), self._loop)
        return future.result(timeout=timeout + 5)

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
            ok = first_line.startswith("GET /health")
            status = b"200 OK" if ok else b"404 Not Found"
            body = HEALTH_BODY if ok else b"not-found\n"
            writer.write(
                b"HTTP/1.1 " + status + b"\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
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
        try:
            async for raw in websocket:
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

    async def _send_request(self, op: str, args: dict, timeout: float) -> dict:
        client = self._client
        if client is None:
            raise ConnectionError("Maya extension is not connected to the bridge")
        request_id = uuid.uuid4().hex[:12]
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await client.send(json.dumps({"id": request_id, "op": op, "args": args}))
        try:
            message = await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError as exc:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"extension did not answer op {op!r} in {timeout}s") from exc
        if not message.get("ok"):
            raise RuntimeError(f"extension op {op!r} failed: {message.get('error', 'unknown error')}")
        return message.get("result") or {}


class ExtensionBrowserController:
    """BrowserController-compatible controller backed by the Maya extension."""

    DRIVER = "extension"

    def __init__(self, server: ExtensionBridgeServer):
        self.server = server

    def ping(self) -> bool:
        return bool(self.server.request("ping").get("pong"))

    def set_status(self, text: str) -> None:
        self.server.request("set_status", {"text": text})

    def open_new_tab_url(self, url: str) -> int:
        tab_id = int(self.server.request("open_url", {"url": url}).get("tabId", 0))
        _emit("open_url", url=url, result=f"extension_tab={tab_id}")
        return tab_id

    def open_search(self, query: str) -> None:
        self.open_new_tab_url("https://www.google.com/search?q=" + quote_plus(query))

    def open_search_new_tab(self, query: str) -> None:
        self.open_search(query)

    def open_flight_search_new_tab(self, query: str) -> None:
        self.open_new_tab_url("https://www.google.com/travel/flights")

    def inspect_page(self, max_chars: int = 4500) -> BrowserPage:
        result = self.server.request("page_text", {"max_chars": max_chars})
        text = str(result.get("text", ""))
        page = BrowserPage(str(result.get("title", "")), str(result.get("url", "")), text, _text_hash(text), _modal_state(text))
        _emit("inspect", url=page.url, title=page.title, text_hash=page.text_hash, result=f"chars={len(page.text)} extension")
        return page

    def inspect_elements(self, max_items: int = 25) -> list[BrowserElement]:
        result = self.server.request("elements", {"max_items": max_items})
        items = result if isinstance(result, list) else result.get("items", [])
        elements = [BrowserElement(str(item.get("label", "")), str(item.get("kind", ""))) for item in items if item.get("label")]
        _emit("inspect_elements", result=f"count={len(elements)} extension")
        return elements

    def inspect_search_results(self, max_items: int = 8) -> list[str]:
        result = self.server.request("result_options", {"max_items": max_items})
        items = result.get("items", []) if isinstance(result, dict) else result
        rows = []
        for item in items:
            label = " ".join(str(item.get("label", "")).split())
            href = str(item.get("href", "")).strip()
            if not label:
                continue
            rows.append(f"{label} | {href}" if href else label)
        _emit("inspect_results", result=f"count={len(rows)} extension")
        return rows

    def capture_screenshot(self, directory: Path, label: str) -> str:
        result = self.server.request("screenshot")
        data_url = str(result.get("dataUrl", ""))
        if not data_url.startswith("data:image/png;base64,"):
            return ""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{label}.png"
        path.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
        return str(path)

    def click_text(self, target: str) -> str:
        raw = str(self.server.request("click_text", {"target": target}).get("result", ""))
        _emit("click", target=target, result=raw)
        return raw

    def click_exact_text_last(self, target: str) -> str:
        raw = str(self.server.request("click_exact_last", {"target": target}).get("result", ""))
        _emit("click_exact_last", target=target, result=raw)
        return raw

    def click_visible_text(self, target: str) -> str:
        raw = str(self.server.request("click_visible", {"target": target}).get("result", ""))
        _emit("click_visible", target=target, result=raw)
        return raw

    def click_price_result(self, target: str = "") -> str:
        raw = str(self.server.request("click_price_result", {"target": target}).get("result", ""))
        _emit("click_price_result", target=target, result=raw)
        return raw

    def click_search_result(self, target: str = "", rank: int = 1) -> str:
        raw = str(self.server.request("click_search_result", {"target": target, "rank": rank}).get("result", ""))
        _emit("click_search_result", target=f"rank={rank} {target}".strip(), result=raw)
        return raw

    def click_text_verified(self, target: str) -> BrowserClickResult:
        before = self.inspect_page(max_chars=1200)
        raw = self.click_text(target)
        after = self.inspect_page(max_chars=1200)
        present_after = self.target_visible(target)
        if not raw.startswith("CLICKED:"):
            return BrowserClickResult(
                "not_found", target, "", before.title, before.url, after.title, after.url,
                before.text_hash, after.text_hash, before.modal_state, after.modal_state, present_after,
            )
        label = raw.split(":", 1)[1].strip()
        result = BrowserClickResult(
            "clicked", target, label, before.title, before.url, after.title, after.url,
            before.text_hash, after.text_hash, before.modal_state, after.modal_state, present_after,
        )
        _emit("click_verified", target=target, result=f"verified={result.verified} changed={result.changed} extension", url=after.url)
        return result

    def fill_field(self, target: str, value: str) -> str:
        raw = str(self.server.request("fill_field", {"target": target, "value": value}).get("result", ""))
        _emit("fill", target=target, value=value, result=raw)
        return raw

    def target_visible(self, target: str) -> bool:
        return bool(self.server.request("target_visible", {"target": target}).get("visible"))

    def close_run_tabs(self, *, keep_banner: bool = False) -> int:
        return int(self.server.request("close_run_tabs", {"keep_banner": keep_banner}).get("closed", 0))

    def close_active_tab_or_blank(self) -> str:
        closed = self.close_run_tabs(keep_banner=False)
        raw = f"CLOSED_EXTENSION_TABS:{closed}" if closed else "NO_EXTENSION_TABS"
        _emit("close_tab", result=raw)
        return raw


def main() -> None:
    import argparse
    import time

    parser = argparse.ArgumentParser(description="Maya extension bridge")
    parser.add_argument("--serve", action="store_true", help="run the bridge and wait for the extension")
    parser.add_argument("--probe", action="store_true", help="open example.com in the Maya group and print page text")
    args = parser.parse_args()
    server = ExtensionBridgeServer()
    server.start()
    print(f"bridge listening on ws://{server.host}:{server.port}/maya")
    print(f"token file: {TOKEN_PATH}")
    if args.probe:
        print("waiting for the Maya Chrome extension to connect...")
        for _ in range(600):
            if server.is_connected:
                break
            time.sleep(0.2)
        if not server.is_connected:
            print("extension did not connect within 120 seconds")
            return
        controller = ExtensionBrowserController(server)
        controller.set_status("probe")
        controller.open_new_tab_url("https://example.com")
        time.sleep(2.0)
        page = controller.inspect_page()
        print(f"title: {page.title}\nurl: {page.url}\ntext: {page.text[:200]}")
        return
    if args.serve:
        while True:
            time.sleep(5)
            print(f"extension connected: {server.is_connected}")


if __name__ == "__main__":
    main()
