from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile

from maya_core.mcp_registry import audit_mcp_server, list_mcp_servers, propose_mcp_server, set_mcp_status
from security_manifest import get_manifest


async def main() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        await propose_mcp_server(tmp.name, "files", "npx files", ["TOKEN"], "read files and create artifacts")
        rows = await list_mcp_servers(tmp.name)
        assert rows[0]["name"] == "files"
        manifest = await get_manifest(tmp.name, "mcp", "files")
        assert manifest and manifest["permissions"]["read_files"] is True
        assert not await set_mcp_status(tmp.name, "files", "enabled")
        rows = await list_mcp_servers(tmp.name)
        assert rows[0]["status"] == "proposed"
        assert await set_mcp_status(tmp.name, "files", "approved")
        assert await set_mcp_status(tmp.name, "files", "enabled")
        audit = await audit_mcp_server(tmp.name, "files")
        assert "enabled" in audit
        assert await set_mcp_status(tmp.name, "files", "disabled")
        disabled = await list_mcp_servers(tmp.name, status="disabled")
        assert len(disabled) == 1
    print("mcp_registry_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
