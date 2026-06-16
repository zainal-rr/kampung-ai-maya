from __future__ import annotations

"""Evidence records for live browser reliability runs.

Each live run produces one 8-field record: user request, parsed intent,
attempted browser steps, final page state, extracted answer, safety boundary,
evidence artifacts (screenshots, page text), and a pass/partial/fail label.
Records are written as append-only JSONL so a crashed night loses nothing.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


LIVE_RELIABILITY_DIR = Path("logs") / "live_tests" / "reliability"
MAX_STEP_TEXT = 300
MAX_FINAL_TEXT = 12000
MAX_ANSWER_TEXT = 4000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class StepRecord:
    at: str
    action: str
    target: str = ""
    value: str = ""
    result: str = ""
    url: str = ""
    title: str = ""
    text_hash: str = ""


@dataclass
class BrowserRunRecord:
    run_id: str
    night_id: str
    lane: str
    prompt: str
    parsed_intent: dict = field(default_factory=dict)
    route_skill: str = ""
    route_reason: str = ""
    steps: list = field(default_factory=list)
    final_url: str = ""
    final_title: str = ""
    final_text_hash: str = ""
    final_text: str = ""
    extracted: list = field(default_factory=list)
    answer: str = ""
    safety_boundary: str = ""
    safety_stop: bool = False
    screenshots: list = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    status: str = "not-run"
    reasons: list = field(default_factory=list)
    recovered: bool = False


class BrowserRunRecorder:
    """Collects intent, route, and browser steps for one live run."""

    def __init__(self, run_id: str, night_id: str, lane: str, prompt: str):
        self.record = BrowserRunRecord(run_id, night_id, lane, prompt, started_at=utc_now())

    def note_intent(self, payload: dict) -> None:
        for key, value in payload.items():
            self.record.parsed_intent[str(key)] = _short(str(value), MAX_STEP_TEXT)

    def note_route(self, skill: str, reason: str) -> None:
        self.record.route_skill = skill
        self.record.route_reason = reason

    def record_step(
        self,
        action: str,
        *,
        target: str = "",
        value: str = "",
        result: str = "",
        url: str = "",
        title: str = "",
        text_hash: str = "",
    ) -> None:
        self.record.steps.append(
            StepRecord(
                utc_now(),
                action,
                _short(target, MAX_STEP_TEXT),
                _short(value, MAX_STEP_TEXT),
                _short(result, MAX_STEP_TEXT),
                _short(url, MAX_STEP_TEXT),
                _short(title, MAX_STEP_TEXT),
                text_hash,
            )
        )

    def add_screenshot(self, path: str) -> None:
        if path:
            self.record.screenshots.append(path)

    def finalize(
        self,
        *,
        answer: str,
        final_url: str = "",
        final_title: str = "",
        final_text: str = "",
        final_text_hash: str = "",
        extracted: tuple | list = (),
        safety_boundary: str = "",
        safety_stop: bool = False,
    ) -> BrowserRunRecord:
        record = self.record
        record.answer = _short(answer, MAX_ANSWER_TEXT)
        record.final_url = _short(final_url, MAX_STEP_TEXT)
        record.final_title = _short(final_title, MAX_STEP_TEXT)
        record.final_text = _short(final_text, MAX_FINAL_TEXT)
        record.final_text_hash = final_text_hash
        record.extracted = [_short(str(item), MAX_STEP_TEXT) for item in extracted][:8]
        record.safety_boundary = _short(safety_boundary, MAX_ANSWER_TEXT)
        record.safety_stop = safety_stop
        record.finished_at = utc_now()
        return record


def redact(value: str) -> str:
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "<REDACTED_EMAIL>", value)
    value = re.sub(r"\b(?:\d[ -]*?){13,16}\b", "<REDACTED_CARD>", value)
    value = re.sub(r"\bZainal\s+Abidin\s+Bin\s+Jamal\b", "<REDACTED_ACCOUNT_NAME>", value, flags=re.I)
    return value


def run_to_dict(record: BrowserRunRecord) -> dict:
    return _redact_value(asdict(record))


def append_run(record: BrowserRunRecord, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run_to_dict(record), ensure_ascii=False) + "\n")


def load_runs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    runs = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return runs


def night_summary(runs: list[dict]) -> dict:
    lanes: dict[str, dict] = {}
    for run in runs:
        lane = lanes.setdefault(run.get("lane", "?"), {"total": 0, "pass": 0, "partial": 0, "fail": 0})
        lane["total"] += 1
        status = run.get("status", "fail")
        lane[status if status in ("pass", "partial", "fail") else "fail"] += 1
    work = [run for run in runs if run.get("lane") != "safety"]
    safety = [run for run in runs if run.get("lane") == "safety"]
    passed = sum(1 for run in work if run.get("status") == "pass")
    return {
        "total": len(runs),
        "lanes": lanes,
        "completion_rate": round(passed / len(work) * 100, 1) if work else 0.0,
        "safety_total": len(safety),
        "safety_passed": sum(1 for run in safety if run.get("status") == "pass"),
        "stale_context_criticals": _count_reason(runs, "critical:stale-context"),
        "hallucination_criticals": _count_reason(runs, "critical:hallucination"),
        "honesty_criticals": _count_reason(runs, "critical:honesty"),
        "safety_criticals": _count_reason(runs, "critical:safety"),
        "recovered_runs": sum(1 for run in runs if run.get("recovered")),
    }


def write_night_markdown(runs: list[dict], path: Path) -> None:
    summary = night_summary(runs)
    lines = [
        f"# Browser Reliability Night {runs[0]['night_id'] if runs else ''}",
        "",
        f"completion: {summary['completion_rate']}% | safety stops: "
        f"{summary['safety_passed']}/{summary['safety_total']} | "
        f"stale criticals: {summary['stale_context_criticals']} | "
        f"hallucination criticals: {summary['hallucination_criticals']} | "
        f"honesty criticals: {summary['honesty_criticals']}",
        "",
    ]
    for lane, stats in sorted(summary["lanes"].items()):
        lines.append(f"- {lane}: {stats['pass']} pass / {stats['partial']} partial / {stats['fail']} fail")
    lines.append("")
    for run in runs:
        lines.append(f"## {run['run_id']} [{run.get('status', '?').upper()}]")
        lines.append(f"prompt: {run.get('prompt', '')}")
        lines.append(f"route: {run.get('route_skill', '')} | url: {run.get('final_url', '')}")
        intent = run.get("parsed_intent") or {}
        if intent:
            lines.append("intent: " + "; ".join(f"{key}={value}" for key, value in intent.items()))
        steps = run.get("steps") or []
        lines.append(f"steps: {len(steps)}")
        for step in steps[:14]:
            detail = step.get("result") or step.get("url") or step.get("value")
            lines.append(f"  - {step.get('action', '')}: {step.get('target', '')} {detail}".rstrip())
        for item in run.get("extracted") or []:
            lines.append(f"extracted: {item}")
        for shot in run.get("screenshots") or []:
            lines.append(f"screenshot: {shot}")
        for reason in run.get("reasons") or []:
            lines.append(f"reason: {reason}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", "utf-8")


def _count_reason(runs: list[dict], prefix: str) -> int:
    return sum(1 for run in runs if any(str(reason).startswith(prefix) for reason in run.get("reasons", [])))


def _redact_value(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    return value


def _short(value: str, limit: int) -> str:
    cleaned = str(value)
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."
