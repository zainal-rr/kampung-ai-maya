"""W5-1 filesystem path jail — one deterministic chokepoint, fail-closed.

Spec: docs/blast_radius_and_retrieval_design_2026-06-12.md (W5-1).
Canaries: blast_radius_canaries_smoke.py (S1-S7).

HONEST LIMIT (S7, recorded on purpose): this is in-process policy, NOT OS
containment. A Python-level check does not bind a child process that decides
to ignore it. OS-level enforcement is the W5-2 tier.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from maya_core.workspace_paths import legacy_workspace_root, maya_workspace_root, project_roots

HONEST_LIMIT = (
    "resolve_safe_path() is in-process policy, NOT OS containment. It binds "
    "Maya's own tool calls and the scrubbed Artisan child environment; it does "
    "not bind a child process that ignores it. OS-level enforcement is W5-2."
)

# Hard denylist — overrides the allowlist (S3). A credential path under an
# allowed root is still denied. Matched against the RESOLVED path, so a
# symlink inside the workspace pointing at ~/.ssh is denied too (S6).
DENY_PATH_PARTS = frozenset({
    ".ssh",
    ".gnupg",
    ".aws",
    ".docker",
    ".kube",
    ".codex",
    ".password-store",
    "Keychains",
    "LaunchAgents",
    "LaunchDaemons",
})
DENY_SUBPATHS = (
    ".config/gcloud",
    "Application Support/Google/Chrome",
    "Application Support/Firefox",
    "Application Support/com.apple",
)
DENY_NAME_PATTERNS = (
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"\.(pem|key|p12|pfx|keystore|jks)$", re.IGNORECASE),
    re.compile(r"^id_(rsa|ed25519|ecdsa|dsa)(\..*)?$", re.IGNORECASE),
    re.compile(r"^\.?(zshrc|zprofile|bashrc|bash_profile|profile|netrc|pgpass)$", re.IGNORECASE),
    re.compile(r"\.keychain(-db)?$", re.IGNORECASE),
)

# Credential-shaped environment variable names are stripped from child
# processes (Artisan/Codex). Keeps PATH/HOME/LANG etc. (S4).
ENV_DENY_RE = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|COOKIE|SESSION|BEARER)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SafePathDecision:
    allowed: bool
    mode: str
    reason: str
    resolved: Path | None = None

    def __bool__(self) -> bool:
        return self.allowed


def _user_dirs() -> tuple[Path, ...]:
    home = Path.home()
    return (home / "Desktop", home / "Documents", home / "Downloads")


def allowed_roots(mode: str) -> tuple[Path, ...]:
    """Write and read share the same allowlist today: workspace roots,
    configured project roots, the common user folders Maya already serves
    (Desktop/Documents/Downloads), and scratch. Everything else is denied."""
    del mode  # same roots for read and write at the W5-1 tier
    return (
        maya_workspace_root(),
        legacy_workspace_root(),
        *project_roots(),
        *_user_dirs(),
        Path(tempfile.gettempdir()),
    )


def resolve_safe_path(
    raw: str | os.PathLike,
    mode: str = "read",
    *,
    roots: tuple[Path, ...] | None = None,
) -> SafePathDecision:
    """The W5-1 chokepoint. Fail-closed: anything unresolvable is denied."""
    if mode not in ("read", "write"):
        return SafePathDecision(False, str(mode), "unknown access mode")
    try:
        text = str(raw).strip().strip("\"'")
        if not text or "\x00" in text:
            return SafePathDecision(False, mode, "empty or unresolvable path")
        resolved = Path(text).expanduser().resolve(strict=False)
    except Exception as exc:  # noqa: BLE001 - fail closed on anything
        return SafePathDecision(False, mode, f"unresolvable path: {exc}")

    deny = _deny_reason(resolved)
    if deny:
        return SafePathDecision(False, mode, deny, resolved)

    for root in roots if roots is not None else allowed_roots(mode):
        try:
            root_resolved = Path(root).expanduser().resolve(strict=False)
        except Exception:  # noqa: BLE001
            continue
        if resolved == root_resolved or _within(resolved, root_resolved):
            return SafePathDecision(True, mode, "inside allowed root", resolved)
    return SafePathDecision(
        False, mode, "outside Maya's allowed folders", resolved
    )


def _deny_reason(resolved: Path) -> str:
    parts = set(resolved.parts)
    hit = parts & DENY_PATH_PARTS
    if hit:
        return f"protected location ({sorted(hit)[0]})"
    posix = resolved.as_posix()
    for sub in DENY_SUBPATHS:
        if sub in posix:
            return f"protected location ({sub})"
    name = resolved.name
    for pattern in DENY_NAME_PATTERNS:
        if pattern.search(name):
            return f"protected file type ({name})"
    return ""


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def scrubbed_subprocess_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for Artisan/Codex children: credential-shaped names are
    stripped so generated code never inherits API keys or tokens (S4)."""
    source = dict(os.environ) if base is None else dict(base)
    return {k: v for k, v in source.items() if not ENV_DENY_RE.search(k)}
