from __future__ import annotations

import asyncio
import tempfile

from mcp_registry import audit_mcp_server, list_mcp_servers, propose_mcp_server, set_mcp_status
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
