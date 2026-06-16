from __future__ import annotations

from presentation_design_review import review_presentation_design, wants_presentation_review
from presentation_reviser import revise_latest_presentation, wants_presentation_revision


async def handle_presentation_command(db_path: str, text: str, channel: str) -> tuple[str, str, str, bool] | None:
    if wants_presentation_revision(text):
        path, _images, summary = revise_latest_presentation(text)
        if not path:
            return summary, "PowerPoint revision + rendered verification", "presentation revision", False
        marker = f"\n[file:{path}]" if channel == "telegram" else ""
        return (
            f"{summary}{marker}",
            "PowerPoint revision + rendered verification",
            "presentation revision",
            False,
        )
    if wants_presentation_review(text):
        reply, cost = await review_presentation_design(db_path, text)
        lane = (
            "Gemini slide vision + Claude presentation review + Design Engineering"
            if "including rendered slide visuals" in reply
            else "Claude presentation review + Design Engineering"
        )
        return reply, lane, "presentation design review", cost
    return None
