"""Smoke-test the Maya UI read API without starting a network server."""

from __future__ import annotations

import os

os.environ.setdefault("MAYA_UI_TOKEN", "ui-smoke-token")

from fastapi.testclient import TestClient  # noqa: E402

from server.app import app  # noqa: E402


def _get(client: TestClient, path: str) -> dict:
    joiner = "&" if "?" in path else "?"
    response = client.get(f"{path}{joiner}token=ui-smoke-token")
    assert response.status_code == 200, (path, response.status_code, response.text)
    payload = response.json()
    assert "error" not in payload, payload
    return payload


def main() -> None:
    client = TestClient(app)
    health = _get(client, "/api/health")
    assert health["read_only"] is True
    for path, key in (
        ("/api/desk", "last_routes"),
        ("/api/proof", "deterministic"),
        ("/api/automations", "counts"),
        ("/api/memory/audit?limit=5", "events"),
        ("/api/artifacts/detail?limit=5", "reviews"),
        ("/api/events/recent?limit=3", "cursor"),
    ):
        payload = _get(client, path)
        assert key in payload, (path, payload)
    denied = client.get("/api/health?token=wrong")
    assert denied.status_code == 401
    print("maya_ui_read_api_smoke: ok")


if __name__ == "__main__":
    main()
