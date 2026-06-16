from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import quote_plus

from browser_control import BrowserClickResult, BrowserElement, BrowserPage, _emit
from browser_control_js import _modal_state, _text_hash
from maya_browser.extension_state import remember_extension_open_result
from untrusted_input_boundary import assess_untrusted_context


PING_TIMEOUT = 3.0


class ExtensionBrowserController:
    """BrowserController-compatible controller backed by the Maya extension."""

    DRIVER = "extension"

    def __init__(self, server):
        self.server = server

    def ping(self) -> bool:
        return bool(self.server.request("ping", timeout=PING_TIMEOUT).get("pong"))

    def set_status(self, text: str) -> None:
        self.server.request("set_status", {"text": text})

    def ensure_maya_group(self) -> dict:
        result = self.server.request("ensure_group")
        group, window = result.get("groupId", ""), result.get("windowId", "")
        _emit("ensure_group", result=f"group={group} window={window} maya_group={bool(result.get('openedInMayaGroup'))}")
        return result

    def open_new_tab_url(self, url: str) -> int:
        result = self.server.request("open_url", {"url": url})
        remember_extension_open_result(result)
        tab_id = int(result.get("tabId", 0))
        group_id = result.get("groupId", "")
        window_id = result.get("windowId", "")
        opened = bool(result.get("openedInMayaGroup"))
        _emit("open_url", url=url, result=f"extension_tab={tab_id} group={group_id} window={window_id} maya_group={opened}")
        return tab_id

    def open_search(self, query: str) -> None:
        self.open_new_tab_url("https://www.google.com/search?q=" + quote_plus(query))

    def open_search_new_tab(self, query: str) -> None:
        self.open_search(query)

    def open_flight_search_new_tab(self, query: str) -> None:
        self.open_new_tab_url("https://www.google.com/travel/flights")

    def inspect_page(self, max_chars: int = 4500) -> BrowserPage:
        self.ensure_maya_group()
        result = self.server.request("page_text", {"max_chars": max_chars})
        if result.get("openedInMayaGroup"):
            remember_extension_open_result(result)
        text = str(result.get("text", ""))
        url = str(result.get("url", ""))
        context = assess_untrusted_context(text, source="browser", source_id=url)
        page = BrowserPage(
            str(result.get("title", "")),
            url,
            text,
            _text_hash(text),
            _modal_state(text),
            context.untrusted_influence,
            context.injection_detected,
            context.source,
            context.risk_notes,
        )
        _emit("inspect", url=page.url, title=page.title, text_hash=page.text_hash, result=f"chars={len(page.text)} extension")
        return page

    def inspect_elements(self, max_items: int = 25) -> list[BrowserElement]:
        self.ensure_maya_group()
        result = self.server.request("elements", {"max_items": max_items})
        items = result if isinstance(result, list) else result.get("items", [])
        elements = [BrowserElement(str(item.get("label", "")), str(item.get("kind", ""))) for item in items if item.get("label")]
        _emit("inspect_elements", result=f"count={len(elements)} extension")
        return elements

    def inspect_search_results(self, max_items: int = 8) -> list[str]:
        self.ensure_maya_group()
        result = self.server.request("result_options", {"max_items": max_items})
        items = result.get("items", []) if isinstance(result, dict) else result
        rows = []
        for item in items:
            label = " ".join(str(item.get("label", "")).split())
            href = str(item.get("href", "")).strip()
            if label:
                rows.append(f"{label} | {href}" if href else label)
        _emit("inspect_results", result=f"count={len(rows)} extension")
        return rows

    def capture_screenshot(self, directory: Path, label: str) -> str:
        self.ensure_maya_group()
        result = self.server.request("screenshot")
        data_url = str(result.get("dataUrl", ""))
        if not data_url.startswith("data:image/png;base64,"):
            return ""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{label}.png"
        path.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
        return str(path)

    def click_text(self, target: str) -> str:
        return self._simple_result("click_text", {"target": target}, "click", target)

    def click_exact_text_last(self, target: str) -> str:
        return self._simple_result("click_exact_last", {"target": target}, "click_exact_last", target)

    def click_visible_text(self, target: str) -> str:
        return self._simple_result("click_visible", {"target": target}, "click_visible", target)

    def click_price_result(self, target: str = "") -> str:
        return self._simple_result("click_price_result", {"target": target}, "click_price_result", target)

    def click_search_result(self, target: str = "", rank: int = 1) -> str:
        raw = self._simple_result("click_search_result", {"target": target, "rank": rank}, "click_search_result", f"rank={rank} {target}".strip())
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
        return self._simple_result("fill_field", {"target": target, "value": value}, "fill", target, value=value)

    def target_visible(self, target: str) -> bool:
        self.ensure_maya_group()
        return bool(self.server.request("target_visible", {"target": target}).get("visible"))

    def close_run_tabs(self, *, keep_banner: bool = False) -> int:
        return int(self.server.request("close_run_tabs", {"keep_banner": keep_banner}).get("closed", 0))

    def close_active_tab_or_blank(self) -> str:
        closed = self.close_run_tabs(keep_banner=False)
        raw = f"CLOSED_EXTENSION_TABS:{closed}" if closed else "NO_EXTENSION_TABS"
        _emit("close_tab", result=raw)
        return raw

    def _simple_result(self, op: str, args: dict, emit_op: str, target: str, *, value: str = "") -> str:
        self.ensure_maya_group()
        raw = str(self.server.request(op, args).get("result", ""))
        _emit(emit_op, target=target, value=value, result=raw)
        return raw
