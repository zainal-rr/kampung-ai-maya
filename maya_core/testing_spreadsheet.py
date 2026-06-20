from __future__ import annotations


def is_kampung_ai_testing_comparison(topic: str) -> bool:
    low = topic.lower()
    return (
        "kampung ai" in low
        and "telegram" in low
        and "imac" in low
        and any(word in low for word in ("test", "testing", "comparison", "compare"))
    )


def kampung_ai_testing_rows() -> tuple[list[str], list[list[str]]]:
    headers = ["Surface", "What To Test", "Works While Away", "Needs Physical iMac", "Expected Route Or Tool", "Pass Criteria", "Notes"]
    rows = [
        ["Telegram", "Normal chat and tone", "Yes", "No", "Gemini Flash text", "Replies are natural, concise, and text-only for typed input.", "Main surface from 25 May to 7 June."],
        ["Telegram", "Files and artifacts", "Yes", "No", "Document workflow", "Markdown, Word, PowerPoint, and Excel files are attached and land in Desktop/Maya.", "Use Splashtop only to visually inspect files if needed."],
        ["Telegram", "Routing checks", "Yes", "No", "/route", "Normal, review, coding, current-world, and /complex routes are correct.", "Capture /route when behavior feels wrong."],
        ["Telegram", "Memory and context", "Yes", "No", "Memory and context stores", "Preferences save only after verification and /context remains coherent.", "Avoid saving sensitive details."],
        ["Telegram", "Workflow persistence", "Yes", "No", "LangGraph harness", "Continue resumes a delayed workflow instead of restarting.", "Test with 10 to 30 minute gaps."],
        ["iMac", "Local voice", "No", "Yes", "Grok Voice Agent + wake path", "Wake phrase works and paid voice closes after 5 seconds silence.", "Do this before 25 May or after 8 June."],
        ["iMac", "Screen sight", "Limited", "Useful", "Screen sight + Gemini", "/screen toggles on and off and follow-ups use fresh captures.", "Can be checked remotely only when intentional."],
        ["iMac", "Camera sight", "Limited", "Useful", "Cisco Desk Camera 4K + Gemini", "/see toggles on and off and uses Cisco camera only.", "Do not leave camera active casually."],
        ["iMac", "Office visual QA", "Limited", "Useful", "PowerPoint, Word, Excel apps", "Files open without repair and visual layout is acceptable.", "Splashtop can help inspect this remotely."],
        ["Hardware", "Mudra and Omi", "No", "Yes", "Prepared adapters", "Raw events or transcripts are staged only; no automatic actions.", "Full tests wait until hardware arrives after return."],
    ]
    return headers, rows
