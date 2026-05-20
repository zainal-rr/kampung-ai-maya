from __future__ import annotations

import asyncio
import tempfile
import zipfile
from pathlib import Path

import imac_workflows
from assistant import KampungAssistant
from browser_control import BrowserClickResult, BrowserPage
from imac_workflows import ImacWorkflowRouter
from lesson_store import init_lesson_db
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import init_db
from telegram_delivery import split_file_markers


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []
        self.files: list[tuple[str, str | None]] = []

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.files.append((path, app_name))


class FakeBrowser:
    def __init__(self, bridge: FakeBridge):
        self.bridge = bridge
        self.clicks: list[str] = []

    def open_search(self, query: str) -> None:
        self.bridge.open_url("https://example.test/search?q=" + query)

    def inspect_page(self) -> BrowserPage:
        return BrowserPage("Flights", "https://example.test/flights", "AirAsia RM120\nMalaysia Airlines RM180")

    def inspect_elements(self):
        from browser_control import BrowserElement
        return [BrowserElement("AirAsia", "button"), BrowserElement("Depart date", "input")]

    def click_text(self, target: str) -> str:
        self.clicks.append(target)
        return "CLICKED: " + target

    def fill_field(self, target: str, value: str) -> str:
        self.clicks.append(f"fill:{target}:{value}")
        return "FILLED: " + target

    def click_text_verified(self, target: str) -> BrowserClickResult:
        self.clicks.append(target)
        return BrowserClickResult(
            "clicked",
            target,
            target,
            "Flights",
            "https://example.test/flights",
            "Flights",
            "https://example.test/flights",
        )


class FakeScreen:
    def capture_once(self):
        from screen_service import ScreenSnapshot
        return ScreenSnapshot(True, "screen visible", b"fake")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-imac-workflows-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        workspace = Path(tmp) / "workspace"
        await _init(db_path)
        bridge = FakeBridge()
        assistant = KampungAssistant(db_path=db_path)
        router = ImacWorkflowRouter(db_path, bridge, workspace)
        router.browser = FakeBrowser(bridge)
        router.human_browser.browser = router.browser
        router.human_browser.screen = FakeScreen()
        assistant.commands.workflows = router
        assistant.commands.documents.bridge = bridge
        assistant.commands.documents.workspace = workspace
        imac_workflows.run_network_diagnostics = _fake_network

        flight = await assistant.handle_text("check flight to Penang in imac", "telegram")
        _require("flight options" in flight.lower(), "flight workflow did not start")
        _require("Penang" in bridge.urls[-1], "flight search did not use destination")

        cheaper = await assistant.handle_text("find cheaper option", "telegram")
        _require("updated the browser search" in cheaper.lower(), "flight follow-up failed")
        _require("cheaper" in bridge.urls[-1].lower(), "flight follow-up query missing")

        buy = await assistant.handle_text("buy it", "telegram")
        _require("before booking" in buy.lower(), "booking guard missing")

        inspected = await assistant.handle_text("compare visible results", "telegram")
        _require("I inspected Chrome" in inspected and "Clickable or fillable targets" in inspected, "browser inspect failed")

        filled = await assistant.handle_text("fill depart date with tomorrow", "telegram")
        _require("filled depart date" in filled.lower(), "browser form fill failed")

        clicked = await assistant.handle_text("click AirAsia", "telegram")
        _require("I clicked AirAsia" in clicked, "safe browser click failed")

        sensitive = await assistant.handle_text("click buy now", "telegram")
        _require("looks sensitive" in sensitive.lower(), "sensitive click did not ask")
        approved = await assistant.handle_text("yes", "telegram")
        _require("I clicked buy now" in approved and "stop before booking" in approved, "approved sensitive click failed")

        status = await assistant.handle_text("browser status", "telegram")
        _require("Browser task:" in status and "clicked buy now" in status, "browser task memory failed")

        deck = await assistant.handle_text("make presentation on quantum computing", "telegram")
        message, markers = split_file_markers(deck)
        _require("PowerPoint draft" in message and markers, "presentation workflow failed")
        deck_path = Path(markers[-1])
        _require(deck_path.suffix == ".pptx" and deck_path.exists(), "pptx was not created")
        _require(_zip_has(deck_path, "ppt/presentation.xml"), "pptx missing presentation xml")

        network = await assistant.handle_text("what happened to my network", "telegram")
        _require("opened the troubleshooting document in Word" in network, "network workflow failed")
        doc_path = Path(bridge.files[-1][0])
        _require(doc_path.suffix == ".docx" and doc_path.exists(), "docx was not created")
        _require(_zip_has(doc_path, "word/document.xml"), "docx missing document xml")
        print("imac_workflows_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


def _fake_network():
    return [
        ("Default route", "ok", "gateway: 192.168.1.1"),
        ("DNS config", "ok", "resolver: 1.1.1.1"),
        ("Ping Cloudflare DNS", "ok", "1 packets received"),
        ("Ping google.com", "ok", "1 packets received"),
    ]


def _zip_has(path: Path, member: str) -> bool:
    with zipfile.ZipFile(path) as archive:
        return member in archive.namelist()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
