from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class BrowserAgentState:
    goal: str
    query: str
    task_type: str = "research"
    current_url: str = ""
    page_title: str = ""
    filters: list[str] = field(default_factory=list)
    selected_option: str = ""
    compared_options: list[str] = field(default_factory=list)
    last_observation_id: str = ""
    retry_count: int = 0
    estimated_cost: float = 0.0
    confidence: float = 0.0
    pending_sensitive_action: str = ""
    steps: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "goal": self.goal,
                "query": self.query,
                "task_type": self.task_type,
                "current_url": self.current_url,
                "page_title": self.page_title,
                "filters": self.filters[-10:],
                "selected_option": self.selected_option,
                "compared_options": self.compared_options[-10:],
                "last_observation_id": self.last_observation_id,
                "retry_count": self.retry_count,
                "estimated_cost": self.estimated_cost,
                "confidence": self.confidence,
                "pending_sensitive_action": self.pending_sensitive_action,
                "steps": self.steps[-12:],
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> "BrowserAgentState | None":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return cls(
            goal=str(data.get("goal", "")),
            query=str(data.get("query", "")),
            task_type=str(data.get("task_type", data.get("kind", "research"))),
            current_url=str(data.get("current_url", "")),
            page_title=str(data.get("page_title", "")),
            filters=list(data.get("filters", [])),
            selected_option=str(data.get("selected_option", "")),
            compared_options=list(data.get("compared_options", [])),
            last_observation_id=str(data.get("last_observation_id", "")),
            retry_count=int(data.get("retry_count") or 0),
            estimated_cost=float(data.get("estimated_cost") or 0),
            confidence=float(data.get("confidence") or 0),
            pending_sensitive_action=str(data.get("pending_sensitive_action", "")),
            steps=list(data.get("steps", [])),
        )


def task_type_for(text: str) -> str:
    lowered = text.lower()
    if "flight" in lowered or "airline" in lowered or "ticket" in lowered:
        return "flight_search"
    if any(word in lowered for word in ("buy", "price", "compare", "shopping", "product")):
        return "product_comparison"
    if any(word in lowered for word in ("account", "login", "settings")):
        return "account_navigation"
    if any(word in lowered for word in ("form", "fill", "application")):
        return "form_help"
    if any(word in lowered for word in ("troubleshoot", "fix", "guide", "error")):
        return "troubleshooting_lookup"
    return "research"


def observation_id(title: str, url: str, text_hash: str) -> str:
    return ":".join(part for part in (title[:24], url[:48], text_hash[:12]) if part)
