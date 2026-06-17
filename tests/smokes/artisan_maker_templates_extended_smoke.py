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

from maya_core.artisan_maker import complete_blender_maker_output, select_maker_template, write_maker_template_source


def main() -> None:
    cases = (
        ("make a printable key tag", "label_tag"),
        ("make a small wall hook for 3D printing", "wall_hook"),
        ("make a desk organizer tray", "organizer_tray"),
    )
    with tempfile.TemporaryDirectory(prefix="maya-maker-templates-") as tmp:
        root = Path(tmp)
        for request, template_id in cases:
            folder = root / template_id
            plan = select_maker_template(request)
            _require(plan is not None and plan.template_id == template_id, f"wrong template for {request}")
            script = write_maker_template_source(folder, plan)
            _require(script.exists(), f"missing source for {template_id}")
            qa = complete_blender_maker_output(folder, request=request, brief="Stop before physical print.")
            if qa.passed:
                _require(qa.blend_files and qa.mesh_files, f"missing outputs for {template_id}")
                _require(qa.dimensions_mm, f"missing dimensions for {template_id}")
                _require(qa.preview_files, f"missing preview for {template_id}")
            else:
                issues = "\n".join(qa.issues)
                _require("Blender binary not found" in issues, qa.summary + " " + issues)
                _require(not qa.blend_files and not qa.mesh_files, f"missing Blender should not claim outputs for {template_id}")
            _require(qa.readme_files, f"missing README for {template_id}")
    print("artisan_maker_templates_extended_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
