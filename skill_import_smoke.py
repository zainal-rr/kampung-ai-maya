from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from security_manifest import get_manifest
from skill_importer import import_local_skill
from skill_store import find_skill


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        skill_dir = Path(tmpdir) / "sample_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# Sample Browser Skill\n\nDescription: Browse and create reports.\n\n## Trigger Phrases\n- research sample\n\n## Tools\n- browser\n",
            "utf-8",
        )
        db_path = str(Path(tmpdir) / "test.db")
        reply = await import_local_skill(db_path, str(skill_dir))
        assert "not active" in reply
        skill = await find_skill(db_path, "sample browser")
        assert skill and skill["status"] == "proposed"
        assert Path(skill["scaffold_path"]).exists()
        manifest = await get_manifest(db_path, "skill", skill["skill_id"])
        assert manifest and manifest["permissions"]["browse_web"] is True
    print("skill_import_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
