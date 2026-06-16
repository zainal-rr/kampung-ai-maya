from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

from maya_core.context_layers import init_context_layers_db
from maya_core.lesson_store import init_lesson_db
from maya_core.markdown_drafter import MarkdownDraft
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db
from telegram_delivery import split_file_markers


HTML_APP = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Travel Planner</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; padding: 24px; background: #f7faf9; color: #17211d; }
    main { max-width: 720px; margin: 0 auto; display: grid; gap: 16px; }
    form, section { border: 1px solid #d7e2dd; border-radius: 8px; padding: 16px; background: white; }
    label { display: grid; gap: 6px; font-weight: 700; }
    input, button { min-height: 40px; border-radius: 6px; font: inherit; }
    input { border: 1px solid #b7c7c0; padding: 0 10px; }
    button { border: 0; background: #166050; color: white; padding: 0 14px; cursor: pointer; }
    li { margin-top: 8px; }
  </style>
</head>
<body>
  <main>
    <h1>Travel Planner</h1>
    <form id="tripForm">
      <label>Destination <input id="destination" autocomplete="off" required></label>
      <button id="add" type="submit">Add Trip</button>
    </form>
    <section aria-label="Saved trips">
      <h2>Saved Trips</h2>
      <ul id="tripList"></ul>
    </section>
  </main>
  <script>
    const key = "mayaHtmlRenderTrips";
    const list = document.getElementById("tripList");
    const form = document.getElementById("tripForm");
    const input = document.getElementById("destination");
    const trips = JSON.parse(localStorage.getItem(key) || "[]");
    function render() {
      list.innerHTML = "";
      for (const trip of trips) {
        const item = document.createElement("li");
        item.textContent = trip;
        list.appendChild(item);
      }
    }
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      trips.push(input.value.trim());
      localStorage.setItem(key, JSON.stringify(trips));
      input.value = "";
      render();
    });
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="maya-html-render-") as tmp:
        root = Path(tmp)
        old_workspace = os.environ.get("MAYA_WORKSPACE_ROOT")
        os.environ["MAYA_WORKSPACE_ROOT"] = str(root / "Maya")
        try:
            html_path = asyncio.run(_generated_html_path(root))
            rendered, reason = _render_with_playwright(html_path)
        finally:
            if old_workspace is None:
                os.environ.pop("MAYA_WORKSPACE_ROOT", None)
            else:
                os.environ["MAYA_WORKSPACE_ROOT"] = old_workspace
        if rendered:
            print("html_render_smoke: ok")
            return 0
        if os.getenv("MAYA_HTML_RENDER_SMOKE_REQUIRED") == "1":
            raise AssertionError(reason)
        print(f"html_render_smoke: skipped ({reason})")
        return 0


async def _generated_html_path(root: Path) -> Path:
    import maya_documents.document_actions as da

    db_path = str(root / "smoke.db")
    await _init(db_path)
    old_html = da.draft_html_with_artisan
    old_fallback = da.draft_html_with_gemini
    old_review = da.review_html_app
    try:
        da.draft_html_with_artisan = _fake_html_draft
        da.draft_html_with_gemini = _unused_fallback
        da.review_html_app = _same_review
        router = da.DocumentActionRouter(db_path, workspace=root / "Maya")
        reply = await router.handle("make me a html file for a travel planner app", "telegram")
        _, files = split_file_markers(reply or "")
        _require(files and files[0].suffix == ".html" and files[0].exists(), "generated HTML file missing")
        _require(
            router.last_model_lane == "Codex HTML app builder + Claude HTML review + local HTML QA",
            "HTML route did not use the expected QA lane",
        )
        return files[0]
    finally:
        da.draft_html_with_artisan = old_html
        da.draft_html_with_gemini = old_fallback
        da.review_html_app = old_review


def _render_with_playwright(path: Path) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return False, f"Playwright is not installed: {exc}"
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:
            return False, f"Playwright Chromium is not installed: {exc}"
        try:
            for viewport in ({"width": 390, "height": 844}, {"width": 1280, "height": 800}):
                context = browser.new_context(viewport=viewport)
                try:
                    page = context.new_page()
                    page.goto(path.as_uri(), wait_until="domcontentloaded")
                    body_text = page.locator("body").inner_text(timeout=3000)
                    _require("Travel Planner" in body_text, "rendered page text is missing")
                    _require(page.locator("#destination").count() == 1, "destination input missing")
                    _require(page.locator("#add").count() == 1, "add button missing")
                    page.fill("#destination", "Kyoto")
                    page.click("#add")
                    _require("Kyoto" in page.locator("#tripList").inner_text(timeout=3000), "app interaction failed")
                    stored = page.evaluate("localStorage.getItem('mayaHtmlRenderTrips')")
                    _require("Kyoto" in (stored or ""), "app state did not persist")
                finally:
                    context.close()
        finally:
            browser.close()
    return True, "rendered"


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)


async def _fake_html_draft(db_path: str, topic: str) -> MarkdownDraft:
    return MarkdownDraft(HTML_APP)


async def _unused_fallback(db_path: str, topic: str) -> MarkdownDraft:
    raise AssertionError("Gemini fallback should not be used when Artisan generated valid HTML")


async def _same_review(db_path: str, topic: str, html: str) -> tuple[str, str]:
    return html, "reviewed"


def _require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
