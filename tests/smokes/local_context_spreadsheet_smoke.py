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

from openpyxl import load_workbook

from document_actions import DocumentActionRouter
from storage import init_db
from telegram_delivery import split_file_markers


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-local-sheet-") as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        router = DocumentActionRouter(db_path, workspace=Path(os.environ["MAYA_WORKSPACE_ROOT"]))
        reply = await router.handle("make an Excel comparison sheet for Telegram testing and iMac testing in Kampung AI", "telegram")
        _, files = split_file_markers(reply or "")
        text = _workbook_text(files[0]) if files else ""
        _require("Works While Away" in text, "local testing comparison missing travel columns")
        _require("Splashtop" in text, "local testing comparison missing remote maintenance note")
        _require("Perak" not in text and "rural" not in text.lower(), "local testing comparison drifted")
    print("local_context_spreadsheet_smoke: ok")


def _workbook_text(path: Path) -> str:
    book = load_workbook(path, data_only=False)
    values = []
    for sheet in book.worksheets:
        for row in sheet.iter_rows(values_only=True):
            values.extend(str(item) for item in row if item is not None)
    return "\n".join(values)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
