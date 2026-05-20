from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path


LABEL = "com.kampungai.maya"
ROOT = Path(__file__).resolve().parent
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def build_plist() -> dict:
    command = (
        f'cd "{ROOT}" && set -a && source .env && set +a && '
        f'exec "{ROOT / "venv/bin/python"}" "{ROOT / "main.py"}"'
    )
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": ["/bin/zsh", "-lc", command],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(logs / "launchd.stdout.log"),
        "StandardErrorPath": str(logs / "launchd.stderr.log"),
        "ProcessType": "Interactive",
    }


def install() -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as file_obj:
        plistlib.dump(build_plist(), file_obj)
    bootout()
    subprocess.run(["launchctl", "bootstrap", domain(), str(PLIST_PATH)], check=False)
    subprocess.run(["launchctl", "enable", f"{domain()}/{LABEL}"], check=False)
    print(f"Installed launch agent at {PLIST_PATH}")


def uninstall() -> None:
    bootout()
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
    print(f"Removed {PLIST_PATH}")


def status() -> None:
    print(f"plist: {'present' if PLIST_PATH.exists() else 'missing'} -> {PLIST_PATH}")
    result = subprocess.run(["launchctl", "print", f"{domain()}/{LABEL}"], capture_output=True, text=True, check=False)
    print("loaded:", "yes" if result.returncode == 0 else "no")
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip())


def bootout() -> None:
    subprocess.run(["launchctl", "bootout", domain(), str(PLIST_PATH)], check=False)


def domain() -> str:
    return f"gui/{os.getuid()}"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()
    else:
        status()
