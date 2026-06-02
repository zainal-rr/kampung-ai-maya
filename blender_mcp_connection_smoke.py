from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    blender = _blender_binary()
    addon_path = Path.home() / "Library/Application Support/Blender/5.1/scripts/addons/blender_mcp.py"
    _require(addon_path.exists(), f"Blender MCP add-on is not installed at {addon_path}")
    with tempfile.TemporaryDirectory(prefix="maya-blender-mcp-") as tmp:
        script = Path(tmp) / "mcp_smoke.py"
        script.write_text(_script(), "utf-8")
        proc = subprocess.run(
            [blender, "--background", "--factory-startup", "--python-exit-code", "11", "--python", str(script)],
            capture_output=True,
            text=True,
            timeout=45,
        )
    if proc.returncode != 0:
        raise AssertionError(f"Blender MCP smoke failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    _require("mcp scene inspection ok" in proc.stdout, proc.stdout + proc.stderr)
    print("blender_mcp_connection_smoke: ok")


def _script() -> str:
    return r"""
import bpy

bpy.ops.preferences.addon_enable(module='blender_mcp')
prefs = bpy.context.preferences.addons['blender_mcp'].preferences
prefs.telemetry_consent = False
bpy.context.scene.blendermcp_port = 9876
bpy.ops.blendermcp.start_server()
server = bpy.types.blendermcp_server

try:
    initial = server.execute_command({"type": "get_scene_info", "params": {}})
    if initial.get("status") != "success":
        raise RuntimeError(initial)
    create = server.execute_command({
        "type": "execute_code",
        "params": {
            "code": "import bpy\nbpy.ops.mesh.primitive_cube_add(size=10, location=(0, 0, 5))\nbpy.context.object.name='maya_mcp_smoke_cube'"
        }
    })
    if create.get("status") != "success":
        raise RuntimeError(create)
    scene = server.execute_command({"type": "get_scene_info", "params": {}})
    objects = scene.get("result", {}).get("objects", [])
    if not any(obj.get("name") == "maya_mcp_smoke_cube" for obj in objects):
        raise RuntimeError(scene)
    print("mcp scene inspection ok")
finally:
    bpy.ops.blendermcp.stop_server()
"""


def _blender_binary() -> str:
    path = shutil.which("blender")
    if path:
        return path
    app_binary = Path("/Applications/Blender.app/Contents/MacOS/Blender")
    if app_binary.exists():
        return str(app_binary)
    raise AssertionError("Blender is not installed or not found.")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
