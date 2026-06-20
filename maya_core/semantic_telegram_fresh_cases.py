from __future__ import annotations

from dataclasses import dataclass


TARGET_CASES = 500


@dataclass(frozen=True)
class FreshCase:
    text: str
    input_type: str
    expected: str


def build_cases() -> list[FreshCase]:
    cases: list[FreshCase] = []
    for input_type in ("text", "voice note"):
        cases.extend(_make(input_type, _travel_budget_requests(), "travel_budget", 65))
        cases.extend(_make(input_type, _food_budget_requests(), "food_budget", 55))
        cases.extend(_make(input_type, _edit_people_requests(), "edit_people", 20))
        cases.extend(_make(input_type, _nontravel_budget_requests(), "nontravel_budget", 30))
        cases.extend(_make(input_type, _word_requests(), "word", 20))
        cases.extend(_make(input_type, _deck_requests(), "deck", 20))
        cases.extend(_make(input_type, _generic_document_requests(), "clarify_document", 25))
        cases.extend(_make(input_type, _normal_chat_requests(), "normal_chat", 15))
    return cases[:TARGET_CASES]


def _make(input_type: str, seeds: tuple[str, ...], expected: str, count: int) -> list[FreshCase]:
    variants = []
    noise = (
        "{x}",
        "Hey Maya, {x}",
        "Hey Maya, um {x}",
        "Maya, okay wait {x}",
        "um {x}",
        "okay wait {x}",
        "{x}, please",
        "sorry, {x}",
    )
    for seed in seeds:
        for wrapper in noise:
            variants.append(FreshCase(wrapper.format(x=seed), input_type, expected))
    if len(variants) < count:
        raise AssertionError(f"not enough variants for {expected}")
    return variants[:count]


def _travel_budget_requests() -> tuple[str, ...]:
    return (
        "Give me a Tokyo Excel sheet for 2 days with 2 people",
        "Make an Osaka spreadsheet for 3 days and one traveler",
        "Create a Seoul travel budget Excel for 4 days and 2 adults",
        "I need a Kyoto trip cost sheet for two days and three people",
        "Build a Bangkok budget workbook for 5 days, 2 pax",
        "Prepare a Singapore Excel travel sheet for 2 days, 1 person",
        "Can you make a Taipei cost workbook for 3 days with 2 people",
        "Make me a Hong Kong spending sheet for two days and two adults",
        "Give me a Penang trip budget sheet for 4 days 2 people",
        "Create a Bali Excel tracker, 5 days, 2 pax",
        "Need a Tokyo travel spending workbook for one person and 2 days",
    )


def _food_budget_requests() -> tuple[str, ...]:
    return (
        "A Tokyo food cost sheet",
        "Put my Tokyo restaurant spending plan in Excel for 2 days and 2 adult",
        "Make me a Seoul dining budget tracker for two days and two people",
        "Create an Osaka restaurant cost workbook for 3 days 2 pax",
        "I need a Kyoto meals spreadsheet for two days and one person",
        "Give me a Bangkok food budget Excel for 4 days and 3 people",
        "Prepare a Taipei cafe spending tracker for 2 days 2 adults",
        "Make a Tokyo restaurant budget sheet with source links",
        "Create a Seoul food trip cost tracker in Excel",
        "Need an Excel sheet for Osaka meals, 2 days, 2 pax",
    )


def _edit_people_requests() -> tuple[str, ...]:
    return (
        "change it to two person now",
        "change that to one traveler",
        "update the latest workbook to 3 people",
        "make it for two adults",
        "set the number of people in the sheet to 4",
    )


def _nontravel_budget_requests() -> tuple[str, ...]:
    return (
        "Make a monthly household budget Excel for 4 people",
        "Create an office pantry inventory sheet",
        "Build a vendor comparison spreadsheet for monitor options",
        "Make a client workshop cost comparison workbook",
        "Create a home renovation budget tracker",
        "Prepare a subscription spending tracker in Excel",
    )


def _word_requests() -> tuple[str, ...]:
    return (
        "Make me a Tokyo itinerary trip for 4 days with 2 people",
        "Make me a router config",
        "Prepare a technical troubleshooting guide",
        "Draft a Kampung AI quality proposal",
        "Make a router setup guide in Word",
        "Create a Kampung AI document quality proposal Word document",
        "Write a research brief Word doc about agentic workflows",
        "Make me a Seoul food trip Word document",
        "Prepare a technical troubleshooting guide in Word",
    )


def _deck_requests() -> tuple[str, ...]:
    return (
        "Make me a Seoul food trip deck",
        "Create a PowerPoint about Kampung AI roadmap",
        "Prepare slides for router migration plan",
        "Build a deck about agentic workflow",
        "Make a presentation on document quality",
    )


def _generic_document_requests() -> tuple[str, ...]:
    return (
        "Make me a Tokyo food trip document",
        "Create a document about Kampung AI roadmap",
        "I need a router setup document",
        "Prepare a Seoul planning document",
        "Draft a document for the budget review",
    )


def _normal_chat_requests() -> tuple[str, ...]:
    return (
        "what is quantum computing",
        "why is spin important",
        "tell me something about Tokyo food",
        "how should I think about budgeting",
        "explain what a spreadsheet is",
    )
