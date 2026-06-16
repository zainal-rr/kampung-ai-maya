from __future__ import annotations

import asyncio
import re

from maya_documents.artifact_preflight import ArtifactPreflight
from maya_core.assistant_routes import RouteResult
from maya_core.markdown_drafter import MarkdownDraft
from maya_documents.pptx_quality_gate import PptxQualityResult


async def fake_normal_route(**kwargs) -> RouteResult:
    return RouteResult("This is a normal chat answer.", "Gemini Flash text", "normal Telegram text", False)


class FreshNews:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def chat(self, messages):
        text = messages[-1]["content"].lower()
        if _edit_intent(text):
            instruction = text.replace('"', "'")
            return (
                '{"action":"edit","kind":"xlsx","domain":"","topic":"",'
                f'"instruction":"{instruction}","question":"","save_copy":false,'
                '"confidence":"high","parameters":{}}'
            )
        if "document" in text and "word document" not in text and "word doc" not in text:
            return (
                '{"action":"clarify","kind":"","domain":"","topic":"","instruction":"",'
                '"question":"Which type should I create: Word doc, Excel sheet, or PowerPoint slides?",'
                '"save_copy":false,"confidence":"high","parameters":{}}'
            )
        if any(word in text for word in ("excel", "sheet", "spreadsheet", "workbook", "budget", "cost", "spending")):
            domain = ""
            topic = "Tokyo"
            if any(word in text for word in ("household", "pantry", "vendor", "comparison", "renovation", "subscription", "workshop")):
                domain = "business_comparison" if any(word in text for word in ("comparison", "vendor", "workshop")) else "household_budget"
                topic = text
            return (
                '{"action":"create","kind":"xlsx",'
                f'"domain":"{domain}","topic":"{topic}","instruction":"","question":"",'
                '"save_copy":false,"confidence":"high","parameters":{}}'
            )
        return '{"action":"none","kind":"","domain":"","topic":"","instruction":"","question":"","save_copy":false,"confidence":"low","parameters":{}}'


def _edit_intent(text: str) -> bool:
    return bool(re.search(r"\b(change|update|set|edit|modify|revise)\b|\bmake\s+it\s+for\b", text))


async def fake_preflight(db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
    return ArtifactPreflight(artifact_type, topic, "gemini", "runtime preflight", True)


async def fake_draft(db_path: str, topic: str, preflight_context: str = "") -> MarkdownDraft:
    lowered = topic.lower()
    if "router" in lowered or "technical troubleshooting" in lowered:
        return MarkdownDraft(_technical_guide_markdown(), grounded=False)
    if "proposal" in lowered:
        return MarkdownDraft(_proposal_markdown(), grounded=False)
    if "research" in lowered or "brief" in lowered or "agentic workflow" in lowered:
        return MarkdownDraft(_research_markdown(), grounded=False)
    if any(word in lowered for word in ("food trip", "travel", "itinerary", "seoul", "tokyo", "kyoto")):
        city = "Kyoto" if "kyoto" in lowered else "Tokyo" if "tokyo" in lowered else "Seoul"
        return MarkdownDraft(_travel_markdown(city, _day_count(lowered)), grounded=False)
    return MarkdownDraft(_generic_markdown(), grounded=False)


async def fake_review(db_path: str, topic: str, slides):
    return slides


async def fake_powerpoint_qa(db_path, path, title, slides, run_id, last_doc_key, auto_improve=True, **_kwargs):
    from maya_documents.office_modern_files import create_pptx
    from maya_core.storage import upsert_preference

    await asyncio.to_thread(create_pptx, path, title, slides)
    await upsert_preference(db_path, last_doc_key, str(path), source="document")
    return PptxQualityResult(True, [], [], len(slides), "Visual QA passed. Design polish: good.")


def _technical_guide_markdown() -> str:
    return """# Router Setup Guide

## Purpose

Set up a home router safely from first login to final verification. The guide prioritizes admin access, internet connectivity, WiFi security, rollback awareness, and checks that prevent locking yourself out.

## Prerequisites

Use the router admin URL, admin username, current admin password, ISP connection details, Ethernet cable, and a laptop. Decide the SSID, WiFi password, guest network need, DHCP range, and whether firmware should be checked before changes.

## Configuration Steps

1) Connect by Ethernet, open the admin interface, and log in with the current admin credentials.
2) Change the admin password before editing WAN, LAN, or WiFi settings.
3) Configure WAN or ISP details, set the LAN DHCP range, choose DNS, set the SSID, set the WiFi password, and use WPA2 or WPA3 security mode.
4) Check firmware status, apply updates only when power is stable, then save settings after confirming the admin page remains reachable.

## Verification

Confirm a WAN IP appears, browse to a known website, run a DNS lookup or ping, join WiFi with the new password, and log back into the admin interface with the new admin password.

## Troubleshooting

If internet fails, reconnect by Ethernet and check WAN credentials, DHCP, DNS, and cable placement. If WiFi fails, verify security mode compatibility and use the admin page before resetting.

## Safety Notes

Do not share admin passwords, WiFi passwords, ISP credentials, or exported config publicly. Do not interrupt firmware updates, and keep a private note of the final non-sensitive settings.

## Next Steps

Create a guest network if needed, review connected devices, record the safe final network name, and schedule a firmware check after the setup has been stable for a few days.
"""


def _proposal_markdown() -> str:
    return """# Kampung AI Document Quality Proposal

## Executive Summary

Kampung AI should treat Office files as reviewed artifacts, not chat output. The proposal standardizes semantic routing, local file builders, visual QA, and failed-QA delivery gates.

## Objective

Improve first-delivery usefulness for Word, Excel, and PowerPoint across Telegram and iMac voice. Reduce rejected drafts, generic files, wrong attachments, and edits that silently rewrite the wrong artifact.

## Scope

The scope covers artifact intent classification, document builders, local validation, Claude review, repair loops, latest-document continuity, and channel delivery behavior for Word, Excel, and PowerPoint.

## Recommended Approach

Use semantic artifact intent first, then choose the correct artifact builder. Validate locally, review content, repair once or repeatedly where safe, and never attach failed QA as a finished file.

## Deliverables

Deliver semantic routing tests, Word visual QA, Excel domain checks, PowerPoint render checks, delivery-gate tests, and a clear route/review report for each artifact.

## Timeline

Complete Word and Excel stability first, then PowerPoint visual polish, then iMac voice regression on June 8, followed by a one-week reliability log.

## Risks

Risks include overfitting to phrases, generic file fallback, model drift, too much regex, and stale test artifacts being mistaken for live evidence.

## Next Steps

Run fresh text and voice transcript tests, fix semantic failures, document the architecture, and keep rejected files local unless explicitly requested.
"""


def _research_markdown() -> str:
    return """# Agentic Workflow Research Brief

## Research Question

How should Maya structure agentic workflows so planning, approval, execution, verification, repair, and final reporting remain traceable and safe?

## Scope

This brief covers local personal-agent workflows, checkpointed harness runs, approval gates, event logs, tool execution, and repair reports. It excludes cloud deployment and commercial onboarding.

## Key Findings

Agentic behavior improves when each step has a state, owner, tool evidence, rollback boundary, and pass/fail result. Long-running work should park voice sessions and continue through workers.

## Evidence

Kampung AI already has route records, artifact stores, harness runs, local CI, and approval gates. The missing layer is stricter checkpoint execution with visible proof for each step.

## Risks Or Unknowns

Weaknesses include vague approvals, unverified tool results, stale memory context, external site changes, and workflows that prepare proposals but do not execute after approval.

## Sources

Use public architecture references, local trace logs, route audits, and Maya Desk proof reports. Do not rely on leaked source code or undocumented platform behavior.

## Next Steps

Implement checkpointed /complex execution, add rollback records before writes, and score completed workflows separately from proposal-only workflows.
"""


def _day_count(text: str) -> int:
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    match = re.search(r"\b([1-5])\s*(?:day|days)\b", text)
    if match:
        return int(match.group(1))
    for word, value in words.items():
        if re.search(rf"\b{word}\s+(?:day|days)\b", text):
            return value
    return 2


def _day_plan_markdown(city: str, days: int) -> str:
    neighborhoods = (
        ("Tsukiji and Ginza", "seafood bowls, tamagoyaki, ramen, and coffee"),
        ("Shibuya and Harajuku", "standing sushi, yuzu ramen, pancakes, and dessert cafes"),
        ("Asakusa and Ueno", "tempura, melon pan, market snacks, and casual izakaya dinner"),
        ("Shinjuku and Kagurazaka", "yakitori, soba, kissaten coffee, and one dinner splurge"),
        ("Kichijoji and Nakano", "harmonica alley snacks, ramen, bakeries, and backup casual dining"),
    )
    if city.lower() == "seoul":
        neighborhoods = (
            ("Myeongdong and Gwangjang", "kal-guksu, dumplings, bindaetteok, hotteok, and market snacks"),
            ("Seongsu and Gangnam", "cafes, pastries, Korean BBQ, and a reservation-friendly dinner"),
            ("Bukchon and Insadong", "tea houses, mandu, traditional sweets, and casual dinner"),
            ("Hongdae and Yeonnam", "street food, fried chicken, cafe hopping, and late-night snacks"),
            ("Itaewon and Hannam", "bakery stops, international Korean fusion, and one dinner splurge"),
        )
    if city.lower() == "kyoto":
        neighborhoods = (
            ("Higashiyama and Gion", "matcha sweets, yudofu, wagashi, and market-style snacks"),
            ("Arashiyama and Nishiki", "soba, tofu dishes, street snacks, and a tea house stop"),
            ("Fushimi and Uji", "inari sushi, green tea desserts, and casual izakaya dinner"),
            ("Kawaramachi and Pontocho", "coffee, ramen, kaiseki-lite dinner, and riverside backups"),
            ("Kurama and Kibune", "mountain soba, tea, and a slower dinner backup"),
        )
    lines = []
    for index in range(1, max(1, min(days, 5)) + 1):
        area, focus = neighborhoods[index - 1]
        lines.append(
            f"## Day {index} Plan\n\n"
            f"Use {area} as the main movement block. Start with a focused breakfast or market stop, "
            f"build lunch around {focus}, keep one cafe or snack stop flexible, and end with a dinner anchor nearby. "
            f"Record estimated and actual spend after each meal so the itinerary stays useful for the group."
        )
    return "\n\n".join(lines)


def _travel_markdown(city: str = "Seoul", days: int = 2) -> str:
    if city.lower() == "kyoto":
        return f"""# Kyoto Food Trip

## Trip Overview

A compact {days}-day Kyoto food plan for one or more travelers, built around temples, market food, tea houses, tofu dishes, and realistic transit between eastern Kyoto and Arashiyama.

{_day_plan_markdown("Kyoto", days)}

## Place Highlights

Prioritize Higashiyama, Gion, Nishiki Market, Arashiyama, Fushimi Inari, Pontocho, and Kawaramachi as the main movement clusters. These areas keep cultural stops and food stops close enough for a realistic two-day plan.

## Food And Restaurant Highlights

Prioritize yudofu, soba, matcha sweets, wagashi, market snacks, tea houses, ramen, and one calm dinner near Pontocho or Gion. Keep backups near the same station or walking route.

## Budget Notes

Use JPY 7,000 to 11,000 per person per day as the normal food range, with an extra buffer for one nicer dinner or tea experience. Track snacks, cafes, market meals, and dinner anchors separately.

## Booking And Transit Notes

Use IC card transit, group Higashiyama and Gion together, and avoid crossing Kyoto repeatedly in one day. Stop before payment, login submission, passport entry, OTP, or final booking unless explicitly confirmed.

## Recommendations

Start early for temple-heavy mornings, keep lunch near the walking route, and leave one open slot for a tea house or queue change.
"""
    if city.lower() == "tokyo":
        return f"""# Tokyo Food Trip

## Trip Overview

A compact {days}-day Tokyo food plan for one or more travelers, built around markets, ramen, cafes, and one dinner splurge. It assumes train movement and flexible backup restaurants.

{_day_plan_markdown("Tokyo", days)}

## Place Highlights

Prioritize Tsukiji Outer Market, Ginza, Tokyo Station, Shibuya, Harajuku, Asakusa, Ueno, Shinjuku, and Kagurazaka as the main movement clusters. These areas keep food stops close to train access and give backup restaurants if queues are too long.

## Food And Restaurant Highlights

Prioritize Tsukiji seafood bowls, Yamacho tamagoyaki, Rokurinsha ramen, Uobei sushi, Afuri yuzu ramen, kissaten coffee, tempura, and yakiniku. Each stop has a backup in the same train area so the plan survives queues.

## Budget Notes

Use JPY 8,000 to 12,000 per person per day as the normal food range, with an extra JPY 5,000 to 8,000 buffer for one sushi, tempura, or yakiniku splurge. Track snacks, cafes, market meals, and dinner anchors separately.

## Booking And Transit Notes

Use Suica or Pasmo for train movement, Google Maps for route timing, and cluster Day 1 around Tsukiji, Ginza, and Tokyo Station before moving to Shibuya or Harajuku on Day 2. Stop before payment, login submission, passport entry, OTP, or final booking unless explicitly confirmed.

## Recommendations

Go early for market meals, avoid overloading each day, and choose neighborhoods so food stops and transit do not fight each other.
"""
    return f"""# Seoul Food Trip

## Trip Overview

A compact {days}-day Seoul food plan for one or more travelers, built around markets, cafes, and one dinner splurge. It assumes subway movement and flexible backup restaurants.

{_day_plan_markdown("Seoul", days)}

## Place Highlights

Prioritize Myeongdong, Gwangjang Market, Seongsu, Gangnam, Bukchon, Insadong, Hongdae, Yeonnam, Itaewon, and Hannam as the main movement clusters. These areas keep food stops close to subway access and give backup restaurants if queues are too long.

## Food And Restaurant Highlights

Prioritize kal-guksu, bindaetteok, hotteok, cafe pastries, samgyetang, and Korean BBQ. Each stop should have a backup option and a realistic queue expectation.

## Budget Notes

Track estimated and actual spend after each meal. Keep a daily food range, add a splurge buffer, and separate snacks, cafes, market meals, and dinner anchors.

## Booking And Transit Notes

Use T-money for subway movement, Naver Maps for route timing, and CatchTable only for restaurants that clearly support reservations. Stop before payment, login submission, passport entry, OTP, or final booking unless explicitly confirmed.

## Recommendations

Go off-peak for market meals, avoid overloading each day, and choose neighborhoods so food stops and transit do not fight each other.
"""

def _generic_markdown() -> str:
    return (
        "# Maya Artifact\n\n"
        "## Overview\n\n"
        "This artifact gives Zainal a practical, editable starting point with clear assumptions and concrete next steps.\n\n"
        "## Key Points\n\n"
        "Include useful rows, sections, or slides for the requested scenario. Keep private information out of the artifact and avoid placeholder text.\n\n"
        "## Recommended Approach\n\n"
        "Use the artifact as a working draft, verify missing real-world data, and update the values after actual use.\n\n"
        "## Risks\n\n"
        "The main risks are missing source data, stale assumptions, and treating an editable draft as a final external submission.\n\n"
        "## Next Steps\n\n"
        "Review the assumptions, fill missing real prices where needed, and update the artifact after actual use.\n"
    )
