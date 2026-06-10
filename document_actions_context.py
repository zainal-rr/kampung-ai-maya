from __future__ import annotations

import asyncio
import inspect
import logging
import os
import re
import shutil
from pathlib import Path

from artifact_naming import named_artifact_path, versioned_path
from artifact_sessions import (
    active_artifact_session,
    apply_artifact_edit_delta,
    record_artifact_session,
    topic_from_state,
    update_artifact_session_after_edit,
)
from artifact_parameters import artifact_parameter_question
from artifact_parameter_resolver import resolve_artifact_parameters
from artifact_preflight import ArtifactPreflight, artifact_preflight_with_gemini
from artifact_quality import (
    ArtifactQualityResult,
    extract_docx_text,
    extract_xlsx_text,
    review_artifact_quality,
    validate_docx_path,
    validate_html_content,
    validate_xlsx_path,
)
from created_file_opener import open_created_file
from document_failures import document_generation_failed
from document_natural_artifact_parser import artifact_intent_clarification
from document_request_parser import document_request, markdown_update
from document_style import style_document_text, style_sections, style_table
from html_reviewer import review_html_app
from office_drafter import (
    sections_from_markdown,
    slides_from_markdown,
    spreadsheet_from_markdown,
    word_sections_from_markdown,
)
from office_modern_files import create_docx, create_xlsx
from pptx_document_flow import create_powerpoint_with_qa
from presentation_reviewer import review_presentation_slides
from word_quality import word_prompt_context
from word_section_repair import strengthen_word_sections
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from markdown_drafter import (
    MarkdownDraft,
    draft_html_with_gemini,
    draft_html_with_artisan,
    draft_markdown_with_gemini,
    html_builder_lane,
    should_use_model_draft,
)
from permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text, path_allowed
from project_store import active_project, remember_project_note
from storage import get_preference, upsert_preference
from testing_spreadsheet import is_kampung_ai_testing_comparison, kampung_ai_testing_rows
from utils import OSBridge
from visual_workflow import VisualWorkflowRenderer
from workspace_paths import workspace_dir


logger = logging.getLogger("document_actions")
LAST_DOC_KEY = "maya_last_document_path"
LAST_DRAFT_DOC_KEY = "maya_last_draft_document_path"
DIRECT_DOC_RUN_ID = "direct_document_actions"
