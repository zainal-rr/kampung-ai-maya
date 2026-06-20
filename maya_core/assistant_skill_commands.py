from __future__ import annotations

import re

from maya_core.assistant_command_helpers import direct_key
from maya_core.skill_evaluator import evaluate_skill_scaffold
from maya_core.skill_importer import adapt_imported_skill_for_maya, import_local_skill, import_npx_skill
from maya_core.skill_library import mirror_skill
from maya_core.skill_memory_store import add_skill_memory, disable_skill_memory, list_skill_memory
from maya_core.skill_registry import BUILT_IN_SKILLS, SkillRegistry
from maya_core.skill_learning_store import mark_skill_disabled, missing_required_tests, record_skill_test, skill_has_required_tests
from maya_core.weekly_skill_review import latest_skill_review
from maya_core.user_model_store import list_user_model_items
from maya_core.skill_store import find_skill, latest_skill_usage, list_custom_skills, list_skill_proposals, update_skill_status
from maya_core.mcp_registry import audit_mcp_server, list_mcp_servers, propose_mcp_server, set_mcp_status
from maya_core.security_manifest import get_manifest, list_manifests, manifest_summary
from maya_core.skill_performance_analyzer import skill_performance_text
from maya_core.starter_skill_catalog import catalog_summary, install_starter_catalog


async def handle_skill_listing(db_path: str, skills: SkillRegistry, text: str) -> str | None:
    key = direct_key(text)
    if key == "show active skills":
        custom = await list_custom_skills(db_path, limit=20, status="active")
        built_in = [f"{idx}) {item.name}: {item.description}" for idx, item in enumerate(BUILT_IN_SKILLS, 1)]
        custom_lines = [f"{idx}) {row['name']}: {row['description']}" for idx, row in enumerate(custom, 1)]
        reply = "Built-in active skills:\n" + "\n".join(built_in)
        if custom_lines:
            reply += "\n\nCustom active skills:\n" + "\n".join(custom_lines)
        else:
            reply += "\n\nCustom active skills:\nNone."
        return reply
    if key in {"why did you pick that skill", "show skill usage", "show skill log"}:
        events = await latest_skill_usage(db_path, limit=5)
        if not events:
            return "No skill usage has been logged yet."
        lines = [f"{idx}) {item['name']}: {item['reason']}" for idx, item in enumerate(events, start=1)]
        return "Recent skill choices:\n" + "\n".join(lines)
    memory = await _skill_memory_reply(db_path, text)
    if memory is not None:
        return memory
    if key == "what did this skill learn":
        events = await latest_skill_usage(db_path, limit=1)
        if not events:
            return "No skill usage has been logged yet."
        rows = await list_skill_memory(db_path, str(events[0]["skill_id"]))
        if not rows:
            return f"No skill memory saved for {events[0]['name']} yet."
        lines = [f"{idx}) {row['kind']}: {row['content']}" for idx, row in enumerate(rows, 1)]
        return f"Skill memory for {events[0]['name']}:\n" + "\n".join(lines)
    if key in {"show skill review", "what is the skill review"}:
        review = await latest_skill_review(db_path)
        return review or "No skill review has been saved yet."
    if key == "show user model":
        items = await list_user_model_items(db_path)
        if not items:
            return "No user model entries saved yet."
        lines = [f"{idx}) {item['category']}: {item['content']} ({item['source']}, {item['confidence']})" for idx, item in enumerate(items, 1)]
        return "User model:\n" + "\n".join(lines)
    mcp = await _mcp_reply(db_path, text)
    if mcp is not None:
        return mcp
    manifest = await _manifest_reply(db_path, text)
    if manifest is not None:
        return manifest
    if key == "show starter skill catalog":
        return catalog_summary()
    if key == "install starter skill catalog":
        count = await install_starter_catalog(db_path)
        return f"Starter skill catalog installed as proposed skills: {count}."
    if key in {"show skill performance", "analyze skill performance"}:
        return await skill_performance_text(db_path)
    if key not in {"what skills do you have", "list my skills", "show skills", "what can you do"}:
        return None
    items = await skills.list_skills(limit=12)
    return "Current skills:\n" + "\n".join(f"- {item}" for item in items[:12])


async def handle_skill_proposals(db_path: str, text: str) -> str | None:
    if direct_key(text) not in {"show skill proposals", "list skill proposals", "show all skill proposals"}:
        return None
    proposals = await list_skill_proposals(db_path, limit=15)
    if not proposals:
        return "There are no skill proposals yet."
    lines = [
        f"{idx}) {item['summary']} (proposal id: #{item['id']}, status: {item['status']})"
        for idx, item in enumerate(proposals, 1)
    ]
    return "Skill proposals, latest 15:\n" + "\n".join(lines)


async def handle_skill_lifecycle(db_path: str, text: str) -> str | None:
    npx_import = re.match(r"^npx\s+skills\s+add\s+(.+)$", text, re.IGNORECASE)
    if npx_import:
        return await import_npx_skill(db_path, npx_import.group(1).strip())
    imported = re.match(r"^import skill from\s+(.+)$", text, re.IGNORECASE)
    if imported:
        return await import_local_skill(db_path, imported.group(1).strip())
    match = re.match(r"^(approve|activate|disable|edit|test|improve)\s+skill\s+(.+)$", text, re.IGNORECASE)
    if not match:
        return None
    action, query = match.group(1).lower(), match.group(2).strip()
    skill = await find_skill(db_path, query)
    if not skill:
        return "I could not find a matching skill."
    if action == "edit":
        path = skill.get("scaffold_path") or ""
        return f"Skill file: {path}" if path else "That skill does not have a scaffold file yet."
    if action == "test":
        if skill.get("source") == "imported":
            path = str(skill.get("scaffold_path") or "")
            if path and "Maya Activation Wrapper" not in open(path, encoding="utf-8").read():
                return (
                    f"{skill['name']} is an imported skill. It needs a Maya activation wrapper before tests can pass. "
                    f"Run: improve skill {skill['name']}."
                )
        results = evaluate_skill_scaffold(str(skill.get("scaffold_path") or ""))
        for test_type, (status, notes) in results.items():
            await record_skill_test(db_path, str(skill["skill_id"]), text, status, notes, test_type)
        failed = [test for test, (status, _) in results.items() if status != "passed"]
        if failed:
            return f"Skill tests recorded for {skill['name']}. Failed: {', '.join(failed)}."
        return f"Skill tests recorded for {skill['name']}. It can be activated after approval."
    if action == "improve":
        path = skill.get("scaffold_path") or ""
        if skill.get("source") == "imported" and adapt_imported_skill_for_maya(path, str(skill["name"])):
            return f"Added Maya activation wrapper for {skill['name']}. Now run: test skill {skill['name']}."
        return f"Improve this scaffold, then run its tests: {path}" if path else "That skill has no scaffold to improve yet."
    status = "approved" if action == "approve" else "active" if action == "activate" else "disabled"
    if action == "activate" and skill.get("status") != "approved":
        return "Approve the skill first, then activate it after its tests pass."
    if action == "activate" and not await get_manifest(db_path, "skill", str(skill["skill_id"])):
        return "Add a security manifest before activation tests can make that skill active."
    if action == "activate" and not await skill_has_required_tests(db_path, str(skill["skill_id"])):
        missing = ", ".join(await missing_required_tests(db_path, str(skill["skill_id"])))
        return f"Run and pass the missing activation tests before making it active: {missing}."
    if action == "disable":
        await mark_skill_disabled(db_path, str(skill["skill_id"]), "Disabled by Zainal.")
    if action == "approve":
        await record_skill_test(db_path, str(skill["skill_id"]), text, "passed", "Approved by Zainal.", "approval")
    updated = await update_skill_status(db_path, str(skill["skill_id"]), status)
    if not updated:
        return "I could not update that skill."
    if action in {"activate", "disable"}:
        mirror_skill(str(skill.get("scaffold_path") or ""), status)
    return f"Done. I set {skill['name']} to {status}."


async def _skill_memory_reply(db_path: str, text: str) -> str | None:
    show = re.match(r"^(?:show skill memory for|what did)\s+(.+?)(?:\s+learn)?$", text, re.IGNORECASE)
    if show:
        skill = await find_skill(db_path, show.group(1).strip())
        if not skill:
            return "I could not find a matching skill."
        rows = await list_skill_memory(db_path, str(skill["skill_id"]))
        if not rows:
            return f"No skill memory saved for {skill['name']} yet."
        lines = [f"{idx}) {row['kind']}: {row['content']} ({row['source']}, {row['confidence']})" for idx, row in enumerate(rows, 1)]
        return f"Skill memory for {skill['name']}:\n" + "\n".join(lines)
    remember = re.match(r"^remember skill preference for\s+(.+?)\s*:\s*(.+)$", text, re.IGNORECASE)
    if remember:
        skill = await find_skill(db_path, remember.group(1).strip())
        if not skill:
            return "I could not find a matching skill."
        ok, message = await add_skill_memory(
            db_path,
            skill_id=str(skill["skill_id"]),
            kind="user_preference",
            content=remember.group(2).strip(),
            source="explicit",
        )
        return message if ok else message
    forget = re.match(r"^forget this skill preference(?: for\s+(.+?))?(?:\s+about\s+(.+))?$", text, re.IGNORECASE)
    if forget:
        query = (forget.group(1) or "").strip()
        skill = await find_skill(db_path, query) if query else None
        if not skill:
            return "Tell me which skill preference to forget."
        count = await disable_skill_memory(db_path, str(skill["skill_id"]), (forget.group(2) or "").strip())
        return f"Disabled {count} skill memory item."
    return None


async def _mcp_reply(db_path: str, text: str) -> str | None:
    key = direct_key(text)
    if key in {"show mcp tools", "show mcp servers"}:
        rows = await list_mcp_servers(db_path)
        if not rows:
            return "No MCP tools are registered yet."
        return "MCP tools:\n" + "\n".join(f"{i}) {r['name']} ({r['status']}): {r['permission_scope']}" for i, r in enumerate(rows, 1))
    if key in {"show disabled mcp tools", "show disabled mcp servers"}:
        rows = await list_mcp_servers(db_path, status="disabled")
        return "Disabled MCP tools:\n" + "\n".join(f"{i}) {r['name']}" for i, r in enumerate(rows, 1)) if rows else "No disabled MCP tools."
    match = re.match(r"^propose mcp\s+(.+?)\s+command\s+(.+?)(?:\s+scope\s+(.+))?$", text, re.I)
    if match:
        await propose_mcp_server(db_path, match.group(1).strip(), match.group(2).strip(), permission_scope=(match.group(3) or "").strip())
        return f"Proposed MCP tool {match.group(1).strip()}. It is not enabled yet."
    match = re.match(r"^(approve|enable|disable)\s+mcp\s+(.+)$", text, re.I)
    if match:
        status = "approved" if match.group(1).lower() == "approve" else "enabled" if match.group(1).lower() == "enable" else "disabled"
        ok = await set_mcp_status(db_path, match.group(2).strip(), status)
        return f"MCP tool set to {status}." if ok else "I could not find that MCP tool."
    match = re.match(r"^audit mcp\s+(.+)$", text, re.I)
    if match:
        return await audit_mcp_server(db_path, match.group(1).strip())
    return None


async def _manifest_reply(db_path: str, text: str) -> str | None:
    match = re.match(r"^(?:show|audit)\s+manifest\s+(.+?)\s+(.+)$", text, re.I)
    if match:
        manifest = await get_manifest(db_path, match.group(1).strip(), match.group(2).strip())
        return manifest_summary(manifest) if manifest else "I could not find that manifest."
    if direct_key(text) == "show security manifests":
        rows = await list_manifests(db_path)
        if not rows:
            return "No security manifests are saved yet."
        return "Security manifests:\n" + "\n".join(f"{i}) {r['subject_type']} {r['subject_id']}" for i, r in enumerate(rows[:12], 1))
    return None
