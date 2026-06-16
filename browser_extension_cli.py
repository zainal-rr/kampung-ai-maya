from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable, Type

from maya_browser.bridge_status import query_bridge_status


def run_bridge_cli(
    *,
    server_cls: Type,
    controller_cls: Type,
    token_path: Path,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    parser = argparse.ArgumentParser(description="Maya extension bridge")
    parser.add_argument("--serve", action="store_true", help="run the bridge and wait for the extension")
    parser.add_argument("--probe", action="store_true", help="open example.com in the Maya group and print page text")
    parser.add_argument("--status", action="store_true", help="query bridge status without starting a bridge")
    args = parser.parse_args()
    if args.status:
        status = query_bridge_status(timeout=1.0)
        print(json.dumps(status or {"reason_code": "bridge_status_unavailable"}, sort_keys=True))
        raise SystemExit(0 if status.get("owner_kind") == "engine" and status.get("client_connected") else 1)

    server = server_cls(owner_kind="manual")
    server.start()
    print(f"bridge listening on ws://{server.host}:{server.port}/maya")
    print(f"token file: {token_path}")
    if args.probe:
        print("waiting for the Maya Chrome extension to connect...")
        for _ in range(600):
            if server.is_connected:
                break
            sleep(0.2)
        if not server.is_connected:
            print("extension did not connect within 120 seconds")
            return
        controller = controller_cls(server)
        controller.set_status("probe")
        controller.open_new_tab_url("https://example.com")
        sleep(2.0)
        page = controller.inspect_page()
        print(f"title: {page.title}\nurl: {page.url}\ntext: {page.text[:200]}")
        return
    if args.serve:
        while True:
            sleep(5)
            print(f"extension connected: {server.is_connected}")
