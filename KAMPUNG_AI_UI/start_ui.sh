#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/KAMPUNG_AI_UI"

if [[ -z "${MAYA_UI_TOKEN:-}" ]]; then
  export MAYA_UI_TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(16))
PY
)"
  echo "[maya-ui] generated MAYA_UI_TOKEN=$MAYA_UI_TOKEN"
fi

exec "$ROOT/venv/bin/python" -m uvicorn server.app:app --host 127.0.0.1 --port "${MAYA_UI_PORT:-8765}"
