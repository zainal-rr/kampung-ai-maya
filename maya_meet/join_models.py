from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse


MEET_HOST = "meet.google.com"
MEET_CODE_RE = re.compile(r"^[a-z]{3}-[a-z]{4}-[a-z]{3}$", re.IGNORECASE)


@dataclass(frozen=True)
class MeetJoinOutcome:
    status: str
    reason_code: str
    session_id: str = ""
    bot_id: str = ""
    meeting_url: str = ""
    canonical_meeting_url: str = ""
    recall_status: str = ""
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "session_id": self.session_id,
            "bot_id": self.bot_id,
            "meeting_url": self.meeting_url,
            "canonical_meeting_url": self.canonical_meeting_url,
            "recall_status": self.recall_status,
            "detail": self.detail,
        }

    def telegram_text(self) -> str:
        if self.status == "live":
            return f"Maya is in the Meet now. Session: {self.session_id}"
        if self.status == "waiting":
            return f"Maya is waiting to be admitted to the Meet. Session: {self.session_id}"
        if self.status == "joining":
            return f"Maya is joining the Meet. Session: {self.session_id}"
        if self.status == "failed":
            return f"I could not join the Meet: {self.reason_code}. {self.detail}".strip()
        return f"Meet join status: {self.status} ({self.reason_code})."


def canonical_meet_url(meeting_url: str) -> str:
    text = meeting_url.strip().strip("\"'")
    parsed = urlparse(text)
    if not parsed.scheme:
        parsed = urlparse("https://" + text)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host != MEET_HOST:
        raise ValueError("expected meet.google.com link")
    code = parsed.path.strip("/").split("/", 1)[0].lower()
    if not MEET_CODE_RE.match(code):
        raise ValueError("expected Google Meet code like abc-defg-hij")
    return urlunparse(("https", MEET_HOST, "/" + code, "", "", ""))
