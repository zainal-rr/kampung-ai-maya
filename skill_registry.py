from __future__ import annotations

from dataclasses import dataclass

from skill_learning_store import increment_skill_usage
from skill_outcome_store import record_skill_outcome
from skill_store import latest_skill_usage, list_custom_skills, record_skill_usage


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
    SkillDefinition("office_documents", "Office Documents", "Work with Word, Excel, and PowerPoint through local files and macOS app control.", "bounded", "policy_guard", ("word", "docx", "document", "excel", "xlsx", "spreadsheet", "powerpoint", "pptx", "presentation", "slides")),
    SkillDefinition("travel_research", "Travel Research", "Search flight options, compare prices, dates, baggage, and timing before any booking.", "bounded", "policy_guard", ("flight", "flights", "ticket", "airline", "travel", "booking")),
    SkillDefinition("network_troubleshooting", "Network Troubleshooting", "Run basic local network checks and create Word troubleshooting notes when the explanation is lengthy.", "bounded", "policy_guard", ("network", "wifi", "internet", "router", "dns", "troubleshoot")),
    SkillDefinition("checkout_guard", "Checkout Guard", "Stop before purchases, payments, bookings, uploads, or private data exposure unless Zainal confirms.", "sensitive", "chat_confirmation", ("buy", "book", "pay", "checkout", "passport", "card", "payment")),
    SkillDefinition("cloud_accounts", "Cloud Accounts", "Use configured Cloudflare and GCP accounts under the permission policy.", "bounded", "policy_guard", ("cloudflare", "gcp", "google cloud", "wrangler", "gcloud")),
    SkillDefinition("telegram_send", "Telegram Send", "Send messages or reports to Telegram after approval.", "sensitive", "chat_confirmation", ("telegram", "send", "share")),
    SkillDefinition("voice_reply", "Voice Reply", "Speak through Ara/xAI or local macOS fallback voice.", "safe", "none", ("voice", "speak", "audio")),
    SkillDefinition("imac_control", "iMac Control", "Run safe local iMac actions like notifications and app switching.", "sensitive", "chat_confirmation", ("imac", "app", "volume", "fullscreen")),
    SkillDefinition("skill_scaffold", "Skill Scaffold", "Draft a new Maya skill spec and scaffold for review.", "sensitive", "chat_confirmation", ("skill", "create skill", "new ability")),
)


class SkillRegistry:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def list_skills(self, limit: int = 20) -> list[str]:
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
        lowered = query.lower()
        relevant = []
        for skill in BUILT_IN_SKILLS:
            score = sum(1 for keyword in skill.keywords if keyword in lowered)
            if score:
                relevant.append((score, skill))
        relevant.sort(key=lambda item: item[0], reverse=True)

        custom = await list_custom_skills(self.db_path, limit=limit, status="active")
        custom_lines = [f"- {row['name']}: {row['description']}" for row in custom[:2]]
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
        for row in custom[:2]:
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
