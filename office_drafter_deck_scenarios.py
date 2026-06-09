from __future__ import annotations

import re

from office_text_utils import _complete, _plain


def _travel_food_deck(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    display = _display_title(title)
    day_lines = _matching_lines(sections, ("day", "itinerary", "route", "plan"))
    food_lines = _matching_lines(sections, ("food", "restaurant", "highlight", "meal", "cafe", "market"))
    budget_lines = _matching_lines(sections, ("budget", "cost", "spend", "money"))
    transit_lines = _matching_lines(sections, ("transit", "booking", "logistics", "transport"))
    recommendation_lines = _matching_lines(sections, ("recommendation", "next", "backup", "tip"))
    return [
        (
            display,
            [
                f"{display} is organized as a food-first itinerary with realistic pacing.",
                _first(food_lines, "Anchor the trip around a few must-eat stops, then keep backup restaurants nearby."),
                _first(transit_lines, "Cluster meals by neighborhood so the deck stays useful in the actual city."),
            ],
        ),
        (
            "The trip works best when each day has one food anchor.",
            _take(
                day_lines,
                [
                    "Use one priority meal per day, then fill the rest with market snacks, cafes, and flexible stops.",
                    "Avoid crossing the city for a single bite unless it is the main stop.",
                    "Keep buffers for queues, weather, digestion, and late starts.",
                ],
            ),
        ),
        (
            "Food highlights need practical backups, not just famous names.",
            _take(
                food_lines,
                [
                    "Balance iconic restaurants with market food so the plan still works if a queue is too long.",
                    "Prioritize a mix of noodles, street snacks, cafes, BBQ, and one comfort meal.",
                    "Save nearby alternatives before the trip so missed stops do not break the route.",
                ],
            ),
        ),
        (
            "Budget around one splurge and many small decisions.",
            _take(
                budget_lines,
                [
                    "Separate market snacks, cafes, sit-down meals, transit, and one higher-cost dinner.",
                    "Use estimated versus actual spend so the deck can become a live trip tracker.",
                    "Keep cash available for markets and smaller stalls while using cards for larger restaurants.",
                ],
            ),
        ),
        (
            "Logistics should protect the food plan.",
            _take(
                transit_lines,
                [
                    "Group stops by subway area instead of creating a citywide zigzag.",
                    "Reserve popular dinners where possible and keep a lower-effort meal nearby.",
                    "Use the final stop of each day as a flexible recovery option.",
                ],
            ),
        ),
        (
            "Recommendations turn the itinerary into decisions.",
            _take(
                recommendation_lines,
                [
                    "Book the hard-to-replace meal first, then let smaller snack stops stay flexible.",
                    "Pick the neighborhood sequence before choosing every restaurant.",
                    "Use the deck as a decision aid: what to reserve, what to skip, and what to keep as backup.",
                ],
            ),
        ),
    ]


def _travel_deck(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    display = _display_title(title)
    itinerary_lines = _matching_lines(sections, ("day", "itinerary", "route", "plan", "schedule"))
    nature_lines = _matching_lines(sections, ("hiking", "nature", "mountain", "trail", "weather", "safety"))
    booking_lines = _matching_lines(sections, ("flight", "hotel", "airbnb", "booking", "accommodation", "transport"))
    budget_lines = _matching_lines(sections, ("budget", "cost", "money", "estimate", "actual"))
    decision_lines = _matching_lines(sections, ("recommendation", "decision", "next", "risk", "tradeoff"))
    return [
        (
            display,
            [
                f"{display} should help decide the route, budget, and practical next steps.",
                _first(itinerary_lines, "Start with the travel dates, destination sequence, and realistic daily pacing."),
                _first(booking_lines, "Separate flight, accommodation, and local transport decisions so costs stay clear."),
            ],
        ),
        (
            "The route should match the real purpose of the trip.",
            _take(
                itinerary_lines + nature_lines,
                [
                    "Anchor the plan around the main reason for going, then protect enough rest and buffer time.",
                    "Avoid packing every day with long transfers unless the route truly needs it.",
                    "Keep at least one weather or energy backup for nature-heavy trips.",
                ],
            ),
        ),
        (
            "Booking decisions should be compared before committing.",
            _take(
                booking_lines,
                [
                    "Compare flights by price, schedule, layover risk, and arrival time.",
                    "Compare stays by location, quality, cancellation rules, and total cost.",
                    "Stop before payment or booking confirmation until the traveler approves.",
                ],
            ),
        ),
        (
            "Budget needs estimates, actuals, and assumptions.",
            _take(
                budget_lines,
                [
                    "Track flights, accommodation, food, transport, activities, shopping, and contingency.",
                    "Keep estimated and actual costs side by side so the sheet can be updated during the trip.",
                    "State assumptions such as number of travelers, exchange rate, and one-way versus return travel.",
                ],
            ),
        ),
        (
            "Risks should change the plan, not sit in a footnote.",
            _take(
                decision_lines + nature_lines,
                [
                    "Weather, distance, safety, visa or entry rules, and health needs should affect the schedule.",
                    "Use fallback options for days where a hike, transfer, or booking may fail.",
                    "Make the next decision explicit before moving to payment or final booking.",
                ],
            ),
        ),
    ]


def _browser_deck(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    display = _display_title(title)
    search_lines = _matching_lines(sections, ("google search", "search", "result", "web page"))
    media_lines = _matching_lines(sections, ("google images", "youtube", "video", "channel"))
    community_lines = _matching_lines(sections, ("reddit", "thread", "comment", "community"))
    travel_lines = _matching_lines(sections, ("google flights", "flight", "booking.com", "airbnb", "hotel"))
    safety_lines = _matching_lines(sections, ("safety", "login", "payment", "booking", "passport", "card", "otp"))
    return [
        (
            display,
            [
                f"{display} should be handled as deterministic site skills, not improvised browsing.",
                _first(search_lines, "Start by routing the request to the correct site-specific browser skill."),
                _first(safety_lines, "Keep sensitive actions blocked before login, payment, booking submit, cards, OTP, or passport fields."),
            ],
        ),
        (
            "Search skills need clean queries and source inspection.",
            _take(
                search_lines,
                [
                    "Google Search should clean the spoken request before typing it into the page.",
                    "Open a useful result when asked and summarize the page from page text or vision fallback.",
                    "Report uncertainty when the page cannot be inspected safely.",
                ],
            ),
        ),
        (
            "Media skills should rank before opening.",
            _take(
                media_lines,
                [
                    "Google Images should show relevant visual options without adding command words into the query.",
                    "YouTube should compare title fit, channel trust, views, recency, and duration.",
                    "Subscribed or known high-trust channels should get a priority boost when they match.",
                ],
            ),
        ),
        (
            "Community and travel sites need structured evidence.",
            _take(
                community_lines + travel_lines,
                [
                    "Reddit summaries should separate common praise, complaints, and caveats.",
                    "Google Flights, Booking.com, and Airbnb should extract price, location, timing, rating, and important conditions.",
                    "Open a selected option for review, but stop before booking or payment.",
                ],
            ),
        ),
        (
            "Safety boundaries make automation trustworthy.",
            _take(
                safety_lines,
                [
                    "Never submit login, payment, booking, passport, card, OTP, or private financial fields.",
                    "If automation is blocked, say exactly where it stopped and leave the page open for manual help.",
                    "Keep Maya's answer natural while route logs carry the technical detail.",
                ],
            ),
        ),
    ]


def _technical_deck(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    display = _display_title(title)
    setup_lines = _matching_lines(sections, ("setup", "step", "configuration", "configure", "install"))
    safety_lines = _matching_lines(sections, ("risk", "safety", "security", "password", "firmware"))
    verify_lines = _matching_lines(sections, ("verify", "verification", "test", "troubleshoot"))
    return [
        (
            display,
            [
                f"{display} should give a safe sequence, not just a list of tips.",
                _first(setup_lines, "Start from prerequisites, then configure, verify, and only then save changes."),
                _first(safety_lines, "Protect credentials, firmware changes, and rollback before touching production settings."),
            ],
        ),
        (
            "Start with the prerequisites that prevent avoidable failure.",
            _take(
                setup_lines,
                [
                    "Confirm access method, credentials, interface names, IP plan, and the exact device model.",
                    "Separate first-time access from final configuration so mistakes are easier to isolate.",
                    "Document placeholders before typing commands into the terminal.",
                ],
            ),
        ),
        (
            "Configuration should be typed in a controlled sequence.",
            _take(
                setup_lines[1:],
                [
                    "Apply WAN, LAN, DHCP, WiFi, and admin-password changes in small verified blocks.",
                    "Do not save the running configuration until connectivity and management access are confirmed.",
                    "Keep a known-good fallback path before changing routing or wireless security.",
                ],
            ),
        ),
        (
            "Verification decides whether the setup is actually done.",
            _take(
                verify_lines,
                [
                    "Check interface state, IP addressing, DNS, internet reachability, and client WiFi join behavior.",
                    "Use troubleshooting commands before assuming the ISP, cable, or router is faulty.",
                    "Record the final validated state so future support starts from facts.",
                ],
            ),
        ),
        (
            "The main risks are credentials, firmware, and irreversible saves.",
            _take(
                safety_lines,
                [
                    "Use a private password manager for admin credentials and never paste secrets into shared notes.",
                    "Keep firmware work separate from initial setup unless the current version is unsafe.",
                    "Back up the current config before major routing or wireless changes.",
                ],
            ),
        ),
    ]


def _proposal_deck(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    display = _display_title(title)
    problem_lines = _matching_lines(sections, ("problem", "current", "context", "why"))
    solution_lines = _matching_lines(sections, ("proposal", "solution", "standard", "approach"))
    implementation_lines = _matching_lines(sections, ("implementation", "roadmap", "phase", "plan"))
    risk_lines = _matching_lines(sections, ("risk", "out of scope", "constraint", "dependency"))
    return [
        (
            display,
            [
                f"{display} needs a clear decision, a practical path, and visible tradeoffs.",
                _first(problem_lines, "The deck frames what is broken or underpowered today."),
                _first(solution_lines, "The recommendation is structured so it can be approved or revised."),
            ],
        ),
        (
            "The current gap is a quality problem, not only a tooling problem.",
            _take(
                problem_lines,
                [
                    "A process can call the right models and still produce weak artifacts if standards are not enforced.",
                    "The deck should distinguish route success from output quality.",
                    "The review loop must catch empty sections, generic copy, and incomplete frameworks before delivery.",
                ],
            ),
        ),
        (
            "The proposal is a repeatable quality pipeline.",
            _take(
                solution_lines,
                [
                    "Use artifact-specific standards, local validation, Claude review, and one bounded repair pass.",
                    "Treat skills as standards that runtime code must actively load and enforce.",
                    "Keep channel delivery separate from document quality so iMac and Telegram share the same baseline.",
                ],
            ),
        ),
        (
            "Implementation should move one artifact family at a time.",
            _take(
                implementation_lines,
                [
                    "Finish Word first, then Excel, then PowerPoint, with golden artifact tests for each.",
                    "Use short everyday prompts in testing so Maya learns the real usage pattern.",
                    "Do not reopen app-building until Office artifacts are consistently useful.",
                ],
            ),
        ),
        (
            "Risks need explicit gates before rollout.",
            _take(
                risk_lines,
                [
                    "Reject files that are empty, generic, visually broken, or missing the user's core requirement.",
                    "Keep repair bounded so failures are honest instead of hidden.",
                    "Store review output so `/review` can show why the artifact passed or failed.",
                ],
            ),
        ),
    ]


def _display_title(title: str) -> str:
    text = _plain(title)
    text = re.sub(r"\b(powerpoint|pptx|presentation|slide deck|slides|deck)\b", "", text, flags=re.I)
    text = re.sub(r"\b(make|create|draft|about|for|me|a|an|the)\b", "", text, flags=re.I)
    text = " ".join(text.split()).strip(" -:")
    return text.title() if text else title.title()


def _matching_lines(sections: list[tuple[str, list[str]]], keywords: tuple[str, ...]) -> list[str]:
    matched: list[str] = []
    for heading, lines in sections:
        haystack = f"{heading} {' '.join(lines)}".lower()
        if any(keyword in haystack for keyword in keywords):
            matched.extend(lines)
    return matched


def _take(lines: list[str], fallback: list[str], count: int = 3) -> list[str]:
    chosen = [_complete(_plain(line)) for line in lines if _plain(line)][:count]
    if len(chosen) < count:
        chosen.extend(fallback[: count - len(chosen)])
    return chosen[:count]


def _first(lines: list[str], fallback: str) -> str:
    return _complete(_plain(lines[0])) if lines else fallback
