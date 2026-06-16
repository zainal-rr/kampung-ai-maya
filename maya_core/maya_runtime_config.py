from __future__ import annotations

"""Typed runtime configuration for the single-user Maya runtime.

This is intentionally for operational/runtime knobs only. It must not absorb
memory content, profile summaries, project facts, or other historical user
knowledge.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class MayaRuntimeConfig:
    owner_name: str
    telegram_allowed_chat_ids: tuple[str, ...]
    workspace_root: Path
    legacy_workspace_root: Path
    project_roots: tuple[Path, ...]
    preferred_audio_output_names: tuple[str, ...]
    blocked_audio_output_names: tuple[str, ...]
    browser_driver_default: str
    voice_model: str
    voice_name: str


def runtime_config() -> MayaRuntimeConfig:
    return _runtime_config_from_env(_env_snapshot())


def reload_runtime_config() -> MayaRuntimeConfig:
    _runtime_config_from_env.cache_clear()
    return runtime_config()


def parse_csv(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(raw or "").split(",") if item.strip())


def normalized_names(values: tuple[str, ...]) -> list[str]:
    return [item.casefold().strip() for item in values if item.strip()]


def _env_snapshot() -> tuple[tuple[str, str], ...]:
    keys = (
        "MAYA_OWNER_NAME",
        "TELEGRAM_ALLOWED_CHAT_IDS",
        "MAYA_WORKSPACE_ROOT",
        "MAYA_LEGACY_WORKSPACE_ROOT",
        "MAYA_PROJECT_ROOTS",
        "MAYA_VOICE_ALLOWED_HEADPHONE_NAMES",
        "MAYA_VOICE_BLOCKED_WAKE_NAMES",
        "MAYA_BROWSER_DRIVER",
        "MAYA_BROWSER_DRIVER_DEFAULT",
        "XAI_REALTIME_MODEL",
        "XAI_REALTIME_VOICE",
    )
    return tuple((key, os.getenv(key, "")) for key in keys)


@lru_cache(maxsize=4)
def _runtime_config_from_env(snapshot: tuple[tuple[str, str], ...]) -> MayaRuntimeConfig:
    env = dict(snapshot)
    workspace_root = Path(env.get("MAYA_WORKSPACE_ROOT") or (Path.home() / "Desktop" / "Maya")).expanduser()
    legacy_root = Path(env.get("MAYA_LEGACY_WORKSPACE_ROOT") or (Path.home() / "Downloads" / "Kampung AI")).expanduser()
    project_roots = (
        Path.home() / "projects",
        workspace_root / "Projects",
        legacy_root / "Projects",
        *tuple(Path(item).expanduser() for item in parse_csv(env.get("MAYA_PROJECT_ROOTS", ""))),
    )
    browser_driver = (
        env.get("MAYA_BROWSER_DRIVER")
        or env.get("MAYA_BROWSER_DRIVER_DEFAULT")
        or "extension"
    ).strip().lower()
    return MayaRuntimeConfig(
        owner_name=env.get("MAYA_OWNER_NAME") or "Zainal",
        telegram_allowed_chat_ids=parse_csv(env.get("TELEGRAM_ALLOWED_CHAT_IDS", "")),
        workspace_root=workspace_root,
        legacy_workspace_root=legacy_root,
        project_roots=tuple(dict.fromkeys(path.resolve(strict=False) for path in project_roots)),
        preferred_audio_output_names=parse_csv(
            env.get("MAYA_VOICE_ALLOWED_HEADPHONE_NAMES")
            or "Zainal’s Headphone,Sony,WH-1000XM5,MX5"
        ),
        blocked_audio_output_names=parse_csv(
            env.get("MAYA_VOICE_BLOCKED_WAKE_NAMES")
            or "AirPods,iMac Microphone,iMac Speakers"
        ),
        browser_driver_default=browser_driver,
        voice_model=env.get("XAI_REALTIME_MODEL") or "grok-voice-latest",
        voice_name=env.get("XAI_REALTIME_VOICE") or "Ara",
    )
