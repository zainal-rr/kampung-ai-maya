from __future__ import annotations

from artisan_runner_context import *


async def _post_process_artisan_output(
    target: ArtisanTarget,
    request: str,
    brief: str,
    result: dict,
    changed_files: list[str],
) -> dict:
    if result.get("dry_run"):
        return {}
    if target.workflow_type == "artisan_app":
        qa = qa_artisan_app_project(target.cwd, request=request, brief=brief, changed_files=changed_files)
        if qa.passed:
            result["status"] = "completed"
            result["status_note"] = "Artisan app QA passed."
            result["summary"] = _append_summary(result["summary"], qa.summary + " " + "; ".join(qa.checks[:8]))
        else:
            result["status"] = "failed"
            result["status_note"] = "Artisan app QA failed."
            result["summary"] = _append_summary(result["summary"], qa.summary + " Issues: " + "; ".join(qa.issues[:8]))
        return {"app_qa": qa.as_dict()}
    if target.workflow_type == "artisan_3d":
        maker = complete_blender_maker_output(target.cwd, request=request, brief=brief)
        if maker.passed:
            result["status"] = "completed"
            result["status_note"] = "Blender maker QA passed."
            recovery = ""
            if "timed out" in result.get("summary", "").lower():
                if any("fallback" in item.lower() for item in maker.warnings):
                    recovery = " Codex timed out before producing usable maker output, so Maya used a constrained local fallback and completed Blender export/validation."
                else:
                    recovery = " Codex timed out after producing maker source, then Maya completed local Blender export and validation."
            result["summary"] = _append_summary(result["summary"], maker.summary + recovery + " " + "; ".join(maker.checks[:8]))
        else:
            result["status"] = "failed"
            result["status_note"] = "Blender maker QA failed."
            result["summary"] = _append_summary(result["summary"], maker.summary + " Issues: " + "; ".join(maker.issues[:8]))
        return {"maker_qa": maker.as_dict()}
    return {}


def _append_summary(original: str, addition: str) -> str:
    original = (original or "").strip()
    addition = (addition or "").strip()
    if not original:
        return addition
    if not addition:
        return original
    return f"{original}\n\n{addition}"


def _result(status: str, fallback: str, stdout: bytes, stderr: bytes, run_id: str, final_path: Path | None = None) -> dict:
    raw_out = stdout.decode("utf-8", "replace")
    raw_err = stderr.decode("utf-8", "replace")
    transcript = _write_transcript(run_id, {"stdout": raw_out, "stderr": raw_err, "status": status})
    parsed = _parse_json(raw_out)
    final_text = _read_text(final_path) if final_path else ""
    summary = _summary_from_output(parsed, final_text or raw_out, raw_err, fallback)
    return {
        "status": status,
        "status_note": summary[:200],
        "summary": summary,
        "session_id": str(parsed.get("session_id") or parsed.get("sessionId") or ""),
        "tests_run": _tests_from_summary(summary),
        "transcript_path": transcript,
    }


def _write_transcript(run_id: str, payload: dict) -> str:
    path = _transcript_path(run_id)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
    return str(path)


def _transcript_path(run_id: str) -> Path:
    folder = workspace_dir("reports", create=True) / "artisan"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{run_id}.json"


def _parse_json(text: str) -> dict:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"result": data}
    except json.JSONDecodeError:
        return {}


def _summary_from_output(parsed: dict, stdout: str, stderr: str, fallback: str) -> str:
    for key in ("result", "summary", "message", "text"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    combined = "\n".join(part for part in (stdout.strip(), stderr.strip(), fallback) if part)
    return combined[:2000] or "Codex returned no summary."


def _read_text(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    try:
        return path.read_text("utf-8")
    except OSError:
        return ""


def _tests_from_summary(summary: str) -> list[str]:
    tests = []
    for line in summary.splitlines():
        if re.search(r"\b(test|pytest|npm test|smoke|build)\b", line, re.I):
            tests.append(line.strip()[:160])
    return tests[:12]


def _file_snapshot(path: Path) -> set[str]:
    if not path.exists():
        return set()
    files: set[str] = set()
    for item in path.rglob("*"):
        if not item.is_file() or any(part in {"node_modules", ".git", "__pycache__"} for part in item.parts):
            continue
        try:
            files.add(str(item.relative_to(path)))
        except ValueError:
            continue
    return files


def _compact(text: str, limit: int = 500) -> str:
    clean = " ".join(str(text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


async def _record_artifacts(db_path: str, run_id: str, target: ArtisanTarget, changed: list[str], result: dict) -> None:
    await record_structured_artifact(
        db_path,
        run_id,
        local_artifact("artisan_workspace", str(target.cwd), result["summary"][:500], "artisan_runner"),
    )
    for item in changed[:20]:
        await record_structured_artifact(
            db_path,
            run_id,
            local_artifact("artisan_file", str(target.cwd / item), "Artisan changed or created this file.", "artisan_runner"),
        )
