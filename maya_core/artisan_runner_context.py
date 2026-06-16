from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import aiosqlite
from dotenv import load_dotenv

from maya_core.repo_paths import repo_root
from maya_core.cost_tracker import record_usage
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from harness_store import create_approval, init_harness_db, new_run_id, record_event, upsert_run
from office_files import safe_slug
from lane_prompts import ARTISAN_SYSTEM_PROMPT
from project_store import active_project, remember_project_note
from storage import get_preference, upsert_preference
from workspace_paths import is_workspace_path, workspace_dir
from maya_core.artisan_app_qa import qa_artisan_app_project
from maya_core.artisan_maker import complete_blender_maker_output, select_maker_template, write_maker_template_source
from maya_core.artisan_worktree import create_repo_isolation
from maya_core.artisan_runner_models import ArtisanTarget


load_dotenv(repo_root(__file__) / ".env")
