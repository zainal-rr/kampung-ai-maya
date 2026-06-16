from __future__ import annotations

"""Secret lookup for Kampung AI.

Modes:
- env: current behavior, read process environment / .env.
- keychain: read macOS Keychain only.
- auto: try Keychain first, then env fallback.

Default remains env during migration.
"""

import os
import subprocess
from collections.abc import Callable, Sequence

from dotenv import load_dotenv


load_dotenv(override=False)


DEFAULT_KEYCHAIN_SERVICE = "Kampung AI"
SECRET_ENV_NAMES = (
    "XAI_API_KEY",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
)

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def secret_mode() -> str:
    return os.getenv("MAYA_SECRET_PROVIDER", "env").strip().lower() or "env"


def get_secret(
    name: str,
    default: str | None = None,
    *,
    mode: str | None = None,
    service: str | None = None,
    runner: Runner | None = None,
) -> str | None:
    selected = (mode or secret_mode()).strip().lower()
    if selected == "env":
        return os.getenv(name, default)
    if selected == "keychain":
        return _keychain_get(name, service=service, runner=runner) or default
    if selected == "auto":
        return _keychain_get(name, service=service, runner=runner) or os.getenv(name, default)
    raise ValueError(f"Unknown MAYA_SECRET_PROVIDER mode: {selected}")


def require_secrets(names: Sequence[str]) -> None:
    missing = [name for name in names if not get_secret(name)]
    if missing:
        raise ValueError(f"Missing required environment variables or Keychain secrets: {', '.join(sorted(missing))}")


def migrate_env_to_keychain(
    names: Sequence[str] = SECRET_ENV_NAMES,
    *,
    service: str | None = None,
    runner: Runner | None = None,
) -> dict[str, str]:
    results: dict[str, str] = {}
    for name in names:
        value = os.getenv(name)
        if not value:
            results[name] = "missing_env"
            continue
        _keychain_set(name, value, service=service, runner=runner)
        results[name] = "stored"
    return results


def redact_secret_value(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:3]}...{text[-3:]}"


def redact_secrets_in_text(text: str, secret_values: Sequence[str | None]) -> str:
    clean = str(text)
    for value in secret_values:
        if value:
            clean = clean.replace(str(value), redact_secret_value(str(value)))
    return clean


def _keychain_get(name: str, *, service: str | None = None, runner: Runner | None = None) -> str | None:
    command = [
        "/usr/bin/security",
        "find-generic-password",
        "-s",
        service or os.getenv("MAYA_KEYCHAIN_SERVICE", DEFAULT_KEYCHAIN_SERVICE),
        "-a",
        name,
        "-w",
    ]
    proc = _run(command, runner)
    if proc.returncode != 0:
        return None
    value = (proc.stdout or "").strip()
    return value or None


def _keychain_set(name: str, value: str, *, service: str | None = None, runner: Runner | None = None) -> None:
    command = [
        "/usr/bin/security",
        "add-generic-password",
        "-U",
        "-s",
        service or os.getenv("MAYA_KEYCHAIN_SERVICE", DEFAULT_KEYCHAIN_SERVICE),
        "-a",
        name,
        "-w",
        value,
    ]
    proc = _run(command, runner)
    if proc.returncode != 0:
        raise RuntimeError(f"Could not store {name} in macOS Keychain: {(proc.stderr or '').strip()}")


def _run(command: Sequence[str], runner: Runner | None = None) -> subprocess.CompletedProcess[str]:
    if runner is not None:
        return runner(command)
    try:
        return subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(list(command), 1, "", str(exc))
