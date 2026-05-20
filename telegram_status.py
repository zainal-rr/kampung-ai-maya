from __future__ import annotations

import os

from activation import current_work_location
from cost_tracker import usage_summary_text
from maya_eye_preview import preview_status
from permission_policy import permission_summary
from provider_readiness import provider_readiness_text
from project_actions import project_status
from route_tracker import last_route_text
from screen_session import screen_sight_status
from self_healing import self_heal_text
from storage import get_preference
from telegram_voice_state import voice_enabled
from vision_session import guided_sight_status


async def status_text(db_path: str) -> str:
    work_location = await current_work_location(db_path)
    voice = "on, Ara required" if await voice_enabled(db_path) else "off"
    vision = os.getenv("ENABLE_VISION_CAMERA", "0")
    effective_vision = "1" if vision == "1" and work_location == "imac" else "0"
    last_eye = await get_preference(db_path, "maya_eye_last_status") or "not checked yet"
    sight = await guided_sight_status(db_path)
    screen = await screen_sight_status(db_path)
    last_screen = await get_preference(db_path, "maya_screen_last_status") or "not checked yet"
    project = await project_status(db_path)
    return (
        "Maya status:\n"
        f"1) work location: {work_location}\n"
        f"2) telegram voice: {voice}\n"
        f"3) sight enabled: {vision}\n"
        f"4) sight usable now: {effective_vision}\n"
        f"5) guided sight: {sight}\n"
        f"6) local preview: {preview_status()}\n"
        f"7) screen sight: {screen}\n"
        f"8) last sight result: {last_eye}\n"
        f"9) last screen result: {last_screen}\n"
        f"10) project: {project}\n"
        f"11) cost: {(await usage_summary_text(db_path)).splitlines()[0]}\n"
        f"12) provider readiness: {provider_readiness_text().splitlines()[0]}\n"
        f"13) last route: {(await last_route_text(db_path)).splitlines()[0]}\n"
        f"14) self heal: {(await self_heal_text(db_path)).splitlines()[0]}\n"
        f"15) local permissions: {permission_summary()}"
    )


def command_help() -> str:
    return (
        "Maya commands:\n"
        "1) Main commands\n"
        "a) /help: show this command map\n"
        "b) /status: show iMac, voice, sight, screen, project, cost, provider, route, and self-heal status\n"
        "c) /imac on or /imac off: switch iMac mode\n"
        "d) /see: start camera guidance\n"
        "e) /screen or /screen off: start or stop screen awareness\n"
        "f) /project: show active project, or use /project close\n"
        "g) /memory: show memory sources, or use /memory preferences, /memory lessons, /memory forget text\n"
        "h) /complex question: use Maya's complex reasoning lane\n"
        "2) Hidden aliases that still work\n"
        "a) /openimac: same as /imac on\n"
        "b) /closeimac: same as /imac off\n"
        "c) /remember note: save a preference or lesson\n"
        "d) /voice: show Telegram Ara voice status\n"
        "e) /tasks: show open tasks\n"
        "f) /routines: show routines\n"
        "g) /preferences: show saved preferences\n"
        "h) /forget target: forget a specific memory\n"
        "i) /memorycleanup: clean stale memory\n"
        "j) /lessons: show recent lessons\n"
        "k) /skills: show available skills\n"
        "l) /createskill idea: propose a new skill\n"
        "m) /proposals: show skill proposals\n"
        "n) /cost: show usage estimate\n"
        "o) /providers: show provider readiness\n"
        "p) /route: show last routing decision\n"
        "q) /context: show compacted context\n"
        "r) /weekly: show weekly reflection\n"
        "s) /newtopic: reset current topic\n"
        "t) /selfheal: run safe self-heal check\n"
        "You can still talk normally: open project Kampung AI, show my tasks, remember my preference."
    )
