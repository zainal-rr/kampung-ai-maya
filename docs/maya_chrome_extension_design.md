# Maya Chrome Extension Design

Goal: give Maya the same browser experience Claude in Chrome has — a named,
colored "Maya" tab group, a toolbar badge that shows when she is working, tabs
that are created, tracked, and cleaned up automatically — while keeping every
existing skill, safety boundary, and the reliability harness unchanged.

## Why an extension

Chrome's AppleScript dictionary (Maya's current driver) has no tab groups, no
badges, and no per-tab tracking. Those are extension-only APIs
(`chrome.tabGroups`, `chrome.action`, `chrome.tabs`). Claude in Chrome is an
extension; the equivalent for Maya is a small local extension that talks to
Maya's Python process.

## Architecture

```
Maya skills (flight/stay/site/browser skills, reliability harness)
        │  unchanged calls (open_new_tab_url, inspect_page, click_*, fill_field, ...)
        ▼
browser_driver selector
  ├── ExtensionBrowserController  (preferred when extension connected)
  └── BrowserController/AppleScript (automatic fallback, current behavior)
        │
        ▼ (extension path)
browser_extension_bridge.py
  WebSocket server on ws://127.0.0.1:8975  (token-gated, localhost only)
        ▲
        │ persistent WebSocket, JSON messages
chrome_extension/maya (MV3)
  ├── background.js  — WS client, command router, Maya tab group, badge
  ├── content functions — page text / click / fill / result options
  └── popup — connection + current-run status
```

Transport is WebSocket rather than Chrome native messaging because Maya is a
long-running process (native messaging would make Chrome spawn a relay
subprocess; a localhost socket is simpler and supports screenshots without
message-size pain).

## Message protocol

All messages are JSON. Maya -> extension requests:

```json
{"id": "req-42", "op": "open_url", "args": {"url": "https://...", "activate": true}}
```

Extension -> Maya responses:

```json
{"id": "req-42", "ok": true, "result": {"tabId": 123}}
{"id": "req-42", "ok": false, "error": "tab was closed"}
```

Extension -> Maya events (no id): `{"event": "connected", "extension": "maya", "version": 1}`,
`{"event": "tab_removed", "tabId": 123}`.

### Command set (maps 1:1 to BrowserController)

| op | args | replaces (AppleScript) |
| --- | --- | --- |
| ping | - | - |
| ensure_group | title, color | (impossible today) |
| open_url | url, activate | open_new_tab_url |
| page_text | tabId?, max_chars | inspect_page |
| elements | tabId?, max_items | inspect_elements |
| result_options | tabId?, max_items | inspect_search_results |
| click_text / click_visible / click_exact_last | tabId?, target | click_* |
| click_search_result | tabId?, target, rank | click_search_result |
| click_price_result | tabId?, target | click_price_result |
| fill | tabId?, target, value | fill_field |
| screenshot | tabId? | screencapture fallback |
| close_run_tabs | keep_banner | close_active_tab_or_blank |
| set_status | run_id, text | keeps the Maya group active and updates the badge state |

`tabId` defaults to the group's active tab. The five DOM routines are direct
ports of the proven JS in `browser_control_js.py` (same filters: badHref,
badText, entry_point exclusion, YouTube/Reddit site rules).

## Tab group lifecycle

1. First command of a run: `ensure_group` creates or reuses one tab group per
   window titled `Maya` (soft yellow, the closest Chrome built-in color to the
   Kampung AI tile background). All `open_url` tabs are created inside it.
2. `set_status` keeps the group title as `Maya` and the toolbar badge shows
   `RUN` while commands execute. This keeps the tab group clean and stable.
3. `close_run_tabs` closes the group's tabs (optionally keeping one banner
   tab) — no more leftover tab soup after a reliability night, and no stale
   page feeding the next run's active context (the night1 Penang bug class).
4. If the user drags a tab out of the group, the extension stops driving it.

## Safety model

- Server binds 127.0.0.1 only; the extension must present the token from
  `logs/extension/maya_extension_token.txt` (generated on first server start)
  and a `chrome-extension://` origin.
- All existing Python-side gates stay exactly where they are
  (`permission_policy`, `travel_booking_safety`, sensitive-field blocks) —
  the extension is a dumber hand, not a new decision maker.
- Defense in depth: background.js refuses `fill`/`click` ops when the tab URL
  matches checkout/login/payment patterns, mirroring `_sensitive_page`.
- The extension never reads cookies, passwords, or other profiles' tabs; only
  tabs inside the Maya group are scriptable.

## Fallback semantics

`browser_driver.py` starts the local bridge and uses the extension only when it
is connected. Extension down → silently use AppleScript (current behavior,
still fully functional). Live reliability notes should record the chosen driver
before P3 makes the extension the default trusted path.

## Rollout phases

- **P0 complete:** extension loads unpacked, connects, ping round-trip, Maya
  group + badge, `open_url`/`page_text`/`screenshot`/`set_status`/
  `close_run_tabs` working. Python bridge + smoke in CI.
- **P1 complete:** click/fill/result-options routines are ported from
  `browser_control_js.py`; `ExtensionBrowserController` supports the browser
  control methods used by Google Search, Google Images, YouTube, Reddit,
  Google Flights, Booking.com, and Airbnb.
- **P2 in progress:** driver selector exists and production skills can prefer
  the extension when it is connected, with AppleScript fallback. Remaining
  proof is a live mini-night with the unpacked extension loaded in Chrome.
- **P3 future:** make extension the default trusted path after live extension
  evidence holds for repeated nights; AppleScript stays as fallback.

## Testing

- `browser_extension_bridge_smoke.py` (CI): real WebSocket round-trip against
  a fake extension client — ping, open_url, page_text parsing into
  `BrowserPage`, elements, result options, click/fill calls, verified click,
  screenshot base64 -> PNG file, request timeout, reconnect.
- Live check: generate the token with `ensure_bridge_token`, load the unpacked
  extension, run `python3 browser_extension_bridge.py --probe`, paste the
  token in the popup, then confirm example.com opens in the Maya group and
  prints page text.
- Reliability harness unchanged; P2 adds a `--driver extension` flag.
