from __future__ import annotations

import os


def artifact_qa_max_attempts(artifact_type: str, default: int = 3) -> int:
    specific = f"{artifact_type.upper()}_QA_MAX_ATTEMPTS"
    raw = os.getenv(specific) or os.getenv("ARTIFACT_QA_MAX_ATTEMPTS") or str(default)
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(1, min(10, value))


def qa_retry_exhausted_message(label: str, attempts: int) -> str:
    return (
        f"I could not get the {label} through QA after {attempts} internal attempt"
        f"{'s' if attempts != 1 else ''}. I kept it as a draft and I am not calling it final. "
        "Ask me for the draft if you want to inspect it, or use the attached draft if I sent one."
    )
