from typing import Iterable

from dotenv import load_dotenv


# override=False: real environment variables (launchd, shell, CI) win over .env.
load_dotenv(override=False)

from maya_core.secret_provider import get_secret, require_secrets  # noqa: E402


def get_env(name: str, default: str | None = None) -> str | None:
    return get_secret(name, default)


def require_env(names: Iterable[str]) -> None:
    require_secrets(tuple(names))
