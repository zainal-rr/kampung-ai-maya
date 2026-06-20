from __future__ import annotations

import os

from maya_core.activation import current_work_location
from maya_core.cost_tracker import usage_summary_text
from maya_core.maya_eye_preview import preview_status
from maya_core.permission_policy import permission_summary
from maya_core.provider_readiness import provider_readiness_text
from maya_core.project_actions import project_status
from maya_core.retention_policy import retention_status_summary
from maya_core.route_tracker import last_route_text
from maya_core.screen_session import screen_sight_status
from maya_core.self_heal_store import latest_self_heal_report
from maya_core.storage import get_preference
from maya_telegram.telegram_voice_state import voice_enabled
from maya_core.vision_session import guided_sight_status


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
        "1) Registered menu commands\n"
        "a) /help: show this command map\n"
        "b) /status: show iMac, voice, sight, screen, project, cost, provider, route, self-heal, and permissions status\n"
        "c) /imac on|off: switch iMac mode\n"
        "d) /see: toggle camera guidance on or off\n"
        "e) /screen [question]: toggle screen awareness, or ask about the current screen\n"
        "f) /project [close]: show or close the active project\n"
        "g) /memory [subcommand]: show or manage memory\n"
        "h) /join meet-url: send Maya into a Google Meet\n"
        "i) /leave [meet-url]: remove Maya from the current Meet\n"
        "j) /meetstatus [meet-url]: show Maya Meet status from source-of-truth\n"
        "k) /reliability: show the reliability scorecard and incident ledger\n"
        "l) /complex question: use Maya's complex reasoning lane\n"
        "2) Hidden slash commands that still work\n"
        "a) /openimac, /closeimac: aliases for /imac on and /imac off\n"
        "b) /remember note: save an owner-authored preference or lesson\n"
        "c) /voice [on|off]: show or set Telegram Ara voice status\n"
        "d) /tasks, /routines, /preferences: list stored work state\n"
        "e) /forget target: forget a specific memory\n"
        "f) /memorycleanup, /memorymigrate, /memoryinspect [target], /memorypin target, /memoryunpin target\n"
        "g) /lessons, /skills, /createskill idea, /proposals\n"
        "h) /cost, /providers, /route\n"
        "i) /delivery, /lastdelivery, /turn, /lastturn\n"
        "j) /review, /artifactreview, /artifactqa\n"
        "k) /context, /weekly [status|run], /newtopic, /selfheal [dryrun|force]\n"
        "l) /artisan [transcript|app|maker|apply]\n"
        "m) /reliability note [category] what happened: log today's reliability failure note\n"
        "3) Reliability note categories\n"
        "a) correction, missed_reply, route, voice, memory, delivery, browser, cost, false_done\n"
        "You can still talk normally: open project Kampung AI, show my tasks, remember my preference."
    )
