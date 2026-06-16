from __future__ import annotations

from artisan_runner import create_artisan_implementation_request


async def create_codex_implementation_request(
    db_path: str | None,
    request: str,
    channel: str,
    *,
    gemini_build_brief: str = "",
) -> tuple[str, str]:
    """Compatibility wrapper for the old Codex lane name.

    New code should call create_artisan_implementation_request directly.
    """
    return await create_artisan_implementation_request(
        db_path,
        request,
        channel,
        gemini_build_brief=gemini_build_brief,
    )
