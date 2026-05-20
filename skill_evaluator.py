from __future__ import annotations

from pathlib import Path

from skill_learning_store import EVALUATION_TESTS


def evaluate_skill_scaffold(scaffold_path: str) -> dict[str, tuple[str, str]]:
    path = Path(scaffold_path) if scaffold_path else None
    if path is None or not path.exists() or not path.is_file():
        return {test: ("failed", "Scaffold file is missing.") for test in sorted(EVALUATION_TESTS)}
    text = path.read_text("utf-8")
    lowered = text.lower()
    placeholders = (
        "define the natural phrases",
        "define phrases that should not",
        "list local files",
        "safe actions:\n- confirmation actions:",
        "unit or smoke test:\n- safety test:",
    )
    has_placeholders = any(marker in lowered for marker in placeholders)
    checks = {
        "trigger": ("## trigger phrases" in lowered and "trigger:" in lowered, "Concrete trigger examples exist."),
        "non_trigger": ("non-trigger:" in lowered, "Concrete non-trigger boundary exists."),
        "safety": ("## safety" in lowered and "hard no:" in lowered, "Concrete safety boundary exists."),
        "happy_path": ("happy path:" in lowered and "success:" in lowered, "Concrete happy path exists."),
        "failure_path": ("failure path:" in lowered and ("rollback" in lowered or "cancel" in lowered), "Concrete failure path exists."),
        "regression": ("regression:" in lowered and "expected:" in lowered, "Concrete regression expectation exists."),
    }
    return {
        test_type: ("passed" if passed and not has_placeholders else "failed", note if passed and not has_placeholders else f"Missing concrete {test_type} scaffold requirement.")
        for test_type, (passed, note) in checks.items()
    }
