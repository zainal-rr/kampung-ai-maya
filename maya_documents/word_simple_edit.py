from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph


def simple_docx_edit_instruction(instruction: str) -> bool:
    lowered = " ".join(str(instruction).lower().split())
    return bool(
        re.search(r"\b(?:add|include|insert|append)\b", lowered)
        and re.search(r"\b(?:transit|transport|booking)\s+(?:tips|notes|section|details)?\b", lowered)
    )


def apply_simple_docx_edit(path: Path, instruction: str) -> str:
    if not simple_docx_edit_instruction(instruction):
        raise ValueError("unsupported simple Word edit")
    doc = Document(path)
    if _has_text(doc, "Transit Tips:"):
        return "transit tips already present"
    if not _add_to_booking_section(doc, _transit_tip_lines(path)):
        doc.add_heading("Booking And Transit Notes", level=1)
        for line in _transit_tip_lines(path):
            doc.add_paragraph(line)
    doc.save(path)
    return "added transit tips to Booking And Transit Notes"


def _add_to_booking_section(doc: Document, lines: list[str]) -> bool:
    start = _heading_index(doc, "Booking And Transit Notes")
    if start < 0:
        return False
    end = _next_heading_index(doc, start + 1)
    insert_after = doc.paragraphs[(end - 1) if end > start else start]
    for line in lines:
        insert_after = _insert_after(insert_after, line)
    return True


def _heading_index(doc: Document, heading: str) -> int:
    wanted = _normalize_heading(heading)
    for index, paragraph in enumerate(doc.paragraphs):
        style = getattr(paragraph.style, "name", "") or ""
        if style.lower().startswith("heading") and _normalize_heading(paragraph.text) == wanted:
            return index
    return -1


def _next_heading_index(doc: Document, start: int) -> int:
    for index in range(start, len(doc.paragraphs)):
        style = getattr(doc.paragraphs[index].style, "name", "") or ""
        if style.lower().startswith("heading"):
            return index
    return -1


def _insert_after(paragraph: Paragraph, text: str) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    new_para.add_run(text)
    return new_para


def _has_text(doc: Document, marker: str) -> bool:
    lowered = marker.lower()
    for paragraph in doc.paragraphs:
        if lowered in str(paragraph.text).lower():
            return True
    return False


def _transit_tip_lines(path: Path) -> list[str]:
    lowered = path.stem.lower()
    if "seoul" in lowered:
        return [
            "Transit Tips: use Naver Maps or KakaoMap for walking routes, subway transfers, and real-time bus options because Google Maps is weaker in Seoul.",
            "Transit Tips: keep a T-money card topped up before food stops so subway, bus, and convenience-store payments do not slow the itinerary.",
            "Cluster meals by neighborhood: Myeongdong and Gwangjang work well on one day, while Seongsu, Ikseon-dong, or Hongdae work better as a separate route.",
            "Avoid crossing the city for a single snack unless it is a priority stop; use a nearby cafe or street-food backup when queues run long.",
        ]
    return [
        "Transit Tips: use the local transit app or official journey planner before leaving each stop, because live transfer times can change during the day.",
        "Group activities by neighborhood so the plan spends more time on the actual itinerary and less time moving between distant areas.",
        "Keep one backup route for each major transfer, especially when the plan depends on a train, bus, ferry, or airport connection.",
        "Write down the nearest station, stop, or pickup point for each major activity so the document remains useful offline.",
    ]


def _normalize_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()
