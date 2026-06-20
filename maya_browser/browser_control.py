from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote_plus

from maya_core.utils import OSBridge
from maya_browser.browser_control_models import BrowserElement, BrowserPage
from maya_browser.browser_control_parse import element_summary, page_summary, parse_page
from maya_browser.browser_control_js import (
    _as_string,
    _click_exact_last_js,
    _click_js,
    _click_price_result_js,
    _click_search_result_js,
    _click_visible_text_js,
    _elements_js,
    _fill_js,
    _modal_state,
    _page_text_js,
    _search_result_options_js,
    _target_visible_js,
    _text_hash,
)


_RECORDER = None
_parse_page = parse_page


def set_browser_recorder(recorder) -> None:
    """Install (or clear with None) a live-run recorder for browser steps."""
    global _RECORDER
    _RECORDER = recorder


def browser_recorder():
    return _RECORDER


def note_browser_intent(payload: dict) -> None:
    if _RECORDER is not None:
        _RECORDER.note_intent(payload)


def note_browser_route(skill: str, reason: str) -> None:
    if _RECORDER is not None:
        _RECORDER.note_route(skill, reason)


def _emit(action: str, *, target: str = "", value: str = "", result: str = "", url: str = "", title: str = "", text_hash: str = "") -> None:
    if _RECORDER is not None:
        _RECORDER.record_step(action, target=target, value=value, result=result, url=url, title=title, text_hash=text_hash)


@dataclass(frozen=True)
class BrowserClickResult:
    status: str
    target: str
    clicked_label: str
    before_title: str
    before_url: str
    after_title: str
    after_url: str
    before_hash: str = ""
    after_hash: str = ""
    before_modal: str = ""
    after_modal: str = ""
    target_present_after: bool = False

    @property
    def clicked(self) -> bool:
        return self.status == "clicked"

    @property
    def changed(self) -> bool:
        return (
            (self.before_title, self.before_url, self.before_hash, self.before_modal)
            != (self.after_title, self.after_url, self.after_hash, self.after_modal)
        )

    @property
    def verified(self) -> bool:
        return self.clicked and (self.changed or not self.target_present_after)


class BrowserController:
    DRIVER = "applescript"

    def __init__(self, bridge: OSBridge | None = None, app_name: str = "Google Chrome"):
        self.bridge = bridge or OSBridge()
        self.app_name = app_name

    def open_search(self, query: str) -> None:
        url = "https://www.google.com/search?q=" + quote_plus(query)
        _emit("open_url", target="google_search", value=query, url=url)
        self.bridge.open_url(url, self.app_name)

    def open_new_tab_url(self, url: str) -> None:
        _emit("open_url", url=url)
        opener = getattr(self.bridge, "open_url_new_tab", None)
        if opener:
            opener(url, self.app_name)
            return
        self.bridge.open_url(url, self.app_name)

    def open_search_new_tab(self, query: str) -> None:
        self.open_new_tab_url("https://www.google.com/search?q=" + quote_plus(query))

    def open_flight_search_new_tab(self, query: str) -> None:
        self.open_new_tab_url("https://www.google.com/travel/flights")

    def inspect_page(self, max_chars: int = 4500) -> BrowserPage:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            "set pageTitle to title of active tab of front window\n"
            "set pageUrl to URL of active tab of front window\n"
            f"set pageText to execute active tab of front window javascript {_as_string(_page_text_js(max_chars))}\n"
            'return pageTitle & "\n---URL---\n" & pageUrl & "\n---TEXT---\n" & pageText\n'
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        page = parse_page(raw)
        _emit("inspect", url=page.url, title=page.title, text_hash=page.text_hash, result=f"chars={len(page.text)}")
        return page

    def inspect_elements(self, max_items: int = 25) -> list[BrowserElement]:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set rawJson to execute active tab of front window javascript {_as_string(_elements_js(max_items))}\n"
            "return rawJson\n"
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            return []
        elements = [BrowserElement(str(item.get("label", "")), str(item.get("kind", ""))) for item in items if item.get("label")]
        _emit("inspect_elements", result=f"count={len(elements)}")
        return elements

    def inspect_search_results(self, max_items: int = 8) -> list[str]:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set rawJson to execute active tab of front window javascript {_as_string(_search_result_options_js(max_items))}\n"
            "return rawJson\n"
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            return []
        results = []
        for item in items:
            label = " ".join(str(item.get("label", "")).split())
            href = str(item.get("href", "")).strip()
            if not label:
                continue
            results.append(f"{label} | {href}" if href else label)
        _emit("inspect_results", result=f"count={len(results)}")
        return results

    def click_text(self, target: str) -> str:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set clickResult to execute active tab of front window javascript {_as_string(_click_js(target))}\n"
            "return clickResult\n"
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        _emit("click", target=target, result=raw)
        return raw

    def click_exact_text_last(self, target: str) -> str:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set clickResult to execute active tab of front window javascript {_as_string(_click_exact_last_js(target))}\n"
            "return clickResult\n"
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        _emit("click_exact_last", target=target, result=raw)
        return raw

    def click_visible_text(self, target: str) -> str:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set clickResult to execute active tab of front window javascript {_as_string(_click_visible_text_js(target))}\n"
            "return clickResult\n"
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        _emit("click_visible", target=target, result=raw)
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
        _emit("click_verified", target=target, result=f"verified={result.verified} changed={result.changed}", url=after.url)
        return result

    def fill_field(self, target: str, value: str) -> str:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set fillResult to execute active tab of front window javascript {_as_string(_fill_js(target, value))}\n"
            "return fillResult\n"
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        _emit("fill", target=target, value=value, result=raw)
        return raw

    def click_price_result(self, target: str = "") -> str:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set clickResult to execute active tab of front window javascript {_as_string(_click_price_result_js(target))}\n"
            "return clickResult\n"
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        _emit("click_price_result", target=target, result=raw)
        return raw

    def click_search_result(self, target: str = "", rank: int = 1) -> str:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set clickResult to execute active tab of front window javascript {_as_string(_click_search_result_js(target, rank))}\n"
            "return clickResult\n"
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        _emit("click_search_result", target=f"rank={rank} {target}".strip(), result=raw)
        return raw

    def target_visible(self, target: str) -> bool:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set visibleResult to execute active tab of front window javascript {_as_string(_target_visible_js(target))}\n"
            "return visibleResult\n"
            "end tell"
        )
        return self.bridge._run_applescript(script).strip().lower() == "true"

    def close_active_tab_or_blank(self) -> str:
        """Close the active tab, keeping one blank tab so Chrome does not fan out."""
        script = (
            f'tell application "{self.app_name}"\n'
            "if (count of windows) is 0 then return \"NO_WINDOW\"\n"
            "tell front window\n"
            "if (count of tabs) > 1 then\n"
            "close active tab\n"
            "return \"CLOSED_TAB\"\n"
            "else\n"
            "set URL of active tab to \"about:blank\"\n"
            "return \"BLANKED_ONLY_TAB\"\n"
            "end if\n"
            "end tell\n"
            "end tell"
        )
        raw = self.bridge._run_applescript(script)
        _emit("close_tab", result=raw)
        return raw
