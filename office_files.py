from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "maya-work"


def create_docx(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [_paragraph(title, "Title")]
    for heading, lines in sections:
        body.append(_paragraph(heading, "Heading1"))
        body.extend(_paragraph(line) for line in lines)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body)}<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
        "</w:sectPr></w:body></w:document>"
    )
    with ZipFile(path, "w", ZIP_DEFLATED) as doc:
        doc.writestr("[Content_Types].xml", _docx_content_types())
        doc.writestr("_rels/.rels", _docx_rels())
        doc.writestr("word/document.xml", document)
    return path


def create_pptx(path: Path, title: str, slides: list[tuple[str, list[str]]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", ZIP_DEFLATED) as deck:
        deck.writestr("[Content_Types].xml", _pptx_content_types(len(slides)))
        deck.writestr("_rels/.rels", _pptx_root_rels())
        deck.writestr("ppt/presentation.xml", _presentation_xml(len(slides)))
        deck.writestr("ppt/_rels/presentation.xml.rels", _presentation_rels(len(slides)))
        deck.writestr("ppt/theme/theme1.xml", _theme_xml())
        deck.writestr("ppt/slideMasters/slideMaster1.xml", _simple_layout_xml("master"))
        deck.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _master_rels())
        deck.writestr("ppt/slideLayouts/slideLayout1.xml", _simple_layout_xml("layout"))
        deck.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _layout_rels())
        for index, (heading, bullets) in enumerate(slides, start=1):
            deck.writestr(f"ppt/slides/slide{index}.xml", _slide_xml(heading, bullets))
            deck.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", _slide_rels())
    return path


def create_xlsx(path: Path, title: str, headers: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", _xlsx_content_types())
        book.writestr("_rels/.rels", _xlsx_root_rels())
        book.writestr("xl/workbook.xml", _xlsx_workbook())
        book.writestr("xl/_rels/workbook.xml.rels", _xlsx_workbook_rels())
        book.writestr("xl/styles.xml", _xlsx_styles())
        book.writestr("xl/worksheets/sheet1.xml", _xlsx_sheet(title, headers, rows))
    return path


def presentation_outline(topic: str) -> list[tuple[str, list[str]]]:
    topic_title = topic.strip().title()
    return [
        (topic_title, [f"A concise presentation on {topic.strip()}", "Prepared by Maya"]),
        ("Why It Matters", ["What the topic changes", "Where people encounter it", "Why timing matters"]),
        ("Core Ideas", ["Key concept 1", "Key concept 2", "Key concept 3"]),
        ("Practical Uses", ["Real world use cases", "Risks or limits", "What to watch next"]),
        ("Discussion", ["Main takeaway", "Questions to decide", "Next research step"]),
    ]


def spreadsheet_rows(topic: str) -> tuple[list[str], list[list[str]]]:
    lowered = topic.lower()
    if any(word in lowered for word in ("budget", "cost", "money", "expense")):
        return (
            ["Item", "Category", "Estimated Cost", "Actual Cost", "Notes"],
            [
                ["Example item", "Planning", "0", "", "Replace with real value"],
                ["Total", "", "=SUM(C3:C3)", "=SUM(D3:D3)", "Draft formula"],
            ],
        )
    if any(word in lowered for word in ("flight", "compare", "comparison")):
        return (
            ["Option", "Provider", "Date", "Price", "Pros", "Cons"],
            [["Option 1", "", "", "", "Add advantage", "Add tradeoff"]],
        )
    return (
        ["Topic", "Detail", "Status", "Owner", "Notes"],
        [[topic.strip().title(), "Draft entry", "To review", "Zainal", "Created by Maya"]],
    )


def _paragraph(text: str, style: str | None = None) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{style_xml}<w:r><w:t>{escape(text)}</w:t></w:r></w:p>"


def _docx_content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )


def _docx_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )


def _pptx_content_types(count: int) -> str:
    slides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/ppt/presentation.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        f"{slides}</Types>"
    )


def _pptx_root_rels() -> str:
    return _rels([("rId1", "officeDocument", "ppt/presentation.xml")])


def _presentation_rels(count: int) -> str:
    rels = [("rId1", "slideMaster", "slideMasters/slideMaster1.xml")]
    rels += [(f"rId{i + 1}", "slide", f"slides/slide{i}.xml") for i in range(1, count + 1)]
    return _rels(rels, office=True)


def _presentation_xml(count: int) -> str:
    ids = "".join(f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, count + 1))
    return (
        '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx=\"12192000\" cy=\"6858000\" type=\"screen16x9\"/>"
        "</p:presentation>"
    )


def _slide_xml(title: str, bullets: list[str]) -> str:
    body = "".join(f"<a:p><a:r><a:t>{escape(item)}</a:t></a:r></a:p>" for item in bullets)
    return (
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        f'{_shape(2, "Title", 700000, 400000, 10800000, 900000, [title], 3400)}'
        f'{_shape(3, "Body", 900000, 1700000, 10300000, 4200000, bullets, 2100)}'
        '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    )


def _shape(shape_id: int, name: str, x: int, y: int, cx: int, cy: int, lines: list[str], size: int) -> str:
    paragraphs = "".join(f'<a:p><a:r><a:rPr sz="{size}"/><a:t>{escape(line)}</a:t></a:r></a:p>' for line in lines)
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm></p:spPr>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/>{paragraphs}</p:txBody></p:sp>'
    )


def _simple_layout_xml(kind: str) -> str:
    tag = "sldMaster" if kind == "master" else "sldLayout"
    return f'<p:{tag} xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld></p:{tag}>'


def _master_rels() -> str:
    return _rels([("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"), ("rId2", "theme", "../theme/theme1.xml")], True)


def _layout_rels() -> str:
    return _rels([("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")], True)


def _slide_rels() -> str:
    return _rels([("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml")], True)


def _rels(items: list[tuple[str, str, str]], office: bool = False) -> str:
    base = "http://schemas.openxmlformats.org/officeDocument/2006/relationships" if office else "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    rows = "".join(f'<Relationship Id="{rid}" Type="{base}/{kind}" Target="{target}"/>' for rid, kind, target in items)
    return f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rows}</Relationships>'


def _theme_xml() -> str:
    return '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Maya"><a:themeElements><a:clrScheme name="Maya"/></a:themeElements></a:theme>'


def _xlsx_content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )


def _xlsx_root_rels() -> str:
    return _rels([("rId1", "officeDocument", "xl/workbook.xml")])


def _xlsx_workbook_rels() -> str:
    return _rels([("rId1", "worksheet", "worksheets/sheet1.xml"), ("rId2", "styles", "styles.xml")], True)


def _xlsx_workbook() -> str:
    return (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Maya Draft" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )


def _xlsx_styles() -> str:
    return '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cellXfs count="1"><xf numFmtId="0"/></cellXfs></styleSheet>'


def _xlsx_sheet(title: str, headers: list[str], rows: list[list[str]]) -> str:
    all_rows = [[title], [], headers] + rows
    body = "".join(_xlsx_row(index, row) for index, row in enumerate(all_rows, start=1))
    return f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>'


def _xlsx_row(index: int, values: list[str]) -> str:
    cells = "".join(_xlsx_cell(index, col, value) for col, value in enumerate(values, start=1))
    return f'<row r="{index}">{cells}</row>'


def _xlsx_cell(row: int, col: int, value: str) -> str:
    ref = f"{chr(64 + col)}{row}"
    if value.startswith("="):
        return f'<c r="{ref}"><f>{escape(value[1:])}</f></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
