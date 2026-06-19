# Router Clearance Conformance

This Step 0 checkpoint makes Maya's router clearance map closed-world from the
real text entrypoint.

The importable source of truth is `maya_core.router_clearance_registry`. It
enumerates:

- Gate 0: `KampungAssistant.handle_text` and `AssistantRouter` peer dispatch.
- Gate A: `AssistantCommandRouter`.
- Gate B: delegated routers such as learning, harness, document, local, web,
  project, screen, vision, document mixins, nested browser workflows, slash
  commands, and model-lane responders.

Each effect or disclosure surface declares:

- classification: `effect`, `disclosure`, `both`, or `inert`;
- required gate;
- gate placement: `gate_internal` or `gate_at_callsite`;
- conformance test id.

The ratchet smoke parses the live source and fails if a declared class/module
gains a new method/function without a registry row, or if a required callsite
marker appears more or fewer times than the declared rows. Duplicate reachable
paths are represented as separate callsite rows unless the gate is proven
internal to the handler.
This is measurement and conformance only; it does not add a new policy engine or
change runtime behavior.

The seven live W7 fixes are tracked in the same registry. A fix can be marked
regression-pinnable or manual-or-regression, but fake tests that pass on both old
and new behavior are not acceptable evidence.
