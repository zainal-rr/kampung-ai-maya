from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from maya_meet.config import recall_config_from_env
from maya_meet.recall_client import create_recall_bot
from maya_meet.store import create_meet_session, update_meet_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Recall bot for a Maya M1 meeting proof.")
    parser.add_argument("meeting_url", help="Google Meet URL")
    parser.add_argument("--db", default="session_history.db")
    parser.add_argument("--session-id", default="")
    args = parser.parse_args()
    result = asyncio.run(join_meeting(args.meeting_url, db_path=args.db, session_id=args.session_id or None))
    print(json.dumps(result, indent=2, sort_keys=True))


async def join_meeting(meeting_url: str, *, db_path: str, session_id: str | None = None) -> dict[str, str]:
    clean_session_id = session_id or "meet_" + uuid.uuid4().hex
    await create_meet_session(db_path, session_id=clean_session_id, meeting_url=meeting_url)
    config = recall_config_from_env()
    result = await asyncio.to_thread(create_recall_bot, config, meeting_url, session_id=clean_session_id, preflight_output=True)
    if result.status == "created":
        await update_meet_session(db_path, clean_session_id, bot_id=result.bot_id, status="bot_created")
    else:
        await update_meet_session(db_path, clean_session_id, status="join_failed", failure_reason=result.reason_code)
    payload = result.as_dict()
    payload["session_id"] = clean_session_id
    return payload


if __name__ == "__main__":
    main()
