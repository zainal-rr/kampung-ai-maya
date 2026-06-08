from __future__ import annotations


def markdown_content(topic: str) -> str:
    cleaned = topic.strip()
    title = cleaned.title()
    sections = _sections(cleaned)
    body = [f"# {title}", "", "## Overview", "", sections["overview"]]
    for heading in sections["order"]:
        body.extend(["", f"## {heading}", ""])
        body.extend(f"{idx}) {item}" for idx, item in enumerate(sections[heading], start=1))
    return "\n".join(body) + "\n"


def _sections(topic: str) -> dict[str, list[str] | str]:
    lowered = topic.lower()
    if "router" in lowered:
        return _router_sections()
    if _looks_like_ai_model(lowered):
        return _ai_model_sections(topic)
    return _general_sections(topic)


def _router_sections() -> dict[str, list[str] | str]:
    return {
        "overview": "A practical router setup note covering cabling, login, WiFi setup, and basic checks.",
        "order": ["Before You Start", "Setup Steps", "Checks", "Common Issues", "Next Steps"],
        "Before You Start": [
            "Confirm the router model and power adapter.",
            "Prepare the internet cable from the modem or wall port.",
            "Keep the default login sticker nearby if the router is new.",
        ],
        "Setup Steps": [
            "Connect power and wait until the router finishes booting.",
            "Connect the internet cable to the WAN or internet port.",
            "Connect a laptop by Ethernet or join the default WiFi network.",
            "Open the router admin page or mobile app.",
            "Change the admin password before changing other settings.",
            "Set the WiFi name and WiFi password.",
            "Save the settings and let the router restart if needed.",
        ],
        "Checks": [
            "Confirm the internet light is stable.",
            "Test a website from a connected phone or laptop.",
            "Run a speed test near the router.",
            "Check WiFi signal in the rooms where you usually work.",
        ],
        "Common Issues": [
            "If there is no internet, check whether the cable is in the WAN port.",
            "If login fails, reset only after saving any needed ISP details.",
            "If WiFi is weak, move the router higher and away from thick walls.",
        ],
        "Next Steps": [
            "Label the WAN and LAN cables.",
            "Save the admin URL and non sensitive setup notes.",
            "Create a simple network diagram if more devices are added.",
        ],
    }


def _ai_model_sections(topic: str) -> dict[str, list[str] | str]:
    return {
        "overview": f"A research note for {topic}, focused on what to verify before changing Maya's routing.",
        "order": ["What To Verify", "Possible Uses", "Cost Checks", "Risks", "Next Steps"],
        "What To Verify": [
            "Official model name and availability.",
            "Input and output pricing.",
            "Context window and file limits.",
            "Vision, research, and tool use strengths.",
            "Latency compared with the current default model.",
        ],
        "Possible Uses": [
            "Premium research lane when the cheaper model is uncertain.",
            "Long Malay or Manglish quality replies if the language result is better.",
            "Screen or vision reasoning when small text or messy layout matters.",
            "Omi transcript and weekly memory review when quality matters more than cost.",
        ],
        "Cost Checks": [
            "Keep the cheaper model as the default path.",
            "Use the premium model only after uncertainty, low confidence, or explicit request.",
            "Track route and cost after every test call.",
        ],
        "Risks": [
            "Do not switch default routing based on hype alone.",
            "Do not use premium calls for ordinary Telegram text.",
            "Do not store claims as memory until verified from a reliable source.",
        ],
        "Next Steps": [
            "Run provider smoke with the exact model id.",
            "Compare one research answer, one screen answer, and one Malay answer.",
            "Update lane policy only after the test result is better enough to justify cost.",
        ],
    }


def _general_sections(topic: str) -> dict[str, list[str] | str]:
    return {
        "overview": f"A practical note about {topic}.",
        "order": ["Key Ideas", "Details To Add", "Checks", "Open Questions", "Next Steps"],
        "Key Ideas": ["State the main idea.", "Explain why it matters.", "Name the expected outcome."],
        "Details To Add": ["Add facts, examples, or steps.", "Add links or sources if research is needed."],
        "Checks": ["Confirm the note answers the original request.", "Remove vague placeholder text."],
        "Open Questions": ["What is still unknown?", "What should Maya verify next?"],
        "Next Steps": ["Review the note.", "Ask Maya to research or expand the weak sections."],
    }


def _looks_like_ai_model(lowered: str) -> bool:
    markers = ("gemini", "gpt", "claude", "grok", "model", "llm", "ai")
    return any(marker in lowered for marker in markers)
