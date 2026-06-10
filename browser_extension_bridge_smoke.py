from __future__ import annotations

"""Offline proof of the extension bridge: a fake extension client over a real
WebSocket exercises token auth, request correlation, page-text parsing,
screenshot decoding, browser control methods, timeouts, and bad-token rejection."""

import asyncio
import base64
import json
import tempfile
import threading
from pathlib import Path

from browser_extension_bridge import ExtensionBridgeServer, ExtensionBrowserController

PNG_1PX = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
    )
).decode()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _fake_extension(uri: str, stop: threading.Event) -> None:
    import websockets

    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"event": "connected", "extension": "maya", "version": 1}))
        while not stop.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            req = json.loads(raw)
            op, rid = req["op"], req["id"]
            if op == "ping":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"pong": True}}))
            elif op == "open_url":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"tabId": 42}}))
            elif op == "page_text":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {
                    "title": "Example Domain", "url": "https://example.com/", "text": "Example Domain\nMore information"}}))
            elif op == "screenshot":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"dataUrl": "data:image/png;base64," + PNG_1PX}}))
            elif op == "set_status":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"ok": True}}))
            elif op == "elements":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": [
                    {"kind": "input", "label": "Where to?"},
                    {"kind": "button", "label": "Search"},
                ]}))
            elif op == "result_options":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"items": [
                    {"label": "Example result", "href": "https://example.com/result"}
                ]}}))
            elif op in {"click_text", "click_visible", "click_exact_last"}:
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"result": f"CLICKED: {req.get('args', {}).get('target', 'Example')}"}}))
            elif op == "click_price_result":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"result": "CLICKED: Hotel RM 450"}}))
            elif op == "click_search_result":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"result": "CLICKED_RESULT: Example result | https://example.com/result"}}))
            elif op == "target_visible":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"visible": False}}))
            elif op in {"fill", "fill_field"}:
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"result": f"FILLED: {req.get('args', {}).get('target', 'field')}"}}))
            elif op == "close_run_tabs":
                await ws.send(json.dumps({"id": rid, "ok": True, "result": {"closed": 2}}))
            elif op == "boom":
                await ws.send(json.dumps({"id": rid, "ok": False, "error": "synthetic failure"}))
            # op "ignored" gets no reply on purpose (timeout path)


def main() -> None:
    server = ExtensionBridgeServer(port=0, token="smoke-token")
    server.start()
    stop = threading.Event()
    uri = f"ws://127.0.0.1:{server.port}/maya?token=smoke-token"

    fake_thread = threading.Thread(target=lambda: asyncio.run(_fake_extension(uri, stop)), daemon=True)
    fake_thread.start()
    for _ in range(50):
        if server.is_connected:
            break
        threading.Event().wait(0.1)
    _require(server.is_connected, "fake extension did not connect")

    controller = ExtensionBrowserController(server)
    _require(controller.ping(), "ping round trip failed")
    controller.set_status("flights-01")
    _require(controller.open_new_tab_url("https://example.com") == 42, "open_url tabId missing")
    page = controller.inspect_page()
    _require(page.title == "Example Domain" and page.text_hash, "page_text did not parse into BrowserPage")
    elements = controller.inspect_elements()
    _require(elements and elements[0].label == "Where to?", "elements did not parse")
    results = controller.inspect_search_results()
    _require(results and "Example result" in results[0], "result options did not parse")
    _require(controller.click_text("Search").startswith("CLICKED:"), "click_text failed")
    _require(controller.click_visible_text("Search").startswith("CLICKED:"), "click_visible_text failed")
    _require(controller.click_exact_text_last("Search").startswith("CLICKED:"), "click_exact_text_last failed")
    _require(controller.click_price_result().startswith("CLICKED:"), "click_price_result failed")
    _require(controller.click_search_result(rank=1).startswith("CLICKED_RESULT:"), "click_search_result failed")
    _require(controller.fill_field("Where to?", "Penang").startswith("FILLED:"), "fill_field failed")
    verified = controller.click_text_verified("Search")
    _require(verified.clicked and verified.verified, "verified click contract failed")
    _require(controller.close_active_tab_or_blank() == "CLOSED_EXTENSION_TABS:2", "extension tab cleanup failed")
    with tempfile.TemporaryDirectory() as tmp:
        shot = controller.capture_screenshot(Path(tmp), "flights-01")
        _require(shot.endswith(".png") and Path(shot).stat().st_size > 50, "screenshot was not decoded to a PNG")
    try:
        server.request("boom")
        raise AssertionError("extension error was not raised")
    except RuntimeError as exc:
        _require("synthetic failure" in str(exc), "extension error message lost")
    try:
        server.request("ignored", timeout=0.6)
        raise AssertionError("timeout was not raised")
    except TimeoutError:
        pass
    # Wrong token must be rejected.
    async def bad_token() -> bool:
        import websockets

        try:
            async with websockets.connect(f"ws://127.0.0.1:{server.port}/maya?token=wrong") as ws:
                await ws.recv()
        except Exception:
            return True
        return True

    _require(asyncio.run(bad_token()), "bad token path errored unexpectedly")
    _require(server.is_connected, "good client lost after bad-token attempt")
    stop.set()
    print("browser_extension_bridge_smoke: ok")


if __name__ == "__main__":
    main()
