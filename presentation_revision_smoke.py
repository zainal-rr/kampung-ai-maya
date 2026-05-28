from __future__ import annotations

import os
import tempfile
from pathlib import Path

from office_modern_files import create_pptx
from presentation_reviser import revise_latest_presentation, wants_presentation_revision


def main() -> None:
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = tmp
        deck = Path(tmp) / "presentations" / "meta-ray-ban-display.pptx"
        create_pptx(deck, "Meta Ray-Ban Display", [
            ("Meta Ray-Ban Display puts a HUD in everyday glasses", ["Spec | Price | Bundle"]),
            ("The hardware is purpose-built for outdoor readability", ["600x600 pixels | 5,000 nits | 6 hours battery"]),
        ])
        assert wants_presentation_revision("revise the Meta Ray-Ban Display presentation")
        path, images, summary = revise_latest_presentation("revise the Meta Ray-Ban Display presentation")
        assert path and path.exists()
        assert path.name == "meta-ray-ban-display-reviewed.pptx"
        assert len(images) == 5
        assert "rebuilt with real visual layouts" in summary
        assert "did not overwrite" in summary
        assert deck.exists()
        ai_deck = Path(tmp) / "presentations" / "ai-agents-in-2026.pptx"
        create_pptx(ai_deck, "AI Agents In 2026", [
            ("AI Agents Are Moving From Chat to Action", ["Agents plan, use tools, and execute bounded workflows"]),
            ("Autonomy Introduces New Operational Risk", ["Approvals, audit trails, and rollback paths matter"]),
        ])
        ai_path, ai_images, ai_summary = revise_latest_presentation("revise the AI agents in 2026 presentation")
        assert ai_path and ai_path.exists()
        assert ai_path.name == "ai-agents-in-2026-reviewed.pptx"
        assert ai_images
        assert "topic-safe PowerPoint layout" in ai_summary
        text = _pptx_text(ai_path)
        assert "monocular HUD" not in text
        assert "AI Agents" in text or "Agents" in text
        assert "Why it matters | Why it matters" not in text
        assert " significant " not in f" {text.lower()} "
    if old_root is None:
        os.environ.pop("MAYA_WORKSPACE_ROOT", None)
    else:
        os.environ["MAYA_WORKSPACE_ROOT"] = old_root
    print("presentation_revision_smoke: ok")


def _pptx_text(path: Path) -> str:
    from pptx import Presentation

    deck = Presentation(path)
    parts = []
    for slide in deck.slides:
        for shape in slide.shapes:
            text = getattr(shape, "text", "").strip()
            if text:
                parts.append(" ".join(text.split()))
    return " ".join(parts)


if __name__ == "__main__":
    main()
