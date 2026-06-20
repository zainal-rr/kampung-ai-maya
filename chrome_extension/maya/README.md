# Maya Browser Automation extension

This gives Maya a Claude-style automation experience: a named **Maya**
tab group, a toolbar badge (ON = bridge connected, RUN = command executing),
and automatic tab cleanup. Design: `docs/maya_chrome_extension_design.md`.

## Install (load unpacked)

1. Generate and print the bridge token:
   `./venv/bin/python -c "from browser_extension_bridge import ensure_bridge_token; print(ensure_bridge_token())"`
2. Open `chrome://extensions`, enable **Developer mode**, click
   **Load unpacked**, choose this `chrome_extension/maya/` folder.
3. Start a probe server:
   `./venv/bin/python browser_extension_bridge.py --probe`
4. Click the Maya icon, paste the token from
   `logs/extension/maya_extension_token.txt`, press **Save & reconnect**.
5. Badge turns **ON** and the probe opens example.com inside the Maya group
   and prints its page text.

## Status

Implemented: ping, Maya tab group, badge, open_url, page_text, elements,
result-options, click/fill controls, screenshot, set_status, close_run_tabs,
and the Python driver selector with AppleScript fallback.

Flights on the extension driver use the validated Google Flights deep link
(`/travel/flights?q=...`) and land directly on results — no keyboard
autocomplete needed (`flight_search_deeplink.py`, gated by
`flight_deeplink_smoke.py` in CI).

Still needs live proof: one extension mini-night including the flights lane,
to confirm the deep-link path beats the AppleScript form-fill live.
