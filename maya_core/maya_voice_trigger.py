from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent


def main() -> None:
    load_dotenv(ROOT / ".env", override=True)
    action = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "start"
    if action not in {"start", "stop"}:
        raise SystemExit("usage: maya_voice_trigger.py [start|stop]")
    env_name = "MAYA_VOICE_TRIGGER_FILE" if action == "start" else "MAYA_VOICE_STOP_TRIGGER_FILE"
    default_name = ".maya_voice_trigger" if action == "start" else ".maya_voice_stop"
    path = Path(os.getenv(env_name, default_name))
    if not path.is_absolute():
        path = ROOT / path
    path.write_text(str(time.time()), encoding="utf-8")
    print(f"maya_voice_trigger: {action} -> {path}")


if __name__ == "__main__":
    main()
