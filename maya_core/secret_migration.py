from __future__ import annotations

"""Name-only Keychain migration helper for Kampung AI secrets."""

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from maya_core.repo_paths import repo_root
from maya_core.secret_provider import SECRET_ENV_NAMES, get_secret, migrate_env_to_keychain, redact_secrets_in_text


ROOT = repo_root(__file__)
DEFAULT_LOG_GLOBS = ("logs/**/*.log", "logs/**/*.json", "docs/**/*.md")
SECRET_NAME_SUFFIXES = ("API_KEY", "TOKEN", "SECRET")


def _env_names() -> list[str]:
    values = dotenv_values(ROOT / ".env")
    return sorted(name for name, value in values.items() if name.endswith(SECRET_NAME_SUFFIXES) and value)


def inventory() -> list[dict[str, str]]:
    load_dotenv(ROOT / ".env", override=False)
    names = sorted(set((*SECRET_ENV_NAMES, *_env_names())))
    rows: list[dict[str, str]] = []
    for name in names:
        env_present = bool(os.getenv(name) or dotenv_values(ROOT / ".env").get(name))
        keychain_present = bool(get_secret(name, mode="keychain"))
        auto_present = bool(get_secret(name, mode="auto"))
        rows.append({
            "name": name,
            "env": "present" if env_present else "missing",
            "keychain": "present" if keychain_present else "missing",
            "auto": "present" if auto_present else "missing",
        })
    return rows


def migrate(names: list[str]) -> dict[str, str]:
    load_dotenv(ROOT / ".env", override=False)
    return migrate_env_to_keychain(tuple(names))


def verify(names: list[str]) -> dict[str, str]:
    return {name: "present" if get_secret(name, mode="keychain") else "missing" for name in names}


def log_leak_scan(names: list[str]) -> dict[str, str]:
    load_dotenv(ROOT / ".env", override=False)
    values = [os.getenv(name) for name in names if os.getenv(name)]
    results: dict[str, str] = {}
    for pattern in DEFAULT_LOG_GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            redacted = redact_secrets_in_text(text, values)
            results[str(path.relative_to(ROOT))] = "clean" if redacted == text else "contains_secret"
    return results


def _print_rows(rows: list[dict[str, str]]) -> None:
    for row in rows:
        print(f"{row['name']}: env={row['env']} keychain={row['keychain']} auto={row['auto']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--migrate", nargs="*")
    parser.add_argument("--verify", nargs="*")
    parser.add_argument("--scan-logs", nargs="*")
    args = parser.parse_args()

    if args.inventory:
        _print_rows(inventory())
    if args.migrate is not None:
        for name, status in migrate(args.migrate).items():
            print(f"{name}: {status}")
    if args.verify is not None:
        for name, status in verify(args.verify).items():
            print(f"{name}: {status}")
    if args.scan_logs is not None:
        leaks = {path: status for path, status in log_leak_scan(args.scan_logs).items() if status != "clean"}
        print(f"log_secret_leaks: {len(leaks)}")
        for path in sorted(leaks):
            print(f"{path}: {leaks[path]}")
    if not any((args.inventory, args.migrate is not None, args.verify is not None, args.scan_logs is not None)):
        parser.print_help()


if __name__ == "__main__":
    main()
