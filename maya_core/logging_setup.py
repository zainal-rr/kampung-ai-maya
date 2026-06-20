from __future__ import annotations

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path


SECRET_PATTERNS = (
    (re.compile(r"(https://api\.telegram\.org/bot)[^/]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]+\b"), "[REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]+\b"), "[REDACTED]"),
)


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = message
        for pattern, replacement in SECRET_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def _quiet_noisy_loggers() -> None:
    for name in ("httpx", "httpcore", "telegram", "telegram.ext", "google_genai", "google_genai.models"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        logger.propagate = True


def _level(name: str, default: int) -> int:
    raw = os.getenv(name, "").upper().strip()
    return getattr(logging, raw, default)


def configure_logging(log_dir: str = "logs") -> Path:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    if any(getattr(handler, "name", "") == "maya_runtime" for handler in logger.handlers):
        return directory

    logger.setLevel(logging.INFO)
    _quiet_noisy_loggers()
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    redactor = SecretRedactionFilter()

    runtime = RotatingFileHandler(directory / "runtime.log", maxBytes=1_000_000, backupCount=3)
    runtime.name = "maya_runtime"
    runtime.setLevel(logging.INFO)
    runtime.setFormatter(formatter)
    runtime.addFilter(redactor)

    errors = RotatingFileHandler(directory / "error.log", maxBytes=1_000_000, backupCount=3)
    errors.name = "maya_errors"
    errors.setLevel(logging.ERROR)
    errors.setFormatter(formatter)
    errors.addFilter(redactor)

    stream = logging.StreamHandler()
    stream.name = "maya_console"
    stream.setLevel(_level("MAYA_CONSOLE_LOG_LEVEL", logging.WARNING))
    stream.setFormatter(formatter)
    stream.addFilter(redactor)

    logger.addHandler(runtime)
    logger.addHandler(errors)
    logger.addHandler(stream)
    return directory
