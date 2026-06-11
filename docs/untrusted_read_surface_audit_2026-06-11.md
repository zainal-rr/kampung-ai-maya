# W7 Untrusted Read Surface Audit — 2026-06-11

## Summary

Audited current read surfaces after the W7 live-boundary work. The main read paths that can ingest external or user-visible content already carry untrusted-context metadata into the permission kernel.

Rule remains:

- Maya may summarize untrusted content.
- Untrusted content may not command side-effect actions.
- Injection-influenced external, scope-widening, or unknown actions are denied or confirmation-gated.

## Covered Surfaces

| Surface | Entry Point | W7 Handling | Evidence |
|---|---|---|---|
| Browser DOM through AppleScript | `browser_control_parse.parse_page` | Calls `assess_untrusted_context(..., source="browser")`; stores `untrusted_influence`, `injection_detected`, and signals on `BrowserPage`. | `untrusted_live_path_smoke.py` |
| Browser DOM through Chrome extension | `browser_extension_bridge.ExtensionBrowserController.inspect_page` | Calls `assess_untrusted_context(..., source="browser")`; stores flags on `BrowserPage`. | `browser_extension_bridge_smoke.py`, `untrusted_live_path_smoke.py` |
| Browser observations in harness | `harness_tools.observe_browser` | Propagates page W7 flags into `HarnessObservation`. | `untrusted_live_path_smoke.py` |
| Screen snapshots | `screen_responder.ScreenResponder` | Calls `assess_untrusted_context(..., source="screen")` on cleaned screen text and annotates suspicious screen content. | `untrusted_input_boundary_smoke.py`, `untrusted_live_path_smoke.py` |
| Active iMac context | `active_context.ActiveContextInspector` | Wraps Excel, Word, PowerPoint, Chrome, Markdown/TextEdit/Cursor, and one-shot screen fallback with `_mark_untrusted`. | `active_context.py`, `untrusted_live_path_smoke.py` |
| PowerPoint visible-slide repair | `active_context_powerpoint.verify_powerpoint_visible_context` | Preserves untrusted flags from the base context after screen verification. | `active_context_powerpoint_smoke.py` |
| Harness tool calls | `maya_harness_sdk.MayaHarnessSDK.call_tool` | Passes `_untrusted_influence` and `_injection_detected` into `MayaPermissionKernel.check(...)`. | `untrusted_live_path_smoke.py` |
| Permission kernel | `maya_permission_kernel.MayaPermissionKernel` | Applies `untrusted_action_decision(...)` after base permission decision. | `untrusted_input_boundary_smoke.py` |

## No New Unguarded Live Surface Found

The audit found many local file reads used for deterministic artifact QA, logs, smokes, and repo inspection. Those are not new external read surfaces by themselves. The live external surfaces remain browser, screen, active-app context, future Omi/document transcript ingestion, and harness observations.

## Surfaces To Keep Watching

- Omi transcript sync once physical Omi transcript ingestion is live.
- Email/PDF/web-upload readers if added later.
- New browser skills that bypass `BrowserController.inspect_page`.
- Any future MCP connector that reads external content directly.

## Regression Commands

```bash
./venv/bin/python untrusted_input_boundary_smoke.py
./venv/bin/python untrusted_live_path_smoke.py
./venv/bin/python browser_extension_bridge_smoke.py
```
