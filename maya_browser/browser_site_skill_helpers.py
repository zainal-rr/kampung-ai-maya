from __future__ import annotations

import json
import re
import time
from urllib.parse import parse_qs, urlparse

from maya_core.storage import get_preference, upsert_preference


GOOGLE_SEARCH_SKILL_ID = "google_search"
YOUTUBE_SKILL_ID = "youtube_research"
REDDIT_SKILL_ID = "reddit_research"
RESULT_CONTEXT_KEY = "maya_browser_result_context"
RESULT_CONTEXT_TTL_SECONDS = 1800
SITE_RESULT_TARGETS = (
    "reddit",
    "wikipedia",
    "gamespot",
    "polygon",
    "imdb",
    "youtube",
    "github",
    "stackoverflow",
    "medium",
    "tripadvisor",
)


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
            r"^(?:and\s+)?(?:open|pull\s+up|bring\s+up|show\s+me|show|go\s+to|visit)\s+(?:the\s+)?",
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
    if _site_followup_target(text):
        return True
    return bool(re.search(r"\b(one|result|link|post|page|thread|article)\b", lowered)) and any(
        re.search(rf"\b{site}\b", lowered) for site in SITE_RESULT_TARGETS
    )


def _site_followup_target(text: str) -> str:
    lowered = " ".join(text.lower().split())
    for site in SITE_RESULT_TARGETS:
        if re.search(rf"\bthe\s+{site}\b", lowered):
            return site
        if re.search(rf"\b{site}\s+(one|result|review|thread|post|page|article|link)\b", lowered):
            return site
    return ""


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
    if site := _site_followup_target(text):
        return site
    cleaned = re.sub(r"\b(open|click|select|choose|maybe|the|that|this|one|first|top|second|third|fourth|fifth|result|video|thread|post|page|article|link|title)\b", " ", text, flags=re.I)
    cleaned = re.sub(r"\b(can|could|would)\s+you\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(please|maya)\b", " ", cleaned, flags=re.I)
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
    patterns = (
        r"\b(?:write|leave|add|make|create|submit|send)\s+(?:a\s+)?comment\b",
        r"\b(?:write|make|create|submit)\s+(?:a\s+)?post\b",
        r"\b(?:upvote|downvote|subscribe|upload)\b",
        r"\bjoin\s+subreddit\b",
        r"\bsend\s+(?:a\s+)?message\b",
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def _sensitive_browser_action(text: str) -> bool:
    lowered = text.lower()
    if any(word in lowered for word in ("pay", "payment", "checkout", "login", "password", "otp", "card", "passport", "private key", "api key", "submit")):
        return True
    return _looks_like_posting_or_account_action(text)


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


async def _remember_result_context(db_path: str, spec, query: str, page, options: list[str]) -> None:
    merged_options: list[str] = []
    for item in [*options, *_extract_visible_options(page.text, limit=10)]:
        clean = " ".join(str(item).split()).strip()
        if clean and clean not in merged_options:
            merged_options.append(clean)
        if len(merged_options) >= 10:
            break
    payload = {
        "created_at": time.time(),
        "provider": spec.workflow_prefix,
        "query": query,
        "page_title": page.title,
        "page_url": page.url,
        "options": merged_options,
    }
    await upsert_preference(db_path, RESULT_CONTEXT_KEY, json.dumps(payload, ensure_ascii=True), source="skill")


async def _load_result_context(db_path: str) -> dict:
    raw = await get_preference(db_path, RESULT_CONTEXT_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        age = time.time() - float(data.get("created_at", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return data if age <= RESULT_CONTEXT_TTL_SECONDS else {}


def _context_query_for_site(context: dict, site: str) -> str:
    if not site or not context:
        return ""
    domain = _site_domain(site)
    options = [str(item).lower() for item in context.get("options", [])]
    if domain and any(site in item or domain in item for item in options):
        return str(context.get("query", "")).strip()
    return ""


def _missing_context_reply(skill_name: str, site: str) -> str:
    return (
        f"{skill_name} skill has no active search result context for the {site.title()} result. "
        "Tell me the topic to search first, then I can open the matching result."
    )


def _verify_contextual_open(page, context: dict, site: str) -> tuple[bool, str]:
    if not _url_matches_site(page.url, site):
        return False, f"opened URL is not on {site}"
    if _is_literal_site_search(page.url, site):
        return False, "opened a site search page instead of a result page"
    query = str(context.get("query", "")).strip()
    terms = _topic_terms(query)
    if not terms:
        return True, ""
    haystack = f"{page.title}\n{page.url}\n{page.text[:2000]}".lower()
    if any(term in haystack for term in terms):
        return True, ""
    return False, f"opened page does not mention the active topic '{query}'"


def _site_domain(site: str) -> str:
    return {
        "reddit": "reddit.com",
        "youtube": "youtube.com",
        "github": "github.com",
        "stackoverflow": "stackoverflow.com",
        "wikipedia": "wikipedia.org",
        "gamespot": "gamespot.com",
        "polygon": "polygon.com",
        "imdb": "imdb.com",
        "medium": "medium.com",
        "tripadvisor": "tripadvisor",
    }.get(site, "")


def _url_matches_site(url: str, site: str) -> bool:
    domain = _site_domain(site)
    if not domain:
        return False
    host = urlparse(url).netloc.lower()
    if site == "tripadvisor":
        return host == "tripadvisor.com" or host.endswith(".tripadvisor.com") or ".tripadvisor." in host
    return host == domain or host.endswith("." + domain)


def _is_literal_site_search(url: str, site: str) -> bool:
    parsed = urlparse(url)
    if "search" not in parsed.path.lower():
        return False
    query = " ".join(value for values in parse_qs(parsed.query).values() for value in values).lower()
    return site in query and any(marker in query for marker in ("open", "click", "can i", "can you"))


def _topic_terms(query: str) -> list[str]:
    stop = {
        "google",
        "search",
        "find",
        "online",
        "review",
        "reviews",
        "reddit",
        "youtube",
        "video",
        "videos",
        "thread",
        "threads",
    }
    return [token for token in re.split(r"\W+", query.lower()) if len(token) >= 4 and token not in stop][:6]
