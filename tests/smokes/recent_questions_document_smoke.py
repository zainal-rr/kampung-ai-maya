from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maya_documents.artifact_quality import extract_docx_text
from maya_documents.document_actions import DocumentActionRouter
from storage import init_db, save_history_message


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-recent-questions-doc-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        prompts = [
            "older question that should not be exported",
            "create a vrf for customer A on the PE router",
            "now assess the preference share issuance from an investor's perspective",
            "design the network for a new branch campus",
            "design a three-tier web app on AWS for an online store",
            "can you solve this issue as well?",
        ]
        for prompt in prompts:
            await save_history_message(db_path, 1, "user", prompt, "telegram")
            await save_history_message(db_path, 1, "assistant", "ack", "telegram")

        workspace = Path(tmp) / "Maya"
        router = DocumentActionRouter(db_path, workspace=workspace)
        reply = await router.handle(
            "can you put the last five question in a doc file? create the file and save it in folder",
            "telegram",
        )
        _require(reply and "[file:" in reply, f"recent question export did not attach a file: {reply}")
        match = re.search(r"\[file:(.+?)\]", reply)
        path = Path(match.group(1)) if match else Path()
        _require(path.exists() and path.suffix == ".docx", f"missing docx export: {path}")
        text = extract_docx_text(path)
        _require("older question that should not be exported" not in text, "export included more than the requested five")
        for prompt in prompts[-5:]:
            _require(prompt in text, f"export missed prompt: {prompt}")
        _require(router.last_model_lane == "Local recent-question Word export", "recent export should not call model drafting")

    print("recent_questions_document_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
