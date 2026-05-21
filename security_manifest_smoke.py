from __future__ import annotations

import asyncio
import tempfile

from security_manifest import SecurityManifest, get_manifest, list_manifests, manifest_summary, upsert_manifest
from skill_registry import ensure_builtin_skill_manifests


async def main() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        manifest = SecurityManifest(
            "skill",
            "flight_research",
            {"browse_web": True, "browser_click": True},
            hard_blocks=["private_exposure"],
        )
        await upsert_manifest(tmp.name, manifest)
        saved = await get_manifest(tmp.name, "skill", "flight_research")
        assert saved is not None
        assert saved["permissions"]["browse_web"] is True
        assert "browser_click" in saved["approval_required"]
        assert "private_exposure" in saved["hard_blocks"]
        assert len(await list_manifests(tmp.name)) == 1
        assert "flight_research" in manifest_summary(saved)
        await ensure_builtin_skill_manifests(tmp.name)
        built_in = await get_manifest(tmp.name, "skill", "web_browse")
        assert built_in and built_in["permissions"]["browse_web"] is True
    print("security_manifest_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
