# Maya Clearance Map And Planner Feed Quarantine — 2026-06-19

This checkpoint splits Maya's model lanes by clearance instead of by model
brand. The rule is:

- Control prompts plan from structured `PlannerFact` records.
- Answer synthesis may read untrusted content as answer material.
- Structured facts are not sanitized facts. Values inside them remain
  untrusted unless Maya's permission kernel/source-trust layer later proves
  they are allowed control values.

The importable source of truth is `maya_core.clearance_map`. Its stop gate
fails if any lane can combine raw untrusted content with ungated effects, or if
any private-disclosure path is not marked gated.

## Lane Outcome

- The Mind / GPT planner: facts-only for planning/action/verification prompts.
- The Senses / Gemini: may read untrusted material, emits summaries/facts.
- The Steward / Claude: reviews and recommends; does not execute directly.
- TheNews/The Pulse / Grok: responder lane; output remains destination scoped.
- The Artisan / Codex: worker lane; effects remain brokered/kernel-gated.
- Harness synthesis: may use raw observations as answer material, but its
  output is not fed back into planner facts as trusted control context.

## Verification Shape

The smoke test is property-based: a paraphrased injected directive inside a
fact summary may still be visible to the planner as content, but if it nudges a
tool proposal, the kernel must deny or confirm the effect. The safety property
does not depend on removing every suspicious word from summaries.

