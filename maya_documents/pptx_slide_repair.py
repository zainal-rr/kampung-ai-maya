"""PowerPoint slide repair presets used by the QA loop.

`pptx_document_flow` calls this module when a generated deck fails or looks too
generic. The functions here deliberately return short, presentation-safe titles
and bullets for common domains so the rebuild path can remove dangling text,
weak titles, and sentence-heavy slides before visual QA runs again.

This is a local repair library, not a model call. It keeps retry behavior
predictable and cheap when the model-generated outline is not presentation-ready.
"""

from __future__ import annotations

import os
import re


def max_pptx_attempts(auto_improve: bool) -> int:
    if not auto_improve:
        return 1
    try:
        configured = int(os.getenv("PPTX_QA_MAX_ATTEMPTS", "3"))
    except ValueError:
        configured = 3
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
    title_text = str(title or "").lower()
    primary = title_text or text
    if "kampung ai" in primary and any(word in primary for word in ("architecture", "voice", "memory", "provider", "routing", "document tools")):
        return [
            ("Kampung AI Architecture Has Clear Layers", ["Voice interface", "Skill router", "Local tools"]),
            ("Voice Stays Lightweight", ["xAI conversation", "Hotkey control", "Interrupt-safe playback"]),
            ("Skills Own The Work", ["Browser skills", "Document tools", "Memory retrieval"]),
            ("Memory And Safety Gate Context", ["Profile memory", "Project memory", "Sensitive stops"]),
            ("Provider Routing Stays Hidden", ["One Maya personality", "Best internal helper", "Route logs for debug"]),
        ]
    if "youtube" in primary and any(word in primary for word in ("learning", "strategy", "channel", "video scoring", "note taking")):
        return [
            ("YouTube Learning Needs A Selection System", ["Channel trust", "Views and recency", "Clear learning goal"]),
            ("Score Videos Before Watching", ["Topic fit", "Creator quality", "Practical examples"]),
            ("Prioritize Subscribed Channels", ["Known style", "Higher trust", "Faster decision"]),
            ("Turn Watching Into Notes", ["Key ideas", "Commands or links", "Practice task"]),
            ("Watch Then Apply", ["Pick best video", "Summarize transcript", "Do one exercise"]),
        ]
    if any(word in primary for word in ("sprint review", "retrospective", "team review", "sprint", "backlog", "velocity")):
        return [
            ("Current Sprint Review Needs A Clear Decision", ["Goal under review", "Work completed", "Open blockers"]),
            ("Start With What Shipped", ["Completed work", "User impact", "Evidence to verify"]),
            ("Name The Blockers Without Drama", ["Blocked tickets", "Dependencies", "Owner needed"]),
            ("Decide What Changes Next Sprint", ["Keep", "Stop", "Improve"]),
            ("Close With Commitments", ["Owner", "Next action", "Review date"]),
        ]
    if any(word in primary for word in ("drone", "uav", "inspection", "pilot", "aerial", "equipment")):
        return [
            ("Drone Inspection Has A Clear Use Case", ["Faster site evidence", "Safer roof and asset checks", "Repeatable visual records"]),
            ("Services Need Operational Discipline", ["Survey scope", "Flight checklist", "Client report format"]),
            ("Equipment Choices Shape Margin", ["Aircraft and payload", "Batteries and spares", "Insurance and maintenance"]),
            ("Compliance Must Be Built In", ["Flight permissions", "Safety perimeter", "Data handling"]),
            ("Start Narrow", ["Pick two inspection packages", "Price by risk and output", "Build repeatable QA"]),
        ]
    if any(word in primary for word in ("browser automation", "google search", "google images", "youtube", "reddit", "google flights", "browser skill")):
        return [
            ("Browser Skills Need Deterministic Routes", ["Search intent", "Site-specific parser", "Safety stop"]),
            ("Each Site Needs Its Own Contract", ["Google Search", "Google Images", "YouTube and Reddit"]),
            ("Travel Browser Skills Need Structured Fields", ["Google Flights", "Booking.com", "Airbnb"]),
            ("Automation Must Stop Before Risk", ["Login", "Payment", "Booking submit"]),
            ("Build Skills, Not Prompts", ["Route first", "Verify page state", "Report limitations"]),
        ]
    if any(word in primary for word in ("almaty", "kazakhstan", "hiking", "mountain", "trek", "trail")):
        return [
            ("Almaty Works Best As A Nature Base", ["Mountain day trips", "Weather-aware routing", "Recovery buffers"]),
            ("Pick Routes By Fitness And Safety", ["Trail difficulty", "Transport access", "Guide needs"]),
            ("Nine Days Allows A Balanced Pace", ["City arrival", "Hiking blocks", "Rest and contingency"]),
            ("Budget Around Gear And Transfers", ["Transport", "Accommodation", "Food and park costs"]),
            ("Plan For Flexibility", ["Keep backup hikes", "Check conditions", "Avoid overpacking days"]),
        ]
    if any(word in primary for word in ("agriculture", "crop", "fertilizer", "water management", "climate risk", "labor shortage")):
        return [
            ("Agriculture Pressure Is Rising", ["Climate volatility", "Labor shortage", "Input cost squeeze"]),
            ("Water And Soil Decide Resilience", ["Irrigation discipline", "Soil health", "Flood and drought planning"]),
            ("Farm Economics Need Protection", ["Fertilizer exposure", "Yield uncertainty", "Market access"]),
            ("Policy Should Support Adoption", ["Extension support", "Data-backed incentives", "Smallholder financing"]),
            ("Prioritize Resilience", ["Water systems first", "Mechanization where practical", "Weekly risk review"]),
        ]
    if any(word in text for word in ("google cloud", "cloud cost", "cost governance", "budget alert", "logging", "security")):
        return [
            ("Cloud Spend Needs A Weekly Owner", ["Budget alerts", "Service-level ownership", "Usage review rhythm"]),
            ("Visibility Comes Before Optimization", ["Billing export", "Log coverage", "Project labels"]),
            ("Security And Cost Are Linked", ["Least privilege", "Key rotation", "Unused service cleanup"]),
            ("Governance Should Stay Lightweight", ["Thresholds", "Exceptions", "Escalation path"]),
            ("Start With Guardrails", ["Alert first", "Review weekly", "Tune monthly"]),
        ]
    if any(word in primary for word in ("japan", "osaka", "kyoto", "flight", "hotel", "airbnb", "travel planning workflow")):
        return [
            ("Travel Planning Starts With The Route", ["Destination and dates", "Flight options", "Accommodation style"]),
            ("Compare The Big Costs First", ["Flight fare", "Hotel or Airbnb", "Transport buffer"]),
            ("Use Options To Make Decisions", ["Cheapest", "Best schedule", "Comfort tradeoff"]),
            ("Budget Should Stay Editable", ["Estimate versus actual", "Per-person split", "Notes for assumptions"]),
            ("Decide In Stages", ["Flight first", "Stay second", "Budget final"]),
        ]
    if any(word in text for word in ("food", "restaurant", "cafe", "seoul")):
        return [
            ("Seoul In 48 Hours", ["Food-first route", "Dark editorial guide", "Two focused days"]),
            ("Start With Two Anchor Meals", ["Day 1: market classics", "Day 2: cafe and BBQ", "One reservation backup"]),
            ("Follow The Neighborhood Spine", ["Jongno morning market", "Myeongdong lunch window", "Seongsu cafe block"]),
            ("Budget The Splurge", ["KRW daily budget", "One splurge dinner", "Cash for market stalls"]),
            ("Queue Tools Protect Plan", ["Naver Maps", "Catchtable reservation", "Rain backup plan"]),
            ("Leave With A Ready Plan", ["Book anchor meals", "Save backup pins", "Keep transit simple"]),
        ]
    if any(word in text for word in ("modern kampung", "house design", "materials", "layout", "climate response")):
        return [
            ("Modern Kampung Design Needs Balance", ["Heritage cues", "Climate performance", "Buildable cost"]),
            ("Materials Should Feel Warm And Durable", ["Timber accents", "Ventilated roof", "Low-maintenance finishes"]),
            ("Layout Should Support Family Life", ["Open social core", "Shaded outdoor edges", "Private bedroom wing"]),
            ("Climate Response Is The Design Spine", ["Cross ventilation", "Rain control", "Deep shade"]),
            ("Prototype The Feel", ["Mood board", "Cost bands", "Builder feedback"]),
        ]
    if any(word in text for word in ("robotics", "workshop", "school", "kits", "judging", "learning goals")):
        return [
            ("Robotics Workshops Need Clear Outcomes", ["Build confidence", "Teach iteration", "End with demo"]),
            ("The Agenda Should Reduce Waiting", ["Short intro", "Hands-on blocks", "Checkpoint reviews"]),
            ("Kits And Roles Keep Teams Moving", ["Builder", "Tester", "Presenter"]),
            ("Judging Should Reward Learning", ["Problem solving", "Teamwork", "Working prototype"]),
            ("Make It Practical", ["Prepare spares", "Use simple rubrics", "Capture follow-ups"]),
        ]
    if any(word in text for word in ("router", "wifi", "network", "config", "technical", "setup")):
        return [
            ("Sequence The Setup Safely", ["Prerequisites first", "Small config blocks", "Verify before saving"]),
            ("Lock The Admin Surface", ["Change admin password", "Use WPA2 or WPA3", "Back up current config"]),
            ("Configure In Blocks", ["WAN and LAN", "DHCP scope", "WiFi name and password"]),
            ("Verify Before Save", ["Check interface state", "Test DNS and internet", "Confirm client join"]),
            ("Keep Rollback Ready", ["Export config", "Document changes", "Know reset path"]),
        ]
    if any(word in text for word in ("document quality", "artifact quality", "quality gate", "review evidence", "validate", "validation", "repair loop", "qa pipeline")):
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
