from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import tempfile
from pathlib import Path

from maya_documents.artifact_quality import validate_docx_path
from maya_documents.office_drafter import word_sections_from_markdown
from maya_documents.office_modern_files import create_docx
from word_quality import detect_word_intent, word_prompt_context, word_quality_spec


SCENARIOS = (
    (
        "Make me a Word document for a 2-day Seoul food trip",
        "travel_itinerary",
        (
            "Trip Overview",
            "Day 1 Plan",
            "Day 2 Plan",
            "Food And Restaurant Highlights",
            "Budget Notes",
            "Booking And Transit Notes",
            "Recommendations",
        ),
    ),
    (
        "Write a Word setup guide for router configuration",
        "technical_guide",
        (
            "Purpose",
            "Prerequisites",
            "Configuration Steps",
            "Verification",
            "Troubleshooting",
            "Safety Notes",
            "Next Steps",
        ),
    ),
    (
        "Write a proposal for Kampung AI Telegram features",
        "proposal",
        (
            "Executive Summary",
            "Objective",
            "Scope",
            "Recommended Approach",
            "Deliverables",
            "Timeline",
            "Risks",
            "Next Steps",
        ),
    ),
    (
        "Make a research brief about Gemini image generation",
        "research_brief",
        (
            "Research Question",
            "Scope",
            "Key Findings",
            "Evidence",
            "Risks Or Unknowns",
            "Sources",
            "Next Steps",
        ),
    ),
    (
        "Make meeting notes for Kampung AI document quality sprint",
        "meeting_notes",
        ("Meeting Summary", "Decisions", "Action Items", "Open Questions", "Follow Up"),
    ),
    (
        "Write a refund request letter",
        "letter",
        ("Recipient", "Subject", "Opening", "Request", "Supporting Details", "Requested Resolution", "Closing"),
    ),
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-word-quality-") as tmp:
        root = Path(tmp)
        for topic, intent, headings in SCENARIOS:
            _require(detect_word_intent(topic) == intent, f"wrong intent for {topic}")
            spec = word_quality_spec(topic)
            for heading in headings:
                _require(heading in spec.required_headings, f"{heading} missing from spec")
            path = create_docx(root / f"{intent}.docx", topic, _router_sections(headings) if intent == "technical_guide" else _good_sections(intent, headings))
            qa = validate_docx_path(path, topic, doc_kind=intent)
            _require(qa.passed, f"{intent} docx should pass: {qa.issues}")

        markdown = (
            "# Router Setup\n\n"
            "## Role And Assumptions\n\n"
            "1) This is practical setup guidance for a real home router change.\n\n"
            "## Configuration Steps\n\n"
            "1) Connect the WAN cable, log into the admin UI, and save current settings.\n"
        )
        sections = word_sections_from_markdown(markdown, "Write a Word setup guide for router configuration")
        headings = [heading for heading, _ in sections]
        _require("Role And Assumptions" not in headings, "boilerplate heading should be canonicalized away")
        _require("Purpose" in headings and "Configuration Steps" in headings, "technical headings not retained")

        travel_markdown = (
            "# Seoul Food Trip\n\n"
            "## Day 1 Plan: Traditions and Street Staples\n\n"
            "1) Start with handmade kalguksu, then visit Gwangjang Market for bindaetteok and mayak gimbap.\n\n"
            "## Day 2 Plan: Cafes and BBQ\n\n"
            "1) Keep lunch light, then reserve Korean BBQ for the evening near Myeongdong or Hongdae.\n"
        )
        travel_sections = word_sections_from_markdown(travel_markdown, "Make me a Word document for a 2-day Seoul food trip")
        travel_headings = [heading for heading, _ in travel_sections]
        _require("Day 1 Plan" in travel_headings, "decorated Day 1 heading should map to canonical day heading")
        _require("Day 2 Plan" in travel_headings, "decorated Day 2 heading should map to canonical day heading")

        short_spec = word_quality_spec("make me a Seoul food trip doc")
        _require("Day 1 Plan" in short_spec.required_headings, "short food trip should default to day-level plan")
        _require("Day 2 Plan" in short_spec.required_headings, "short food trip should default to two days")
        mismatch = create_docx(
            root / "mismatch.docx",
            "Seoul Food Trip",
            [
                ("Trip Overview", ["This 5 day itinerary focuses on Seoul food, but the request was a short food trip doc."]),
                ("Daily Plan", ["Day 1: Myeongdong food walk. Day 2: Gwangjang Market breakfast."]),
                ("Food And Restaurant Highlights", ["Kalguksu, bindaetteok, Korean BBQ, hotteok, and cafes."]),
                ("Budget Notes", ["Track restaurants, snacks, transit, and coffee separately."]),
                ("Booking And Transit Notes", ["Use Naver Map and keep meals clustered by neighborhood."]),
                ("Recommendations", ["Keep the first version compact unless the user asks for a longer trip."]),
            ],
        )
        mismatch_qa = validate_docx_path(mismatch, "make me a Seoul food trip doc", doc_kind="travel_itinerary")
        _require(not mismatch_qa.passed, "short food trip should reject mismatched 5-day/Daily Plan output")
        _require(any("missing day-level" in issue or "declares 5 days" in issue for issue in mismatch_qa.issues), "mismatch QA reason missing")

        weak_router = create_docx(
            root / "weak-router.docx",
            "Router Setup Guide",
            [
                ("Purpose", ["This explains how to cable a basic home router."]),
                ("Prerequisites", ["Use a modem, router, power adapter, Ethernet cable, and laptop."]),
                ("Configuration Steps", ["Connect the modem to the WAN port and power on the router."]),
                ("Verification", ["Check that the internet light is on and browse to a known website."]),
                ("Troubleshooting", ["Try another cable if the internet light does not turn on."]),
                ("Safety Notes", ["Do not power off the router during firmware updates."]),
                ("Next Steps", ["Review the manufacturer documentation."]),
            ],
        )
        weak_router_qa = validate_docx_path(weak_router, "make router setup guide in Word", doc_kind="technical_guide")
        _require(not weak_router_qa.passed, "router guide should fail when it only covers cabling")
        _require(any("router technical guide missing" in issue for issue in weak_router_qa.issues), "router QA reason missing")

        weak_putty = create_docx(
            root / "weak-putty.docx",
            "Router Setup Guide With PuTTY Config",
            [
                ("Purpose", ["Configure a router through PuTTY and keep the setup secure."]),
                ("Prerequisites", ["Use a router, console cable, PuTTY, COM port details, ISP credentials, and a management computer."]),
                ("Configuration Steps", ["Open PuTTY, select Serial, enter COM3, set speed 9600, and press Enter. Change the admin password, SSID, WiFi password, and WPA2 or WPA3 security mode."]),
                ("Verification", ["Run ping 8.8.8.8 and confirm internet DNS connectivity after the WAN IP appears."]),
                ("Troubleshooting", ["If PuTTY shows garbage characters, try 115200 baud."]),
                ("Safety Notes", ["Do not interrupt firmware updates and keep the new admin password private."]),
                ("Next Steps", ["Review connected devices and document final settings."]),
            ],
        )
        weak_putty_qa = validate_docx_path(weak_putty, "router setup guide with PuTTY config", doc_kind="technical_guide")
        _require(not weak_putty_qa.passed, "PuTTY guide should fail without actual config commands")
        _require(any("PuTTY/CLI" in issue for issue in weak_putty_qa.issues), "PuTTY QA reason missing")

        meraki_context = word_prompt_context("make a Word document about Cisco Meraki MX firewall config")
        _require("Dashboard" in meraki_context, "Meraki prompt context missing Dashboard grounding")
        _require("organization" in meraki_context.lower(), "Meraki prompt context missing organization grounding")
        _require("claim device" in meraki_context.lower(), "Meraki prompt context missing claim-device grounding")
        generic_meraki = create_docx(
            root / "weak-meraki.docx",
            "Cisco Meraki MX Firewall Config",
            [
                ("Purpose", ["This explains a router setup where exact menu names vary by router brand."]),
                ("Prerequisites", ["Have admin access and change the admin password before continuing."]),
                ("Configuration Steps", ["Configure internet, WiFi, and firewall settings in the router interface."]),
                ("Verification", ["Confirm internet access."]),
                ("Troubleshooting", ["Restart the router if needed."]),
                ("Safety Notes", ["Do not share credentials."]),
                ("Next Steps", ["Document the setup."]),
            ],
        )
        weak_meraki_qa = validate_docx_path(generic_meraki, "make a Word document about Cisco Meraki MX firewall config", doc_kind="technical_guide")
        _require(any("Meraki" in issue for issue in weak_meraki_qa.issues), "Meraki generic-router QA reason missing")

        good_putty = create_docx(
            root / "good-putty.docx",
            "Router Setup Guide With PuTTY Config",
            _putty_router_sections(),
        )
        good_putty_qa = validate_docx_path(good_putty, "router setup guide with PuTTY config", doc_kind="technical_guide")
        _require(good_putty_qa.passed, f"PuTTY router guide should pass: {good_putty_qa.issues}")

        weak_proposal = create_docx(
            root / "weak-proposal.docx",
            "Proposal For Kampung AI Document Quality",
            [
                ("Executive Summary", ["This proposal introduces a document quality framework for Kampung AI."]),
                ("Objective", ["Improve document quality and reduce repeated manual fixes."]),
                ("Scope", ["In Scope", "Word, Excel, and PowerPoint artifact standards.", "Out of Scope"]),
                ("Recommended Approach", ["The Three Tier Review Process", "Tier 1: local QA.", "Tier 2: Claude review."]),
                ("Deliverables", ["Quality rubric, QA scripts, and artifact skill updates."]),
                ("Timeline", ["Week 1: Word. Week 2: Excel and PowerPoint."]),
                ("Risks", ["Model output may still omit critical details without repair gates."]),
                ("Next Steps", ["Approve the repair policy.", "***"]),
            ],
        )
        weak_proposal_qa = validate_docx_path(weak_proposal, "make proposal doc for Kampung AI document quality", doc_kind="proposal")
        _require(not weak_proposal_qa.passed, "proposal should fail empty Out of Scope and missing Tier 3")
        _require(any("Out of Scope" in issue or "three-tier" in issue for issue in weak_proposal_qa.issues), "proposal QA reason missing")

        bad = create_docx(
            root / "bad.docx",
            "Bad Proposal",
            [
                ("Role And Assumptions", ["This document has generic boilerplate."]),
                ("Working Context", ["It does not have the proposal sections required for delivery."]),
                ("Plan", ["Add a specific point later."]),
            ],
        )
        bad_qa = validate_docx_path(bad, "Write a proposal for Kampung AI Telegram features", doc_kind="proposal")
        _require(not bad_qa.passed, "boilerplate proposal should fail")
        _require(any("boilerplate heading" in issue or "missing scenario headings" in issue for issue in bad_qa.issues), "bad QA reason missing")

        generic_network = create_docx(
            root / "generic-network.docx",
            "Network Troubleshooting Notes",
            [
                ("Summary", ["This diagnostic note records a short network check and avoids pretending to be a configuration guide."]),
                ("Checks Run", ["Route, DNS, and ping checks were inspected with basic status notes."]),
                ("Next Steps", ["Review the router, ISP, DNS resolver, or local link depending on which check failed."]),
            ],
        )
        generic_network_qa = validate_docx_path(generic_network, "network troubleshooting notes")
        _require(
            not any("Purpose" in issue or "Prerequisites" in issue or "Configuration Steps" in issue for issue in generic_network_qa.issues),
            f"missing doc_kind must not infer technical-guide headings: {generic_network_qa.issues}",
        )

        diagnostic = create_docx(
            root / "diagnostic.docx",
            "Network Troubleshooting Notes",
            [
                ("Summary", ["The route, DNS, and ping checks provide a basic picture of connectivity and whether local routing or name resolution needs attention."]),
                ("Checks Run", ["Default route returned a gateway, DNS configuration listed a resolver, and ping checks verified both numeric and domain reachability."]),
                ("Findings", ["No failed basic checks were observed, so the first pass points away from immediate local route, DNS, or link failure."]),
                ("Next Steps", ["If symptoms continue, test another device, restart the router, review ISP status, and repeat DNS plus ping checks after the restart."]),
            ],
        )
        diagnostic_qa = validate_docx_path(diagnostic, "network troubleshooting notes", doc_kind="diagnostic_report")
        _require(diagnostic_qa.passed, f"diagnostic report should pass declared diagnostic QA: {diagnostic_qa.issues}")

        missing_findings = create_docx(
            root / "diagnostic-missing-findings.docx",
            "Network Troubleshooting Notes",
            [
                ("Summary", ["The route, DNS, and ping checks provide a basic picture of current connectivity."]),
                ("Checks Run", ["Default route, DNS configuration, and ping checks were inspected."]),
                ("Next Steps", ["Repeat checks after restarting the router and testing another device."]),
            ],
        )
        missing_findings_qa = validate_docx_path(missing_findings, "network troubleshooting notes", doc_kind="diagnostic_report")
        _require(not missing_findings_qa.passed, "diagnostic report should require Findings")
        _require(any("Findings" in issue for issue in missing_findings_qa.issues), "diagnostic missing-Findings reason absent")
    print("word_quality_smoke: ok")


def _good_sections(intent: str, headings: tuple[str, ...]) -> list[tuple[str, list[str]]]:
    examples = {
        "travel_itinerary": {
            "Trip Overview": ["1) Use a compact two-day Seoul food route focused on Jongno, Myeongdong, Hongdae, and one Korean BBQ dinner.", "2) Keep stops clustered by subway area so meals, markets, and cafes do not require cross-city backtracking."],
            "Day 1 Plan": ["1) Start late morning at Myeongdong Kyoja for kalguksu, walk through Myeongdong snack streets, then move to Gwangjang Market for bindaetteok.", "2) End near Euljiro or Jongno with grilled fish, pojangmacha snacks, or a simple noodle supper if queues are long."],
            "Day 2 Plan": ["1) Keep breakfast light, visit a Yeonnam or Hongdae cafe, then reserve the evening for Korean BBQ near Hongdae or Mapo.", "2) Leave a two-hour buffer between lunch and dinner so snacks and cafe stops do not crowd the plan."],
        },
        "proposal": {
            "Executive Summary": ["1) Kampung AI needs a stricter document quality pipeline so Word, Excel, and PowerPoint files are useful on first delivery.", "2) The proposal creates scenario skills, local validation, Claude review, and repair gates before Maya calls an artifact complete."],
            "Recommended Approach": ["1) Use a three-tier review process: local structural QA, Claude quality review, and one repair pass when either gate rejects.", "2) Keep Telegram and iMac on the same router so delivery changes by channel but artifact quality does not."],
        },
        "research_brief": {
            "Research Question": ["1) Determine when Gemini image generation is useful for presentation work and when sourced images are better.", "2) Focus on quality, controllability, cost, and whether the visual improves comprehension."],
            "Evidence": ["1) Compare official provider capabilities, rendered slide examples, and failure cases such as random decoration or unreadable generated text.", "2) Separate official model behavior from subjective design preference before making a recommendation."],
        },
        "meeting_notes": {
            "Meeting Summary": ["1) The sprint focused on making Maya's Word outputs useful without long prompts.", "2) The team agreed to test short everyday requests before moving to Excel and PowerPoint."],
            "Action Items": ["1) Codex will strengthen Word QA and add golden document checks.", "2) Zainal will test five short Telegram prompts after Maya restarts."],
        },
        "letter": {
            "Opening": ["1) I am writing to request a refund for an order that did not meet the agreed condition or service expectation.", "2) I would appreciate a clear review of the issue and a practical resolution."],
            "Request": ["1) Please process a refund to the original payment method or confirm the next step required from me.", "2) If further evidence is needed, I can provide the order number, receipt, and photos."],
        },
    }
    return [
        (
            heading,
            examples.get(intent, {}).get(
                heading,
                [
                    f"1) {heading} records a concrete decision, action, risk, or recommendation tied to the requested topic.",
                    f"2) {heading} gives enough detail for the reader to act without asking for a basic expansion.",
                ],
            ),
        )
        for heading in headings
    ]


def _router_sections(headings: tuple[str, ...]) -> list[tuple[str, list[str]]]:
    content = {
        "Purpose": [
            "1) Set up a home router with secure internet, WiFi, and admin access.",
            "2) The guide covers physical cabling, router login, secure wireless settings, verification, and recovery steps.",
        ],
        "Prerequisites": [
            "1) Router, modem, Ethernet cable, admin interface address, and temporary default credentials.",
            "2) Keep the ISP account details nearby in case the WAN connection requires PPPoE, VLAN, or static IP values.",
        ],
        "Configuration Steps": [
            "1) Log into the router admin interface, change the default admin password, then save it securely.",
            "2) Configure the WAN or internet connection, set the SSID or WiFi network name, and create a strong WiFi password.",
            "3) Use WPA2 or WPA3 security mode, disable weak legacy encryption, and check for a firmware update.",
        ],
        "Verification": ["1) Confirm the WAN IP is present, ping a public resolver, join the WiFi network, and test DNS browsing."],
        "Troubleshooting": [
            "1) If internet fails, check WAN cabling, modem bridge mode, DHCP, DNS, and WiFi password entry.",
            "2) If the admin interface is unreachable, reconnect by Ethernet, verify the gateway IP, or reset only after saving known settings.",
        ],
        "Safety Notes": ["1) Do not interrupt firmware updates and keep a record of admin password and SSID changes."],
        "Next Steps": ["1) Create a guest network, review connected devices, and schedule firmware checks."],
    }
    return [(heading, content.get(heading, [f"1) {heading} detail."])) for heading in headings]


def _putty_router_sections() -> list[tuple[str, list[str]]]:
    return [
        ("Purpose", ["1) Configure a lab router through PuTTY with a simple Cisco-style example that must be adapted to the user's actual router model.", "2) The guide shows what to type, what to replace, and how to verify the result safely."]),
        ("Prerequisites", ["1) PuTTY, console or SSH access, correct COM port or router IP, admin credentials, interface names, SSID, WiFi password, and LAN subnet plan.", "2) Replace placeholders such as GigabitEthernet0/0, GigabitEthernet0/1, YOUR_SSID, and YOUR_WIFI_PASSWORD before using the sample."]),
        ("Configuration Steps", ["1) In PuTTY, connect by Serial with the detected COM port and 9600 baud, or by SSH to the router management IP if SSH is already enabled.", "2) Sample commands: enable; configure terminal; hostname HomeRouter; enable secret CHANGE_ADMIN_PASSWORD; interface GigabitEthernet0/0; ip address dhcp; no shutdown; interface GigabitEthernet0/1; ip address 192.168.1.1 255.255.255.0; no shutdown; ip dhcp pool LAN; network 192.168.1.0 255.255.255.0; default-router 192.168.1.1; dns-server 1.1.1.1 8.8.8.8; wlan ssid YOUR_SSID; wpa2 psk YOUR_WIFI_PASSWORD; end; write memory.", "3) If the router uses Juniper, MikroTik, TP-Link, or another OS, adapt the syntax instead of pasting Cisco-style commands directly."]),
        ("Verification", ["1) Run show ip interface brief, show running-config, ping 8.8.8.8, and ping google.com to verify interfaces, saved config, internet reachability, and DNS.", "2) Join the SSID from a phone or laptop and confirm it asks for the WPA2/WPA3 password."]),
        ("Troubleshooting", ["1) If PuTTY displays unreadable characters, switch baud rate from 9600 to 115200 and reopen the serial session.", "2) If WAN does not receive an address, check modem bridge mode, ISP VLAN/PPPoE requirements, and interface names."]),
        ("Safety Notes", ["1) Do not paste commands until placeholders are replaced and do not run write memory until the current session is verified.", "2) Keep firmware updates separate from first-time config and maintain a backup before changing routing or wireless security."]),
        ("Next Steps", ["1) Create a guest SSID, save a sanitized copy of the final config, and record the admin password only in a private password manager.", "2) Schedule a firmware check and review connected clients after all household devices are migrated."]),
    ]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
