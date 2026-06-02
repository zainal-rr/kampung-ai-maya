from __future__ import annotations

import tempfile
from pathlib import Path

from artifact_quality import extract_docx_text, validate_docx_path
from office_modern_files import create_docx


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-word-golden-") as tmp:
        root = Path(tmp)
        for index, case in enumerate(_cases(), start=1):
            path = create_docx(root / f"golden-{index}.docx", case["title"], case["sections"])
            qa = validate_docx_path(path, case["topic"])
            _require(qa.passed, f"{case['topic']} should pass golden Word QA: {qa.issues}")
            text = extract_docx_text(path).lower()
            for marker in case["must_contain"]:
                _require(marker.lower() in text, f"golden doc missing marker {marker!r} for {case['topic']}")
            for marker in ("role and assumptions", "working context", "model generated content", "add more detail", "lorem ipsum"):
                _require(marker not in text, f"golden doc contains banned marker {marker!r}")

        weak = create_docx(
            root / "weak.docx",
            "Weak Word Draft",
            [
                ("Overview", ["This section gives concrete working detail for the user's exact request, not generic filler."]),
                ("Key Points", ["Model generated content."]),
                ("Next Steps", ["Add more detail later."]),
            ],
        )
        weak_qa = validate_docx_path(weak, "make me a project plan doc")
        _require(not weak_qa.passed, "generic meta Word draft should fail")
        _require(any("generic" in issue.lower() or "too thin" in issue.lower() for issue in weak_qa.issues), "weak failure reason missing")
    print("word_golden_artifact_smoke: ok")


def _cases() -> list[dict]:
    return [
        {
            "topic": "make me a Seoul food trip doc",
            "title": "Seoul Food Trip",
            "must_contain": ["Myeongdong Kyoja", "Gwangjang Market", "Korean BBQ", "T-money"],
            "sections": [
                ("Trip Overview", ["1) This compact two-day Seoul food trip assumes Zainal wants high-confidence classics, short transit hops, and enough buffer for queues.", "2) The route clusters Myeongdong, Jongno, Gwangjang Market, Hongdae, and Mapo so every meal has nearby backup options."]),
                ("Day 1 Plan", ["1) Start at Myeongdong Kyoja for kalguksu, then use Myeongdong street stalls for hotteok, egg bread, and light snacks.", "2) Move by subway to Gwangjang Market for bindaetteok and mayak gimbap, then finish with grilled fish or noodles around Jongno if still hungry."]),
                ("Day 2 Plan", ["1) Begin with a Yeonnam or Hongdae cafe, keep lunch flexible, then reserve dinner for Korean BBQ near Hongdae or Mapo.", "2) Keep at least two hours between lunch and dinner so snacks, coffee, and walking time do not make the evening rushed."]),
                ("Food And Restaurant Highlights", ["1) Prioritize kalguksu, bindaetteok, hotteok, Korean BBQ, market gimbap, and one modern Seoul cafe stop.", "2) Keep restaurant backups in the same neighborhood instead of crossing Seoul for a single snack."]),
                ("Budget Notes", ["1) Track restaurant meals, market snacks, cafes, transit, and BBQ separately because the BBQ dinner is the likely budget spike.", "2) Carry some cash for market stalls and use cards for sit-down restaurants where accepted."]),
                ("Booking And Transit Notes", ["1) Use Naver Map or KakaoMap for walking exits, load a T-money card, and avoid peak subway transfers when carrying food.", "2) Reserve Korean BBQ if the chosen restaurant is popular, especially on Friday or Saturday night."]),
                ("Recommendations", ["1) Treat the plan as food-first and keep sightseeing optional around meals.", "2) If queues are long, switch to the nearest backup instead of breaking the day structure."]),
            ],
        },
        {
            "topic": "make router setup guide in Word",
            "title": "Router Setup Guide",
            "must_contain": ["admin password", "SSID", "WPA2", "firmware", "WAN IP"],
            "sections": [
                ("Purpose", ["1) Set up a home or small-office router with working internet, secure WiFi, and recoverable admin access.", "2) The guide covers cabling, admin login, WAN configuration, WiFi security, firmware safety, and final checks."]),
                ("Prerequisites", ["1) Prepare the modem, router, power adapter, Ethernet cable, admin interface address, and temporary default credentials.", "2) Keep ISP settings ready in case the WAN requires PPPoE, VLAN ID, static IP, or DNS values."]),
                ("Configuration Steps", ["1) Connect modem LAN to router WAN, connect a laptop by Ethernet, open the admin interface, and change the default admin password immediately.", "2) Configure the WAN internet profile, set the SSID or WiFi network name, create a strong WiFi password, and select WPA2 or WPA3 security.", "3) Check for firmware updates only when power is stable and save a backup of the router configuration after the first successful setup."]),
                ("Verification", ["1) Confirm the router has a WAN IP, browse to a known website, test DNS resolution, and join the WiFi network with the new password.", "2) Walk to the main usage areas and verify signal strength before deciding whether a mesh node is needed."]),
                ("Troubleshooting", ["1) If internet fails, check WAN cabling, modem bridge mode, DHCP status, DNS values, and ISP account requirements.", "2) If WiFi fails, retype the password, confirm the SSID is visible, and temporarily test from the same room as the router."]),
                ("Safety Notes", ["1) Do not interrupt firmware updates, do not reuse the admin password as the WiFi password, and keep a backup before changing advanced routing settings.", "2) Disable remote admin access unless there is a specific secured reason to use it."]),
                ("Next Steps", ["1) Create a guest network, name critical devices, review connected clients, and schedule a monthly firmware check.", "2) Save the admin URL and password location in a private password manager, not in the document itself."]),
            ],
        },
        {
            "topic": "make proposal doc for Kampung AI document quality",
            "title": "Proposal For Kampung AI Document Quality",
            "must_contain": ["quality gates", "one repair pass", "Telegram and iMac", "Out of Scope"],
            "sections": [
                ("Executive Summary", ["1) Kampung AI should produce Word, Excel, and PowerPoint files that are useful on first delivery, not merely valid files.", "2) The proposal adds scenario skills, preflight planning, quality gates, Claude review, and one repair pass before Maya calls artifacts complete."]),
                ("Objective", ["1) Reduce repeated manual correction by making quality standards executable in Maya's runtime.", "2) Keep Telegram and iMac outputs consistent by sharing one artifact quality pipeline."]),
                ("Scope", ["1) In Scope: Word document quality, Excel workbook structure, PowerPoint narrative and visual QA, route transparency, and artifact metadata.", "2) Out of Scope: app-building, payment workflows, private-data policies, and unrelated brand redesign work."]),
                ("Recommended Approach", ["1) Use a three-tier review process: local structural QA, Claude Opus quality review, and a bounded repair pass if either gate rejects.", "2) Store the accepted result with path, summary, route, cost flag, and latest-document continuity."]),
                ("Deliverables", ["1) Quality skills for each artifact type, golden `.docx`/`.xlsx`/`.pptx` tests, repair prompts, and channel-specific delivery rules.", "2) Updated checklist entries so future next-step answers come from the roadmap instead of improvisation."]),
                ("Timeline", ["1) Start with Word, then Excel, then PowerPoint, because fixing all three at once hides regressions.", "2) Run real Telegram tests only after code-level golden checks pass."]),
                ("Risks", ["1) Model drafts can still omit scenario details, so local QA must reject thin or generic content.", "2) Review cost rises with Opus, so Opus should run after the file exists and local QA has useful extracted content."]),
                ("Next Steps", ["1) Finish the Word rubric, run short-prompt tests, and only move to Excel after Word passes the fixed sample set.", "2) Keep app-building gated until Office artifacts meet the quality bar."]),
            ],
        },
    ]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
