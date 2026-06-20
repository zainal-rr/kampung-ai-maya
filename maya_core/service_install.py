from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from maya_core.repo_paths import repo_root
from maya_core.service_install_ci import (
    NIGHTLY_CI_PLIST_PATH,
    build_nightly_ci_plist,
    install_nightly_ci,
    restart_nightly_ci,
    status_nightly_ci,
    uninstall_nightly_ci,
)

LABEL = "com.kampungai.maya"
WEEKLY_MEMORY_LABEL = "com.kampungai.maya.weeklymemory"
NIGHTLY_MEMORY_LABEL = "com.kampungai.maya.nightlymemory"
MEET_TUNNEL_LABEL = "com.kampungai.maya.meettunnel"
ROOT = Path(os.getenv("KAMPUNG_AI_REPO_ROOT", str(repo_root(__file__)))).expanduser().resolve()
APP_NAME = "Kampung AI"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
WEEKLY_MEMORY_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{WEEKLY_MEMORY_LABEL}.plist"
NIGHTLY_MEMORY_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{NIGHTLY_MEMORY_LABEL}.plist"
MEET_TUNNEL_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{MEET_TUNNEL_LABEL}.plist"


def build_plist() -> dict:
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": engine_program_arguments(),
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "EnvironmentVariables": {
            "KAMPUNG_AI_REPO_ROOT": str(ROOT),
            "KAMPUNG_AI_APP_PATH": str(kampung_ai_app_path()),
            "MAYA_HOTKEY_BACKEND": "file",
        },
        "StandardOutPath": str(logs / "launchd.stdout.log"),
        "StandardErrorPath": str(logs / "launchd.stderr.log"),
        "ProcessType": "Interactive",
    }


def engine_program_arguments() -> list[str]:
    app_executable = kampung_ai_app_executable()
    if os.getenv("KAMPUNG_AI_USE_APP_ENGINE", "1") != "0" and app_executable.exists():
        return [str(app_executable), "--engine"]
    return [str(ROOT / "venv/bin/python"), str(ROOT / "main.py")]


def kampung_ai_app_path() -> Path:
    return Path(os.getenv("KAMPUNG_AI_APP_PATH", f"/Applications/{APP_NAME}.app")).expanduser()


def kampung_ai_app_executable() -> Path:
    return kampung_ai_app_path() / "Contents" / "MacOS" / APP_NAME


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


def build_nightly_memory_plist() -> dict:
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return {
        "Label": NIGHTLY_MEMORY_LABEL,
        "ProgramArguments": [
            str(ROOT / "venv/bin/python"),
            str(ROOT / "nightly_consolidation.py"),
            "--db",
            "session_history.db",
            "--live",
        ],
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {
            "KAMPUNG_AI_REPO_ROOT": str(ROOT),
            # Keep embedding rerank evidence-gated. The 2026-06-11 memory eval
            # showed no improvement over lexical + neighbor + supersede recall.
            "MEMORY_EMBED_RERANK_LIVE": "0",
        },
        "StartCalendarInterval": {"Hour": 2, "Minute": 30},
        "StandardOutPath": str(logs / "nightly-memory.stdout.log"),
        "StandardErrorPath": str(logs / "nightly-memory.stderr.log"),
        "ProcessType": "Background",
    }


def build_meet_tunnel_plist() -> dict:
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    cloudflared = os.getenv("MAYA_MEET_CLOUDFLARED_BIN", "cloudflared")
    config_path = Path(os.getenv("MAYA_MEET_CLOUDFLARED_CONFIG", str(Path.home() / ".cloudflared" / "maya-meet.yml"))).expanduser()
    tunnel_name = os.getenv("MAYA_MEET_CLOUDFLARED_TUNNEL", "maya-meet")
    return {
        "Label": MEET_TUNNEL_LABEL,
        "ProgramArguments": [
            cloudflared,
            "tunnel",
            "--config",
            str(config_path),
            "run",
            tunnel_name,
        ],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "EnvironmentVariables": {
            "KAMPUNG_AI_REPO_ROOT": str(ROOT),
        },
        "StandardOutPath": str(logs / "meet-tunnel.stdout.log"),
        "StandardErrorPath": str(logs / "meet-tunnel.stderr.log"),
        "ProcessType": "Background",
    }


def install() -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as file_obj:
        plistlib.dump(build_plist(), file_obj)
    restart()
    print(f"Installed launch agent at {PLIST_PATH}")


def ensure_running() -> None:
    desired = build_plist()
    if _plist_matches(PLIST_PATH, desired) and is_loaded():
        print(f"{LABEL} already running.")
        return

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as file_obj:
        plistlib.dump(desired, file_obj)

    if is_loaded():
        restart()
    else:
        subprocess.run(["launchctl", "bootstrap", domain(), str(PLIST_PATH)], check=False)
        subprocess.run(["launchctl", "enable", f"{domain()}/{LABEL}"], check=False)
        print(f"Started {LABEL}")
    print(f"Installed launch agent at {PLIST_PATH}")


def install_weekly_memory() -> None:
    WEEKLY_MEMORY_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with WEEKLY_MEMORY_PLIST_PATH.open("wb") as file_obj:
        plistlib.dump(build_weekly_memory_plist(), file_obj)
    restart_weekly_memory()
    print(f"Installed weekly memory launch agent at {WEEKLY_MEMORY_PLIST_PATH}")


def install_nightly_memory() -> None:
    NIGHTLY_MEMORY_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NIGHTLY_MEMORY_PLIST_PATH.open("wb") as file_obj:
        plistlib.dump(build_nightly_memory_plist(), file_obj)
    restart_nightly_memory()
    print(f"Installed nightly memory launch agent at {NIGHTLY_MEMORY_PLIST_PATH}")


def install_meet_tunnel() -> None:
    MEET_TUNNEL_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MEET_TUNNEL_PLIST_PATH.open("wb") as file_obj:
        plistlib.dump(build_meet_tunnel_plist(), file_obj)
    restart_meet_tunnel()
    print(f"Installed Meet tunnel launch agent at {MEET_TUNNEL_PLIST_PATH}")


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


def uninstall_nightly_memory() -> None:
    bootout_nightly_memory()
    if NIGHTLY_MEMORY_PLIST_PATH.exists():
        NIGHTLY_MEMORY_PLIST_PATH.unlink()
    print(f"Removed {NIGHTLY_MEMORY_PLIST_PATH}")


def uninstall_meet_tunnel() -> None:
    bootout_meet_tunnel()
    if MEET_TUNNEL_PLIST_PATH.exists():
        MEET_TUNNEL_PLIST_PATH.unlink()
    print(f"Removed {MEET_TUNNEL_PLIST_PATH}")


def status() -> None:
    print(f"plist: {'present' if PLIST_PATH.exists() else 'missing'} -> {PLIST_PATH}")
    print(f"app: {'present' if kampung_ai_app_executable().exists() else 'missing'} -> {kampung_ai_app_path()}")
    result = subprocess.run(["launchctl", "print", f"{domain()}/{LABEL}"], capture_output=True, text=True, check=False)
    print("loaded:", "yes" if result.returncode == 0 else "no")
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip())


def is_loaded() -> bool:
    result = subprocess.run(["launchctl", "print", f"{domain()}/{LABEL}"], capture_output=True, text=True, check=False)
    return result.returncode == 0


def _plist_matches(path: Path, expected: dict) -> bool:
    if not path.exists():
        return False
    try:
        with path.open("rb") as file_obj:
            current = plistlib.load(file_obj)
    except Exception:
        return False
    keys = ("Label", "ProgramArguments", "WorkingDirectory", "RunAtLoad", "KeepAlive", "EnvironmentVariables")
    return all(current.get(key) == expected.get(key) for key in keys)


def status_weekly_memory() -> None:
    print(f"plist: {'present' if WEEKLY_MEMORY_PLIST_PATH.exists() else 'missing'} -> {WEEKLY_MEMORY_PLIST_PATH}")
    result = subprocess.run(["launchctl", "print", f"{domain()}/{WEEKLY_MEMORY_LABEL}"], capture_output=True, text=True, check=False)
    print("loaded:", "yes" if result.returncode == 0 else "no")
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip())


def status_nightly_memory() -> None:
    print(f"plist: {'present' if NIGHTLY_MEMORY_PLIST_PATH.exists() else 'missing'} -> {NIGHTLY_MEMORY_PLIST_PATH}")
    result = subprocess.run(["launchctl", "print", f"{domain()}/{NIGHTLY_MEMORY_LABEL}"], capture_output=True, text=True, check=False)
    print("loaded:", "yes" if result.returncode == 0 else "no")
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip())


def status_meet_tunnel() -> None:
    print(f"plist: {'present' if MEET_TUNNEL_PLIST_PATH.exists() else 'missing'} -> {MEET_TUNNEL_PLIST_PATH}")
    result = subprocess.run(["launchctl", "print", f"{domain()}/{MEET_TUNNEL_LABEL}"], capture_output=True, text=True, check=False)
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


def restart_nightly_memory() -> None:
    bootout_nightly_memory()
    subprocess.run(["launchctl", "bootstrap", domain(), str(NIGHTLY_MEMORY_PLIST_PATH)], check=False)
    subprocess.run(["launchctl", "enable", f"{domain()}/{NIGHTLY_MEMORY_LABEL}"], check=False)
    print(f"Restarted {NIGHTLY_MEMORY_LABEL}")


def restart_meet_tunnel() -> None:
    bootout_meet_tunnel()
    subprocess.run(["launchctl", "bootstrap", domain(), str(MEET_TUNNEL_PLIST_PATH)], check=False)
    subprocess.run(["launchctl", "enable", f"{domain()}/{MEET_TUNNEL_LABEL}"], check=False)
    print(f"Restarted {MEET_TUNNEL_LABEL}")


def bootout() -> None:
    subprocess.run(["launchctl", "bootout", domain(), str(PLIST_PATH)], check=False)


def bootout_weekly_memory() -> None:
    subprocess.run(["launchctl", "bootout", domain(), str(WEEKLY_MEMORY_PLIST_PATH)], check=False)


def bootout_nightly_memory() -> None:
    subprocess.run(["launchctl", "bootout", domain(), str(NIGHTLY_MEMORY_PLIST_PATH)], check=False)


def bootout_meet_tunnel() -> None:
    subprocess.run(["launchctl", "bootout", domain(), str(MEET_TUNNEL_PLIST_PATH)], check=False)


def domain() -> str:
    return f"gui/{os.getuid()}"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "install":
        install()
    elif action == "ensure":
        ensure_running()
    elif action == "install-weekly-memory":
        install_weekly_memory()
    elif action == "install-nightly-memory":
        install_nightly_memory()
    elif action == "install-nightly-ci":
        install_nightly_ci()
    elif action == "install-meet-tunnel":
        install_meet_tunnel()
    elif action == "restart":
        restart()
    elif action == "restart-weekly-memory":
        restart_weekly_memory()
    elif action == "restart-nightly-memory":
        restart_nightly_memory()
    elif action == "restart-nightly-ci":
        restart_nightly_ci()
    elif action == "restart-meet-tunnel":
        restart_meet_tunnel()
    elif action == "uninstall":
        uninstall()
    elif action == "uninstall-weekly-memory":
        uninstall_weekly_memory()
    elif action == "uninstall-nightly-memory":
        uninstall_nightly_memory()
    elif action == "uninstall-nightly-ci":
        uninstall_nightly_ci()
    elif action == "uninstall-meet-tunnel":
        uninstall_meet_tunnel()
    elif action == "status-weekly-memory":
        status_weekly_memory()
    elif action == "status-nightly-memory":
        status_nightly_memory()
    elif action == "status-nightly-ci":
        status_nightly_ci()
    elif action == "status-meet-tunnel":
        status_meet_tunnel()
    else:
        status()
