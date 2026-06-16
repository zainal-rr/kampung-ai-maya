from __future__ import annotations

from pathlib import Path

from maya_documents.office_modern_files import create_pptx
from pptx_quality_gate import inspect_pptx_quality, PptxQualityResult


def rebuild_topic_safe(path: Path, slides: list[tuple[str, list[str]]]) -> PptxQualityResult:
    title = slides[0][0] if slides else path.stem.replace("-", " ").title()
    create_pptx(path, title, slides)
    return inspect_pptx_quality(path)
