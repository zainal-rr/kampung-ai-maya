from __future__ import annotations

from pathlib import Path

from artifact_quality import artifact_skill_context


async def powerpoint_quality_context(db_path: str) -> str:
    parts = [
        "PowerPoint artifact quality skill:",
        artifact_skill_context("pptx"),
    ]
    design = await _active_design_skill_text(db_path)
    if design:
        parts.extend(("\nDesign Engineering taste context:", design))
    return "\n".join(part for part in parts if part).strip()[:14000]


async def _active_design_skill_text(db_path: str) -> str:
    try:
        from skill_store import find_skill

        skill = await find_skill(db_path, "Design Engineering")
        if skill and str(skill.get("status", "")).lower() == "active":
            path = Path(str(skill.get("scaffold_path") or ""))
            if path.exists():
                return path.read_text("utf-8", errors="ignore")[:5000]
    except Exception:
        pass
    path = Path("maya_skills") / "active" / "design_engineering.md"
    return path.read_text("utf-8", errors="ignore")[:5000] if path.exists() else ""
