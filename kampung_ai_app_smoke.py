from __future__ import annotations

import os
import tempfile
from pathlib import Path

import kampung_ai_app


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="kampung-ai-app-smoke-") as tmp:
        root = Path(tmp)
        home = root / "home"
        home.mkdir()
        (root / "venv" / "lib" / "python3.14" / "site-packages").mkdir(parents=True)
        old_root = os.environ.get("KAMPUNG_AI_REPO_ROOT")
        old_home = os.environ.get("HOME")
        try:
            os.environ["KAMPUNG_AI_REPO_ROOT"] = str(root)
            os.environ["HOME"] = str(home)
            site_packages = kampung_ai_app._venv_site_packages(root)
            _require(site_packages is not None and site_packages.name == "site-packages", "site-packages not found")
            lock = kampung_ai_app._acquire_controller_lock()
            _require(lock is not None, "first controller lock failed")
            try:
                _require(kampung_ai_app._acquire_controller_lock() is None, "second controller lock unexpectedly succeeded")
            finally:
                lock.close()
        finally:
            if old_root is None:
                os.environ.pop("KAMPUNG_AI_REPO_ROOT", None)
            else:
                os.environ["KAMPUNG_AI_REPO_ROOT"] = old_root
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
    print("kampung_ai_app_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
