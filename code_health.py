"""Runtime code-size gate for Maya modules.

The 300-line rule is meant to catch oversized runtime modules before they become
hard to reason about. It now counts logical executable lines rather than physical
lines, so detailed comments, blank lines, and docstrings do not punish readable
code. Large live-test/replay scripts are excluded because they are evidence
fixtures, not runtime architecture.

`local_ci.py` treats hard violations as blocking. Urgent/watchlist ranges remain
visible so refactors can be planned before files cross the hard limit.
"""

from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass
from pathlib import Path


LINE_LIMIT = 300
WARNING_MIN = 250
URGENT_MIN = 280


@dataclass(frozen=True)
class FileLineCount:
    path: Path
    lines: int

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class CodeHealth:
    files: list[FileLineCount]
    warnings: list[FileLineCount]
    urgent: list[FileLineCount]
    violations: list[FileLineCount]

    @property
    def ok(self) -> bool:
        return not self.violations


def collect_code_health(root: Path | str = ".") -> CodeHealth:
    root_path = Path(root)
    files = sorted(
        (_count_file(path) for path in root_path.glob("*.py") if not _excluded_from_runtime_gate(path)),
        key=lambda item: item.name,
    )
    warnings = [item for item in files if WARNING_MIN <= item.lines < URGENT_MIN]
    urgent = [item for item in files if URGENT_MIN <= item.lines <= LINE_LIMIT]
    violations = [item for item in files if item.lines > LINE_LIMIT]
    return CodeHealth(files=files, warnings=warnings, urgent=urgent, violations=violations)


def format_code_health(health: CodeHealth) -> str:
    lines = [
        f"limit: {LINE_LIMIT} lines per .py file",
        f"warning_range: {WARNING_MIN}-{URGENT_MIN - 1}",
        f"urgent_range: {URGENT_MIN}-{LINE_LIMIT}",
    ]
    if not health.violations and not health.urgent and not health.warnings:
        lines.append("status: clean")
        return "\n".join(lines)

    if health.violations:
        lines.append("violations: " + _format_counts(health.violations))
    if health.urgent:
        lines.append("urgent_refactor: " + _format_counts(health.urgent))
    if health.warnings:
        lines.append("watchlist: " + _format_counts(health.warnings))
    return "\n".join(lines)


def _count_file(path: Path) -> FileLineCount:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return FileLineCount(path=path, lines=_logical_code_lines(text))


def _logical_code_lines(text: str) -> int:
    code_lines: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type in {
            tokenize.COMMENT,
            tokenize.ENCODING,
            tokenize.ENDMARKER,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.NL,
            tokenize.NEWLINE,
        }:
            continue
        code_lines.add(token.start[0])
    code_lines.difference_update(_docstring_lines(text))
    return len(code_lines)


def _docstring_lines(text: str) -> set[int]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    lines: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if not (
            isinstance(first, ast.Expr)
            and isinstance(getattr(first, "value", None), ast.Constant)
            and isinstance(first.value.value, str)
        ):
            continue
        start = getattr(first, "lineno", 0)
        end = getattr(first, "end_lineno", start)
        lines.update(range(start, end + 1))
    return lines


def _excluded_from_runtime_gate(path: Path) -> bool:
    name = path.name
    return (
        name.startswith("live_")
        or name.endswith("_smoke.py")
        or name.endswith("_fakes.py")
        or "_replay_" in name
        or name.startswith("phase22_")
    )


def _format_counts(items: list[FileLineCount]) -> str:
    return ", ".join(f"{item.name} ({item.lines})" for item in items)


if __name__ == "__main__":
    print(format_code_health(collect_code_health(Path(__file__).resolve().parent)))
