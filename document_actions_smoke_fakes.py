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
