from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

from maya_core.assistant_skill_commands import handle_skill_lifecycle
from maya_core.security_manifest import get_manifest
from maya_core.skill_importer import import_installed_skills, import_local_skill, import_npx_skill
from maya_core.skill_store import find_skill


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
        bad = await import_npx_skill(db_path, "bad;rm -rf")
        assert "simple owner/repo" in bad
        installed = Path(tmpdir) / ".agents" / "skills" / "taste"
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text(
            "# Taste Skill\n\nDescription: Review visual taste.\n\n## Trigger Phrases\n- critique design\n\n## Tools\n- review\n",
            "utf-8",
        )
        names = await import_installed_skills(db_path, Path(tmpdir), "npx skills add fake/taste")
        assert "Taste Skill" in names
        imported = await find_skill(db_path, "taste")
        assert imported and imported["status"] == "proposed"
        reply = await handle_skill_lifecycle(db_path, "test skill Taste Skill")
        assert reply and "activation wrapper" in reply
        reply = await handle_skill_lifecycle(db_path, "improve skill Taste Skill")
        assert reply and "Now run" in reply
        reply = await handle_skill_lifecycle(db_path, "test skill Taste Skill")
        assert reply and "It can be activated after approval" in reply
    print("skill_import_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
