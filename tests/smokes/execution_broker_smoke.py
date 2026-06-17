from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import os
import shutil
import tempfile
import time
import contextlib
from pathlib import Path

from maya_core.execution_broker import BrokerPolicyError, CommandSpec, broker_env, run_command, broker_argv, sandbox_profile

ROOT = Path(__file__).resolve().parents[2]

def main() -> None:
    os.environ["MAYA_TEST_API_KEY"] = "secret-should-not-leak"
    with tempfile.TemporaryDirectory(prefix="maya-w5-broker-") as tmp:
        root = Path(tmp).resolve()
        allowed = root / "allowed"
        blocked = root / "blocked"
        allowed.mkdir()
        blocked.mkdir()
        secret_file = root / ".env"
        secret_file.write_text("TOKEN=secret\n", "utf-8")
        credential_samples = {
            ".env.local": "TOKEN=secret\n",
            "id_rsa": "PRIVATE KEY\n",
            "server.pem": "-----BEGIN PRIVATE KEY-----\nsecret\n",
        }
        for name, content in credential_samples.items():
            (allowed / name).write_text(content, "utf-8")
        codex_config = allowed / ".codex"
        codex_config.mkdir()
        (codex_config / "auth.json").write_text("codex-login-token\n", "utf-8")
        gcloud_config = allowed / ".config" / "gcloud"
        gcloud_config.mkdir(parents=True)
        (gcloud_config / "application_default_credentials.json").write_text("gcloud-secret\n", "utf-8")

        env = broker_env(CommandSpec(argv=("/usr/bin/env",)))
        _require("MAYA_TEST_API_KEY" not in env, "secret-shaped env leaked by default")
        _require("PATH" in env, "safe PATH missing")

        (allowed / "plain.txt").write_text("plain-ok\n", "utf-8")
        read_ok = run_command(
            CommandSpec(
                argv=("/bin/cat", str(allowed / "plain.txt")),
                cwd=allowed,
                profile="readonly",
                read_roots=(allowed,),
                timeout=5,
            )
        )
        _require(read_ok.returncode == 0 and "plain-ok" in _text(read_ok.stdout), "jailed read could not read declared root")
        home_probe = Path.home() / "w5-read-jail-home-probe.txt"
        home_probe.write_text("home-personal-data\n", "utf-8")
        try:
            read_home = run_command(
                CommandSpec(
                    argv=("/bin/cat", str(home_probe)),
                    cwd=allowed,
                    profile="readonly",
                    read_roots=(allowed,),
                    timeout=5,
                )
            )
            _require(read_home.returncode != 0, "jailed read allowed home-dir file outside declared roots")
        finally:
            with contextlib.suppress(OSError):
                home_probe.unlink()

        write_ok = run_command(
            CommandSpec(
                argv=("/bin/sh", "-c", f"echo ok > {allowed / 'ok.txt'}"),
                cwd=allowed,
                profile="workspace_write",
                write_roots=(allowed,),
                timeout=5,
            )
        )
        _require(write_ok.returncode == 0 and (allowed / "ok.txt").exists(), f"allowed write failed: {write_ok}")

        write_bad = run_command(
            CommandSpec(
                argv=("/bin/sh", "-c", f"echo bad > {blocked / 'bad.txt'}"),
                cwd=allowed,
                profile="workspace_write",
                write_roots=(allowed,),
                timeout=5,
            )
        )
        _require(write_bad.returncode != 0 and not (blocked / "bad.txt").exists(), "out-of-root write succeeded")

        read_bad = run_command(
            CommandSpec(
                argv=("/bin/cat", str(secret_file)),
                cwd=allowed,
                profile="readonly",
                deny_read_paths=(secret_file,),
                timeout=5,
            )
        )
        _require(read_bad.returncode != 0, "sandbox allowed .env read")
        for name in credential_samples:
            result = run_command(
                CommandSpec(
                    argv=("/bin/cat", str(allowed / name)),
                    cwd=allowed,
                    profile="readonly",
                    read_roots=(allowed,),
                    timeout=5,
                )
            )
            _require(result.returncode != 0, f"sandbox allowed credential-shaped read: {name}")
        codex_read_bad = run_command(
            CommandSpec(
                argv=("/bin/cat", str(codex_config / "auth.json")),
                cwd=allowed,
                profile="readonly",
                read_roots=(allowed,),
                timeout=5,
            )
        )
        _require(codex_read_bad.returncode != 0, "sandbox allowed .codex read by default")
        gcloud_read_bad = run_command(
            CommandSpec(
                argv=("/bin/cat", str(gcloud_config / "application_default_credentials.json")),
                cwd=allowed,
                profile="readonly",
                read_roots=(allowed,),
                timeout=5,
            )
        )
        _require(gcloud_read_bad.returncode != 0, "sandbox allowed .config/gcloud read by default")
        codex_read_ok = run_command(
            CommandSpec(
                argv=("/bin/cat", str(codex_config / "auth.json")),
                cwd=allowed,
                profile="codex_auth",
                read_roots=(allowed,),
                timeout=5,
                allow_credential_reads=True,
            )
        )
        _require(codex_read_ok.returncode == 0, "explicit credential-read profile could not read declared credential path")
        _require_raises(
            BrokerPolicyError,
            lambda: run_command(
                CommandSpec(
                    argv=("/bin/cat", str(codex_config / "auth.json")),
                    cwd=allowed,
                    profile="readonly",
                    read_roots=(allowed,),
                    timeout=5,
                    allow_credential_reads=True,
                )
            ),
            "credential-read flag was accepted outside codex_auth profile",
        )

        _personal_data_read_jail_checks(allowed)

        env_bad = run_command(
            CommandSpec(
                argv=("/bin/sh", "-c", "test -z \"$MAYA_TEST_API_KEY\""),
                cwd=allowed,
                profile="readonly",
                timeout=5,
            )
        )
        _require(env_bad.returncode == 0, "child inherited secret env var")
        _require_raises(
            BrokerPolicyError,
            lambda: broker_env(CommandSpec(argv=("/usr/bin/env",), extra_env={"MAYA_TEST_API_KEY": "secret"})),
            "secret-shaped extra_env name was accepted",
        )
        _require_raises(
            BrokerPolicyError,
            lambda: broker_env(CommandSpec(argv=("/usr/bin/env",), extra_env={"MAYA_EXTRA": "sk-abc12345678901234567890"})),
            "secret-shaped extra_env value was accepted",
        )
        if shutil.which("sandbox-exec"):
            _require(write_ok.sandboxed, "sandbox-exec available but write command was not sandboxed")
            _require_raises(
                BrokerPolicyError,
                lambda: run_command(
                    CommandSpec(
                        argv=("/bin/true",),
                        cwd=allowed,
                        profile="workspace_write",
                        write_roots=(Path.home(),),
                        timeout=5,
                    )
                ),
                "unsafe write root was accepted",
            )

        network_bad = run_command(
            CommandSpec(
                argv=("/usr/bin/python3", "-c", "import socket; socket.create_connection(('1.1.1.1', 53), 1)"),
                cwd=allowed,
                profile="readonly",
                network=False,
                timeout=5,
            )
        )
        _require(network_bad.returncode != 0, "network-denied profile reached network")
        blender_spec = CommandSpec(
            argv=("/usr/bin/python3", "-c", "print('generated-blender-profile')"),
            cwd=allowed,
            profile="generated_blender",
            write_roots=(allowed,),
            timeout=5,
        )
        blender_argv, blender_sandboxed = broker_argv(blender_spec)
        blender_profile = sandbox_profile(blender_spec)
        _require(blender_sandboxed, "generated_blender profile did not use sandbox wrapper")
        _require("(allow iokit*)" in blender_profile, "generated_blender profile missing iokit allowance")
        _require("(allow network*)" not in blender_profile, "generated_blender profile allows network by default")
        _require("sandbox-exec" in blender_argv[0] if shutil.which("sandbox-exec") else True, "generated_blender command was not wrapped by sandbox-exec")
        blender_network_bad = run_command(
            CommandSpec(
                argv=("/usr/bin/python3", "-c", "import socket; socket.create_connection(('1.1.1.1', 53), 1)"),
                cwd=allowed,
                profile="generated_blender",
                write_roots=(allowed,),
                network=False,
                timeout=5,
            )
        )
        _require(blender_network_bad.returncode != 0, "generated_blender profile reached network by default")
        timeout_marker = allowed / "timeout-escape.txt"
        timed_out = run_command(
            CommandSpec(
                argv=("/bin/sh", "-c", f"(sleep 2; echo escaped > {timeout_marker}) & sleep 20"),
                cwd=allowed,
                profile="workspace_write",
                write_roots=(allowed,),
                timeout=0.5,
            )
        )
        _require(timed_out.timed_out and timed_out.returncode == 124, "timeout did not report broker timeout")
        time.sleep(2.5)
        _require(not timeout_marker.exists(), "timed-out process left a background writer running")

    print("execution_broker_smoke: ok")


def _personal_data_read_jail_checks(cwd: Path) -> None:
    log_probe_dir = ROOT / "logs" / "w5_read_jail_smoke"
    log_probe_dir.mkdir(parents=True, exist_ok=True)
    log_probe = log_probe_dir / "probe.txt"
    log_probe.write_text("personal-log-data\n", "utf-8")
    desktop_probes: list[Path] = []
    for folder, content in (
        ("documents", "personal-document-data\n"),
        ("artifacts", "personal-artifact-data\n"),
        ("voiceprints", "personal-biometric-data\n"),
    ):
        target_dir = Path.home() / "Desktop" / "Maya" / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        probe = target_dir / "w5-read-jail-smoke.txt"
        probe.write_text(content, "utf-8")
        desktop_probes.append(probe)
    try:
        targets = [(log_probe, "logs"), *((path, f"Desktop/Maya {path.parent.name}") for path in desktop_probes)]
        for path, label in targets:
            denied = run_command(
                CommandSpec(
                    argv=("/bin/cat", str(path)),
                    cwd=cwd,
                    profile="readonly",
                    read_roots=(ROOT,),
                    timeout=5,
                )
            )
            _require(denied.returncode != 0, f"jailed read allowed protected personal data: {label}")
        session_db = ROOT / "session_history.db"
        if session_db.exists():
            db_denied = run_command(
                CommandSpec(
                    argv=("/bin/cat", str(session_db)),
                    cwd=cwd,
                    profile="readonly",
                    read_roots=(ROOT,),
                    timeout=5,
                )
            )
            _require(db_denied.returncode != 0, "jailed read allowed session_history.db")
        backup_db = next((path for path in (ROOT / "backups").rglob("*.db")), None) if (ROOT / "backups").exists() else None
        if backup_db:
            backup_denied = run_command(
                CommandSpec(
                    argv=("/bin/cat", str(backup_db)),
                    cwd=cwd,
                    profile="readonly",
                    read_roots=(ROOT,),
                    timeout=5,
                )
            )
            _require(backup_denied.returncode != 0, "jailed read allowed backup memory DB")
        explicit_log = run_command(
            CommandSpec(
                argv=("/bin/cat", str(log_probe)),
                cwd=cwd,
                profile="readonly",
                read_roots=(ROOT,),
                personal_read_roots=(ROOT / "logs",),
                timeout=5,
            )
        )
        _require(explicit_log.returncode == 0, "explicit personal_read_roots could not read declared logs root")
    finally:
        for probe in desktop_probes:
            with contextlib.suppress(OSError):
                probe.unlink()
        with contextlib.suppress(OSError):
            log_probe.unlink()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _require_raises(exc_type: type[BaseException], func, message: str) -> None:
    try:
        func()
    except exc_type:
        return
    raise AssertionError(message)


def _text(value: bytes | str) -> str:
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="ignore")


if __name__ == "__main__":
    main()
