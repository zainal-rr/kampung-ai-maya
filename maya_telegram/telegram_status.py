from __future__ import annotations

import os

from maya_core.activation import current_work_location
from maya_core.cost_tracker import usage_summary_text
from maya_core.maya_eye_preview import preview_status
from permission_policy import permission_summary
from provider_readiness import provider_readiness_text
from project_actions import project_status
from retention_policy import retention_status_summary
from route_tracker import last_route_text
from screen_session import screen_sight_status
from self_heal_store import latest_self_heal_report
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
        f"14) self heal: {await _self_heal_status_line(db_path)}\n"
        f"15) retention: {await retention_status_summary(db_path)}\n"
        f"16) local permissions: {permission_summary()}"
    )


async def _self_heal_status_line(db_path: str) -> str:
    report = await latest_self_heal_report(db_path)
    if not report:
        return "no open repair proposal"
    return f"latest proposal #{report['id']}: {str(report['issue']).splitlines()[0][:80]}"


def command_help() -> str:
    return (
        "Maya commands:\n"
        "1) Main commands\n"
        "a) /help: show this command map\n"
        "b) /status: show iMac, voice, sight, screen, project, cost, provider, route, and self-heal status\n"
        "c) /imac on or /imac off: switch iMac mode\n"
        "d) /see: toggle camera guidance on or off\n"
        "e) /screen: toggle screen awareness on or off\n"
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
        "i) /memory migrate: link old memory rows to canonical memory IDs\n"
        "j) /memory pin target: keep an important canonical memory eligible\n"
        "k) /memory unpin target: remove manual memory priority\n"
        "l) /memory inspect target: show canonical memory IDs and activation class\n"
        "m) /memorycleanup: clean stale memory\n"
        "n) /lessons: show recent lessons\n"
        "o) /skills: show available skills\n"
        "p) /createskill idea: propose a new skill\n"
        "q) /proposals: show skill proposals\n"
        "r) /cost: show usage estimate\n"
        "s) /providers: show provider readiness\n"
        "t) /route: show last routing decision\n"
        "u) /delivery: show last Telegram delivery attempt\n"
        "v) /turn: show last Telegram processing timing/status\n"
        "w) /context: show compacted context\n"
        "x) /weekly: show weekly reflection\n"
        "y) /newtopic: reset current topic\n"
        "z) /selfheal: run safe self-heal check\n"
        "You can still talk normally: open project Kampung AI, show my tasks, remember my preference."
    )
