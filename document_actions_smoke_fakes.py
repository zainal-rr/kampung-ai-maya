from __future__ import annotations

from artifact_quality import ArtifactQualityResult
from markdown_drafter import MarkdownDraft


async def _fake_draft(db_path: str, topic: str, preflight_context: str = "") -> MarkdownDraft:
    lowered = topic.lower()
    if "updated document topic: 4-day seoul food trip" in lowered or "original user request: 4-day seoul food trip" in lowered:
        return MarkdownDraft(
            "# 4-Day Seoul Food Trip\n\n"
            "## Trip Overview\n\n"
            "1) Four days focused on Seoul food neighborhoods, markets, cafes, BBQ, and flexible backups.\n"
            "2) Keep each day clustered by area so the expanded itinerary stays realistic and easy to follow.\n\n"
            "## Day 1 Plan\n\n"
            "1) Start with Myeongdong Kyoja and Gwangjang Market classics.\n"
            "2) Use this day for the most iconic stops and avoid adding distant cafe detours.\n\n"
            "## Day 2 Plan\n\n"
            "1) Explore Yeonnam cafes, Hongdae snacks, and Mapo Korean BBQ.\n"
            "2) Keep lunch lighter because the BBQ dinner is the highest-cost and heaviest meal.\n\n"
            "## Day 3 Plan\n\n"
            "1) Use Ikseon-dong, Insadong tea, and Jongno dinner stops.\n"
            "2) Add one traditional dessert or tea house stop so the day is not only heavy meals.\n\n"
            "## Day 4 Plan\n\n"
            "1) Keep a lighter final day for convenience store finds, repeat favorites, and airport timing.\n"
            "2) Use the final day to revisit the best neighborhood instead of forcing a new cross-city route.\n\n"
            "## Food And Restaurant Highlights\n\n"
            "1) Prioritize kalguksu, bindaetteok, hotteok, Korean BBQ, tea, cafes, and market snacks.\n"
            "2) Keep each highlight tied to a neighborhood so restaurant backups remain practical.\n\n"
            "## Budget Notes\n\n"
            "1) Track market snacks, sit-down meals, cafes, BBQ, and transit separately across four days.\n"
            "2) Set aside extra cash for markets and a higher card budget for the BBQ dinner.\n\n"
            "## Booking And Transit Notes\n\n"
            "1) Use Naver Map, keep a T-money card loaded, and cluster each day by neighborhood.\n\n"
            "## Recommendations\n\n"
            "1) Keep backup restaurants nearby and avoid crossing the city for a single snack.\n"
            "2) Use the fourth day as a flexible recovery day so the itinerary stays useful if queues or weather change.\n"
        )
    if "seoul" in lowered and "food" in lowered:
        return MarkdownDraft(
            "# Seoul Food Trip\n\n"
            "## Trip Overview\n\n"
            "1) Two days focused on classic Seoul meals, markets, cafes, and one Korean BBQ dinner.\n"
            "2) Keep each day clustered by area so transit stays manageable and meals do not feel rushed.\n\n"
            "## Day 1 Plan: Traditions and Street Staples\n\n"
            "1) Start with handmade kalguksu, move to Gwangjang Market, and keep dinner flexible near Myeongdong.\n"
            "2) Use the first day for iconic foods with short walks between stops.\n\n"
            "## Day 2 Plan: Cafes and BBQ\n\n"
            "1) Keep breakfast simple, visit a cafe district, and reserve Korean BBQ for the evening.\n"
            "2) Leave buffer time between lunch and dinner so the plan stays realistic.\n\n"
            "## Food And Restaurant Highlights\n\n"
            "1) Prioritize kalguksu, bindaetteok, hotteok, Korean BBQ, and a modern Seoul cafe.\n"
            "2) Save backup restaurants in the same neighborhoods in case queues are long.\n\n"
            "## Budget Notes\n\n"
            "1) Track meals, snacks, cafe stops, transit, and one higher-cost BBQ dinner separately.\n"
            "2) Keep cash for markets and use card for restaurants where accepted.\n\n"
            "## Booking And Transit Notes\n\n"
            "1) Cluster meals by subway area and reserve popular dinners when possible.\n"
            "2) Avoid crossing the city just for one snack unless it is the main stop.\n\n"
            "## Recommendations\n\n"
            "1) Keep the plan food-first but leave space for queues, digestion, and weather.\n"
            "2) Use nearby backup restaurants instead of turning one missed meal into a cross-city detour.\n"
        )
    if "putty" in lowered and "router" in lowered:
        return MarkdownDraft(
            "# Router Setup Guide With PuTTY Config\n\n"
            "## Purpose\n\n"
            "1) Configure a basic lab router through PuTTY using a simple Cisco-style example that must be adapted to the actual router brand.\n"
            "2) Show exactly what to type, what each placeholder means, and how to verify before saving.\n\n"
            "## Prerequisites\n\n"
            "1) PuTTY, serial or SSH access, correct COM port or router IP, admin credentials, interface names, SSID, WiFi password, and LAN subnet plan.\n"
            "2) Replace placeholders such as GigabitEthernet0/0, GigabitEthernet0/1, YOUR_SSID, and YOUR_WIFI_PASSWORD before using the sample.\n\n"
            "## Configuration Steps\n\n"
            "1) In PuTTY, connect by Serial with the detected COM port and 9600 baud, or by SSH to the router management IP if SSH is already enabled.\n"
            "2) Example only, adapt to your router: enable; configure terminal; hostname HomeRouter; enable secret CHANGE_ADMIN_PASSWORD; interface GigabitEthernet0/0; ip address dhcp; no shutdown; interface GigabitEthernet0/1; ip address 192.168.1.1 255.255.255.0; no shutdown; ip dhcp pool LAN; network 192.168.1.0 255.255.255.0; default-router 192.168.1.1; dns-server 1.1.1.1 8.8.8.8; wlan ssid YOUR_SSID; wpa2 psk YOUR_WIFI_PASSWORD; end; write memory.\n"
            "3) If the router uses Juniper, MikroTik, TP-Link, or another OS, adapt the syntax instead of pasting Cisco-style commands directly.\n\n"
            "## Verification\n\n"
            "1) Run show ip interface brief, show running-config, ping 8.8.8.8, and ping google.com to verify interfaces, saved config, internet reachability, and DNS.\n"
            "2) Join the SSID from a phone or laptop and confirm it asks for the WPA2 or WPA3 password.\n\n"
            "## Troubleshooting\n\n"
            "1) If PuTTY displays unreadable characters, switch baud rate from 9600 to 115200 and reopen the serial session.\n"
            "2) If WAN does not receive an address, check modem bridge mode, ISP VLAN or PPPoE requirements, and interface names.\n\n"
            "## Safety Notes\n\n"
            "1) Do not paste commands until placeholders are replaced and do not run write memory until the current session is verified.\n"
            "2) Keep firmware updates separate from first-time config and maintain a backup before changing routing or wireless security.\n\n"
            "## Next Steps\n\n"
            "1) Create a guest SSID, save a sanitized copy of the final config, and record the admin password only in a private password manager.\n"
            "2) Schedule a firmware check and review connected clients after all household devices are migrated.\n"
        )
    if "router" in lowered:
        return MarkdownDraft("# Router Setup\n\n## Real Draft\n\n1) Connect the WAN or internet port.\n2) Keep dash - style clean.\n")
    if "desk setup" in lowered:
        return MarkdownDraft(
            "# Desk Setup Guide\n\n"
            "## Purpose\n\n"
            "1) Create a comfortable desk setup for daily work, calls, document review, and light creative tasks.\n"
            "2) Keep the setup easy to maintain so the desk does not become cluttered after a few days.\n\n"
            "## Prerequisites\n\n"
            "1) Confirm desk size, chair height, monitor position, power outlets, cable length, lighting direction, and where frequently used devices will sit.\n"
            "2) Prepare cable ties, a power strip, monitor stand if needed, cleaning cloth, notebook space, and a small tray for loose items.\n\n"
            "## Configuration Steps\n\n"
            "1) Place the monitor at eye level and about an arm length away, then center the keyboard and mouse with your shoulders.\n"
            "2) Put the laptop or secondary screen to the side without blocking the main writing area.\n"
            "3) Route power and charging cables behind the desk, leaving only the connectors you use daily accessible.\n"
            "4) Position lighting so it does not reflect directly on the screen or shine into the camera during calls.\n"
            "5) Keep headphones, notebook, water, and one writing tool within easy reach.\n\n"
            "## Verification\n\n"
            "1) Sit for ten minutes and check wrist angle, neck angle, cable reach, screen glare, and camera framing.\n"
            "2) Start a test call and confirm microphone, headphones, lighting, and screen sharing all behave normally.\n\n"
            "## Troubleshooting\n\n"
            "1) If the desk feels cramped, remove duplicate chargers, move rarely used items to a drawer, and keep only one active notebook.\n"
            "2) If the screen causes strain, reduce brightness, adjust height, and remove reflected light from behind you.\n\n"
            "## Safety Notes\n\n"
            "1) Do not overload a single power strip, pinch cables under heavy furniture, or run charging cables where feet can pull them.\n"
            "2) Keep drinks away from power adapters and give devices enough airflow.\n\n"
            "## Next Steps\n\n"
            "1) Use the setup for one full work session, then adjust only the parts that bothered you.\n"
            "2) Review the desk weekly and remove items that are not used in normal work.\n"
        )
    if "q23" in lowered and "work plan" in lowered:
        return MarkdownDraft(
            "# Q23 Two-Day Work Plan\n\n"
            "## Goal\n\n"
            "1) Complete a focused two-day work plan for Q23 that turns the rough request into a clear operating sequence.\n"
            "2) Keep the plan practical enough for a person to follow without needing another planning pass.\n\n"
            "## Context\n\n"
            "1) The work window is short, so the plan prioritizes setup, execution, review, and handover rather than broad strategy.\n"
            "2) Q23 is treated as the working label until the user provides a fuller project name or owner.\n\n"
            "## Workstreams\n\n"
            "1) Day 1 covers scope confirmation, source collection, task ordering, and the first execution block.\n"
            "2) Day 2 covers remaining execution, quality review, stakeholder notes, and a concise next-action handover.\n\n"
            "## Timeline\n\n"
            "1) Morning Day 1: confirm goal, inputs, constraints, and success criteria.\n"
            "2) Afternoon Day 1: execute the highest-impact tasks and record blockers.\n"
            "3) Morning Day 2: finish remaining work, review quality, and tighten the output.\n"
            "4) Afternoon Day 2: send summary, owners, risks, and next steps.\n\n"
            "## Risks\n\n"
            "1) Missing inputs, unclear owner, or too many parallel priorities can make the two-day window unrealistic.\n"
            "2) Keep a visible blocker list so the plan does not quietly drift.\n\n"
            "## Next Steps\n\n"
            "1) Confirm the exact Q23 owner, deadline, and output format.\n"
            "2) Replace assumptions with real names, dates, and deliverables once available.\n"
        )
    if "maya" in lowered and "testing" in lowered and "checklist" in lowered:
        return MarkdownDraft(
            "# Pre-Travel Maya Testing Checklist\n\n"
            "## Checklist Overview\n\n"
            "1) Use this checklist to confirm Maya is ready before travel, with focus on iMac voice, browser skills, document creation, and recovery steps.\n"
            "2) The goal is to find obvious failures while there is still time to fix them locally.\n\n"
            "## Must Do\n\n"
            "1) Test the iMac voice hotkey, confirm the mic opens, ask a short question, and close the session cleanly.\n"
            "2) Test browser search, Google Images, Google Flights, YouTube, and Reddit using simple voice commands.\n"
            "3) Create one Markdown, Word, Excel, and PowerPoint file, then confirm each opens in the right app.\n\n"
            "## Should Do\n\n"
            "1) Review voice session logs after one test conversation and confirm both user and Maya transcript lines are saved.\n"
            "2) Ask Maya to summarize an opened file by content, not by filename or window title.\n\n"
            "## Optional\n\n"
            "1) Test longer background work while keeping the voice session open, then ask Maya for status.\n"
            "2) Try one travel planning flow that searches flight and accommodation options but stops before booking or payment.\n\n"
            "## Risks Or Watchouts\n\n"
            "1) Audio output can still be affected by device changes, so check that Maya uses the expected headphone route.\n"
            "2) Browser automation may stop on login, payment, booking, OTP, or card fields and should say exactly where it stopped.\n\n"
            "## Done Criteria\n\n"
            "1) Maya can start, answer, interrupt, create a file, open it, summarize it, and close without crashing.\n"
            "2) Any failure has a log entry and a clear next troubleshooting step.\n"
        )
    if "gemini" in lowered or "latest" in lowered:
        return MarkdownDraft("# New Gemini 3.5\n\n## What To Verify\n\n1) Check official sources.\n\n## Sources\n\n1) Google: https://ai.google.dev\n", grounded=True)
    if "html" in lowered or "wonderlog" in lowered:
        return MarkdownDraft("<!DOCTYPE html>\n<html lang=\"en\"><head><title>Wonderlog Style App</title></head><body><main>Trip planner</main></body></html>\n")
    return MarkdownDraft(f"# {topic.title()}\n\n## Real Draft\n\n1) Model generated content.\n")


async def _fake_bad_word_edit(db_path: str, topic: str, preflight_context: str = "") -> MarkdownDraft:
    return MarkdownDraft("# Bad Edit\n\n## Overview\n\n1) Model generated content.\n")


async def _fake_html_draft(db_path: str, topic: str) -> MarkdownDraft:
    return MarkdownDraft(
        "<!DOCTYPE html>\n"
        "<html lang=\"en\"><head><title>Travel Planner</title><style>body{font-family:system-ui}</style></head>"
        "<body><main><h1>Travel Planner</h1><input id=\"item\"><button id=\"add\">Add</button><ul id=\"list\"></ul></main>"
        "<script>document.getElementById('add').addEventListener('click',()=>{const li=document.createElement('li');li.textContent=document.getElementById('item').value;document.getElementById('list').appendChild(li);localStorage.setItem('travelPlanner',document.getElementById('list').textContent);});</script>"
        "</body></html>\n"
    )


async def _fake_html_fallback(db_path: str, topic: str) -> MarkdownDraft:
    return MarkdownDraft(
        "<!DOCTYPE html>\n"
        "<html lang=\"en\"><head><title>Fallback Planner</title><style>body{font-family:system-ui}</style></head>"
        "<body><main><input id=\"city\"><button id=\"save\">Save</button></main>"
        "<script>document.getElementById('save').addEventListener('click',()=>localStorage.setItem('city',document.getElementById('city').value));</script>"
        "</body></html>\n"
    )


async def _fake_html_review(db_path: str, topic: str, html: str):
    return html.replace("</main>", "<p>Reviewed by Claude</p></main>"), "reviewed"


async def _fake_artifact_quality_review(db_path: str, artifact_type: str, topic: str, content: str):
    return ArtifactQualityResult(
        artifact_type=artifact_type,
        passed=True,
        summary="fake artifact review passed",
        review_model="claude-opus-4-8",
        validation_steps=["fake artifact review"],
    )


async def same_review(db_path: str, topic: str, html: str):
    return html, "reviewed"


async def _fake_review(db_path: str, topic: str, slides):
    return [("Reviewed narrative", ["WAN or internet port", "Review - dash"])]
