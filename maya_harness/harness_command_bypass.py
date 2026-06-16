from __future__ import annotations

from maya_documents.document_natural_artifact_parser import artifact_intent_clarification
from maya_documents.document_request_parser import document_request


def is_fresh_artifact_request(text: str) -> bool:
    return document_request(text) is not None or artifact_intent_clarification(text) is not None
