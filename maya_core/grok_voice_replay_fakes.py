from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from openpyxl import Workbook
from pptx import Presentation

from maya_documents.document_request_parser import document_request
from maya_core.storage import upsert_preference
from maya_travel.travel_budget_plan import _parse_plan_updates


class FastReplayDocuments:
    def __init__(self, db_path: str, workspace: Path):
        self.db_path = db_path
        self.workspace = workspace
        self.last_model_lane = ""
        self.last_cost_recorded = False

    async def handle(self, text: str, channel: str) -> str | None:
        edit = re.match(r"^(?:update|edit|change)\s+(?:that|the latest|the last|document|workbook|deck).*$", text, re.I)
        if edit:
            return "Done. I updated the latest document in place. I kept an internal backup before editing."
        request = document_request(text)
        if not request:
            return None
        kind, topic, _project_scoped = request
        self.last_cost_recorded = True
        if kind == "docx":
            path = self._path("documents", topic, "docx")
            self._docx(path, topic)
            self.last_model_lane = "replay Word artifact worker + local Word QA"
        elif kind == "xlsx":
            path = self._path("spreadsheets", topic, "xlsx")
            self._xlsx(path, topic)
            self.last_model_lane = "replay Excel artifact worker + local Excel QA"
        elif kind == "pptx":
            path = self._path("presentations", topic, "pptx")
            self._pptx(path, topic)
            self.last_model_lane = "replay PowerPoint artifact worker + visual QA"
        elif kind == "html":
            path = self._path("artifacts", topic, "html")
            path.write_text("<!DOCTYPE html><html><body><main>Replay app</main></body></html>", "utf-8")
            self.last_model_lane = "replay HTML artifact worker + local HTML QA"
        else:
            return None
        await upsert_preference(self.db_path, "maya_last_document_path", str(path), source="document")
        return f"Done. I created a {kind} replay artifact at {path}. I opened it on the iMac."

    def _path(self, folder: str, topic: str, suffix: str) -> Path:
        path = self.workspace / folder / f"{_slug(topic)}-replay.{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _docx(path: Path, topic: str) -> None:
        doc = Document()
        doc.add_heading(topic.title(), level=1)
        doc.add_paragraph("Replay artifact with useful content, summary, and structure.")
        doc.save(path)

    @staticmethod
    def _xlsx(path: Path, topic: str) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = "Travel Budget"
        ws.append(["Item", "Estimated MYR", "Actual MYR", "Variance", "Notes"])
        plan = _parse_plan_updates(topic)
        ws.append(["Flight", plan.get("selected_flight_price_myr", ""), "", '=IF(OR(B2="",C2=""),"",C2-B2)', "Flight price from transcript"])
        ws.append(["Stay", plan.get("selected_stay_price_myr", ""), "", '=IF(OR(B3="",C3=""),"",C3-B3)', plan.get("stay_price_notes", "Stay price from transcript")])
        ws.append(["Food", 250, "", '=IF(OR(B4="",C4=""),"",C4-B4)', "Restaurant budget starter"])
        ws.append(["Total", "=SUM(B2:B4)", "=SUM(C2:C4)", "=SUM(D2:D4)", ""])
        wb.save(path)

    @staticmethod
    def _pptx(path: Path, topic: str) -> None:
        deck = Presentation()
        for idx in range(1, 4):
            slide = deck.slides.add_slide(deck.slide_layouts[1])
            slide.shapes.title.text = f"{topic.title()} {idx}"
            slide.placeholders[1].text = "Short visible text"
            slide.notes_slide.notes_text_frame.text = "Presenter notes for replay verification."
        deck.save(path)


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text[:48] or "artifact"
