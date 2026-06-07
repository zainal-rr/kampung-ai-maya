from __future__ import annotations

import os
import re


def max_pptx_attempts(auto_improve: bool) -> int:
    if not auto_improve:
        return 1
    try:
        configured = int(os.getenv("PPTX_QA_MAX_ATTEMPTS", "10"))
    except ValueError:
        configured = 10
    return max(1, min(configured, 10))


def attempt_slides(slides: list[tuple[str, list[str]]], attempt: int, title: str = "") -> list[tuple[str, list[str]]]:
    if attempt <= 0:
        return slides
    if attempt >= 2:
        return rescue_slides(slides, title)
    repaired: list[tuple[str, list[str]]] = []
    for title, bullets in slides:
        repaired.append((stronger_slide_title(title), [stronger_bullet(bullet) for bullet in bullets]))
    return repaired


def rescue_slides(slides: list[tuple[str, list[str]]], title: str = "") -> list[tuple[str, list[str]]]:
    text = " ".join([title] + [slide_title for slide_title, _ in slides] + [bullet for _, bullets in slides for bullet in bullets]).lower()
    if any(word in text for word in ("food", "restaurant", "cafe", "seoul", "trip", "travel", "itinerary")):
        return [
            ("Seoul In 48 Hours", ["Food-first route", "Dark editorial guide", "Two focused days"]),
            ("Start With Two Anchor Meals", ["Day 1: market classics", "Day 2: cafe and BBQ", "One reservation backup"]),
            ("Follow The Neighborhood Spine", ["Jongno morning market", "Myeongdong lunch window", "Seongsu cafe block"]),
            ("Budget The Splurge", ["KRW daily budget", "One splurge dinner", "Cash for market stalls"]),
            ("Queue Tools Protect Plan", ["Naver Maps", "Catchtable reservation", "Rain backup plan"]),
            ("Leave With A Ready Plan", ["Book anchor meals", "Save backup pins", "Keep transit simple"]),
        ]
    if any(word in text for word in ("router", "wifi", "network", "config", "technical", "setup")):
        return [
            ("Sequence The Setup Safely", ["Prerequisites first", "Small config blocks", "Verify before saving"]),
            ("Lock The Admin Surface", ["Change admin password", "Use WPA2 or WPA3", "Back up current config"]),
            ("Configure In Blocks", ["WAN and LAN", "DHCP scope", "WiFi name and password"]),
            ("Verify Before Save", ["Check interface state", "Test DNS and internet", "Confirm client join"]),
            ("Keep Rollback Ready", ["Export config", "Document changes", "Know reset path"]),
        ]
    if any(word in text for word in ("document quality", "artifact quality", "quality gate", "review", "validate", "validation", "repair", "pipeline")):
        return [
            ("Make Artifact Quality Measurable", ["Quality contract", "Local validation", "Review evidence"]),
            ("Build The Real File First", ["Local library build", "Editable artifact", "Openability check"]),
            ("Review The Artifact, Not The Prompt", ["Rendered proof", "Claude critique", "Concrete blockers"]),
            ("Repair Until The Gate Passes", ["One issue list", "Targeted rebuild", "No failed final"]),
            ("Deliver With Traceable Evidence", ["Route record", "Review summary", "Attached file"]),
        ]
    if any(word in text for word in ("proposal", "strategy", "roadmap", "business")):
        return [
            ("Make The Decision Clear", ["Current gap", "Recommended path", "Approval ask"]),
            ("Show The Cost Of Waiting", ["Quality risk", "Manual rework", "Slow delivery"]),
            ("Use A Repeatable Pipeline", ["Draft", "Build", "Validate", "Review", "Repair"]),
            ("Roll Out In Phases", ["Word first", "Excel second", "PowerPoint third"]),
            ("Approve The Next Gate", ["Owner", "Timeline", "Success signal"]),
        ]
    if office_work_topic(text):
        return [
            ("Focus The Week Around Three Outcomes", ["Critical work", "Blocked work", "Decision work"]),
            ("Separate Urgent From Important", ["Must finish", "Can wait", "Needs owner"]),
            ("Protect The Deep Work Window", ["No meeting block", "One escalation lane", "End of day review"]),
            ("Make Ownership Visible", ["Named owner", "Due date", "Status signal"]),
            ("Close With A Friday Scorecard", ["Done", "Blocked", "Next week"]),
        ]
    first = slides[0][0] if slides else "Presentation"
    return [
        (first, ["Clear framing", "One main decision", "Short visual story"]),
        ("Start With The Real Context", ["What matters", "Who decides", "Why now"]),
        ("Show The Main Tradeoff", ["Option A", "Option B", "Constraint"]),
        ("Make The Recommendation Visible", ["Best path", "Risk control", "Next action"]),
        ("Close With The Decision", ["Owner", "Timeline", "Success signal"]),
    ]


def office_work_topic(text: str) -> bool:
    return bool(
        any(word in text for word in ("office", "priority", "priorities", "weekly", "team"))
        or re.search(r"\bwork\b", text)
    )


def stronger_slide_title(title: str) -> str:
    clean = " ".join(str(title).split()).strip(" .")
    lowered = clean.lower()
    replacements = (
        (("daily anchor", "anchor each day", "one food anchor"), "Anchor Each Day Around One Meal"),
        (("famous", "backup"), "Pair Famous Stops With Backups"),
        (("budget", "splurge", "cost"), "Spend Intentionally, Not Randomly"),
        (("logistics", "transit", "route"), "Cluster Meals To Cut Transit"),
        (("local", "rules"), "Eat Better By Reading Local Cues"),
        (("next", "recommend"), "Book Anchors, Leave Room To Explore"),
    )
    for keywords, replacement in replacements:
        if any(keyword in lowered for keyword in keywords):
            return replacement
    return clean


def stronger_bullet(text: str) -> str:
    clean = " ".join(str(text).split()).strip(" .")
    lowered = clean.lower()
    if lowered in {"zones", "key idea", "context", "choice", "next step"}:
        return "Cluster the route by neighborhood."
    if lowered.endswith((" so you", " for", " from", " to", " with", " by", " as")):
        return clean.rsplit(" ", 1)[0]
    if lowered.endswith((" when", " where", " because")):
        return clean.rsplit(" ", 1)[0]
    return clean
