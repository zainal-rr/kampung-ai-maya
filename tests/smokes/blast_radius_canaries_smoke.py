"""W5-1 blast-radius canaries (S1-S7).

Spec: docs/blast_radius_and_retrieval_design_2026-06-12.md.
These assert the filesystem path jail and Artisan env scrub. They were written
to FAIL before safe_paths.py existed (canaries-first discipline).
"""

from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from safe_paths import (  # noqa: E402
    HONEST_LIMIT,
    resolve_safe_path,
    scrubbed_subprocess_env,
)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> None:
    home = Path.home()

    # S1 — credential read denied, even when "explicitly instructed".
    s1 = resolve_safe_path(str(home / ".ssh" / "id_rsa"), "read")
    _require(not s1.allowed, f"S1 FAILED: credential read allowed ({s1})")

    # S2 — out-of-jail write denied; allowed-root write allowed. Uses the temp
    # dir (an allowed root) so the canary is portable across iMac and CI.
    out = resolve_safe_path("/etc/cron.d/evil", "write")
    _require(not out.allowed, f"S2 FAILED: out-of-jail write allowed ({out})")
    with tempfile.TemporaryDirectory() as d:
        inside = resolve_safe_path(str(Path(d) / "report.docx"), "write")
        _require(inside.allowed, f"S2 FAILED: allowed-root write denied ({inside})")

    # S3 — denylist overrides allowlist: a credential file under an allowed root.
    with tempfile.TemporaryDirectory() as d:
        planted = resolve_safe_path(str(Path(d) / "id_rsa"), "read")
        _require(not planted.allowed, f"S3 FAILED: id_rsa under allowed root allowed ({planted})")
        dotenv = resolve_safe_path(str(Path(d) / ".env"), "read")
        _require(not dotenv.allowed, f"S3 FAILED: .env under allowed root allowed ({dotenv})")

    # S4 — Artisan env scrub: credential-shaped vars never reach the child.
    base = {"OPENAI_API_KEY": "sk-x", "AWS_SECRET_ACCESS_KEY": "y",
            "DB_PASSWORD": "z", "PATH": "/usr/bin", "HOME": "/home/x", "LANG": "C"}
    scrubbed = scrubbed_subprocess_env(base)
    for leaked in ("OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "DB_PASSWORD"):
        _require(leaked not in scrubbed, f"S4 FAILED: {leaked} leaked to child env")
    for kept in ("PATH", "HOME", "LANG"):
        _require(kept in scrubbed, f"S4 FAILED: {kept} wrongly stripped")

    # S5 — chokepoint exclusivity: the path-taking tools route through
    # resolve_safe_path (grep guard, like context-window C3).
    for module, needle in (
        ("file_actions.py", "resolve_safe_path"),
        ("document_actions.py", "resolve_safe_path"),
        ("telegram_delivery.py", "resolve_safe_path"),
        ("artisan_runner_engine.py", "scrubbed_subprocess_env"),
    ):
        text = (_ROOT / module).read_text(encoding="utf-8")
        _require(needle in text, f"S5 FAILED: {module} does not route through {needle}")

    # S6 — fail-closed on the unresolvable / NUL-byte / empty path.
    for bad in ("", "\x00/tmp/x", "   "):
        d = resolve_safe_path(bad, "read")
        _require(not d.allowed, f"S6 FAILED: bad path allowed ({bad!r} -> {d})")
    # Unknown access mode also fails closed.
    _require(not resolve_safe_path(str(home), "execute").allowed, "S6 FAILED: unknown mode allowed")

    # S7 — honest-limit acknowledgement: the jail names itself as in-process
    # policy, not OS containment, so future readers don't over-trust it.
    _require("OS containment" in HONEST_LIMIT and "in-process policy" in HONEST_LIMIT,
             "S7 FAILED: honest limit not stated")

    print("blast-radius canaries S1-S7: PASS")


if __name__ == "__main__":
    main()
