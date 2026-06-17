from __future__ import annotations


def git_safe_env() -> dict[str, str]:
    """Keep brokered Git from reading user-level config files."""
    return {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
