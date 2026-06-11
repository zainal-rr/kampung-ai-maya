from __future__ import annotations

import os
import tempfile
from pathlib import Path

import sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import secret_migration


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    old_root = secret_migration.ROOT
    old_value = os.environ.get("MAYA_MIGRATION_FAKE_API_KEY")
    try:
        with tempfile.TemporaryDirectory(prefix="maya-secret-migration-") as tmp:
            root = Path(tmp)
            (root / ".env").write_text("MAYA_MIGRATION_FAKE_API_KEY=fake-value\n", encoding="utf-8")
            (root / "logs").mkdir()
            (root / "logs" / "clean.log").write_text("nothing to see\n", encoding="utf-8")
            secret_migration.ROOT = root
            os.environ["MAYA_MIGRATION_FAKE_API_KEY"] = "fake-value"
            rows = secret_migration.inventory()
            names = {row["name"] for row in rows}
            _require("MAYA_MIGRATION_FAKE_API_KEY" in names, "inventory did not include fake key name")
            leaks = secret_migration.log_leak_scan(["MAYA_MIGRATION_FAKE_API_KEY"])
            _require(all(status == "clean" for status in leaks.values()), f"unexpected leak result: {leaks}")
            (root / "logs" / "bad.log").write_text("fake-value\n", encoding="utf-8")
            leaks = secret_migration.log_leak_scan(["MAYA_MIGRATION_FAKE_API_KEY"])
            _require(leaks.get("logs/bad.log") == "contains_secret", f"leak scan missed fake secret: {leaks}")
    finally:
        secret_migration.ROOT = old_root
        if old_value is None:
            os.environ.pop("MAYA_MIGRATION_FAKE_API_KEY", None)
        else:
            os.environ["MAYA_MIGRATION_FAKE_API_KEY"] = old_value
    print("secret_migration_smoke: ok")


if __name__ == "__main__":
    main()
