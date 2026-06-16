from __future__ import annotations

import asyncio
import tempfile

from artifact_parameter_resolver import resolve_artifact_parameters
from storage import init_db, save_history_message


async def main_async() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as handle:
        db_path = handle.name
        await init_db(db_path)

        missing = await resolve_artifact_parameters(db_path, "docx", "solo trip food for two days", "telegram")
        _require("Which city" in missing.question, f"expected clarification, got {missing!r}")

        await save_history_message(db_path, 1, "user", "make me a Seoul food trip document", "telegram")
        resolved = await resolve_artifact_parameters(db_path, "docx", "solo trip food for two days", "telegram")
        _require(resolved.question == "", f"should not ask with recent context, got {resolved!r}")
        _require("Seoul" in resolved.topic, f"expected Seoul topic, got {resolved.topic!r}")

        explicit = await resolve_artifact_parameters(db_path, "docx", "Tokyo solo food trip for two days", "telegram")
        _require(explicit.topic == "Tokyo solo food trip for two days", f"explicit topic changed: {explicit!r}")

    print("artifact_parameter_resolver_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main_async())
