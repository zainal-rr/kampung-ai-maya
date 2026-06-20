from __future__ import annotations

"""W5-2 execution broker.

All command-like child processes should flow through this module. The broker
keeps environment inheritance allowlist-based and can wrap commands in macOS
`sandbox-exec` profiles. `sandbox-exec` is deprecated but still available on
the target iMac; this module deliberately keeps that backend swappable.
"""

import asyncio
from contextlib import suppress
import os
import re
import shutil
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from maya_core.safe_paths import (
    DENY_NAME_PATTERNS,
    DENY_PATH_PARTS,
    DENY_SUBPATHS,
    ENV_DENY_RE,
    resolve_safe_path,
)
from maya_core.execution_broker_read_policy import (
    effective_read_policy,
    path_deny_regex,
    personal_data_read_denies,
    validate_read_policy,
)


SAFE_BASE_ENV = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL", "LC_CTYPE")
GUI_PROFILES = {"gui", "service", "trusted_gui"}
CREDENTIAL_DENY_REGEXES = (
    r"(^|.*/)(\.ssh|\.gnupg|\.aws|\.docker|\.kube|\.codex|\.password-store)(/.*)?$",
    r"(^|.*/)\.config/gcloud(/.*)?$",
    r"(^|.*/)\.env(\..*)?$",
    r"(^|.*/)[^/]*\.(pem|key|p12|pfx|keystore|jks)$",
    r"(^|.*/)id_(rsa|ed25519|ecdsa|dsa)(\..*)?$",
    r"(^|.*/)\.?(zshrc|zprofile|bashrc|bash_profile|profile|netrc|pgpass)$",
    r".*\.keychain(-db)?$",
    r".*/Library/Keychains(/.*)?$",
    r".*/Application Support/(Google/Chrome|Firefox|com\.apple)(/.*)?$",
)
SECRET_VALUE_RE = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|xai-[A-Za-z0-9_-]{16,})",
    re.IGNORECASE,
)


class BrokerPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: Path | None = None
    profile: str = "readonly"
    timeout: float = 30
    stdin_policy: str = "null"
    input_bytes: bytes | None = None
    env_allowlist: tuple[str, ...] = ()
    extra_env: Mapping[str, str] = field(default_factory=dict)
    read_policy: str = "credential_deny"
    read_roots: tuple[Path, ...] = ()
    personal_read_roots: tuple[Path, ...] = ()
    deny_read_paths: tuple[Path, ...] = ()
    write_roots: tuple[Path, ...] = ()
    network: bool = False
    sandbox: bool | None = None
    allow_credential_reads: bool = False
    capture_output: bool = True
    text: bool = False
    check: bool = False


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: bytes | str
    stderr: bytes | str
    profile: str
    sandboxed: bool
    timed_out: bool = False
    error: str = ""

    def to_completed_process(self) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(self.argv, self.returncode, self.stdout, self.stderr)


def run_command(spec: CommandSpec) -> CommandResult:
    argv, sandboxed = broker_argv(spec)
    stdin = subprocess.DEVNULL if spec.stdin_policy == "null" and spec.input_bytes is None else subprocess.PIPE
    stdout = subprocess.PIPE if spec.capture_output else subprocess.DEVNULL
    stderr = subprocess.PIPE if spec.capture_output else subprocess.DEVNULL
    proc = None
    try:
        proc = subprocess.Popen(
            list(argv),
            cwd=str(spec.cwd) if spec.cwd else None,
            env=broker_env(spec),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            text=spec.text,
            start_new_session=True,
        )
        stdout_data, stderr_data = proc.communicate(spec.input_bytes, timeout=spec.timeout)
    except subprocess.TimeoutExpired:
        if proc is not None:
            _kill_process_group(proc.pid)
            with suppress(Exception):
                stdout_data, stderr_data = proc.communicate(timeout=1)
            if "stdout_data" not in locals():
                stdout_data = "" if spec.text else b""
                stderr_data = "" if spec.text else b""
        else:
            stdout_data = "" if spec.text else b""
            stderr_data = "" if spec.text else b""
        return CommandResult(tuple(argv), 124, stdout_data or ("" if spec.text else b""), stderr_data or ("" if spec.text else b""), spec.profile, sandboxed, True, "timeout")
    except OSError as exc:
        return CommandResult(tuple(argv), 127, "" if spec.text else b"", str(exc) if spec.text else str(exc).encode(), spec.profile, sandboxed, False, str(exc))
    result = CommandResult(tuple(argv), proc.returncode, stdout_data or ("" if spec.text else b""), stderr_data or ("" if spec.text else b""), spec.profile, sandboxed)
    if spec.check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, tuple(argv), result.stdout, result.stderr)
    return result


async def run_command_async(spec: CommandSpec) -> CommandResult:
    argv, sandboxed = broker_argv(spec)
    stdin = asyncio.subprocess.DEVNULL if spec.stdin_policy == "null" and spec.input_bytes is None else asyncio.subprocess.PIPE
    stdout = asyncio.subprocess.PIPE if spec.capture_output else asyncio.subprocess.DEVNULL
    stderr = asyncio.subprocess.PIPE if spec.capture_output else asyncio.subprocess.DEVNULL
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(spec.cwd) if spec.cwd else None,
            env=broker_env(spec),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(spec.input_bytes), timeout=spec.timeout)
    except asyncio.TimeoutError:
        if proc is not None:
            _kill_process_group(proc.pid)
            with suppress(Exception):
                await proc.communicate()
        return CommandResult(tuple(argv), 124, b"", b"", spec.profile, sandboxed, True, "timeout")
    except OSError as exc:
        return CommandResult(tuple(argv), 127, b"", str(exc).encode(), spec.profile, sandboxed, False, str(exc))
    result = CommandResult(tuple(argv), proc.returncode, stdout_bytes or b"", stderr_bytes or b"", spec.profile, sandboxed)
    if spec.check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, tuple(argv), result.stdout, result.stderr)
    return result


async def open_command_process_async(spec: CommandSpec) -> tuple[asyncio.subprocess.Process, tuple[str, ...], bool]:
    """Open an interactive child process through the broker.

    This exists for command paths such as ffmpeg audio capture where Maya needs
    to stream stderr and send a graceful quit byte. It keeps argv/env/sandbox
    construction centralized instead of letting call sites bypass the broker.
    """
    argv, sandboxed = broker_argv(spec)
    stdin = asyncio.subprocess.DEVNULL if spec.stdin_policy == "null" and spec.input_bytes is None else asyncio.subprocess.PIPE
    stdout = asyncio.subprocess.PIPE if spec.capture_output else asyncio.subprocess.DEVNULL
    stderr = asyncio.subprocess.PIPE if spec.capture_output else asyncio.subprocess.DEVNULL
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(spec.cwd) if spec.cwd else None,
            env=broker_env(spec),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
    except OSError as exc:
        raise BrokerPolicyError(str(exc)) from exc
    return proc, tuple(argv), sandboxed


def broker_env(spec: CommandSpec) -> dict[str, str]:
    names = set(SAFE_BASE_ENV) | set(spec.env_allowlist)
    env = {name: os.environ[name] for name in names if name in os.environ}
    env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    explicit_secret_names = set(spec.env_allowlist)
    for key, value in dict(spec.extra_env).items():
        name = str(key)
        text = str(value)
        if _secret_env_name(name) and name not in explicit_secret_names:
            raise BrokerPolicyError(f"secret-like env var requires explicit allowlist: {name}")
        if _secret_env_value(text) and name not in explicit_secret_names:
            raise BrokerPolicyError(f"secret-like env value requires explicit allowlist: {name}")
        env[name] = text
    return env


def broker_argv(spec: CommandSpec) -> tuple[tuple[str, ...], bool]:
    try:
        validate_read_policy(spec.read_policy)
    except ValueError as exc:
        raise BrokerPolicyError(str(exc)) from exc
    if spec.write_roots:
        _safe_write_roots(spec.write_roots)
    if not _should_sandbox(spec):
        return spec.argv, False
    profile = sandbox_profile(spec)
    return ("sandbox-exec", "-p", profile, *spec.argv), True


def sandbox_profile(spec: CommandSpec) -> str:
    read_denies = _resolved_roots(spec.deny_read_paths)
    if spec.allow_credential_reads and spec.profile != "codex_auth":
        raise BrokerPolicyError("credential reads are restricted to the codex_auth profile")
    if not spec.allow_credential_reads:
        read_denies = _credential_read_denies(spec) + read_denies
    read_denies = personal_data_read_denies(spec.personal_read_roots) + read_denies
    write_roots = _safe_write_roots(spec.write_roots or ((spec.cwd,) if spec.cwd and spec.profile in {"workspace_write", "media"} else ()))
    read_policy = effective_read_policy(spec.profile, spec.read_policy)
    read_allow = "(allow file-read*)"
    if read_policy == "jailed_roots":
        # On the target macOS host, filtered file-read allowlists abort common
        # dynamically-linked tools. Use the deny-over-broad-read form that
        # sandbox-exec enforces reliably, then deny personal-data roots below.
        pass
    parts = [
        "(version 1)",
        "(deny default)",
        "(allow process*)",
        "(allow sysctl-read)",
        "(allow mach-lookup)",
        "(allow file-read-metadata)",
        "(allow file-map-executable)",
        read_allow,
        '(allow file-write* (literal "/dev/null")' + "".join(f' (subpath "{_sbpl(root)}")' for root in write_roots) + ")",
    ]
    if spec.network:
        parts.append("(allow network*)")
    if spec.profile == "generated_blender":
        parts.append("(allow iokit*)")
    if not spec.allow_credential_reads:
        parts.extend(f'(deny file-read* (regex #"{regex}"))' for regex in CREDENTIAL_DENY_REGEXES)
    parts.extend(f'(deny file-read* (regex #"{path_deny_regex(path)}"))' for path in read_denies)
    return "".join(parts)


def _should_sandbox(spec: CommandSpec) -> bool:
    if spec.sandbox is not None:
        return spec.sandbox
    if spec.profile in GUI_PROFILES:
        return False
    return os.getenv("MAYA_OS_SANDBOX", "1") != "0" and shutil.which("sandbox-exec") is not None


def _credential_read_denies(spec: CommandSpec) -> tuple[Path, ...]:
    home = Path.home()
    roots = {Path.cwd()}
    if spec.cwd:
        roots.add(Path(spec.cwd))
    roots.update(root for root in spec.read_roots if root is not None)
    roots.update(root for root in spec.write_roots if root is not None)
    resolved_roots = _resolved_roots(tuple(roots))
    env_files = tuple(root / ".env" for root in resolved_roots)
    home_parts = tuple(home / part for part in DENY_PATH_PARTS)
    home_subpaths = tuple(home / subpath for subpath in DENY_SUBPATHS)
    named_denies: list[Path] = []
    for root in resolved_roots:
        with suppress(OSError):
            for child in root.iterdir():
                if _credential_name(child):
                    named_denies.append(child)
    return (*home_parts, *home_subpaths, Path.cwd() / ".env", *env_files, *named_denies)


def _resolved_roots(roots: Sequence[Path | None]) -> tuple[Path, ...]:
    resolved: list[Path] = []
    for root in roots:
        if root is None:
            continue
        try:
            resolved.append(Path(root).expanduser().resolve(strict=False))
        except OSError:
            continue
    return tuple(resolved)


def _safe_write_roots(roots: Sequence[Path | None]) -> tuple[Path, ...]:
    resolved = _resolved_roots(roots)
    for root in resolved:
        decision = resolve_safe_path(root, "write")
        if not decision.allowed:
            raise BrokerPolicyError(f"unsafe write root: {root} ({decision.reason})")
    return resolved


def _credential_name(path: Path) -> bool:
    return any(pattern.search(path.name) for pattern in DENY_NAME_PATTERNS)


def _secret_env_name(name: str) -> bool:
    return bool(ENV_DENY_RE.search(name))


def _secret_env_value(value: str) -> bool:
    return bool(SECRET_VALUE_RE.search(value))


def _sbpl(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace('"', '\\"')


def _kill_process_group(pid: int) -> None:
    with suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGKILL)
        return
    with suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)
