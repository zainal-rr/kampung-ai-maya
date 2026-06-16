from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from desktop_file_opener import DesktopFileOpener


class FakeBridge:
    def __init__(self, fail_apps: set[str] | None = None):
        self.opened: list[tuple[str, str | None]] = []
        self.fail_apps = fail_apps or set()

    def open_file(self, path: str, app_name: str | None = None) -> None:
        if app_name in self.fail_apps:
            raise RuntimeError(f"{app_name} unavailable")
        self.opened.append((path, app_name))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-open-files-") as tmp:
        root = Path(tmp) / "Maya"
        for folder in ("notes", "documents", "presentations", "spreadsheets"):
            (root / folder).mkdir(parents=True)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(root)
        (root / "notes" / "router-setup.md").write_text("# Router", encoding="utf-8")
        (root / "documents" / "ai-agents-in-2026.docx").write_bytes(b"doc")
        (root / "presentations" / "ai-agents-in-2026.pptx").write_bytes(b"ppt")
        (root / "spreadsheets" / "kampung-ai-cost.xlsx").write_bytes(b"xls")
        bridge = FakeBridge()
        opener = DesktopFileOpener(bridge)  # type: ignore[arg-type]

        reply = await opener.handle("open latest Word document", "imac")
        _require(reply and "opened" in reply.lower(), "word file did not open")
        _require(bridge.opened[-1][1] == "Microsoft Word", "word app mismatch")

        reply = await opener.handle("open latest PowerPoint", "imac")
        _require(reply and "opened" in reply.lower(), "pptx file did not open")
        _require(bridge.opened[-1][1] == "Microsoft PowerPoint", "powerpoint app mismatch")

        reply = await opener.handle("open PowerPoint ai agents in 2026", "telegram")
        _require(reply and "ai-agents-in-2026.pptx" in reply and "[file:" in reply, "named PowerPoint should attach in Telegram")

        reply = await opener.handle("open latest Excel", "imac")
        _require(reply and "opened" in reply.lower(), "xlsx file did not open")
        _require(bridge.opened[-1][1] == "Microsoft Excel", "excel app mismatch")

        reply = await opener.handle("open router setup md", "imac")
        _require(reply and "router-setup.md" in reply, "named md file did not open")
        _require(bridge.opened[-1][1] == "Cursor", "markdown app mismatch")

        fallback_bridge = FakeBridge({"Cursor"})
        fallback_opener = DesktopFileOpener(fallback_bridge)  # type: ignore[arg-type]
        reply = await fallback_opener.handle("open router setup md", "imac")
        _require(reply and "router-setup.md" in reply, "named md fallback did not open")
        _require(fallback_bridge.opened[-1][1] == "TextEdit", "markdown fallback app mismatch")

    print("desktop_file_opening_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
