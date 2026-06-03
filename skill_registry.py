from __future__ import annotations

from dataclasses import dataclass

from skill_learning_store import get_skill_learning_metadata, increment_skill_usage
from skill_outcome_store import record_skill_outcome
from skill_store import latest_skill_usage, list_custom_skills, record_skill_usage
from security_manifest import SecurityManifest, get_manifest, upsert_manifest


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    name: str
    description: str
    safety: str
    approval_mode: str
    keywords: tuple[str, ...]


BUILT_IN_SKILLS = (
    SkillDefinition("memory_lookup", "Memory Lookup", "Retrieve relevant preferences, tasks, and long-term memory.", "safe", "none", ("remember", "memory", "history", "context")),
    SkillDefinition("task_follow_up", "Task Follow-up", "Create reminders, due tasks, and follow-up actions.", "safe", "none", ("task", "remind", "follow up", "schedule")),
    SkillDefinition("history_summary", "History Summary", "Summarize recent interactions into short reports.", "safe", "none", ("summary", "recap", "history")),
    SkillDefinition("sight_research", "Sight Research", "Use Gemini to research, compare sources, summarize evidence, and prepare source-aware notes.", "bounded", "policy_guard", ("research", "source", "sources", "compare evidence", "find references")),
    SkillDefinition("steward_review", "Steward Review", "Use Claude to review plans, documents, slides, skills, and self-heal proposals for risks and gaps.", "bounded", "policy_guard", ("review", "critique", "audit", "hidden risk", "check this plan", "before acting")),
    SkillDefinition("scheduled_routines", "Scheduled Routines", "Run recurring briefings like morning brief, evening recap, and weekly reflection.", "safe", "none", ("routine", "briefing", "recap", "reflection")),
    SkillDefinition("file_write", "File Write", "Create or write local files when asked.", "safe", "none", ("file", "write file", "create file", "desktop")),
    SkillDefinition("workspace_create", "Workspace Create", "Create folders and starter project workspaces in Desktop/Maya.", "safe", "none", ("folder", "project", "workspace")),
    SkillDefinition("drawing", "Drawing", "Create simple SVG drawings locally, with optional Gemini image generation when enabled.", "safe", "none", ("draw", "diagram", "image", "moon")),
    SkillDefinition("web_browse", "Web Browse", "Open browser searches, inspect active Chrome page text, and click visible non-sensitive browser targets.", "bounded", "policy_guard", ("browse", "internet", "web", "search", "website", "chrome", "safari")),
    SkillDefinition("google_search", "Google Search", "Search Google, inspect result snippets, and open visible non-sensitive results.", "bounded", "policy_guard", ("google", "search", "look up", "find online")),
    SkillDefinition("google_images", "Google Images", "Search Google Images for visual references and open visible image/source results.", "bounded", "policy_guard", ("google images", "image search", "find images")),
    SkillDefinition("youtube_research", "YouTube Research", "Search YouTube, inspect visible video results, and open videos by rank or title. Read-only by default.", "bounded", "policy_guard", ("youtube", "video", "videos")),
    SkillDefinition("reddit_research", "Reddit Research", "Search Reddit, inspect threads/comments, and summarize visible community sentiment. Read-only by default.", "bounded", "policy_guard", ("reddit", "subreddit", "community opinion")),
    SkillDefinition("office_documents", "Office Documents", "Work with Word, Excel, and PowerPoint through local files and macOS app control.", "bounded", "policy_guard", ("word", "docx", "document", "excel", "xlsx", "spreadsheet", "powerpoint", "pptx", "presentation", "slides")),
    SkillDefinition("word_artifact_quality", "Word Artifact Quality", "Quality standards and review gates for Maya-created Word documents.", "bounded", "policy_guard", ("word", "docx", "document", "report", "itinerary")),
    SkillDefinition("excel_artifact_quality", "Excel Artifact Quality", "Quality standards and review gates for Maya-created Excel workbooks.", "bounded", "policy_guard", ("excel", "xlsx", "spreadsheet", "tracker", "budget")),
    SkillDefinition("powerpoint_artifact_quality", "PowerPoint Artifact Quality", "Quality standards and review gates for Maya-created PowerPoint decks.", "bounded", "policy_guard", ("powerpoint", "pptx", "presentation", "slides", "deck")),
    SkillDefinition("powerpoint_design_taste", "PowerPoint Design Taste", "Anti-slop visual taste rules adapted from Leonxlnx taste-skill for Maya-created PowerPoint decks.", "bounded", "policy_guard", ("powerpoint", "pptx", "presentation", "slides", "deck", "visual", "design")),
    SkillDefinition("html_app_artifact_quality", "HTML App Artifact Quality", "Quality standards and review gates for Maya-created single-file HTML apps.", "bounded", "policy_guard", ("html", "web app", "single-file app", "mini app")),
    SkillDefinition("travel_research", "Travel Research", "Search flight options, compare prices, dates, baggage, and timing before any booking.", "bounded", "policy_guard", ("flight", "flights", "ticket", "airline", "travel", "booking")),
    SkillDefinition("network_troubleshooting", "Network Troubleshooting", "Run basic local network checks and create Word troubleshooting notes when the explanation is lengthy.", "bounded", "policy_guard", ("network", "wifi", "internet", "router", "dns", "troubleshoot")),
    SkillDefinition("checkout_guard", "Checkout Guard", "Stop before purchases, payments, bookings, uploads, or private data exposure unless Zainal confirms.", "sensitive", "chat_confirmation", ("buy", "book", "pay", "checkout", "passport", "card", "payment")),
    SkillDefinition("cloud_accounts", "Cloud Accounts", "Use configured Cloudflare and GCP accounts under the permission policy.", "bounded", "policy_guard", ("cloudflare", "gcp", "google cloud", "wrangler", "gcloud")),
    SkillDefinition("google_cloud_console", "Google Cloud Console", "Open and inspect Google Cloud Console read-only pages. Destructive, billing, IAM, deploy, and credential actions require approval.", "bounded", "policy_guard", ("google cloud console", "gcp console", "cloud run", "logs explorer")),
    SkillDefinition("telegram_send", "Telegram Send", "Send messages or reports to Telegram after approval.", "sensitive", "chat_confirmation", ("telegram", "send", "share")),
    SkillDefinition("voice_reply", "Voice Reply", "Speak through Ara/xAI or local macOS fallback voice.", "safe", "none", ("voice", "speak", "audio")),
    SkillDefinition("imac_control", "iMac Control", "Run safe local iMac actions like notifications and app switching.", "sensitive", "chat_confirmation", ("imac", "app", "volume", "fullscreen")),
    SkillDefinition("skill_scaffold", "Skill Scaffold", "Draft a new Maya skill spec and scaffold for review.", "sensitive", "chat_confirmation", ("skill", "create skill", "new ability")),
)


class SkillRegistry:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def list_skills(self, limit: int = 20) -> list[str]:
        await ensure_builtin_skill_manifests(self.db_path)
        custom = await list_custom_skills(self.db_path, limit=limit)
        built_in = [
            f"{item.name}: {item.description} [{item.safety}/{item.approval_mode}]"
            for item in BUILT_IN_SKILLS
        ]
        custom_lines = [
            f"{row['name']}: {row['description']} [{row['safety']}/{row['approval_mode']}]"
            for row in custom
        ]
        return built_in + custom_lines

    async def build_prompt_context(self, query: str, limit: int = 4) -> str:
        await ensure_builtin_skill_manifests(self.db_path)
        lowered = query.lower()
        relevant = []
        for skill in BUILT_IN_SKILLS:
            score = sum(1 for keyword in skill.keywords if keyword in lowered)
            if score:
                relevant.append((score, skill))
        relevant.sort(key=lambda item: item[0], reverse=True)

        custom = await list_custom_skills(self.db_path, limit=50, status="active")
        matching_custom = [row for row in custom if await _custom_skill_matches(self.db_path, row, query)]
        custom_lines = [f"- {row['name']}: {row['description']}" for row in matching_custom[:2]]
        skill_lines = [f"- {item.name}: {item.description}" for _, item in relevant[:limit]]
        lines = skill_lines + custom_lines
        if not lines:
            return ""
        for _, item in relevant[:limit]:
            await record_skill_usage(
                self.db_path,
                skill_id=item.skill_id,
                name=item.name,
                query=query,
                reason="keyword match",
            )
        for row in matching_custom[:2]:
            await record_skill_usage(
                self.db_path,
                skill_id=str(row["skill_id"]),
                name=str(row["name"]),
                query=query,
                reason="active custom skill",
            )
            await increment_skill_usage(self.db_path, str(row["skill_id"]))
        return "Relevant skills:\n" + "\n".join(lines)

    async def record_latest_outcome(self, query: str, channel: str, lane: str, response: str) -> None:
        events = [event for event in await latest_skill_usage(self.db_path, limit=8) if str(event["query"]) == query]
        if not events:
            return
        lowered = response.lower()
        outcome = _outcome_from_text(query, lowered)
        missing_step = "Review failure details." if outcome in {"failure", "partial"} else ""
        correction = query if outcome == "user_corrected" else ""
        artifact = _artifact_marker(response)
        seen = set()
        for event in events:
            skill_id = str(event["skill_id"])
            if skill_id in seen:
                continue
            seen.add(skill_id)
            await record_skill_outcome(
                self.db_path,
                skill_id=skill_id,
                user_request=query,
                channel=channel,
                selected_lane=lane,
                reason_selected=str(event["reason"]),
                outcome=outcome,
                missing_step=missing_step,
                user_correction=correction,
                artifact_or_workflow_id=artifact,
            )


def _outcome_from_text(query: str, lowered_response: str) -> str:
    lowered_query = query.lower()
    if any(marker in lowered_query for marker in ("wrong", "actually", "correction")):
        return "user_corrected"
    if "cancel" in lowered_response:
        return "cancelled"
    if "hard no" in lowered_response or "private exposure" in lowered_response:
        return "blocked"
    if "failed" in lowered_response or "error" in lowered_response:
        return "failure"
    if "could not" in lowered_response or "try again" in lowered_response:
        return "partial"
    return "success"


def _artifact_marker(response: str) -> str:
    marker = "[file:"
    if marker not in response:
        return ""
    return response.split(marker, 1)[1].split("]", 1)[0][:120]


async def _custom_skill_matches(db_path: str, row: dict[str, str], query: str) -> bool:
    haystack = " ".join(
        str(row.get(key, ""))
        for key in ("skill_id", "name", "description")
    ).lower()
    metadata = await get_skill_learning_metadata(db_path, str(row.get("skill_id", "")))
    if metadata:
        haystack += " " + " ".join(str(metadata.get(key, "")) for key in ("triggers", "non_triggers", "tools_needed"))
    tokens = {token for token in query.lower().replace("/", " ").split() if len(token) >= 4}
    if not tokens:
        return False
    return any(token.rstrip("ing") in haystack for token in tokens)


async def ensure_builtin_skill_manifests(db_path: str) -> None:
    for skill in BUILT_IN_SKILLS:
        if await get_manifest(db_path, "skill", skill.skill_id):
            continue
        await upsert_manifest(db_path, _manifest_for_builtin(skill))


def _manifest_for_builtin(skill: SkillDefinition) -> SecurityManifest:
    quality_artifact_skills = {
        "word_artifact_quality", "excel_artifact_quality",
        "powerpoint_artifact_quality", "powerpoint_design_taste", "html_app_artifact_quality",
    }
    artifact_skills = {"history_summary", "office_documents", "drawing", *quality_artifact_skills}
    permissions = {"create_artifacts": skill.skill_id in artifact_skills}
    if skill.skill_id in {"memory_lookup"}:
        permissions["read_files"] = False
    if skill.skill_id in {"file_write", "workspace_create", "office_documents", "drawing", *quality_artifact_skills}:
        permissions["write_files"] = True
    if skill.skill_id in {"web_browse", "google_search", "google_images", "youtube_research", "reddit_research", "travel_research", "sight_research"}:
        permissions.update({"browse_web": True, "browser_click": True})
    if skill.skill_id in {"telegram_send"}:
        permissions["send_files"] = True
    if skill.skill_id in {"skill_scaffold"}:
        permissions.update({"write_files": True, "write_memory": True})
    if skill.skill_id in {"cloud_accounts", "google_cloud_console"}:
        permissions.update({"external_api": True, "browse_web": True, "browser_click": True})
    return SecurityManifest(
        "skill",
        skill.skill_id,
        permissions,
        hard_blocks=["private_exposure", "secrets"],
        notes=f"Built-in skill manifest for {skill.name}.",
    )
