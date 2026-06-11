from __future__ import annotations

import re


def _slide_kicker(title: str, deck_topic: str = "") -> str:
    lowered = str(title).lower()
    context = f"{deck_topic} {title}".lower()
    if _quality_topic(context):
        if any(word in lowered for word in ("visible", "standard", "contract", "artifact quality")):
            return "QUALITY CONTRACT"
        if any(word in lowered for word in ("review", "qa", "gate", "validate", "validation")):
            return "REVIEW BEFORE SEND"
        if any(word in lowered for word in ("unify", "channel", "telegram", "imac", "same pipeline")):
            return "ONE DOCUMENT PIPELINE"
        if any(word in lowered for word in ("channel", "telegram", "imac", "delivery", "ship", "attach")):
            return "FINAL DELIVERY GATE"
        if any(word in lowered for word in ("route", "cost", "trace", "evidence", "proof")):
            return "ROUTE + REVIEW EVIDENCE"
        if any(word in lowered for word in ("skill", "standard", "quality", "artifact", "document")):
            return "ARTIFACT STANDARD"
        if any(word in lowered for word in ("repair", "retry", "loop", "pass")):
            return "REPAIR UNTIL PASS"
        return "DOCUMENT QUALITY"
    if _agent_topic(context):
        if any(word in lowered for word in ("memory", "context", "thread")):
            return "AGENT MEMORY"
        if any(word in lowered for word in ("tool", "approval", "permission", "safety")):
            return "TOOL GATE"
        if any(word in lowered for word in ("workflow", "route", "handoff", "worker")):
            return "WORKFLOW TRACE"
        return "AGENT SYSTEM"
    if _browser_topic(context):
        if any(word in lowered for word in ("youtube", "video")):
            return "YOUTUBE SKILL"
        if any(word in lowered for word in ("reddit", "thread")):
            return "REDDIT SKILL"
        if any(word in lowered for word in ("flight", "hotel", "airbnb", "booking")):
            return "TRAVEL SKILL"
        if any(word in lowered for word in ("safety", "login", "payment")):
            return "SAFETY STOP"
        return "BROWSER SKILL"
    if _travel_topic(context):
        if any(word in lowered for word in ("flight", "booking", "hotel", "airbnb", "accommodation")):
            return "BOOKING DECISION"
        if any(word in lowered for word in ("budget", "cost", "actual", "estimate")):
            return "TRIP BUDGET"
        if any(word in lowered for word in ("risk", "safety", "weather", "hiking", "trail")):
            return "TRIP SAFETY"
        if any(word in lowered for word in ("day", "route", "itinerary", "plan")):
            return "TRIP ROUTE"
        return "TRAVEL PLAN"
    if _drone_topic(context):
        if any(word in lowered for word in ("equipment", "aircraft", "payload")):
            return "DRONE KIT"
        if any(word in lowered for word in ("compliance", "risk", "safety", "permission")):
            return "FLIGHT SAFETY"
        if any(word in lowered for word in ("service", "pricing", "market")):
            return "SERVICE MODEL"
        return "DRONE OPS"
    if _agriculture_topic(context):
        if any(word in lowered for word in ("water", "soil", "climate")):
            return "FARM RESILIENCE"
        if any(word in lowered for word in ("cost", "fertilizer", "economics")):
            return "FARM COST"
        if any(word in lowered for word in ("policy", "support", "adoption")):
            return "POLICY OPTION"
        return "AGRICULTURE"
    if _cloud_topic(context):
        if any(word in lowered for word in ("cost", "budget", "spend")):
            return "CLOUD COST"
        if any(word in lowered for word in ("security", "logging", "monitoring")):
            return "CLOUD CONTROL"
        return "CLOUD GOVERNANCE"
    if _house_topic(context):
        if any(word in lowered for word in ("material", "layout", "climate")):
            return "DESIGN CHOICE"
        if any(word in lowered for word in ("cost", "tradeoff")):
            return "BUILD TRADEOFF"
        return "KAMPUNG DESIGN"
    if _robotics_topic(context):
        if any(word in lowered for word in ("agenda", "schedule")):
            return "WORKSHOP FLOW"
        if any(word in lowered for word in ("kit", "team", "role")):
            return "TEAM SETUP"
        if any(word in lowered for word in ("judging", "assessment")):
            return "LEARNING CHECK"
        return "ROBOTICS WORKSHOP"
    if any(word in lowered for word in ("old", "new", "culture", "heritage", "modern")):
        return "FOOD CULTURE"
    if any(word in lowered for word in ("day", "anchor", "food", "restaurant", "meal", "market", "cafe")):
        return "FOOD PLAN"
    if any(word in lowered for word in ("famous", "backup", "dish", "stop", "highlight")):
        return "FOOD BACKUP"
    if any(word in lowered for word in ("budget", "cost", "spend", "splurge")):
        return "BUDGET"
    if any(word in lowered for word in ("logistics", "transit", "route", "map")):
        return "ROUTE"
    if any(word in lowered for word in ("app", "naver", "catchtable", "booking", "reservation", "protect")):
        return "TOOLS"
    if any(word in lowered for word in ("local", "tip", "rule", "insider", "move", "etiquette", "timing", "hydration")):
        return "LOCAL READ"
    if any(word in lowered for word in ("recommend", "next", "decision")):
        return "DECISION"
    return "KEY POINT"


def _quality_topic(context: str) -> bool:
    markers = (
        "document quality",
        "artifact quality",
        "quality gate",
        "review standard",
        "qa",
        "validation",
    )
    return any(marker in context for marker in markers)


def _agent_topic(context: str) -> bool:
    markers = (
        "kampung ai",
        "maya",
        "agent",
        "thread manager",
        "tool registry",
        "event store",
    )
    return any(marker in context for marker in markers)


def _browser_topic(context: str) -> bool:
    markers = ("browser", "google search", "google images", "youtube", "reddit", "google flights", "booking.com", "airbnb")
    return any(marker in context for marker in markers)


def _travel_topic(context: str) -> bool:
    markers = ("trip", "travel", "itinerary", "flight", "hotel", "airbnb", "hiking", "almaty", "kazakhstan", "japan", "osaka", "kyoto")
    return any(marker in context for marker in markers)


def _drone_topic(context: str) -> bool:
    markers = ("drone", "uav", "inspection", "aerial", "pilot")
    return any(marker in context for marker in markers)


def _agriculture_topic(context: str) -> bool:
    markers = ("agriculture", "crop", "fertilizer", "farm", "water management", "climate risk")
    return any(marker in context for marker in markers)


def _cloud_topic(context: str) -> bool:
    markers = ("google cloud", "cloud cost", "budget alert", "logging", "security", "startup")
    return any(marker in context for marker in markers)


def _house_topic(context: str) -> bool:
    markers = ("modern kampung", "house design", "materials", "layout", "climate response")
    return any(marker in context for marker in markers)


def _robotics_topic(context: str) -> bool:
    markers = ("robotics", "workshop", "school", "kits", "judging")
    return any(marker in context for marker in markers)


def _short(text: str, limit: int = 90, complete: bool = True) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return _complete(clean) if complete else clean.rstrip(".")
    for punctuation in (". ", "? ", "! "):
        pos = clean.rfind(punctuation, 0, limit)
        if pos >= 35:
            clipped = clean[: pos + 1].strip()
            return clipped if complete else clipped.rstrip(".")
    for separator in (" — ", " - ", "; ", ": "):
        first = clean.split(separator, 1)[0].strip()
        if 35 <= len(first) <= limit:
            return first.rstrip(".") + "." if complete else first.rstrip(".")
    clipped = clean[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    # Strip dangling function/auxiliary words exposed by the character cut so
    # the clipped text ends on a content word instead of a mid-claim fragment
    # ("...Is Still Done" -> "...Infrastructure"). Live polish rejections
    # 2026-06-11 traced to exactly these layout-level cuts.
    words = clipped.split()
    while len(words) > 2 and words[-1].lower().strip(",;:.") in _DANGLING_WORDS:
        words.pop()
    clipped = " ".join(words)
    return clipped.rstrip(".") + "." if complete else clipped.rstrip(".")


def _complete(text: str) -> str:
    clean = text.strip(" ,;:-")
    return clean if clean.endswith((".", "?", "!", ")")) else clean + "."


def _notes_text(title: str, bullets: list[str]) -> str:
    lines = [title.strip().rstrip("."), "", "Talk track:"]
    for bullet in bullets[:5]:
        clean = _complete(str(bullet))
        if clean:
            lines.append(f"- {clean}")
    return "\n".join(lines).strip()


def _visual_title(title: str, index: int) -> str:
    text = " ".join(str(title).split()).strip(" .:-")
    lowered = text.lower()
    if index == 0:
        candidate = re.split(r"[:.]", text, 1)[0].strip()
        if len(candidate) < 8 or len(candidate.split()) < 2:
            candidate = text
        return _strong_visual_title(_title_words(candidate, 7))
    day_match = re.match(r"^(day\s*\d+)(?:\s+[a-z]+)?\s*[:\-]\s*(.+)$", text, flags=re.I)
    if day_match:
        day = day_match.group(1).title().replace(" ", " ")
        topic = _title_words(day_match.group(2), 3)
        return f"{day}: {topic}" if topic else f"{day}: Plan"
    if lowered.startswith("configure ") or "configure in blocks" in lowered:
        return "Configure In Blocks"
    if "admin surface" in lowered:
        return "Lock The Admin Surface"
    if "rollback" in lowered:
        return "Keep Rollback Ready"
    mappings = (
        (("anchor", "standout meal"), "Anchor Each Day Around One Meal"),
        (("backup", "famous"), "Pair Famous Stops With Backups"),
        (("compare the big costs", "big costs", "cost first"), "Compare The Big Costs"),
        (("editable", "estimate", "actual"), "Keep Budget Editable"),
        (("budget", "splurge", "cost"), "Budget The Tradeoffs"),
        (("logistics", "transit", "map"), "Cluster Meals To Cut Transit"),
        (("decision", "itinerary"), "Turn The Plan Into Decisions"),
        (("ready plan", "ready", "leave with"), "Leave With A Ready Plan"),
        (("risk", "safety"), "Make The Risks Visible"),
        (("verify", "verification"), "Verify Before You Commit"),
        (("config", "configuration", "setup"), "Sequence The Setup Safely"),
        # NOTE (2026-06-11): the (("proposal", "recommendation"), "Make The
        # Recommendation Clear") mapping was removed. It rewrote EVERY
        # recommendation-flavored closing from every path (drafter arcs,
        # Gemini section headings, rescue templates) into one banned generic
        # title — the live Phase 4 closing-leak root cause. Deck species arcs
        # and rescue templates now own their closing titles.
    )
    for keywords, label in mappings:
        if any(keyword in lowered for keyword in keywords):
            return label
    text = re.split(r"[:.]", text, 1)[0].strip()
    if len(text.split()) <= 6:
        label = _fix_acronyms(text.title())
    else:
        label = _title_words(text, 7)
    return _strong_visual_title(label)


def _visual_bullets(bullets: list[str], limit: int = 5) -> list[str]:
    labels = []
    seen = set()
    for bullet in bullets[: max(1, limit)]:
        label = _visual_label(bullet)
        key = label.lower()
        if label and key not in seen:
            labels.append(label)
            seen.add(key)
        if len(labels) >= limit:
            break
    return labels or ["Context", "Choice", "Next step"]


def _visual_label(text: str) -> str:
    clean = " ".join(str(text).split()).strip(" .:-")
    if not clean:
        return ""
    clean = clean.replace("₩", "KRW ")
    low = clean.lower()
    if "food tour" in low or "weekend" in low:
        return "48-hour food route"
    if "realistic pace" in low or "realistic pacing" in low:
        return "Realistic pace"
    if "signature meal" in low:
        return "One anchor meal"
    if "avoid building" in low or "crossing the city" in low or "zigzag" in low:
        return "Avoid citywide zigzags"
    if "dead time" in low:
        return "Avoid dead time"
    if "gwangjang" in low:
        return "Gwangjang early"
    if "tipping" in low:
        return "No tipping needed"
    if "subway" in low or "real time" in low:
        return "Live transit backup"
    if "rain backup" in low:
        return "Rain backup plan"
    if "theme" == low or low.startswith("theme:"):
        return "Food-first route"
    if "build each day" in low:
        return "One anchor per day"
    if "visual presentation" in low or "authentic" in low:
        return "Authentic flavor first"
    if "krw" in low or "$" in clean:
        return "KRW daily budget"
    day = re.search(r"\b(day\s*\d+)\b", clean, flags=re.I)
    if day:
        prefix = day.group(1).title().replace(" ", " ")
        tail = re.split(r"[,.;]", clean, 1)[0]
        tail = re.sub(r"^\s*day\s*\d+\s*:?\s*", "", tail, flags=re.I).strip()
        tail = re.sub(r"^.*?\banchors?\s+(?:on|around)?\s*", "", tail, flags=re.I).strip()
        tail = _title_words(tail, 4) if tail else "Food Anchor"
        return _fix_acronyms(f"{prefix}: {tail}")
    if ":" in clean:
        left, right = [part.strip() for part in clean.split(":", 1)]
        amount = re.search(r"(?:KRW\s*)?\d[\d,]*(?:\s*[-–]\s*\d[\d,]*)?", right)
        if amount:
            return _fix_acronyms(f"{_title_words(left, 3)}: {amount.group(0).replace('KRW ', 'KRW ')}")
        return _title_words(left, 6)
    keywords = (
        ("food-first", "Food-first route"),
        ("food first", "Food-first route"),
        ("realistic pacing", "Realistic pace"),
        ("two day", "48-hour plan"),
        ("two days", "48-hour plan"),
        ("48 hour", "48-hour plan"),
        ("reservation", "Reserve early"),
        ("reserve", "Reserve early"),
        ("popular", "Reserve early"),
        ("backup", "Nearby backup"),
        ("budget", "Budget range"),
        ("cash", "Cash buffer"),
        ("map", "Map first"),
        ("zone", "Clustered food zones"),
        ("queue", "Queue plan"),
        ("bbq", "BBQ slot"),
        ("cafe", "Cafe route"),
        ("market", "Market stop"),
        ("flex", "Keep flexible"),
        ("download", "Apps ready"),
        ("actual", "Estimate vs actual"),
    )
    low = clean.lower()
    for keyword, label in keywords:
        if keyword in low:
            return label
    if len(clean) <= 44 and len(clean.split()) <= 7:
        return _fix_acronyms(clean.title())
    return _title_words(clean, 7)


_DANGLING_WORDS = {
    "and", "or", "the", "a", "an", "of", "to", "for", "with", "by", "in", "on", "as", "at",
    "from", "into", "onto", "around", "between", "before", "after", "over", "under", "then",
    "are", "is", "was", "were", "often", "still", "done", "being", "been", "not", "very",
    "more", "most", "new", "each", "per", "via", "has", "have", "had", "will", "would",
    "can", "could", "should", "must", "while", "when", "where", "because", "that", "this",
}

# Words of grace beyond a title cap: a complete 10-word claim reads better
# than a 7-word fragment. Live polish rejections 2026-06-11 ("Inspecting
# Critical Infrastructure Is Still Done", "Eliminate Weeks Of Manual") were
# manufactured by hard word-caps chopping complete claims mid-thought.
_TITLE_CAP_GRACE = 3


def _title_words(text: str, count: int) -> str:
    words = [word.strip(" ,;:.()[]{}") for word in str(text).split() if word.strip(" ,;:.()[]{}")]
    stop = _DANGLING_WORDS
    while words and words[-1].lower() in stop:
        words.pop()
    if not words:
        return ""
    if len(words) <= count + _TITLE_CAP_GRACE:
        # Keep the complete claim instead of manufacturing a fragment.
        selected = words
    else:
        selected = words[:count]
    while selected and selected[-1].lower() in stop:
        selected.pop()
    if not selected:
        selected = words[:1]
    return _fix_acronyms(" ".join(selected).title())


def _fix_acronyms(text: str) -> str:
    fixed = str(text)
    replacements = {
        "Krw": "KRW",
        "Myr": "MYR",
        "Usd": "USD",
        "Bbq": "BBQ",
        "Ai": "AI",
        "Wifi": "WiFi",
        "Pptx": "PPTX",
    }
    for source, target in replacements.items():
        fixed = re.sub(rf"\b{source}\b", target, fixed)
    return fixed


def _strong_visual_title(title: str) -> str:
    clean = " ".join(str(title).split()).strip()
    if len(clean) >= 8:
        return clean
    if re.match(r"^day\s*\d+$", clean, flags=re.I):
        return f"{clean.title()}: Plan"
    return f"{clean} Plan".strip()
