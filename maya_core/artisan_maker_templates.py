from __future__ import annotations

from pathlib import Path

from maya_core.artisan_maker_models import ArtisanMakerTemplatePlan
from maya_core.artisan_maker_script_templates import (
    _cable_clip_script,
    _label_tag_script,
    _number_after,
    _number_before,
    _organizer_tray_script,
    _phone_stand_script,
    _wall_hook_script,
)


def select_maker_template(request: str, brief: str = "") -> ArtisanMakerTemplatePlan | None:
    text = f"{request}\n{brief}".lower()
    if "cable clip" in text or "cord clip" in text:
        diameter = _number_before(text, ("mm cable", "mm cord", "mm diameter")) or _number_after(text, ("diameter", "cable", "cord")) or 4.8
        return ArtisanMakerTemplatePlan(
            "cable_clip",
            "Desk Cable Clip",
            "Known simple printable cable clip; deterministic template is more reliable than a long Codex run.",
            {
                "inner_diameter_mm": round(float(diameter), 2),
                "wall_mm": 1.4,
                "depth_mm": 10.0,
                "gap_degrees": 70.0,
            },
        )
    if "phone stand" in text:
        return ArtisanMakerTemplatePlan(
            "phone_stand",
            "Phone Stand",
            "Known simple printable phone stand; deterministic template is more reliable than a long Codex run.",
            {
                "base_width_mm": 90.0,
                "base_depth_mm": 70.0,
                "back_angle_degrees": 12.0,
            },
        )
    if "key tag" in text or "label tag" in text or "name tag" in text:
        return ArtisanMakerTemplatePlan(
            "label_tag",
            "Label Tag",
            "Known simple printable tag; deterministic template gives reliable holes and scale.",
            {"width_mm": 60.0, "height_mm": 24.0, "thickness_mm": 3.0, "hole_mm": 5.0},
        )
    if "wall hook" in text or "small hook" in text or "bag hook" in text:
        return ArtisanMakerTemplatePlan(
            "wall_hook",
            "Small Wall Hook",
            "Known simple printable hook; deterministic template gives reliable mounting plate and hook geometry.",
            {"plate_width_mm": 35.0, "plate_height_mm": 55.0, "hook_depth_mm": 28.0, "thickness_mm": 5.0},
        )
    if "organizer tray" in text or "desk tray" in text or "small tray" in text:
        return ArtisanMakerTemplatePlan(
            "organizer_tray",
            "Organizer Tray",
            "Known simple printable tray; deterministic template gives reliable wall thickness and open top.",
            {"width_mm": 100.0, "depth_mm": 70.0, "height_mm": 18.0, "wall_mm": 2.0},
        )
    return None


def write_maker_template_source(cwd: str | Path, plan: ArtisanMakerTemplatePlan) -> Path:
    root = Path(cwd).expanduser()
    folder = root / f"maya-template-{plan.template_id.replace('_', '-')}"
    folder.mkdir(parents=True, exist_ok=True)
    if plan.template_id == "cable_clip":
        script = folder / "make_cable_clip.py"
        script.write_text(_cable_clip_script(folder, plan.parameters), encoding="utf-8")
        return script
    if plan.template_id == "phone_stand":
        script = folder / "make_phone_stand.py"
        script.write_text(_phone_stand_script(folder, plan.parameters), encoding="utf-8")
        return script
    if plan.template_id == "label_tag":
        script = folder / "make_label_tag.py"
        script.write_text(_label_tag_script(folder, plan.parameters), encoding="utf-8")
        return script
    if plan.template_id == "wall_hook":
        script = folder / "make_wall_hook.py"
        script.write_text(_wall_hook_script(folder, plan.parameters), encoding="utf-8")
        return script
    if plan.template_id == "organizer_tray":
        script = folder / "make_organizer_tray.py"
        script.write_text(_organizer_tray_script(folder, plan.parameters), encoding="utf-8")
        return script
    raise ValueError(f"Unknown maker template: {plan.template_id}")
