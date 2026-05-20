import os
from typing import Iterable

from dotenv import load_dotenv


load_dotenv()


def get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def require_env(names: Iterable[str]) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(f"Missing required environment variables: {joined}")
