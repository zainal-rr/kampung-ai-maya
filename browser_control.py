from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from urllib.parse import quote_plus

from utils import OSBridge


@dataclass(frozen=True)
class BrowserPage:
    title: str
    url: str
    text: str
    text_hash: str = ""
    modal_state: str = ""


@dataclass(frozen=True)
class BrowserElement:
    label: str
    kind: str


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
    def __init__(self, bridge: OSBridge | None = None, app_name: str = "Google Chrome"):
        self.bridge = bridge or OSBridge()
        self.app_name = app_name

    def open_search(self, query: str) -> None:
        self.bridge.open_url("https://www.google.com/search?q=" + quote_plus(query), self.app_name)

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
        return _parse_page(raw)

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
        return [BrowserElement(str(item.get("label", "")), str(item.get("kind", ""))) for item in items if item.get("label")]

    def click_text(self, target: str) -> str:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set clickResult to execute active tab of front window javascript {_as_string(_click_js(target))}\n"
            "return clickResult\n"
            "end tell"
        )
        return self.bridge._run_applescript(script)

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
        return BrowserClickResult(
            "clicked", target, label, before.title, before.url, after.title, after.url,
            before.text_hash, after.text_hash, before.modal_state, after.modal_state, present_after,
        )

    def fill_field(self, target: str, value: str) -> str:
        script = (
            f'tell application "{self.app_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then error \"No browser window is open\"\n"
            f"set fillResult to execute active tab of front window javascript {_as_string(_fill_js(target, value))}\n"
            "return fillResult\n"
            "end tell"
        )
        return self.bridge._run_applescript(script)

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


def page_summary(page: BrowserPage, max_lines: int = 8) -> str:
    lines = [line.strip() for line in page.text.splitlines() if line.strip()]
    excerpt = "\n".join(lines[:max_lines])
    if not excerpt:
        excerpt = "I can read the page title, but the page body is empty or blocked."
    return f"Title: {page.title}\nURL: {page.url}\nVisible text:\n{excerpt}"


def element_summary(elements: list[BrowserElement], max_items: int = 8) -> str:
    if not elements:
        return "Clickable or fillable targets: none obvious."
    lines = [f"{item.kind}: {item.label}" for item in elements[:max_items]]
    return "Clickable or fillable targets:\n" + "\n".join(lines)


def _parse_page(raw: str) -> BrowserPage:
    title, _, rest = raw.partition("\n---URL---\n")
    url, _, text = rest.partition("\n---TEXT---\n")
    clean_text = text.strip()
    return BrowserPage(title.strip(), url.strip(), clean_text, _text_hash(clean_text), _modal_state(clean_text))


def _as_string(script: str) -> str:
    return json.dumps(script)


def _page_text_js(max_chars: int) -> str:
    return (
        "(() => {"
        "const text = document.body ? document.body.innerText : '';"
        f"return text.slice(0, {max(500, max_chars)});"
        "})()"
    )


def _click_js(target: str) -> str:
    return (
        "(() => {"
        f"const target = {json.dumps(target.lower())};"
        "const norm = s => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();"
        "const visible = e => { const r = e.getBoundingClientRect();"
        "return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };"
        "const label = e => norm(e.innerText || e.value || e.getAttribute('aria-label') || e.title || '');"
        "const nodes = [...document.querySelectorAll('a,button,input,[role=button],[role=link],select,summary')];"
        "const match = nodes.find(e => visible(e) && label(e).includes(target));"
        "if (!match) return 'NOT_FOUND';"
        "match.scrollIntoView({block: 'center', inline: 'center'});"
        "match.click();"
        "return 'CLICKED: ' + label(match).slice(0, 120);"
        "})()"
    )


def _target_visible_js(target: str) -> str:
    return (
        "(() => {"
        f"const target = {json.dumps(target.lower())};"
        "const norm = s => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();"
        "const visible = e => { const r = e.getBoundingClientRect();"
        "return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };"
        "const label = e => norm(e.innerText || e.value || e.getAttribute('aria-label') || e.title || '');"
        "const nodes = [...document.querySelectorAll('a,button,input,[role=button],[role=link],select,summary')];"
        "return nodes.some(e => visible(e) && label(e).includes(target));"
        "})()"
    )


def _elements_js(max_items: int) -> str:
    return (
        "(() => {"
        "const norm=s=>(s||'').replace(/\\s+/g,' ').trim();"
        "const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};"
        "const label=e=>norm(e.innerText||e.value||e.getAttribute('aria-label')||e.placeholder||e.name||e.title||'');"
        "const nodes=[...document.querySelectorAll('a,button,input,textarea,select,[role=button],[role=link],summary')];"
        "return JSON.stringify(nodes.filter(visible).map(e=>({kind:e.tagName.toLowerCase(),label:label(e)})).filter(x=>x.label).slice(0,"
        f"{max(1, max_items)}"
        "));"
        "})()"
    )


def _fill_js(target: str, value: str) -> str:
    return (
        "(() => {"
        f"const target={json.dumps(target.lower())};"
        f"const value={json.dumps(value)};"
        "const norm=s=>(s||'').toLowerCase().replace(/\\s+/g,' ').trim();"
        "const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};"
        "const label=e=>norm(e.getAttribute('aria-label')||e.placeholder||e.name||e.id||'');"
        "const nodes=[...document.querySelectorAll('input,textarea,select')];"
        "const match=nodes.find(e=>visible(e)&&label(e).includes(target));"
        "if(!match)return 'NOT_FOUND';"
        "match.focus(); match.value=value;"
        "match.dispatchEvent(new Event('input',{bubbles:true}));"
        "match.dispatchEvent(new Event('change',{bubbles:true}));"
        "return 'FILLED: '+(label(match)||target).slice(0,120);"
        "})()"
    )


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _modal_state(text: str) -> str:
    lowered = text.lower()
    markers = ("cookie", "accept", "dialog", "modal", "continue", "confirm")
    return ",".join(marker for marker in markers if marker in lowered)[:120]
