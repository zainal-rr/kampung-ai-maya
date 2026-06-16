from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from collections import Counter

from maya_core.assistant_text import strip_wake_prefix
from maya_documents.document_actions_word_helpers import _document_edit_request
from maya_documents.document_natural_artifact_parser import artifact_intent_clarification
from maya_documents.document_request_parser import document_request
from maya_telegram.telegram_commands import parse_command
from voice_command_aliases import spoken_command_alias
from voice_telegram_transcript_cases import FORBIDDEN_TOPIC_NOISE, ReplayCase, build_cases
from voice_transcript_policy import clean_voice_transcript_for_intent, should_park_voice_for_worker


def main() -> None:
    cases = build_cases()
    failures: list[str] = []
    counts: Counter[str] = Counter()
    for index, case in enumerate(cases, start=1):
        counts[case.group] += 1
        failures.extend(_check_case(index, case))
        if len(failures) >= 40:
            break
    if failures:
        raise AssertionError("\n".join(failures))
    parts = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    print(f"voice_telegram_transcript_replay_10000: ok ({len(cases)} cases; {parts})")


def _check_case(index: int, case: ReplayCase) -> list[str]:
    cleaned = clean_voice_transcript_for_intent(strip_wake_prefix(case.text))
    alias = spoken_command_alias(cleaned, channel="telegram", input_type="voice note")
    parsed = document_request(cleaned)
    edit = _document_edit_request(cleaned)
    failures: list[str] = []
    if case.group == "artifact":
        _check_artifact(index, case, cleaned, alias, parsed, edit, failures)
    elif case.group == "edit":
        _check_edit(index, case, cleaned, parsed, edit, failures)
    elif case.group == "command":
        _check_command(index, case, cleaned, alias, parsed, edit, failures)
    elif case.group == "clarification":
        _check_clarification(index, case, cleaned, alias, parsed, edit, failures)
    elif case.group == "park":
        _check_park(index, case, cleaned, parsed, failures)
    elif case.group == "chat":
        _check_chat(index, case, cleaned, alias, parsed, edit, failures)
    return failures


def _check_artifact(index, case, cleaned, alias, parsed, edit, failures) -> None:
    if alias:
        failures.append(_fail(index, case, cleaned, f"unexpected alias {alias!r}"))
    if not parsed:
        failures.append(_fail(index, case, cleaned, "artifact did not parse"))
    elif parsed[0] != case.expected:
        failures.append(_fail(index, case, cleaned, f"kind {parsed[0]!r} != {case.expected!r}"))
    elif _topic_noise(parsed[1]):
        failures.append(_fail(index, case, cleaned, f"topic noise: {parsed!r}"))
    if edit:
        failures.append(_fail(index, case, cleaned, f"artifact misread as edit {edit!r}"))
    if not should_park_voice_for_worker(case.text):
        failures.append(_fail(index, case, cleaned, "artifact did not park paid voice"))


def _check_edit(index, case, cleaned, parsed, edit, failures) -> None:
    if not edit:
        failures.append(_fail(index, case, cleaned, f"edit did not parse; document parser={parsed!r}"))
    if not should_park_voice_for_worker(case.text):
        failures.append(_fail(index, case, cleaned, "edit did not park paid voice"))


def _check_command(index, case, cleaned, alias, parsed, edit, failures) -> None:
    if parsed:
        failures.append(_fail(index, case, cleaned, f"command misread as artifact {parsed!r}"))
    if edit:
        failures.append(_fail(index, case, cleaned, f"command misread as edit {edit!r}"))
    if alias != case.expected:
        failures.append(_fail(index, case, cleaned, f"alias {alias!r} != {case.expected!r}"))
    elif not parse_command(alias):
        failures.append(_fail(index, case, cleaned, f"alias is not a command: {alias!r}"))


def _check_clarification(index, case, cleaned, alias, parsed, edit, failures) -> None:
    clarification = artifact_intent_clarification(cleaned)
    if alias or parsed or edit:
        failures.append(_fail(index, case, cleaned, f"clarification misrouted alias={alias!r} parsed={parsed!r} edit={edit!r}"))
    if not clarification or "Word doc, Excel sheet, or PowerPoint slides" not in clarification:
        failures.append(_fail(index, case, cleaned, f"missing artifact-type clarification: {clarification!r}"))
    if should_park_voice_for_worker(case.text):
        failures.append(_fail(index, case, cleaned, "ambiguous document incorrectly parked paid voice"))


def _check_park(index, case, cleaned, parsed, failures) -> None:
    if parsed:
        failures.append(_fail(index, case, cleaned, f"park case misread as artifact {parsed!r}"))
    if not should_park_voice_for_worker(case.text):
        failures.append(_fail(index, case, cleaned, "long work did not park paid voice"))


def _check_chat(index, case, cleaned, alias, parsed, edit, failures) -> None:
    if alias or parsed or edit:
        failures.append(_fail(index, case, cleaned, f"chat misrouted alias={alias!r} parsed={parsed!r} edit={edit!r}"))
    if should_park_voice_for_worker(case.text):
        failures.append(_fail(index, case, cleaned, "chat incorrectly parked paid voice"))


def _topic_noise(topic: str) -> bool:
    lowered = topic.lower()
    return any(noise in lowered for noise in FORBIDDEN_TOPIC_NOISE)


def _fail(index: int, case: ReplayCase, cleaned: str, issue: str) -> str:
    return f"{index}: {issue} | group={case.group} expected={case.expected!r} raw={case.text!r} cleaned={cleaned!r}"


if __name__ == "__main__":
    main()
