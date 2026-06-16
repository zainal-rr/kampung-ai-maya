from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import os
import subprocess
from collections.abc import Sequence

import sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from secret_provider import (
    get_secret,
    migrate_env_to_keychain,
    redact_secret_value,
    redact_secrets_in_text,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeSecurity:
    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        args = list(command)
        if "find-generic-password" in args:
            service = args[args.index("-s") + 1]
            account = args[args.index("-a") + 1]
            value = self.store.get((service, account))
            if value is None:
                return subprocess.CompletedProcess(args, 44, "", "not found")
            return subprocess.CompletedProcess(args, 0, value + "\n", "")
        if "add-generic-password" in args:
            service = args[args.index("-s") + 1]
            account = args[args.index("-a") + 1]
            value = args[args.index("-w") + 1]
            self.store[(service, account)] = value
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 2, "", "unexpected command")


def main() -> None:
    fake = FakeSecurity()
    old_secret = os.environ.get("MAYA_FAKE_SECRET")
    old_mode = os.environ.get("MAYA_SECRET_PROVIDER")
    try:
        os.environ["MAYA_FAKE_SECRET"] = "env-secret-value"
        _require(get_secret("MAYA_FAKE_SECRET", mode="env") == "env-secret-value", "env provider failed")
        _require(get_secret("MAYA_FAKE_SECRET", mode="keychain", runner=fake) is None, "missing keychain should be None")
        result = migrate_env_to_keychain(("MAYA_FAKE_SECRET",), runner=fake)
        _require(result["MAYA_FAKE_SECRET"] == "stored", "migration did not report stored")
        _require(
            get_secret("MAYA_FAKE_SECRET", mode="keychain", runner=fake) == "env-secret-value",
            "keychain provider did not retrieve stored secret",
        )
        os.environ["MAYA_FAKE_SECRET"] = "env-fallback"
        _require(
            get_secret("MAYA_FAKE_SECRET", mode="auto", runner=fake) == "env-secret-value",
            "auto mode should prefer keychain",
        )
        _require(
            get_secret("MAYA_ONLY_ENV_SECRET", "fallback", mode="auto", runner=fake) == "fallback",
            "auto mode should fall back cleanly",
        )
        _require(redact_secret_value("abcdef123456") == "abc...456", "secret redaction shape changed")
        _require(
            "env-secret-value" not in redact_secrets_in_text("value=env-secret-value", ("env-secret-value",)),
            "redacted text leaked raw secret",
        )
    finally:
        if old_secret is None:
            os.environ.pop("MAYA_FAKE_SECRET", None)
        else:
            os.environ["MAYA_FAKE_SECRET"] = old_secret
        if old_mode is None:
            os.environ.pop("MAYA_SECRET_PROVIDER", None)
        else:
            os.environ["MAYA_SECRET_PROVIDER"] = old_mode
    print("secret_provider_smoke: ok")


if __name__ == "__main__":
    main()
