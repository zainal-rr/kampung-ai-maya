from __future__ import annotations

from artisan_runner_context import *
from artisan_runner_postprocess import _result, _write_transcript
from safe_paths import scrubbed_subprocess_env


def build_codex_command(target: ArtisanTarget, final_path: Path, prompt: str) -> list[str]:
    """Worktree-confined Codex invocation (W5-1/S4): --cd and --add-dir pin the
    working set to the target worktree, --sandbox workspace-write keeps Codex's
    own enforcement on. Extracted so the canary can assert confinement."""
    cmd = [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--json",
        "--output-last-message",
        str(final_path),
        "--cd",
        str(target.cwd),
        "--add-dir",
        str(target.cwd),
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
    ]
    model = os.getenv("ARTISAN_CODEX_MODEL", "").strip()
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)
    return cmd


async def _run_artisan_engine(run_id: str, request: str, target: ArtisanTarget, brief: str) -> dict:
    return await _run_codex(run_id, request, target, brief)


async def _run_codex(run_id: str, request: str, target: ArtisanTarget, brief: str) -> dict:
    prompt = _artisan_prompt(request, target, brief)
    if os.getenv("ARTISAN_DRY_RUN") == "1" or not shutil.which("codex"):
        return await _dry_run_result(run_id, target, prompt)
    auth_ok, auth_status = _codex_chatgpt_auth_state()
    if not auth_ok:
        message = (
            "Codex subscription auth guard blocked Artisan. "
            "Run `codex login` and confirm `codex login status` says `Logged in using ChatGPT`. "
            f"Current status: {auth_status}"
        )
        return _result("failed", message, b"", message.encode("utf-8"), run_id)
    transcript_path = _transcript_path(run_id)
    final_path = transcript_path.with_suffix(".final.txt")
    cmd = build_codex_command(target, final_path, prompt)
    timeout = int(os.getenv("ARTISAN_TIMEOUT_SECONDS", "300"))
    # W5-1 (S4): generated code runs worktree-confined with a scrubbed
    # environment — no credential-shaped env vars reach the child process.
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(target.cwd),
        env=scrubbed_subprocess_env(),
        stdin=subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        stdout, stderr = await proc.communicate()
        return _result("failed", "Codex timed out.", stdout, stderr, run_id, final_path=final_path)
    return _result("completed" if proc.returncode == 0 else "failed", "", stdout, stderr, run_id, final_path=final_path)


def _codex_chatgpt_auth_state() -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["codex", "login", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return False, f"unable to check Codex login: {exc}"
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    normalized = output.lower()
    if "logged in using chatgpt" in normalized:
        return True, output or "Logged in using ChatGPT"
    return False, output or "not logged in using ChatGPT"


async def _run_maker_template_source(run_id: str, target: ArtisanTarget, plan) -> dict:
    script = write_maker_template_source(target.cwd, plan)
    transcript = _write_transcript(run_id, {"maker_template": plan.as_dict(), "source_script": str(script)})
    return {
        "status": "completed",
        "status_note": "maker template source written",
        "summary": (
            f"Maya selected the `{plan.template_id}` maker template before Codex because this is a known simple printable object. "
            f"Source written: {script}. Blender export and validation will run locally."
        ),
        "session_id": "",
        "tests_run": ["maker template source written"],
        "transcript_path": transcript,
        "maker_template": plan.as_dict(),
    }


async def _dry_run_result(run_id: str, target: ArtisanTarget, prompt: str) -> dict:
    transcript = _write_transcript(run_id, {"dry_run": True, "prompt": prompt})
    return {
        "status": "completed",
        "status_note": "dry run captured",
        "summary": f"Dry run: Artisan would run Codex in {target.cwd}.",
        "session_id": "",
        "tests_run": [],
        "transcript_path": transcript,
        "dry_run": True,
    }


def _artisan_prompt(request: str, target: ArtisanTarget, brief: str) -> str:
    app_note = ""
    if target.workflow_type == "artisan_app":
        app_note = (
            "\nApp-building rule: create or edit a real project in this working directory. "
            "Include `index.html`, linked CSS/JS or equivalent source files, `README.md` with open/run instructions, "
            "and visible UI text for the requested features. Do not paste code into chat as the deliverable. "
            "If this is an edit follow-up, modify the existing app in place instead of creating a new app folder."
        )
    maker_note = ""
    if target.workflow_type == "artisan_3d":
        maker_note = (
            "\nBlender / 3D printing rule: write the Blender Python generator script first, before any long explanation or export attempt. "
            "Do not run Blender yourself unless the source and README are already written. Maya will run Blender locally after your turn "
            "to export and validate `.blend` and `.stl` files. Create editable Blender/Python/STL-ready assets only. "
            "Do not slice, upload, connect to a printer, or start a physical print."
        )
    repo_note = ""
    if target.approval_state == "repo_approval_required":
        repo_note = _repo_prompt_note(target)
    return (
        f"{ARTISAN_SYSTEM_PROMPT}\n\n"
        "You are being called by Maya's Artisan runtime. Maya owns routing, memory, safety, and user communication.\n"
        "Gemini has already created the required build brief below. Follow it unless it conflicts with safety or repo rules.\n\n"
        f"Working directory: {target.cwd}\n"
        f"Permission mode: {target.permission_mode}\n"
        f"Approval state: {target.approval_state}\n"
        f"Isolation mode: {target.isolation_mode}\n"
        f"Original repo path: {target.original_repo_path or ''}\n"
        f"Base ref: {target.base_ref}\n"
        f"Original repo dirty status: {target.dirty_summary}\n"
        f"{app_note}{maker_note}{repo_note}\n\n"
        f"Gemini build brief:\n{brief}\n\n"
        f"User request:\n{request}\n\n"
        "Return a concise final summary with files changed, tests/checks run, and any approval needed."
    )


def _repo_prompt_note(target: ArtisanTarget) -> str:
    if target.isolation_mode == "git_worktree":
        return (
            "\nRepo isolation rule: this is an isolated Git worktree. You may edit files here, "
            "but you must not commit, push, reset, rebase, merge, delete the worktree, or touch the original repo path. "
            "Summarize the changed files and tests. The changes require Zainal approval before anything is applied "
            "back to the original repo."
        )
    return (
        "\nRepo isolation rule: no isolated worktree is available. Do not edit files. "
        "Inspect, plan, and propose the smallest patch only."
    )


def _repo_approval_details(target: ArtisanTarget, changed_files: list[str]) -> str:
    changed = ", ".join(changed_files[:12]) if changed_files else "no changed files recorded"
    return (
        "Repo changes require Zainal approval before applying anything to the main working tree. "
        f"Original repo: {target.original_repo_path or ''}. "
        f"Isolated worktree: {target.cwd}. "
        f"Base ref: {target.base_ref or 'unknown'}. "
        f"Original dirty status: {target.dirty_summary or 'unknown'}. "
        f"Changed files: {changed}."
    )


def _blender_available() -> bool:
    return bool(shutil.which("blender") or Path("/Applications/Blender.app").exists())
