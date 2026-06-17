from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path

from maya_core.repo_paths import repo_root

NIGHTLY_CI_LABEL = "com.kampungai.maya.nightlyci"
ROOT = Path(os.getenv("KAMPUNG_AI_REPO_ROOT", str(repo_root(__file__)))).expanduser().resolve()
NIGHTLY_CI_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{NIGHTLY_CI_LABEL}.plist"


def build_nightly_ci_plist() -> dict:
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return {
        "Label": NIGHTLY_CI_LABEL,
        "ProgramArguments": [
            str(ROOT / "venv/bin/python"),
            str(ROOT / "local_ci.py"),
            "--extended",
        ],
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {
            "KAMPUNG_AI_REPO_ROOT": str(ROOT),
            "MAYA_TEST_MODE": "1",
        },
        "StartCalendarInterval": {"Hour": 3, "Minute": 30},
        "StandardOutPath": str(logs / "nightly-ci.stdout.log"),
        "StandardErrorPath": str(logs / "nightly-ci.stderr.log"),
        "ProcessType": "Background",
    }


def install_nightly_ci() -> None:
    NIGHTLY_CI_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NIGHTLY_CI_PLIST_PATH.open("wb") as file_obj:
        plistlib.dump(build_nightly_ci_plist(), file_obj)
    restart_nightly_ci()
    print(f"Installed nightly CI launch agent at {NIGHTLY_CI_PLIST_PATH}")


def uninstall_nightly_ci() -> None:
    bootout_nightly_ci()
    if NIGHTLY_CI_PLIST_PATH.exists():
        NIGHTLY_CI_PLIST_PATH.unlink()
    print(f"Removed {NIGHTLY_CI_PLIST_PATH}")


def status_nightly_ci() -> None:
    print(f"plist: {'present' if NIGHTLY_CI_PLIST_PATH.exists() else 'missing'} -> {NIGHTLY_CI_PLIST_PATH}")
    result = subprocess.run(["launchctl", "print", f"{domain()}/{NIGHTLY_CI_LABEL}"], capture_output=True, text=True, check=False)
    print("loaded:", "yes" if result.returncode == 0 else "no")
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip())


def restart_nightly_ci() -> None:
    bootout_nightly_ci()
    subprocess.run(["launchctl", "bootstrap", domain(), str(NIGHTLY_CI_PLIST_PATH)], check=False)
    subprocess.run(["launchctl", "enable", f"{domain()}/{NIGHTLY_CI_LABEL}"], check=False)
    print(f"Restarted {NIGHTLY_CI_LABEL}")


def bootout_nightly_ci() -> None:
    subprocess.run(["launchctl", "bootout", domain(), str(NIGHTLY_CI_PLIST_PATH)], check=False)


def domain() -> str:
    return f"gui/{os.getuid()}"
