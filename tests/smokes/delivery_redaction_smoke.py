from __future__ import annotations

from delivery_redaction import redact_for_delivery, requires_external_redaction
from models import BaseAgent


def main() -> None:
    local = "Google Chrome, Claude, Codex, Cloudflare, and GCP are open."
    _require(_DummyAgent()._prepare_output(local) == local, "Model wrapper should not redact personal replies")
    _require(redact_for_delivery(local, "telegram") == local, "Telegram should not redact app names")
    _require(redact_for_delivery(local, "imac") == local, "iMac should not redact app names")
    github = redact_for_delivery(local, "github")
    _require("[REDACTED] Chrome" in github, "GitHub should redact Google")
    _require("[REDACTED]" in github and "Cloudflare" in github and "GCP" in github, "External redaction was wrong")
    _require(requires_external_redaction("email"), "Email should require redaction")
    _require(not requires_external_redaction("telegram"), "Telegram should stay personal")
    print("delivery_redaction_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class _DummyAgent(BaseAgent):
    def __init__(self):
        super().__init__("dummy")

    async def chat(self, messages):
        return ""


if __name__ == "__main__":
    main()
