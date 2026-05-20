from __future__ import annotations

from screen_service import MacScreenService


def main() -> None:
    snapshot = MacScreenService().capture_once()
    print("== Kampung AI Screen Probe ==")
    print(f"screen_visible: {snapshot.visible}")
    print(f"screen_status: {snapshot.status}")
    print(f"image_bytes: {len(snapshot.image_bytes or b'')}")
    if not snapshot.visible:
        print("recommendation: grant Screen Recording permission to the runtime owner.")


if __name__ == "__main__":
    main()
