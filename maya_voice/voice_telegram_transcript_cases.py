from __future__ import annotations

from dataclasses import dataclass

from maya_voice.voice_telegram_transcript_extra_cases import build_chat_cases, build_edit_cases, build_park_cases


TARGET_CASES = 10_000

FORBIDDEN_TOPIC_NOISE = (
    "put it",
    "put this",
    "needs to be",
    "should be",
    "has to be",
    "must be",
    "keep it",
    "save it",
    "may i",
    "hey maya",
    "hey, may i",
    "background noise",
    "got cut off",
    "me a ",
)

TOPICS = (
    "two day Seoul food trip",
    "router setup guide",
    "Kampung AI document quality proposal",
    "monthly office spending tracker",
    "Seoul food budget",
    "Kampung AI roadmap",
    "weekly office priorities",
    "Penang hotel comparison",
    "client meeting notes",
    "home WiFi upgrade plan",
    "Tokyo cafe itinerary",
    "project launch checklist",
    "PowerPoint quality checklist",
    "sales deck review notes",
    "document quality proposal budget tracker",
    "Airbnb comparison for Seoul",
    "flight comparison to Tokyo",
    "office reimbursement template",
    "product comparison for monitors",
    "YouTube channel research notes",
    "Bambu Lab print checklist",
    "Blender maker workflow",
    "team onboarding guide",
    "proposal for a client workshop",
    "technical troubleshooting guide",
    "security review checklist",
    "weekly memory audit",
    "June 8 iMac voice test plan",
    "browser workflow benchmark",
    "travel booking safety notes",
)

SPOKEN_VARIANTS = (
    "{x}",
    "um {x}",
    "okay so {x}",
    "sorry wait no {x}",
    "Hey Maya, {x}",
    "Hey, may I {x}",
    "{x} with background noise",
    "{x} and",
    "like {x}",
    "uh Maya, {x}",
)


@dataclass(frozen=True)
class ReplayCase:
    group: str
    text: str
    expected: str


def build_cases() -> list[ReplayCase]:
    artifact_cases: list[ReplayCase] = []
    artifact_cases.extend(_artifact_cases("docx", _docx_templates()))
    artifact_cases.extend(_artifact_cases("xlsx", _xlsx_templates()))
    artifact_cases.extend(_artifact_cases("pptx", _pptx_templates()))
    artifact_cases.extend(_artifact_cases("html", _html_templates()))
    artifact_cases.extend(_artifact_cases("md", _md_templates()))
    cases = [
        *_take(artifact_cases, 8300),
        *_take(_ambiguous_document_cases(), 200),
        *_take(build_edit_cases(ReplayCase, SPOKEN_VARIANTS), 300),
        *_take(_command_cases(), 350),
        *_take(build_park_cases(ReplayCase, SPOKEN_VARIANTS), 280),
        *_take(build_chat_cases(ReplayCase, SPOKEN_VARIANTS), 570),
    ]
    if len(cases) < TARGET_CASES:
        raise AssertionError(f"not enough generated cases: {len(cases)}")
    return cases[:TARGET_CASES]


def _take(cases: list[ReplayCase], count: int) -> list[ReplayCase]:
    if len(cases) < count:
        raise AssertionError(f"case group too small: {len(cases)} < {count}")
    return cases[:count]


def _artifact_cases(kind: str, templates: tuple[str, ...]) -> list[ReplayCase]:
    return [
        ReplayCase("artifact", variant.format(x=template.format(topic=topic)), kind)
        for topic in TOPICS
        for template in templates
        for variant in SPOKEN_VARIANTS
    ]


def _docx_templates() -> tuple[str, ...]:
    return (
        "make me a {topic} Word document",
        "make me {topic} in Word",
        "I need a {topic}. Put it in Word",
        "I need {topic}. Put it in work",
        "write a {topic} as a Word document",
        "create a Word document about {topic}",
        "prepare a Word file for {topic}",
        "make a {topic}. It needs to be in Word",
        "make a {topic}. It should be a Word document",
        "create a {topic}. Save it as docx",
        "create a {topic}. Save it in work",
        "draft a {topic} in Word",
        "put together a {topic} Word document",
        "make me a {topic} to be in Word",
    )


def _ambiguous_document_cases() -> list[ReplayCase]:
    templates = (
        "make me a {topic} document",
        "write a {topic} as a document",
        "create a document about {topic}",
        "make a {topic}. It needs to be in document",
        "draft a {topic} in document",
        "make me a {topic} to be in document",
    )
    return [
        ReplayCase("clarification", variant.format(x=template.format(topic=topic)), "artifact_type")
        for topic in TOPICS
        for template in templates
        for variant in SPOKEN_VARIANTS
    ]


def _xlsx_templates() -> tuple[str, ...]:
    return (
        "make me a {topic} budget tracker",
        "make me {topic} in Excel",
        "I need a {topic}. Put it in Excel",
        "create a spreadsheet about {topic}",
        "prepare an Excel workbook for {topic}",
        "make a {topic}. It needs to be in Excel",
        "make a {topic}. It should be a spreadsheet",
        "create a {topic}. Save it as xlsx",
        "draft a {topic} in spreadsheet",
        "put together a {topic} workbook",
        "make me a {topic} spending tracker",
        "make me a {topic} cost tracker",
    )


def _pptx_templates() -> tuple[str, ...]:
    return (
        "make me a {topic} deck",
        "make me {topic} in PowerPoint",
        "I need a {topic}. Put it in PowerPoint",
        "create a presentation about {topic}",
        "make slides for {topic}",
        "prepare a PowerPoint deck for {topic}",
        "make a {topic}. It needs to be a deck",
        "make a {topic}. It should be a presentation",
        "create a {topic}. Save it as pptx",
        "draft a {topic} in slides",
        "put together a {topic} presentation",
        "make me a {topic} slide deck",
    )


def _html_templates() -> tuple[str, ...]:
    return (
        "make an html file about {topic}",
        "make me {topic} in html",
        "create a html page for {topic}",
        "draft {topic} as html",
        "prepare an html file on {topic}",
    )


def _md_templates() -> tuple[str, ...]:
    return (
        "make a markdown note about {topic}",
        "make me {topic} in markdown",
        "create an md file for {topic}",
        "draft {topic} as markdown",
        "prepare a markdown file on {topic}",
    )


def _command_cases() -> list[ReplayCase]:
    commands = {
        "/route": ("show route", "show me the route", "what route did you use", "last route"),
        "/review": ("show review", "show me the review", "what did the review say", "show artifact review"),
        "/delivery": ("show delivery", "did you send it", "show me the delivery"),
        "/weekly status": ("weekly status", "show weekly memory status", "show me weekly status"),
        "/cost": ("show cost", "how much did it cost", "show me the cost"),
        "/memory": ("show memory", "show me memory sources", "what is in your memory"),
        "/providers": ("show providers", "provider readiness", "show provider status"),
        "/status": ("show status", "system status", "maya status"),
        "/turn": ("show last turn", "what happened last turn", "show me the last turn"),
        "/selfheal dryrun": ("self heal dry run", "show self heal dry run", "selfheal dryrun"),
        "/createskill youtube channel navigation": ("create skill for youtube channel navigation", "make a skill for youtube channel navigation"),
        "/complex self heal maya after approval": ("complex self heal maya after approval", "use complex self heal maya after approval"),
        "/remember my telegram test drink is teh ais": ("remember my telegram test drink is teh ais",),
        "/forget my telegram test drink": ("forget my telegram test drink",),
    }
    return [
        ReplayCase("command", variant.format(x=text), expected)
        for expected, phrases in commands.items()
        for text in phrases
        for variant in SPOKEN_VARIANTS
    ]
