from __future__ import annotations

import asyncio
import json

from active_context_scripts import (
    EXCEL_CONTEXT_SCRIPT,
    GENERIC_TEXT_CONTEXT_SCRIPT,
    POWERPOINT_CONTEXT_SCRIPT,
    WORD_CONTEXT_SCRIPT,
    browser_context_script,
)
from active_context_document_parsers import parse_markdown_context, parse_powerpoint_context, parse_word_context
from active_context_models import ActiveContext, log_context
from active_context_parsers import infer_markdown_path, is_sensitive_browser_context, parse_excel_context
from active_context_powerpoint import verify_powerpoint_visible_context
from screen_responder import ScreenResponder
from utils import OSBridge


class ActiveContextInspector:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()

    async def inspect(self, question: str = "", *, allow_screen_fallback: bool = True) -> ActiveContext:
        try:
            app = await asyncio.to_thread(self.bridge.get_frontmost_app)
        except Exception as exc:
            app = "unknown"
            frontmost_error = str(exc)
        else:
            frontmost_error = ""
        lowered = app.lower()
        candidates: list[ActiveContext] = []
        if "excel" in lowered:
            candidates.append(await asyncio.to_thread(self._excel_context, app))
        elif "word" in lowered:
            candidates.append(await asyncio.to_thread(self._word_context, app))
        elif "powerpoint" in lowered:
            candidates.append(await asyncio.to_thread(self._powerpoint_context, app))
        elif "chrome" in lowered or "safari" in lowered:
            candidates.append(await asyncio.to_thread(self._browser_context, app))
        elif any(name in lowered for name in ("textedit", "code", "cursor")):
            candidates.append(await asyncio.to_thread(self._generic_text_context, app))
        else:
            candidates.append(await asyncio.to_thread(self._generic_text_context, app))
        best = _best(candidates)
        if best and allow_screen_fallback and "powerpoint" in lowered and best.active_file and _slide_question(question):
            reply = await ScreenResponder(self.db_path).handle("look at the current PowerPoint slide and identify the visible slide number and title", "imac")
            best = verify_powerpoint_visible_context(best, reply or "")
        if best and (best.selected_content or best.active_file or best.nearby_context or best.document_context):
            log_context(best)
            return best
        if allow_screen_fallback:
            reply = await ScreenResponder(self.db_path).handle(question or "what is on my screen", "imac")
            context = ActiveContext(
                app=app,
                selection_type="screen_snapshot",
                nearby_context=reply or "",
                fallback_used="one_shot_screen",
                source="one_shot_screen",
                confidence=0.65 if reply else 0.2,
                error=frontmost_error,
            )
            log_context(context)
            return context
        return ActiveContext(
            app=app,
            selection_type="none",
            fallback_used="none",
            confidence=0.0,
            error=frontmost_error or (best.error if best else ""),
        )

    def _excel_context(self, app: str) -> ActiveContext:
        data, error = self._json_script(EXCEL_CONTEXT_SCRIPT)
        if not data:
            return ActiveContext(app, "none", error=error)
        parsed = parse_excel_context(
            str(data.get("path") or ""),
            str(data.get("sheet") or ""),
            str(data.get("range") or ""),
        )
        content = "\n".join(
            part for part in (
                f"sheet: {data.get('sheet', '')}",
                f"range: {data.get('range', '')}",
                "values:\n" + str(data.get("values", "")).strip(),
                "formulas:\n" + str(data.get("formulas", "")).strip(),
                "number_formats:\n" + str(data.get("formats", "")).strip(),
            )
            if part.strip()
        )
        return ActiveContext(
            app=app,
            selection_type="excel_selection",
            selected_content=content,
            active_file=str(data.get("path") or data.get("workbook") or ""),
            active_title=parsed.title,
            nearby_context=parsed.nearby_context,
            document_context=parsed.document_context,
            limits=parsed.limits,
            source="excel_applescript_plus_xlsx_parser" if parsed.document_context else "excel_applescript_only",
            confidence=min(0.98, 0.88 + parsed.confidence_boost),
        )

    def _word_context(self, app: str) -> ActiveContext:
        data, error = self._json_script(WORD_CONTEXT_SCRIPT)
        if not data:
            return ActiveContext(app, "none", error=error)
        selected = str(data.get("selection") or "")
        parsed = parse_word_context(str(data.get("path") or ""), selected)
        return ActiveContext(
            app=app,
            selection_type="word_selection",
            selected_content=selected,
            active_file=str(data.get("path") or data.get("document") or ""),
            active_title=parsed.title,
            nearby_context=parsed.nearby_context,
            document_context=parsed.document_context,
            limits=parsed.limits,
            source="word_applescript_plus_docx_parser" if parsed.document_context else "word_applescript_only",
            confidence=min(0.96, (0.84 if selected else 0.55) + parsed.confidence_boost),
        )

    def _powerpoint_context(self, app: str) -> ActiveContext:
        data, error = self._json_script(POWERPOINT_CONTEXT_SCRIPT)
        if not data:
            return ActiveContext(app, "none", error=error)
        selected = str(data.get("selection") or "")
        try:
            slide = int(data.get("slide") or 1)
        except (TypeError, ValueError):
            slide = 1
        parsed = parse_powerpoint_context(str(data.get("path") or ""), slide, selected)
        nearby = "\n".join(part for part in (f"slide: {data.get('slide', '')}", parsed.nearby_context) if part.strip())
        return ActiveContext(
            app=app,
            selection_type="powerpoint_selection",
            selected_content=selected,
            active_file=str(data.get("path") or data.get("presentation") or ""),
            active_title=parsed.title,
            nearby_context=nearby,
            document_context=parsed.document_context,
            limits=parsed.limits,
            source="powerpoint_applescript_plus_pptx_parser" if parsed.document_context else "powerpoint_applescript_only",
            confidence=min(0.95, (0.8 if selected else 0.5) + parsed.confidence_boost),
        )

    def _browser_context(self, app: str) -> ActiveContext:
        target = "Google Chrome" if "chrome" in app.lower() else "Safari"
        data, error = self._json_script(browser_context_script(target))
        if not data:
            return ActiveContext(app, "none", error=error)
        if data.get("error"):
            return ActiveContext(
                app=app,
                selection_type="browser_dom_blocked",
                active_file=str(data.get("url") or ""),
                active_title=str(data.get("title") or ""),
                limits=(
                    "Browser DOM access is blocked by Chrome. Enable View > Developer > "
                    "Allow JavaScript from Apple Events, then try again. Screenshot fallback was not used."
                ),
                source="browser_dom_blocked",
                confidence=0.35,
                error=str(data.get("error") or ""),
            )
        selected = str(data.get("selection") or "")
        url = str(data.get("url") or "")
        sensitive = bool(data.get("sensitive_context")) or is_sensitive_browser_context(
            "\n".join(str(data.get(key) or "") for key in ("selection", "anchor", "nearby", "headings", "page", "hidden")),
            url,
        )
        if sensitive:
            page = ""
            hidden = ""
            limits = "Sensitive browser context detected. Passwords, OTPs, cards, private keys, payment, checkout, and booking fields were skipped."
        else:
            page = str(data.get("page") or "")
            hidden = str(data.get("hidden") or "")
            limits = "Active browser DOM was read for this iMac voice turn. Sensitive form fields were skipped."
        anchor = selected or str(data.get("anchor") or "")
        nearby_parts = [
            f"title: {data.get('title', '')}",
            "headings_or_active_panels:\n" + str(data.get("headings") or ""),
            "nearby_dom:\n" + str(data.get("nearby") or ""),
        ]
        document_parts = [
            "page_text:\n" + page if page else "",
            "hidden_relevant_dom:\n" + hidden if hidden else "",
        ]
        return ActiveContext(
            app=app,
            selection_type="browser_selection" if data.get("selection") else "browser_page",
            selected_content=anchor,
            active_file=url,
            active_title=str(data.get("title") or ""),
            nearby_context="\n".join(part for part in nearby_parts if part.strip()),
            document_context="\n\n".join(part for part in document_parts if part),
            limits=limits,
            source="browser_dom",
            confidence=0.9 if selected else 0.72,
        )

    def _generic_text_context(self, app: str) -> ActiveContext:
        data, error = self._json_script(GENERIC_TEXT_CONTEXT_SCRIPT)
        if not data:
            return ActiveContext(app, "none", error=error)
        selected = str(data.get("selection") or "")
        title = str(data.get("title") or "")
        clipboard_used = False
        if not selected:
            selected = self._clipboard_text_selection()
            clipboard_used = bool(selected)
        active_file = infer_markdown_path(title, selected) if _looks_like_markdown_app(app, title) else ""
        parsed = parse_markdown_context(active_file, selected) if active_file else None
        return ActiveContext(
            app=app,
            selection_type="text_selection" if selected else "none",
            selected_content=selected,
            active_file=active_file,
            active_title=parsed.title if parsed else title,
            nearby_context=parsed.nearby_context if parsed else "",
            document_context=parsed.document_context if parsed else "",
            limits=parsed.limits if parsed else "",
            source="markdown_parser_clipboard" if clipboard_used and parsed and parsed.document_context else ("markdown_parser" if parsed and parsed.document_context else "accessibility_selection"),
            confidence=min(0.92, (0.75 if selected else 0.25) + (parsed.confidence_boost if parsed else 0.0)),
        )

    def _json_script(self, script: str) -> tuple[dict, str]:
        try:
            raw = self.bridge._run_applescript(script)
            if not raw:
                return {}, ""
            return json.loads(raw), ""
        except Exception as exc:
            return {}, str(exc)

    def _clipboard_text_selection(self) -> str:
        script = r'''
set selectedText to ""
try
    set oldClipboard to the clipboard
    tell application "System Events" to keystroke "c" using command down
    delay 0.12
    try
        set selectedText to the clipboard as text
    end try
    set the clipboard to oldClipboard
end try
return selectedText
'''
        try:
            selected = self.bridge._run_applescript(script).strip()
            if selected.startswith("{") and '"selection"' in selected:
                return ""
            return selected
        except Exception:
            return ""


async def inspect_active_context(db_path: str, question: str, *, allow_screen_fallback: bool = True) -> str:
    context = await ActiveContextInspector(db_path).inspect(question, allow_screen_fallback=allow_screen_fallback)
    return context.as_tool_text()


def active_context_instruction() -> str:
    return (
        "When Zainal asks about this, here, selected text, a figure, a slide, a browser passage, or what to click, "
        "use inspect_active_context before answering. Call this tool silently first for active selection questions. "
        "On iMac voice this can use active app selection, broader active document context, active browser DOM, or one fresh screen snapshot. "
        "Do not call screen inspection first for document, spreadsheet, slide, Markdown, or browser-page questions. "
        "Use screen inspection only if inspect_active_context says context_source is one_shot_screen or the question is specifically visual layout. "
        "If context_source is browser_dom_blocked, say the browser DOM access is blocked and do not guess from screenshot. "
        "For PowerPoint, explain the current slide from parsed slide text first. If the highlighted object text is unavailable, say the app did not expose the exact highlight and answer from current slide context. "
        "If the highlighted text is unavailable in another app, say the app did not expose the highlight and answer from document context only. "
        "Answer the anchor first, then use wider context briefly. Prefer document titles from content over filenames."
    )


def _best(contexts: list[ActiveContext]) -> ActiveContext | None:
    if not contexts:
        return None
    return max(contexts, key=lambda item: item.confidence)


def _looks_like_markdown_app(app: str, title: str) -> bool:
    lowered = f"{app} {title}".lower()
    return any(name in lowered for name in ("cursor", "textedit", "code", ".md", "markdown"))


def _slide_question(question: str) -> bool:
    lowered = question.lower()
    return any(word in lowered for word in ("slide", "powerpoint", "ppt", "deck", "presentation", "see it", "screen"))
