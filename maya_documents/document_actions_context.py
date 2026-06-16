from __future__ import annotations

import asyncio
import inspect
import logging
import os
import re
import shutil
from pathlib import Path

from maya_documents.artifact_naming import named_artifact_path, versioned_path
from maya_documents.artifact_sessions import (
    active_artifact_session,
    apply_artifact_edit_delta,
    record_artifact_session,
    topic_from_state,
    update_artifact_session_after_edit,
)
from maya_documents.artifact_parameters import artifact_parameter_question
from maya_documents.artifact_parameter_resolver import resolve_artifact_parameters
from maya_documents.artifact_preflight import ArtifactPreflight, artifact_preflight_with_gemini
from maya_documents.artifact_quality import (
    ArtifactQualityResult,
    extract_docx_text,
    extract_xlsx_text,
    review_artifact_quality,
    resolve_quality_disagreement,
    validate_docx_path,
    validate_html_content,
    validate_xlsx_path,
)
from maya_core.created_file_opener import open_created_file
from maya_documents.document_failures import document_generation_failed
from maya_documents.document_natural_artifact_parser import artifact_intent_clarification
from maya_documents.document_request_parser import document_request, markdown_update
from maya_documents.document_style import style_document_text, style_sections, style_table
from maya_core.html_reviewer import review_html_app
from maya_documents.office_drafter import (
    sections_from_markdown,
    slides_from_markdown,
    spreadsheet_from_markdown,
    word_sections_from_markdown,
)
from maya_documents.office_modern_files import create_docx, create_xlsx
from maya_documents.pptx_document_flow import create_powerpoint_with_qa
from maya_core.presentation_reviewer import review_presentation_slides
from word_quality import word_prompt_context
from word_section_repair import strengthen_word_sections
from maya_harness.harness_artifact_store import record_structured_artifact
from maya_harness.harness_models import local_artifact
from maya_core.markdown_drafter import (
    MarkdownDraft,
    draft_html_with_gemini,
    draft_html_with_artisan,
    draft_markdown_with_gemini,
    html_builder_lane,
    should_use_model_draft,
)
from maya_core.permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text, path_allowed
from maya_core.project_store import active_project, remember_project_note
from storage import get_preference, upsert_preference
from testing_spreadsheet import is_kampung_ai_testing_comparison, kampung_ai_testing_rows
from utils import OSBridge
from visual_workflow import VisualWorkflowRenderer
from workspace_paths import workspace_dir


logger = logging.getLogger("document_actions")
LAST_DOC_KEY = "maya_last_document_path"
LAST_DRAFT_DOC_KEY = "maya_last_draft_document_path"
DIRECT_DOC_RUN_ID = "direct_document_actions"
