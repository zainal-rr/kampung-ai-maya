from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


def normalize_docx_postcondition(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    headings = _string_list(data.get("required_headings"))
    strings = _string_list(data.get("required_strings") or data.get("required_literals"))
    section_strings = _section_requirements(data.get("required_section_strings"))
    section_links = _section_requirements(data.get("required_section_links"))
    additions = []
    for item in data.get("section_additions") or []:
        if not isinstance(item, dict):
            continue
        heading = _clean(item.get("heading"))
        paragraphs = _string_list(item.get("paragraphs") or item.get("lines"))
        links = _string_list(item.get("links") or item.get("urls"))
        if heading or paragraphs or links:
            additions.append({"heading": heading, "paragraphs": paragraphs, "links": links})
            if heading and paragraphs:
                section_strings.append({"heading": heading, "values": paragraphs})
            if heading and links:
                section_links.append({"heading": heading, "values": links})
    return {
        "required_headings": headings,
        "required_strings": strings,
        "required_section_strings": section_strings,
        "required_section_links": section_links,
        "section_additions": additions,
    }


def has_docx_postcondition(raw: dict[str, Any] | None) -> bool:
    data = normalize_docx_postcondition(raw)
    return bool(
        data["required_headings"]
        or data["required_strings"]
        or data["required_section_strings"]
        or data["required_section_links"]
        or data["section_additions"]
    )


def has_scoped_docx_postcondition(raw: dict[str, Any] | None) -> bool:
    data = normalize_docx_postcondition(raw)
    if data["required_section_strings"] or data["required_section_links"] or data["section_additions"]:
        return True
    return bool(data["required_headings"] and not data["required_strings"])


def apply_docx_postcondition(path: Path, raw: dict[str, Any] | None) -> dict[str, Any]:
    condition = normalize_docx_postcondition(raw)
    if not has_docx_postcondition(condition):
        return {"status": "skipped", "changed": False}
    doc = Document(path)
    changed = False
    for addition in condition["section_additions"]:
        changed = _ensure_section(doc, addition["heading"], addition["paragraphs"], addition["links"]) or changed
    for requirement in condition["required_section_strings"]:
        changed = _ensure_section(doc, requirement["heading"], requirement["values"], []) or changed
    for requirement in condition["required_section_links"]:
        changed = _ensure_section(doc, requirement["heading"], [], requirement["values"]) or changed
    if not condition["section_additions"] and condition["required_headings"]:
        heading = condition["required_headings"][0]
        lines = condition["required_strings"]
        changed = _ensure_section(doc, heading, lines, []) or changed
    elif condition["required_strings"]:
        heading = condition["required_headings"][0] if condition["required_headings"] else "Revision"
        missing = [item for item in condition["required_strings"] if item not in _full_text(doc)]
        if missing:
            changed = _ensure_section(doc, heading, missing, []) or changed
    if changed:
        doc.save(path)
    return {"status": "ok", "changed": changed}


def verify_docx_postcondition(path: Path, raw: dict[str, Any] | None) -> dict[str, Any]:
    condition = normalize_docx_postcondition(raw)
    if not has_docx_postcondition(condition):
        return {
            "status": "skipped",
            "passed": True,
            "headings": [],
            "missing_headings": [],
            "missing_strings": [],
            "missing_section_strings": [],
            "missing_section_links": [],
        }
    doc = Document(path)
    headings = docx_headings(path)
    normalized_headings = {_normalize(item) for item in headings}
    text = _full_text(doc)
    missing_headings = [
        heading for heading in condition["required_headings"] if _normalize(heading) not in normalized_headings
    ]
    missing_strings = [item for item in condition["required_strings"] if item not in text]
    missing_section_strings = _missing_section_strings(doc, condition["required_section_strings"])
    missing_section_links = _missing_section_links(doc, condition["required_section_links"])
    passed = not missing_headings and not missing_strings and not missing_section_strings and not missing_section_links
    return {
        "status": "ok" if passed else "failed",
        "passed": passed,
        "headings": headings,
        "missing_headings": missing_headings,
        "missing_strings": missing_strings,
        "missing_section_strings": missing_section_strings,
        "missing_section_links": missing_section_links,
    }


def docx_headings(path: Path) -> list[str]:
    doc = Document(path)
    headings: list[str] = []
    for paragraph in doc.paragraphs:
        style = getattr(paragraph.style, "name", "") or ""
        text = paragraph.text.strip()
        if text and style.lower().startswith("heading"):
            headings.append(text)
    return headings


def _ensure_section(doc: Document, heading: str, paragraphs: list[str], links: list[str]) -> bool:
    heading = heading.strip() or "Revision"
    section_index = _heading_index(doc, heading)
    changed = False
    if section_index < 0:
        doc.add_heading(heading, level=1)
        section_index = len(doc.paragraphs) - 1
        changed = True
    full_text = _full_text(doc)
    missing = [line for line in paragraphs if line and line not in full_text]
    if not missing:
        missing_links = _missing_links_for_section(doc, section_index, links)
        if not missing_links:
            return changed
    else:
        missing_links = _missing_links_for_section(doc, section_index, links)
    insert_after = _section_tail(doc, section_index)
    for line in missing:
        insert_after = _insert_after(insert_after, line)
        changed = True
    for url in missing_links:
        insert_after = _insert_hyperlink_after(insert_after, url, url)
        changed = True
    return changed


def _section_tail(doc: Document, heading_index: int) -> Paragraph:
    next_heading = len(doc.paragraphs)
    for index in range(heading_index + 1, len(doc.paragraphs)):
        style = getattr(doc.paragraphs[index].style, "name", "") or ""
        if style.lower().startswith("heading"):
            next_heading = index
            break
    tail_index = max(heading_index, next_heading - 1)
    return doc.paragraphs[tail_index]


def _heading_index(doc: Document, heading: str) -> int:
    wanted = _normalize(heading)
    for index, paragraph in enumerate(doc.paragraphs):
        style = getattr(paragraph.style, "name", "") or ""
        if style.lower().startswith("heading") and _normalize(paragraph.text) == wanted:
            return index
    return -1


def _insert_after(paragraph: Paragraph, text: str) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    new_para.add_run(text)
    return new_para


def _insert_hyperlink_after(paragraph: Paragraph, text: str, url: str) -> Paragraph:
    new_para = _insert_after(paragraph, "")
    part = new_para.part
    rel_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rel_id)
    run = OxmlElement("w:r")
    run_props = OxmlElement("w:rPr")
    run_style = OxmlElement("w:rStyle")
    run_style.set(qn("w:val"), "Hyperlink")
    run_props.append(run_style)
    run.append(run_props)
    text_node = OxmlElement("w:t")
    text_node.text = text
    run.append(text_node)
    hyperlink.append(run)
    new_para._p.append(hyperlink)
    return new_para


def _missing_section_strings(doc: Document, requirements: list[dict[str, list[str]]]) -> list[str]:
    missing: list[str] = []
    for requirement in requirements:
        section_text = "\n".join(paragraph.text for paragraph in _section_paragraphs(doc, requirement["heading"]))
        for value in requirement["values"]:
            if value not in section_text:
                missing.append(f"{requirement['heading']}: {value}")
    return missing


def _missing_section_links(doc: Document, requirements: list[dict[str, list[str]]]) -> list[str]:
    missing: list[str] = []
    for requirement in requirements:
        section_index = _heading_index(doc, requirement["heading"])
        if section_index < 0:
            missing.extend(f"{requirement['heading']}: {value}" for value in requirement["values"])
            continue
        for value in _missing_links_for_section(doc, section_index, requirement["values"]):
            missing.append(f"{requirement['heading']}: {value}")
    return missing


def _missing_links_for_section(doc: Document, heading_index: int, links: list[str]) -> list[str]:
    existing = set(_section_hyperlink_targets(doc, heading_index))
    return [link for link in links if link not in existing]


def _section_hyperlink_targets(doc: Document, heading_index: int) -> list[str]:
    targets: list[str] = []
    for paragraph in _section_paragraphs(doc, "", heading_index=heading_index):
        for hyperlink in paragraph._p.findall(".//w:hyperlink", paragraph._p.nsmap):
            rel_id = hyperlink.get(qn("r:id"))
            if rel_id and rel_id in paragraph.part.rels:
                targets.append(paragraph.part.rels[rel_id].target_ref)
    return targets


def _section_paragraphs(doc: Document, heading: str, *, heading_index: int | None = None) -> list[Paragraph]:
    start = heading_index if heading_index is not None else _heading_index(doc, heading)
    if start < 0:
        return []
    end = len(doc.paragraphs)
    for index in range(start + 1, len(doc.paragraphs)):
        style = getattr(doc.paragraphs[index].style, "name", "") or ""
        if style.lower().startswith("heading"):
            end = index
            break
    return list(doc.paragraphs[start + 1 : end])


def _full_text(doc: Document) -> str:
    return "\n".join(paragraph.text for paragraph in doc.paragraphs)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item) for item in value if _clean(item)]


def _section_requirements(value: Any) -> list[dict[str, list[str]]]:
    requirements: list[dict[str, list[str]]] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        heading = _clean(item.get("heading") or item.get("section"))
        values = _string_list(item.get("values") or item.get("strings") or item.get("links") or item.get("urls"))
        if heading and values:
            requirements.append({"heading": heading, "values": values})
    return requirements


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()
