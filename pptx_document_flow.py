from __future__ import annotations

import asyncio
from pathlib import Path

from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from pptx_polish_review import claude_polish_grade, local_polish_issues
from office_modern_files import create_pptx
from pptx_quality_gate import inspect_pptx_quality, PptxQualityResult
from pptx_topic_reviser import rebuild_topic_safe
from storage import upsert_preference


async def create_powerpoint_with_qa(
    db_path: str,
    path: Path,
    title: str,
    slides: list[tuple[str, list[str]]],
    run_id: str,
    last_doc_key: str,
    auto_improve: bool = True,
) -> PptxQualityResult:
    await asyncio.to_thread(create_pptx, path, title, slides)
    qa = await asyncio.to_thread(inspect_pptx_quality, path)
    if auto_improve and qa.passed and local_polish_issues(path):
        qa = await asyncio.to_thread(rebuild_topic_safe, path, slides)
        qa.revisions = 1
    await upsert_preference(db_path, last_doc_key, str(path), source="document")
    await record_structured_artifact(
        db_path,
        run_id,
        local_artifact("presentation", str(path), f"PowerPoint QA: {qa.summary()}", "document_actions"),
    )
    if qa.passed:
        issues = local_polish_issues(path)
        polish = "Design polish: draft-level." if issues else (await claude_polish_grade(db_path, path))[0]
        polish = polish.replace("draft level", "draft-level")
        qa.polish = polish
        await record_structured_artifact(
            db_path,
            run_id,
            local_artifact("presentation", str(path), polish, "pptx_polish_review"),
        )
        qa.issues.extend(issues)
    return qa
