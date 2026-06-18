from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from maya_meet.config import recall_config_from_env
from maya_meet.orchestrator import join_meeting as orchestrated_join_meeting
from maya_core.provenance import make_provenance


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Recall bot for a Maya M1 meeting proof.")
    parser.add_argument("meeting_url", help="Google Meet URL")
    parser.add_argument("--db", default="session_history.db")
    parser.add_argument("--session-id", default="")
    args = parser.parse_args()
    result = asyncio.run(join_meeting(args.meeting_url, db_path=args.db, session_id=args.session_id or None))
    print(json.dumps(result, indent=2, sort_keys=True))


async def join_meeting(meeting_url: str, *, db_path: str, session_id: str | None = None) -> dict[str, str]:
    config = recall_config_from_env()
    clean_session_id = session_id or "meet_" + uuid.uuid4().hex
    result = await orchestrated_join_meeting(
        meeting_url,
        db_path=db_path,
        session_id=clean_session_id,
        config=config,
        provenance=make_provenance("owner_text"),
        trigger="cli",
    )
    return result.as_dict()


if __name__ == "__main__":
    main()
