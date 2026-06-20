from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    blender = _blender_binary()
    with tempfile.TemporaryDirectory(prefix="maya-blender-maker-") as tmp:
        root = Path(tmp)
        script = root / "make_phone_stand.py"
        output = root / "out"
        output.mkdir(parents=True, exist_ok=True)
        script.write_text(_script(output), "utf-8")
        env = os.environ.copy()
        env.update(
            {
                "BLENDER_USER_CONFIG": str(root / "config"),
                "BLENDER_USER_SCRIPTS": str(root / "scripts"),
                "BLENDER_USER_EXTENSIONS": str(root / "extensions"),
            }
        )
        proc = subprocess.run(
            [
                blender,
                "--background",
                "--factory-startup",
                "--python-exit-code",
                "11",
                "--python",
                str(script),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if proc.returncode != 0:
            raise AssertionError(f"Blender export failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        blend = output / "phone_stand_smoke.blend"
        stl = output / "phone_stand_smoke.stl"
        _require(blend.exists() and blend.stat().st_size > 1024, "missing .blend output")
        _require(stl.exists() and stl.stat().st_size > 256, "missing .stl output")
    print("blender_maker_smoke: ok")


def _blender_binary() -> str:
    path = shutil.which("blender")
    if path:
        return path
    app_binary = Path("/Applications/Blender.app/Contents/MacOS/Blender")
    if app_binary.exists():
        return str(app_binary)
    raise AssertionError("Blender is not installed or not found.")


def _script(output: Path) -> str:
    return f"""
import math
from pathlib import Path

import bpy

OUT = Path({str(output)!r})
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

def cube(name, location, dimensions, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj

cube('phone_stand_base', (0, 0, 0.2), (90, 70, 4))
cube('phone_stand_back', (0, 22, 28), (90, 5, 55), (math.radians(-12), 0, 0))
cube('phone_lip', (0, -28, 8), (90, 8, 10))

bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'phone_stand_smoke.blend'))
stl_path = OUT / 'phone_stand_smoke.stl'
if hasattr(bpy.ops.wm, 'stl_export'):
    bpy.ops.wm.stl_export(filepath=str(stl_path))
else:
    bpy.ops.export_mesh.stl(filepath=str(stl_path))
"""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
