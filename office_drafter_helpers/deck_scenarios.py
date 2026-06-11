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


def _teaching_deck(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    display = _display_title(title)
    objective_lines = _matching_lines(sections, ("objective", "goal", "outcome", "learn"))
    concept_lines = _matching_lines(sections, ("concept", "overview", "context", "what", "material"))
    practice_lines = _matching_lines(sections, ("schedule", "activity", "practice", "exercise", "session", "step"))
    assessment_lines = _matching_lines(sections, ("assessment", "judging", "evaluation", "feedback", "quiz"))
    return [
        (
            display,
            [
                f"{display} works best as a guided session, not a lecture.",
                _first(objective_lines, "Participants should leave able to do something they could not do before."),
                "The session moves from one core concept to hands-on practice to a visible result.",
            ],
        ),
        (
            "Start with what participants will be able to do.",
            _take(objective_lines, [
                "State two or three observable outcomes in plain language.",
                "Tie every activity back to one of those outcomes.",
                "Cut anything that does not serve an outcome.",
            ]),
        ),
        (
            "Teach one core concept before any hands-on work.",
            _take(concept_lines, [
                "Explain the single idea the whole session depends on.",
                "Use one concrete example participants will recognize.",
                "Keep theory under a quarter of the session time.",
            ]),
        ),
        (
            "Practice time is where the learning happens.",
            _take(practice_lines, [
                "Give teams a task with a visible finish line.",
                "Walk the room; help the stuck teams first.",
                "Keep a fallback task ready for fast finishers.",
            ]),
        ),
        (
            "Close with proof of learning and a next step.",
            _take(assessment_lines, [
                "Let each team show what they built or solved.",
                "Reward learning and effort, not only the winning result.",
                "Send participants away with one concrete thing to practice next.",
            ]),
        ),
    ]


def _review_deck(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    display = _display_title(title)
    delivered_lines = _matching_lines(sections, ("delivered", "done", "completed", "shipped", "summary", "overview"))
    metric_lines = _matching_lines(sections, ("metric", "number", "result", "kpi", "performance", "data"))
    lesson_lines = _matching_lines(sections, ("worked", "didn't", "did not", "issue", "lesson", "risk", "blocker"))
    decision_lines = _matching_lines(sections, ("decision", "next", "action", "follow", "recommend"))
    return [
        (
            display,
            [
                f"{display} should end in decisions, not nostalgia.",
                _first(delivered_lines, "Open with what was actually shipped against what was promised."),
                "The deck separates results, lessons, and the decisions they force.",
            ],
        ),
        (
            "What was delivered against the plan.",
            _take(delivered_lines, [
                "List the committed items and their final status.",
                "Flag anything delivered late or descoped, without burying it.",
                "Credit the work that prevented problems, not only visible features.",
            ]),
        ),
        (
            "The numbers tell the real story.",
            _take(metric_lines, [
                "Show the two or three metrics that changed and why.",
                "Compare against the previous period, not an ideal.",
                "Mark which numbers are measured and which are estimated.",
            ]),
        ),
        (
            "What worked, what did not, and why.",
            _take(lesson_lines, [
                "Name the practice worth repeating next period.",
                "Name the failure mode honestly and its trigger.",
                "Keep blame out; keep the mechanism in.",
            ]),
        ),
        (
            "Decisions and follow-ups leave the room with owners.",
            _take(decision_lines, [
                "Each decision gets an owner and a date.",
                "Park what cannot be decided today with a revisit trigger.",
                "Publish the follow-up list where the team will actually see it.",
            ]),
        ),
    ]


def _pitch_deck(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    display = _display_title(title)
    problem_lines = _matching_lines(sections, ("problem", "pain", "today", "current", "why now"))
    customer_lines = _matching_lines(sections, ("customer", "user", "buyer", "operator", "inspection", "facility", "asset", "roof", "site"))
    solution_lines = _matching_lines(sections, ("solution", "product", "approach", "how it works"))
    operating_lines = _matching_lines(sections, ("operations", "service", "workflow", "delivery", "compliance", "safety", "risk", "data"))
    market_lines = _matching_lines(sections, ("market", "competition", "customer", "model", "pricing", "revenue", "margin"))
    proof_lines = _matching_lines(sections, ("traction", "proof", "result", "milestone", "pilot"))
    ask_lines = _matching_lines(sections, ("ask", "funding", "raise", "investment", "use of funds", "next"))
    return [
        (
            display,
            [
                f"{display} should feel like a fundable operating plan, not only a product idea.",
                _first(problem_lines, "Lead with the inspection pain and who pays for reducing it."),
                _first(customer_lines + solution_lines, "Show the first customer use case before expanding the vision."),
            ],
        ),
        (
            "Manual inspection creates avoidable cost and risk.",
            _take(problem_lines, [
                "Frame the pain in downtime, safety exposure, slow reporting, or missed defects.",
                "Explain why now: sensors, cheaper drones, and faster analysis make the job practical.",
                "Name the first buyer clearly: asset owner, insurer, contractor, or facility operator.",
            ]),
        ),
        (
            "The first wedge is one inspection workflow.",
            _take(customer_lines + solution_lines, [
                "Start with one repeatable job such as roofs, solar assets, towers, farms, or industrial sites.",
                "Show what the customer books, what Maya's operator captures, and what report comes back.",
                "Keep the promise grounded: better evidence, faster turnaround, and safer inspection.",
            ]),
        ),
        (
            "Delivery discipline protects the margin.",
            _take(operating_lines + market_lines, [
                "Define packages by inspection type, site size, turnaround, and report depth.",
                "Treat pilots, equipment, insurance, travel, and data review as unit-economics drivers.",
                "Position against the real alternative: manual inspection, delayed maintenance, or no inspection.",
            ]),
        ),
        (
            "The next ask should buy proof, not vanity scale.",
            _take([*proof_lines, *ask_lines], [
                "Ask for paid pilots, anchor customers, or a small fleet only after the wedge is clear.",
                "State what support buys: customer discovery, pilot delivery, QA process, and repeatable reports.",
                "List the first proof milestones before raising for broad expansion.",
            ]),
        ),
    ]


def _issue_deck(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    """Awareness/policy arc for topic-concern decks: problem -> affected ->
    drivers -> what works -> direction. No sales pitch, no decision template."""
    display = _display_title(title)
    problem_lines = _matching_lines(sections, ("problem", "concern", "issue", "challenge", "pressure", "trend"))
    affected_lines = _matching_lines(sections, ("affected", "impact", "community", "farmer", "smallholder", "people", "who", "cost", "paddy", "palm", "vegetable"))
    driver_lines = _matching_lines(sections, ("cause", "driver", "because", "reason", "factor", "climate", "supply", "water", "labour", "labor", "fertilizer", "input"))
    response_lines = _matching_lines(sections, ("solution", "respond", "mitigation", "policy", "program", "adopt", "works", "extension", "irrigation", "mechanization"))
    direction_lines = _matching_lines(sections, ("next", "future", "recommend", "support", "outlook"))
    malaysia_specific = "malaysia" in title.lower()
    return [
        (
            display,
            [
                f"{display} should explain the pressure in practical, local terms.",
                _first(problem_lines, "Open with the clearest evidence that the pressure is already visible."),
                "The deck moves from farm-level impact to drivers, responses, and a practical next direction.",
            ],
        ),
        (
            "The pressure is already visible at farm level.",
            _take(problem_lines, [
                "Show the trend through yield risk, input cost pressure, weather volatility, or labor gaps.",
                "Anchor the concern in a recognizable crop or region rather than abstract agriculture.",
                "Say plainly what happens if producers delay adaptation.",
            ]),
        ),
        (
            "Small producers carry the shock first.",
            _take(affected_lines, [
                "Name the farmers, workers, and local buyers who feel the impact earliest.",
                "Translate the impact into cash flow, harvest reliability, and household resilience.",
                "If Malaysia is the context, keep paddy, palm oil, vegetables, and smallholders in view." if malaysia_specific else "Keep the affected producer groups visible, not hidden behind national averages.",
            ]),
        ),
        (
            "Water, inputs, and labor drive the risk.",
            _take(driver_lines, [
                "Separate climate and water stress from input costs, labor availability, and market volatility.",
                "Mark which drivers local programs can influence and which need national policy support.",
                "Avoid blaming one cause for a system problem.",
            ]),
        ),
        (
            "The response has to be adoptable, not theoretical.",
            _take([*response_lines, *direction_lines], [
                "Prioritize water management, practical mechanization, extension support, and market certainty.",
                "State what would make adoption easier for smallholders: financing, training, maintenance, or buyers.",
                "End with the most important resilience move to make this year.",
            ]),
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
