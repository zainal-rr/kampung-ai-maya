from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


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
            service_install = kampung_ai_app._load_service_install_module()
            for name in ("ensure_running", "install", "uninstall"):
                _require(hasattr(service_install, name), f"service_install missing {name}")
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
