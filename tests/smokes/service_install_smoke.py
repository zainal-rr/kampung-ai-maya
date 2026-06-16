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

import maya_core.service_install as service_install


def main() -> None:
    calls = []
    restart_calls = []
    old_run = service_install.subprocess.run
    old_app_path = os.environ.get("KAMPUNG_AI_APP_PATH")
    old_plist_path = service_install.PLIST_PATH
    old_nightly_plist_path = service_install.NIGHTLY_MEMORY_PLIST_PATH

    def fake_run(args, **kwargs):
        calls.append(tuple(args))
        class Result:
            returncode = 0 if fake_run.loaded else 1
            stderr = ""
        return Result()

    fake_run.loaded = False

    try:
        with tempfile.TemporaryDirectory(prefix="maya-service-install-") as tmp:
            service_install.PLIST_PATH = Path(tmp) / "com.kampungai.maya.plist"
            app_exe = Path(tmp) / "Kampung AI.app" / "Contents" / "MacOS" / "Kampung AI"
            app_exe.parent.mkdir(parents=True)
            app_exe.write_text("#!/bin/sh\n", encoding="utf-8")
            app_exe.chmod(0o755)
            os.environ["KAMPUNG_AI_APP_PATH"] = str(app_exe.parents[2])
            plist = service_install.build_plist()
            assert plist["ProgramArguments"] == [str(app_exe), "--engine"]
            service_install.subprocess.run = fake_run
            service_install.restart()
            service_install.restart_weekly_memory()
            service_install.restart_nightly_memory()
            restart_calls = list(calls)

            calls.clear()
            service_install.ensure_running()
            assert service_install.PLIST_PATH.exists()
            assert any(call[:2] == ("launchctl", "bootstrap") for call in calls)
            assert any(call[:2] == ("launchctl", "enable") for call in calls)
            assert not any(call[:2] == ("launchctl", "bootout") for call in calls)

            calls.clear()
            fake_run.loaded = True
            service_install.ensure_running()
            assert not any(call[:2] == ("launchctl", "bootstrap") for call in calls)
            assert not any(call[:2] == ("launchctl", "bootout") for call in calls)
    finally:
        service_install.subprocess.run = old_run
        service_install.PLIST_PATH = old_plist_path
        service_install.NIGHTLY_MEMORY_PLIST_PATH = old_nightly_plist_path
        if old_app_path is None:
            os.environ.pop("KAMPUNG_AI_APP_PATH", None)
        else:
            os.environ["KAMPUNG_AI_APP_PATH"] = old_app_path
    assert any(call[:2] == ("launchctl", "bootout") for call in restart_calls)
    assert any(call[:2] == ("launchctl", "bootstrap") for call in restart_calls)
    assert any(call[:2] == ("launchctl", "enable") for call in restart_calls)
    weekly = service_install.build_weekly_memory_plist()
    assert weekly["StartCalendarInterval"] == {"Weekday": 0, "Hour": 20, "Minute": 0}
    assert any(str(item).endswith("weekly_memory.py") for item in weekly["ProgramArguments"])
    nightly = service_install.build_nightly_memory_plist()
    assert nightly["StartCalendarInterval"] == {"Hour": 2, "Minute": 30}
    assert any(str(item).endswith("nightly_consolidation.py") for item in nightly["ProgramArguments"])
    assert "--live" in nightly["ProgramArguments"]
    assert nightly["EnvironmentVariables"]["MEMORY_EMBED_RERANK_LIVE"] == "0"
    print("service_install_smoke: ok")


if __name__ == "__main__":
    main()
