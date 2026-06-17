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

from maya_core.artisan_maker import complete_blender_maker_output


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artisan-maker-") as tmp:
        root = Path(tmp)
        script = root / "make_cube.py"
        script.write_text(
            f"""
from pathlib import Path
import bpy

OUT = Path({str(root)!r})
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.mesh.primitive_cube_add(size=10, location=(0, 0, 0))
bpy.context.object.name = 'maker_smoke_cube'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'maker_smoke.blend'))
if hasattr(bpy.ops.wm, 'stl_export'):
    bpy.ops.wm.stl_export(filepath=str(OUT / 'maker_smoke.stl'))
else:
    bpy.ops.export_mesh.stl(filepath=str(OUT / 'maker_smoke.stl'))
""",
            encoding="utf-8",
        )
        result = complete_blender_maker_output(root, request="make a tiny 3D printable cube")
        if result.passed:
            _require((root / "maker_smoke.blend").exists(), "missing blend")
            _require((root / "maker_smoke.stl").exists(), "missing stl")
        else:
            issues = "\n".join(result.issues)
            _require("Blender binary not found" in issues, result.summary + " " + issues)
            _require(not (root / "maker_smoke.blend").exists(), "missing Blender should not claim blend")
            _require(not (root / "maker_smoke.stl").exists(), "missing Blender should not claim stl")
        _require((root / "README.md").exists(), "missing generated readme")
    print("artisan_maker_completion_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
