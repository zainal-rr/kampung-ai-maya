from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path


LABEL = "com.kampungai.maya"
WEEKLY_MEMORY_LABEL = "com.kampungai.maya.weeklymemory"
ROOT = Path(__file__).resolve().parent
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
WEEKLY_MEMORY_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{WEEKLY_MEMORY_LABEL}.plist"


def build_plist() -> dict:
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": [str(ROOT / "venv/bin/python"), str(ROOT / "main.py")],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(logs / "launchd.stdout.log"),
        "StandardErrorPath": str(logs / "launchd.stderr.log"),
        "ProcessType": "Interactive",
    }


def build_weekly_memory_plist() -> dict:
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return {
        "Label": WEEKLY_MEMORY_LABEL,
        "ProgramArguments": [
            str(ROOT / "venv/bin/python"),
            str(ROOT / "weekly_memory.py"),
            "--save",
            "--live",
            "--trigger-source",
            "launchd",
        ],
        "WorkingDirectory": str(ROOT),
        "StartCalendarInterval": {"Weekday": 0, "Hour": 20, "Minute": 0},
        "StandardOutPath": str(logs / "weekly-memory.stdout.log"),
        "StandardErrorPath": str(logs / "weekly-memory.stderr.log"),
        "ProcessType": "Background",
    }


def install() -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as file_obj:
        plistlib.dump(build_plist(), file_obj)
    restart()
    print(f"Installed launch agent at {PLIST_PATH}")


def install_weekly_memory() -> None:
    WEEKLY_MEMORY_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with WEEKLY_MEMORY_PLIST_PATH.open("wb") as file_obj:
        plistlib.dump(build_weekly_memory_plist(), file_obj)
    restart_weekly_memory()
    print(f"Installed weekly memory launch agent at {WEEKLY_MEMORY_PLIST_PATH}")


def uninstall() -> None:
    bootout()
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
    print(f"Removed {PLIST_PATH}")


def uninstall_weekly_memory() -> None:
    bootout_weekly_memory()
    if WEEKLY_MEMORY_PLIST_PATH.exists():
        WEEKLY_MEMORY_PLIST_PATH.unlink()
    print(f"Removed {WEEKLY_MEMORY_PLIST_PATH}")


def status() -> None:
    print(f"plist: {'present' if PLIST_PATH.exists() else 'missing'} -> {PLIST_PATH}")
    result = subprocess.run(["launchctl", "print", f"{domain()}/{LABEL}"], capture_output=True, text=True, check=False)
    print("loaded:", "yes" if result.returncode == 0 else "no")
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip())


def status_weekly_memory() -> None:
    print(f"plist: {'present' if WEEKLY_MEMORY_PLIST_PATH.exists() else 'missing'} -> {WEEKLY_MEMORY_PLIST_PATH}")
    result = subprocess.run(["launchctl", "print", f"{domain()}/{WEEKLY_MEMORY_LABEL}"], capture_output=True, text=True, check=False)
    print("loaded:", "yes" if result.returncode == 0 else "no")
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip())


def restart() -> None:
    bootout()
    subprocess.run(["launchctl", "bootstrap", domain(), str(PLIST_PATH)], check=False)
    subprocess.run(["launchctl", "enable", f"{domain()}/{LABEL}"], check=False)
    print(f"Restarted {LABEL}")


def restart_weekly_memory() -> None:
    bootout_weekly_memory()
    subprocess.run(["launchctl", "bootstrap", domain(), str(WEEKLY_MEMORY_PLIST_PATH)], check=False)
    subprocess.run(["launchctl", "enable", f"{domain()}/{WEEKLY_MEMORY_LABEL}"], check=False)
    print(f"Restarted {WEEKLY_MEMORY_LABEL}")


def bootout() -> None:
    subprocess.run(["launchctl", "bootout", domain(), str(PLIST_PATH)], check=False)


def bootout_weekly_memory() -> None:
    subprocess.run(["launchctl", "bootout", domain(), str(WEEKLY_MEMORY_PLIST_PATH)], check=False)


def domain() -> str:
    return f"gui/{os.getuid()}"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "install":
        install()
    elif action == "install-weekly-memory":
        install_weekly_memory()
    elif action == "restart":
        restart()
    elif action == "restart-weekly-memory":
        restart_weekly_memory()
    elif action == "uninstall":
        uninstall()
    elif action == "uninstall-weekly-memory":
        uninstall_weekly_memory()
    elif action == "status-weekly-memory":
        status_weekly_memory()
    else:
        status()
