from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from visual_workflow import VisualWorkflowRenderer, visual_workflow_subject


class FakeBridge:
    def __init__(self):
        self.opened = ""

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened = path


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = tmp
        bridge = FakeBridge()
        renderer = VisualWorkflowRenderer(str(Path(tmp) / "test.db"), bridge)  # type: ignore[arg-type]
        reply = await renderer.handle(
            "map this idea visually: Maya routes Telegram, iMac voice, files, memory, and calls",
            "imac",
        )
        _require(reply is not None and "opened it on the iMac" in reply, "iMac reply missing")
        _require(bridge.opened.endswith(".svg"), "visual was not opened")
        _require(Path(bridge.opened).exists(), "visual file missing")
        source = Path(bridge.opened).with_suffix(".mmd")
        _require(source.exists(), "Mermaid source missing")
        _require("flowchart TD" in source.read_text(encoding="utf-8"), "Mermaid source invalid")

        parsed = visual_workflow_subject("create an architecture diagram for browser automation")
        _require(parsed == "browser automation", "subject parser failed")

    print("visual_workflow_smoke ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
