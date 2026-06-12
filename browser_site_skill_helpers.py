from __future__ import annotations

import re


GOOGLE_SEARCH_SKILL_ID = "google_search"
YOUTUBE_SKILL_ID = "youtube_research"
REDDIT_SKILL_ID = "reddit_research"


def _extract_visible_options(text: str, limit: int = 5) -> list[str]:
    noise = re.compile(
        r"^(all|images|videos|maps|shopping|news|forums|more|tools|settings|privacy|terms|sign in|people also ask|related searches|home|shorts|subscriptions)$",
        re.I,
    )
    lines = []
    for raw in text.splitlines():
        line = " ".join(raw.split()).strip()
        if len(line) < 8 or len(line) > 220 or noise.match(line):
            continue
        if line not in lines:
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _clean_site_query(text: str, skill_id: str) -> str:
    cleaned = " ".join(text.strip().split())
    cleaned = re.sub(r"\b(?:please|for me|maya|can you|could you|would you)\b", " ", cleaned, flags=re.I)
    if skill_id == GOOGLE_SEARCH_SKILL_ID:
        wrappers = (
            r"^(?:and\s+)?(?:google|search\s+for|search|look\s+up|find\s+online|check\s+online)\s+",
            r"^(?:and\s+)?(?:open\s+a\s+google\s+search\s+for|open\s+google\s+search\s+for)\s+",
        )
    elif skill_id == YOUTUBE_SKILL_ID:
        wrappers = (
            r"^(?:and\s+)?(?:search\s+youtube(?:\s+for)?|search\s+on\s+youtube\s+for|youtube|find\s+youtube\s+videos?\s+(?:for|about)?|find\s+videos?\s+(?:for|about)?|open\s+youtube\s+and\s+search\s+for)\s+",
        )
    elif skill_id == REDDIT_SKILL_ID:
        wrappers = (
            r"^(?:and\s+)?(?:what\s+does\s+reddit\s+say\s+(?:about|on)?|search\s+reddit\s+(?:for|about)?|reddit|find\s+reddit\s+threads?\s+(?:for|about)?|look\s+on\s+reddit\s+(?:for|about)?)\s+",
        )
    else:
        wrappers = ()
    previous = ""
    while previous != cleaned:
        previous = cleaned
        for wrapper in wrappers:
            cleaned = re.sub(wrapper, "", cleaned, flags=re.I).strip()
    if cleaned.lower() in {"google", "youtube", "reddit", "open google", "open youtube", "open reddit"}:
        return ""
    return " ".join(cleaned.strip(" .").split())


def _is_result_open_request(text: str) -> bool:
    lowered = text.lower()
    explicit = bool(re.search(r"\b(open|click|select|choose)\b", lowered)) and any(
        marker in lowered for marker in ("result", "video", "thread", "link", "first", "second", "third", "title")
    )
    if explicit:
        return True
    return bool(re.search(r"\b(one|result|link|post|page|thread|article)\b", lowered)) and any(
        re.search(rf"\b{site}\b", lowered)
        for site in (
            "reddit",
            "wikipedia",
            "gamespot",
            "polygon",
            "imdb",
            "youtube",
            "github",
            "stackoverflow",
            "medium",
        )
    )


def _rank_from_text(text: str) -> int:
    lowered = text.lower()
    ranks = {
        "first": 1,
        "top": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
    }
    for word, value in ranks.items():
        if re.search(rf"\b{word}\b", lowered):
            return value
    match = re.search(r"\b(?:result|video|thread|link)\s+(\d{1,2})\b", lowered)
    if match:
        return max(1, min(10, int(match.group(1))))
    return 1


def _target_from_click_request(text: str) -> str:
    cleaned = re.sub(r"\b(open|click|select|choose|maybe|the|that|this|one|first|top|second|third|fourth|fifth|result|video|thread|post|page|article|link|title)\b", " ", text, flags=re.I)
    cleaned = re.sub(r"[^\w\s.-]", " ", cleaned)
    cleaned = re.sub(r"^(?:about|for|on|of|regarding)\s+", "", " ".join(cleaned.strip(" .").split()), flags=re.I)
    return cleaned if len(cleaned) >= 3 else ""


def _options_match_target(options: list[str], target: str) -> bool:
    tokens = [token for token in re.split(r"\W+", target.lower()) if len(token) >= 4]
    if not tokens:
        return True
    joined = "\n".join(options).lower()
    return any(token in joined for token in tokens)


def _looks_like_posting_or_account_action(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ("post", "comment", "upvote", "downvote", "subscribe", "join subreddit", "message ", "send message", "upload"))


def _sensitive_browser_action(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ("pay", "payment", "checkout", "login", "password", "otp", "card", "passport", "private key", "api key", "submit"))


_SENSITIVE_URL_RE = re.compile(r"/(checkout|payments?|login|signin|sign-in|account/auth)\b|[?&](checkout|login|auth)=", re.I)
_SENSITIVE_TEXT_RE = re.compile(
    r"card number|cvv|one[- ]time password|\botp code\b|sign in to continue|log in to continue|"
    r"enter your password|private key|api key|seed phrase",
    re.I,
)


def _sensitive_page(text: str, url: str) -> bool:
    """Flag real checkout/login flows, not retail pages that merely mention
    'checkout' or 'payment' in their navigation (the night2 false positive)."""
    if _SENSITIVE_URL_RE.search(url):
        return True
    return bool(_SENSITIVE_TEXT_RE.search(text))


def _unsafe_gcp_action(text: str) -> bool:
    lowered = text.lower()
    blocked = (
        "deploy",
        "delete",
        "restart",
        "stop service",
        "start service",
        "change iam",
        "iam permission",
        "add member",
        "remove member",
        "billing change",
        "change billing",
        "create key",
        "api key",
        "service account key",
        "credential",
        "secret",
    )
    return any(marker in lowered for marker in blocked)


def _gcp_url_for_request(text: str) -> tuple[str, str]:
    lowered = text.lower()
    if "log" in lowered:
        return "https://console.cloud.google.com/logs/query", "logs"
    if "cloud run" in lowered or re.search(r"\brun\b", lowered):
        return "https://console.cloud.google.com/run", "Cloud Run"
    if "api" in lowered:
        return "https://console.cloud.google.com/apis/dashboard", "API dashboard"
    if "billing" in lowered:
        return "https://console.cloud.google.com/billing", "billing overview"
    return "https://console.cloud.google.com", "console home"
