from __future__ import annotations

from response_style import apply_reply_preferences


async def style_document_text(db_path: str, text: str) -> str:
    return await apply_reply_preferences(db_path, text)


async def style_sections(
    db_path: str,
    sections: list[tuple[str, list[str]]],
) -> list[tuple[str, list[str]]]:
    styled = []
    for heading, lines in sections:
        styled_heading = await style_document_text(db_path, heading)
        styled_lines = [
            line if _should_preserve_exact_text(line) else await style_document_text(db_path, line)
            for line in lines
        ]
        styled.append((styled_heading, styled_lines))
    return styled


async def style_table(
    db_path: str,
    headers: list[str],
    rows: list[list[str]],
) -> tuple[list[str], list[list[str]]]:
    styled_headers = [await style_document_text(db_path, item) for item in headers]
    styled_rows = [
        [await style_document_text(db_path, str(cell)) for cell in row]
        for row in rows
    ]
    return styled_headers, styled_rows


def _should_preserve_exact_text(text: str) -> bool:
    lowered = str(text).lower()
    command_markers = (
        "configure terminal",
        "write memory",
        "copy running-config",
        "show running-config",
        "default-router",
        "dns-server",
        "wpa2 psk",
        "ip address",
        "ip dhcp pool",
        "no shutdown",
        "enable secret",
        "interface gigabitethernet",
    )
    return any(marker in lowered for marker in command_markers)
