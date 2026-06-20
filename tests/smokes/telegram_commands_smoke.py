from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from maya_core.assistant import KampungAssistant
from maya_core.lesson_store import init_lesson_db
from maya_core.reliability_incident_store import load_incidents
from maya_documents.artifact_review_store import record_artifact_review
from maya_core.routine_store import init_routine_db
from maya_core.skill_store import init_skill_db
from maya_core.route_tracker import record_route
from maya_core.session_memory_store import init_session_memory_db, save_session_summary
from maya_core.self_heal_store import init_self_heal_db
from maya_core.storage import get_history, init_db, save_history_message, upsert_preference
from maya_core.topic_context import recent_topic_history
from maya_harness.live_reliability_soak import load_soak
from maya_telegram.telegram_command_registry import all_command_names, registered_command_specs
from maya_telegram.telegram_commands import bot_commands, command_to_text, parse_command, voice_enabled
from maya_telegram.telegram_channel import TelegramChannel


async def main() -> None:
    os.environ["MAYA_EYE_PREVIEW"] = "0"
    os.environ["TELEGRAM_VOICE_LOCKED"] = "1"
    os.environ["TELEGRAM_VOICE_REPLIES"] = "1"
    with tempfile.TemporaryDirectory(prefix="maya-telegram-commands-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)

        parsed = parse_command("/openImac")
        _require(parsed and parsed.name == "openimac", "mixed case command did not parse")
        _require(await command_to_text(db_path, parsed) == "open imac", "openImac did not map")
        visible = [item.command for item in bot_commands()]
        _require(
            visible == [spec.name for spec in registered_command_specs()],
            "visible commands not reduced",
        )
        _require(await command_to_text(db_path, parse_command("/imac off")) == "close imac", "imac off did not map")

        remembered = await command_to_text(db_path, parse_command("/remember short replies please"))
        _require(remembered == "remember that short replies please", "remember did not map")
        memory = await command_to_text(db_path, parse_command("/memory"))
        _require("Memory sources:" in memory, "memory command did not return sources")
        _require(await command_to_text(db_path, parse_command("/memory preferences")) == "show my preferences", "memory preferences did not map")
        _require(await command_to_text(db_path, parse_command("/memory lessons")) == "what did you learn from me today", "memory lessons did not map")
        forget_help = await command_to_text(db_path, parse_command("/forget"))
        _require(TelegramChannel._is_direct_command_reply(forget_help), "/forget help should be direct")
        cleanup = await command_to_text(db_path, parse_command("/memorycleanup"))
        _require("Memory cleanup:" in cleanup, "memorycleanup did not run")
        await upsert_preference(db_path, "smoke_city", "my smoke city is Kyoto", "telegram")
        migrated = await command_to_text(db_path, parse_command("/memory migrate"))
        _require("Canonical memory migration:" in migrated, "memory migrate did not run")
        _require("Source rows linked:" in migrated, "memory migrate did not report links")
        migrated_alias = await command_to_text(db_path, parse_command("/memorymigrate"))
        _require("Duplicate source links:" in migrated_alias, "memorymigrate alias did not report dedupe")
        pinned = await command_to_text(db_path, parse_command("/memory pin smoke city"))
        _require("Pinned 1 canonical memory" in pinned, "memory pin did not run")
        inspected = await command_to_text(db_path, parse_command("/memory inspect smoke city"))
        _require("id: mem_" in inspected and "class: pinned" in inspected, "memory inspect did not show pinned canonical memory")
        unpinned = await command_to_text(db_path, parse_command("/memoryunpin smoke city"))
        _require("Unpinned 1 canonical memory" in unpinned, "memoryunpin alias did not run")
        inspected_alias = await command_to_text(db_path, parse_command("/memoryinspect smoke city"))
        _require("class: temporary_test" in inspected_alias, "memoryinspect alias did not show unpinned test class")

        voice_status = await command_to_text(db_path, parse_command("/voice off"))
        _require("locked on" in voice_status and await voice_enabled(db_path), "locked voice status failed")

        see_reply = await command_to_text(db_path, parse_command("/see"))
        _require("visual help" in see_reply or "I can see now" in see_reply, "see did not activate sight")
        _require(TelegramChannel._is_direct_command_reply(see_reply), "/see should be direct")
        see_toggle = await command_to_text(db_path, parse_command("/see"))
        _require("stopped seeing" in see_toggle, "see did not toggle off")
        _require(TelegramChannel._is_direct_command_reply(see_toggle), "/see toggle off should be direct")
        screen_reply = await command_to_text(db_path, parse_command("/screen"))
        _require(screen_reply == "I can see your screen now.", "screen did not activate")
        _require(TelegramChannel._is_direct_command_reply(screen_reply), "/screen should be direct")
        screen_off = await command_to_text(db_path, parse_command("/screen off"))
        _require("Use /screen to toggle" in screen_off, "screen off should point to toggle")
        screen_toggle = await command_to_text(db_path, parse_command("/screen"))
        _require("stopped looking" in screen_toggle, "screen did not toggle off")
        screen_question = await command_to_text(db_path, parse_command("/screen explain this slide"))
        _require(screen_question == "look at my screen: explain this slide", "/screen args did not map")
        _require(await command_to_text(db_path, parse_command("/newtopic")) == "new topic", "newtopic did not map")
        _require(await command_to_text(db_path, parse_command("/lessons")) == "what did you learn from me today", "lessons did not map")
        _require(await command_to_text(db_path, parse_command("/skills")) == "what skills do you have", "skills did not map")
        create_skill = await command_to_text(db_path, parse_command("/createskill build better UI"))
        _require(create_skill == "create skill for build better UI", "createskill did not map")
        _require(await command_to_text(db_path, parse_command("/proposals")) == "show skill proposals", "proposals did not map")
        complex_text = await command_to_text(db_path, parse_command("/complex think this through"))
        _require(complex_text == "[complex]think this through", "complex did not map")
        complex_help = await command_to_text(db_path, parse_command("/complex"))
        _require(TelegramChannel._is_direct_command_reply(complex_help), "/complex help should be direct")
        cost = await command_to_text(db_path, parse_command("/cost"))
        _require("Usage estimate" in cost and "Total estimate" in cost, "cost did not summarize usage")
        _require(TelegramChannel._is_direct_command_reply(cost), "/cost should be direct")
        providers = await command_to_text(db_path, parse_command("/providers"))
        _require("Provider readiness:" in providers, "providers did not show readiness")
        _require(TelegramChannel._is_direct_command_reply(providers), "/providers should be direct")
        await record_route(db_path, "text", "Gemini Flash text", "normal Telegram text", False)
        route = await command_to_text(db_path, parse_command("/route"))
        _require("Last route:" in route and "Gemini Flash text" in route, "route did not show last lane")
        _require(TelegramChannel._is_direct_command_reply(route), "/route should be direct")
        await record_artifact_review(db_path, "xlsx", "Seoul food tracker", "claude-opus-4-8", True, "PASS: useful workbook.")
        review = await command_to_text(db_path, parse_command("/review"))
        _require("Last artifact review:" in review and "PASS: useful workbook" in review, "review did not show artifact QA")
        _require(TelegramChannel._is_direct_command_reply(review), "/review should be direct")
        await save_session_summary(db_path, "Shared session summary\n1) Test\n a) carried context")
        context = await command_to_text(db_path, parse_command("/context"))
        _require("Context window:" in context and "carried context" in context, "context did not inspect summary")
        _require(TelegramChannel._is_direct_command_reply(context), "/context should be direct")
        _require(await command_to_text(db_path, parse_command("/weekly")) == "weekly reflection", "weekly did not map")
        weekly_status = await command_to_text(db_path, parse_command("/weekly status"))
        _require("Weekly memory status:" in weekly_status, "weekly status did not return audit state")
        _require(TelegramChannel._is_direct_command_reply(weekly_status), "/weekly status should be direct")
        status = await command_to_text(db_path, parse_command("/status"))
        _require("screen sight" in status and "project:" in status, "status did not report channel state")
        join_usage = await command_to_text(db_path, parse_command("/join"))
        _require(join_usage.startswith("Meet join: use /join"), "join usage should be direct")
        _require(TelegramChannel._is_direct_command_reply(join_usage), "/join usage should be direct")
        with patch("maya_telegram.telegram_commands.join_meeting", side_effect=_fake_join_meeting):
            join_reply = await command_to_text(db_path, parse_command("/join https://meet.google.com/abc-defg-hij"))
        _require("Meet join: Maya is in the Meet now" in join_reply, join_reply)
        _require(TelegramChannel._is_direct_command_reply(join_reply), "/join should be direct")
        with patch("maya_telegram.telegram_commands.leave_meeting", side_effect=_fake_leave_meeting):
            leave_reply = await command_to_text(db_path, parse_command("/leave"))
        _require("Meet leave: Maya left the Meet" in leave_reply, leave_reply)
        _require(TelegramChannel._is_direct_command_reply(leave_reply), "/leave should be direct")
        meet_status = await command_to_text(db_path, parse_command("/meetstatus"))
        _require(meet_status.startswith("Meet status:"), meet_status)
        _require(TelegramChannel._is_direct_command_reply(meet_status), "/meetstatus should be direct")
        reliability = await command_to_text(db_path, parse_command("/reliability"))
        _require("30-day reliability scorecard" in reliability, "/reliability did not return scorecard")
        _require("Operational incident ledger" in reliability, "/reliability did not include incident ledger")
        _require(TelegramChannel._is_direct_command_reply(reliability), "/reliability should be direct")
        os.environ["MAYA_RELIABILITY_SOAK_PATH"] = str(Path(tmp) / "reliability_soak.json")
        note_reply = await command_to_text(
            db_path,
            parse_command("/reliability note false_done Maya said file was ready but attachment was stale"),
        )
        _require("Note logged for today" in note_reply, "/reliability note did not log")
        _require(TelegramChannel._is_direct_command_reply(note_reply), "/reliability note should be direct")
        rows = load_soak(Path(os.environ["MAYA_RELIABILITY_SOAK_PATH"]))
        _require(len(rows) == 1, "/reliability note did not create a soak row")
        _require(rows[0].false_saved_claims == 1, "/reliability note false_done did not increment false_saved_claims")
        _require("attachment was stale" in rows[0].notes, "/reliability note did not preserve note text")
        correction_reply = await command_to_text(db_path, parse_command("/reliability note Maya chose the wrong route"))
        _require("user_corrections" in correction_reply, "/reliability note default category should be user correction")
        rows = load_soak(Path(os.environ["MAYA_RELIABILITY_SOAK_PATH"]))
        _require(rows[0].user_corrections == 1, "/reliability note default did not increment user_corrections")
        os.environ["MAYA_ERROR_SNAPSHOT_PATH"] = str(Path(tmp) / "telegram_error_snapshots.json")
        os.environ["MAYA_OPERATIONAL_INCIDENT_PATH"] = str(Path(tmp) / "operational_incidents.json")
        error_reply = await command_to_text(
            db_path,
            parse_command("/error false_done Maya said file was ready but attachment was stale"),
        )
        _require("Failure recorded" in error_reply and "Fresh topic started" in error_reply, "/error did not record and reset")
        _require(TelegramChannel._is_direct_command_reply(error_reply), "/error should be direct")
        rows = load_soak(Path(os.environ["MAYA_RELIABILITY_SOAK_PATH"]))
        _require(rows[0].false_saved_claims == 2, "/error false_done did not increment false_saved_claims")
        snapshots = json.loads(Path(os.environ["MAYA_ERROR_SNAPSHOT_PATH"]).read_text("utf-8"))["snapshots"]
        _require("attachment was stale" in snapshots[-1]["note"], "/error snapshot missed note")
        incidents = load_incidents(Path(os.environ["MAYA_OPERATIONAL_INCIDENT_PATH"]))
        _require(incidents and incidents[-1].reason_code == "artifact_missing_after_done", "/error did not record incident")
        await save_history_message(db_path, 1, "user", "old broken thread", "telegram")
        assistant = KampungAssistant(db_path)
        assistant_reply = await assistant.handle_text("/error route Maya routed a simple task wrong", "telegram")
        _require("Fresh topic started" in assistant_reply, "/error assistant path did not confirm fresh topic")
        history = await get_history(db_path, 1, limit=6)
        _require(history[-1]["role"] == "user" and history[-1]["content"] == "new topic", "/error did not insert topic boundary")
        _require(recent_topic_history(history) == [], "/error topic boundary did not clear follow-up context")
        selfheal = await command_to_text(db_path, parse_command("/selfheal"))
        _require("Self heal check:" in selfheal, "selfheal did not run")
        selfheal_dryrun = await command_to_text(db_path, parse_command("/selfheal dryrun"))
        _require("Memory self-heal dry run." in selfheal_dryrun, "selfheal dryrun did not run")
        _require(TelegramChannel._is_direct_command_reply(selfheal_dryrun), "/selfheal dryrun should be direct")
        delivery = await command_to_text(db_path, parse_command("/delivery"))
        _require("Telegram delivery" in delivery, "delivery command did not return audit state")
        _require(TelegramChannel._is_direct_command_reply(delivery), "/delivery should be direct")
        last_delivery = await command_to_text(db_path, parse_command("/lastdelivery"))
        _require("Telegram delivery" in last_delivery, "lastdelivery alias did not return audit state")
        _require(TelegramChannel._is_direct_command_reply(last_delivery), "/lastdelivery should be direct")
        turn = await command_to_text(db_path, parse_command("/turn"))
        _require("Telegram turn" in turn, "turn command did not return audit state")
        _require(TelegramChannel._is_direct_command_reply(turn), "/turn should be direct")
        last_turn = await command_to_text(db_path, parse_command("/lastturn"))
        _require("Telegram turn" in last_turn, "lastturn alias did not return audit state")
        _require(TelegramChannel._is_direct_command_reply(last_turn), "/lastturn should be direct")
        artifact_review = await command_to_text(db_path, parse_command("/artifactreview"))
        _require("Last artifact review:" in artifact_review, "artifactreview alias did not return artifact QA")
        artifact_qa = await command_to_text(db_path, parse_command("/artifactqa"))
        _require("Last artifact review:" in artifact_qa, "artifactqa alias did not return artifact QA")
        memory_pin_alias = await command_to_text(db_path, parse_command("/memorypin smoke city"))
        _require("Pinned 1 canonical memory" in memory_pin_alias, "memorypin alias did not run")
        artisan_summary = await command_to_text(db_path, parse_command("/artisan"))
        _require(TelegramChannel._is_direct_command_reply(artisan_summary), "/artisan should be direct")
        help_text = await command_to_text(db_path, parse_command("/help"))
        _require("Maya commands:" in help_text, "help did not show command map")
        _require(TelegramChannel._is_direct_command_reply(help_text), "/help should be direct")
        missing = [f"/{command}" for command in sorted(all_command_names()) if f"/{command}" not in help_text]
        _require(not missing, f"help omitted command(s): {missing}")
        await _smoke_every_registered_command(db_path)
        unknown = await command_to_text(db_path, parse_command("/Desktop"))
        _require("not in the command list" in unknown, "unknown command should be short")
        _require(TelegramChannel._is_direct_command_reply(unknown), "unknown command should be direct")

        channel = TelegramChannel("fake-token", _FakeAssistant(db_path))
        await channel.handle_message(_FakeUpdate(), _FakeContext())
        await channel.handle_command(_FakeUpdate(), _FakeContext())
        print("telegram_commands_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_self_heal_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _smoke_every_registered_command(db_path: str) -> None:
    probes = {
        "artisan": "/artisan",
        "artifactqa": "/artifactqa",
        "artifactreview": "/artifactreview",
        "closeimac": "/closeimac",
        "complex": "/complex smoke",
        "context": "/context",
        "cost": "/cost",
        "createskill": "/createskill smoke skill",
        "delivery": "/delivery",
        "error": "/error route smoke failure",
        "forget": "/forget smoke city",
        "help": "/help",
        "imac": "/imac off",
        "join": "/join",
        "lastdelivery": "/lastdelivery",
        "lastturn": "/lastturn",
        "leave": "/leave",
        "lessons": "/lessons",
        "memory": "/memory",
        "memorycleanup": "/memorycleanup",
        "memoryinspect": "/memoryinspect smoke city",
        "memorymigrate": "/memorymigrate",
        "memorypin": "/memorypin smoke city",
        "memoryunpin": "/memoryunpin smoke city",
        "meetstatus": "/meetstatus",
        "newtopic": "/newtopic",
        "openimac": "/openimac",
        "preferences": "/preferences",
        "project": "/project",
        "proposals": "/proposals",
        "providers": "/providers",
        "reliability": "/reliability",
        "remember": "/remember smoke preference",
        "review": "/review",
        "route": "/route",
        "routines": "/routines",
        "screen": "/screen explain this slide",
        "see": "/see",
        "selfheal": "/selfheal dryrun",
        "skills": "/skills",
        "status": "/status",
        "tasks": "/tasks",
        "turn": "/turn",
        "voice": "/voice off",
        "weekly": "/weekly status",
    }
    missing = sorted(set(all_command_names()) - set(probes))
    extra = sorted(set(probes) - set(all_command_names()))
    _require(not missing and not extra, f"command probe mismatch missing={missing} extra={extra}")
    for name in all_command_names():
        parsed = parse_command(probes[name])
        _require(parsed and parsed.name == name, f"{name} probe did not parse")
        reply = await command_to_text(db_path, parsed)
        _require(reply and "not in the command list" not in reply, f"{name} returned unknown command: {reply!r}")


class _FakeUpdate:
    effective_message = None
    effective_chat = None


class _FakeContext:
    pass


class _FakeAssistant:
    def __init__(self, db_path: str):
        self.db_path = db_path


class _FakeMeetJoinResult:
    status = "live"
    reason_code = "recall_bot_live"
    detail = ""

    def telegram_text(self) -> str:
        return "Maya is in the Meet now. Session: fake"


class _FakeMeetLeaveResult:
    status = "stopped"
    reason_code = "recall_leave_call_requested"
    detail = ""

    def telegram_text(self) -> str:
        return "Maya left the Meet. Session: fake"


async def _fake_join_meeting(*_args, **kwargs):
    provenance = kwargs.get("provenance")
    _require(getattr(provenance, "source_kind", "") == "owner_text", "/join must use owner_text provenance")
    return _FakeMeetJoinResult()


async def _fake_leave_meeting(*_args, **kwargs):
    provenance = kwargs.get("provenance")
    _require(getattr(provenance, "source_kind", "") == "owner_text", "/leave must use owner_text provenance")
    return _FakeMeetLeaveResult()


if __name__ == "__main__":
    asyncio.run(main())
