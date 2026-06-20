# Whole-Loop Harness Checkpoint

Step 0.5 is a measurement harness, not a product behavior change. The runner
accepts fixed scenarios, records per-lane trace events, supports checkpoint
resume, and scores each case into the 2x2 matrix:

- secure/useful
- secure/not-useful
- unsafe/useful
- unsafe/not-useful

Every non-win must name the first broken lane. The open smoke uses dummy cases
only. Reviewer-authored sealed cases are run after the harness commit is frozen,
so the implementation cannot be tuned to the sealed manifest.

The harness deliberately separates:

- the runner and checkpoint mechanics;
- per-lane trace evidence;
- deterministic security and utility oracles;
- the report shape.

It does not add a new model lane, policy engine, or runtime router behavior.
