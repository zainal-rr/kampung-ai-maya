from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import tempfile
from pathlib import Path

from maya_documents.artifact_quality import validate_docx_path
from document_actions_word_helpers import (
    _generic_technical_troubleshooting_repair_markdown,
    _router_network_repair_markdown,
)
from office_drafter import word_sections_from_markdown
from office_modern_files import create_docx
from word_section_repair import strengthen_word_sections


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _assert_docx_passes(
            Path(tmp) / "technical-troubleshooting-guide.docx",
            "Technical Troubleshooting Guide",
            "technical troubleshooting guide",
            _generic_technical_troubleshooting_repair_markdown(),
        )
        _assert_docx_passes(
            Path(tmp) / "router-and-wifi-setup-guide.docx",
            "Router And WiFi Setup Guide",
            "router setup guide",
            _router_network_repair_markdown(),
        )
    print("word_technical_repair_smoke: ok")


def _assert_docx_passes(path: Path, title: str, topic: str, markdown: str) -> None:
    sections = strengthen_word_sections(topic, word_sections_from_markdown(markdown, topic))
    create_docx(path, title, sections)
    quality = validate_docx_path(path, topic, doc_kind="technical_guide")
    if not quality.passed:
        raise AssertionError(f"{topic} failed local QA: {quality.short_issue_text()}")


if __name__ == "__main__":
    main()
