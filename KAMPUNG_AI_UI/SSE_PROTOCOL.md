# Maya UI Read API — SSE Protocol (v1)

One page. Both sides (server `KAMPUNG_AI_UI/server/`, client `static/app.js`) must conform. Changes bump `proto` and are additive.

## Transport

- `GET /events?token=<t>&he=<int>&re=<int>` → `text/event-stream`, heartbeat comment `:hb` every 15s, `retry: 3000` sent on connect.
- Server polls the read-only store every 1.5s; this is a tail, not a push bus.
- **Read-only guarantee:** every connection uses SQLite URI `?mode=ro`. The server cannot write, by construction.

## Auth

- Token required on every `/api/*` and `/events` request: `?token=` query param (EventSource cannot set headers) or `Authorization: Bearer`.
- Token comes from `MAYA_UI_TOKEN` env; if unset the server generates one and prints it at startup. Static assets are public; they contain no data.

## Cursor / resume

- Cursor is the pair `(he, re)` = last seen `harness_events.id`, `route_events.id`.
- Every SSE message carries `id: <he>:<re>`. On reconnect the client sends them back as query params (`Last-Event-ID` is also honored if present, same format).
- `he=0&re=0` (or absent) = start from latest N (default 30), not from history zero.

## Message shape

```
event: harness | route
id: 2074:6388
data: {"proto":1,"schema_version":1,"type":"harness","ts":"2026-06-11 04:09:15",
       "run_id":"hrn_dd9d8014760b","summary":"finish — completed","lane":null}
```

- `schema_version`: echoed from the row when the column exists; defaults to `1` when it does not (the ALTER TABLE is pending in the kampung-ai repo and is NOT applied by this server).
- Unknown fields MUST be ignored by the client (tolerant reader). Unknown `event:` types MUST be ignored too.
- Lane names are ALWAYS masked to team names (The Sight / The Mind / The Steward / The Pulse / The Artisan) server-side. Raw engine names never cross this API.

## Error envelope

- HTTP errors: JSON `{"error": {"code": "unauthorized|not_found|store_unavailable", "message": "..."}}` with matching status (401/404/503).
- In-stream errors: `event: error` + same JSON in `data:`, then the server closes the stream. Client reconnects with backoff (EventSource default + `retry`).

## Snapshot endpoints (plain GET, same auth)

- `/api/health` → `{ok, db, tables}`
- `/api/desk` → approvals, runs, canaries, costs, tasks, last routes
- `/api/conversation?limit=N` → recent chat-like turns
- `/api/memory?limit=N` → canonical memory rows
- `/api/memory/audit?limit=N` → append-only memory audit events
- `/api/artifacts?limit=N` → latest artifact rows
- `/api/artifacts/detail?limit=N` → artifact sessions, QA reviews, disagreement rows
- `/api/automations` → routines, weekly memory runs, nightly consolidation runs
- `/api/proof` → latest eval/demo/live/browser/health proof snapshot
- `/api/events/recent?limit=N` → last N feed items (same item shape as SSE `data`)

## Out of scope for v1 (deliberate)

No POST/PUT/DELETE/WebSocket. Approvals and commands resolve in chat/Telegram. This server gains write endpoints only after the internal MayaAppServer protocol is stable.
