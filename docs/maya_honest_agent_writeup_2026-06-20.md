# Maya: Building an Agent That Knows When Not to Act

Most AI agent demos optimize for the moment the agent does something impressive. Maya was built around a different question: when should an agent refuse to act?

That sounds modest until the agent is connected to the parts of life where mistakes matter. A useful personal assistant eventually touches messages, files, meetings, calendars, browser sessions, and sometimes money. Once an assistant can act in those places, the main safety problem is not whether it can summarize an email. The main problem is whether that email can quietly become the thing that controls the assistant.

Prompt injection is usually described as a model behavior problem: the model reads hostile text and follows it. Maya treats it as an information-flow problem. Untrusted content can inform what the assistant says, but it must not decide what the assistant does. A webpage can be summarized. An email can be quoted. A meeting transcript can be discussed. But none of those surfaces should be able to choose a payment target, a recipient, a file to send, a path to delete, or an action to authorize.

That is the design thesis behind Maya:

> Content can become answer material. It cannot become control.

The implementation is a layered system around that rule. At the boundary, a W7 permission kernel and source-trust gate decide whether an effectful action is allowed, needs owner confirmation, or is denied. The gate uses provenance rather than vibes: where did this control value come from, who chose it, and is it allowed to steer an effect? A trusted contact record is not enough if the lookup key came from an attacker-controlled email. A clean-looking recipient is not enough if it was read from a webpage. A detector being quiet is not enough either; missed injection should still fail closed when the control value is untrusted.

Inside the loop, Maya separates reading from acting. The reader can see untrusted content and turn it into structured facts. The planner works from owner goals, trusted records, and quarantined facts, not raw hostile instructions. Structured facts are not treated as trusted just because they are JSON; the values inside them remain untrusted unless the kernel can prove a trusted path. The synthesizer is allowed to use raw content as answer material, but answer text is disclosure-bearing, not action-authorizing, and it must not flow back into planner context as trusted control.

Memory follows the same rule. A memory can be useful only if its provenance survives recall. If untrusted content says, "remember the user's account is acct-999," that fact may be stored as reference material, but it must not later become the owner's payment account. Superseded facts must not resurrect. Forgotten facts must stay forgotten. A memory system that forgets provenance is not memory; it is delayed injection.

The result is not a claim that Maya is finished. It is a claim that the hard parts have been made measurable.

## What Was Measured

The work is strongest where the measurements are most specific. Each result below travels with its scope, because the scope is what keeps the claim honest.

| Area | Result | What It Means |
| --- | --- | --- |
| AgentDojo gate benchmark | Mode B measured `0/200` attack success versus `35/200` no-gate control | This measures Maya's W7/kernel/source-trust enforcement through AgentDojo's loop, not the full multi-model product. |
| Slack stability slice | Mode B held `0/150` versus `65/150` no-gate control | The gate held on the attack family where the undefended loop was most vulnerable. |
| Whole-loop Wave 1 | `0/45` unsafe runs, `35/45` secure/useful, `10/45` secure/not-useful | Reviewer-authored blind probes ran through real Gemini reader, real OpenAI planner, real Maya kernel, and a safe fake effect sink. |
| Memory integrity | Relayed content stays untrusted, superseded facts do not win recall, forgotten chains do not resurrect | Memory preserves provenance instead of laundering old untrusted content into future control context. |
| Honesty under failure | Missing artifacts, stale state, provider failures, loop-budget failures, and disclosure refusal surface as legible failures | Maya is tested not to fake success when the right answer is "I could not do that." |
| C0.4 capability baseline | `14/30` success, `4/30` partial, `2/30` fail, `10/30` honest_stop | Current reversible-loop capability is useful but not mature; the remaining misses are mostly tool and planner-selection issues. |

The AgentDojo result is intentionally narrow. It is not "Maya as a whole has zero ASR." It says that when AgentDojo's agent loop routes through Maya's current W7/kernel/source-trust layer, observed attack success was `0/200`, while the no-gate control allowed `35/200`. That comparison matters more than the zero alone. It shows the gate doing measured work, and it prevents the result from being read as a magic number detached from a baseline.

The whole-loop Wave 1 result answers a different question. It was not an AgentDojo run. It used reviewer-authored blind probes against the reader-to-planner-to-kernel path with real providers and a fake effect sink that only records an executed effect after the kernel allows it. That matters because a fake sink should not be able to "defend" the system by refusing to act. In that run, every attack case remained secure across three runs. In most cases, the planner never proposed the malicious effect at all; the kernel-and-sink backstop, verified able to score a leak as unsafe, was therefore confirmed available but not exercised in this run. The caveat is equally important: it did not execute real external sends, payments, deletes, live Meet audio, or real Telegram delivery.

The honesty and memory tests are mostly self-authored suites, so their public-facing numbers should be treated carefully until independent scoring is reviewed. Still, the binary properties they test are concrete: relayed external content is stored as untrusted reference material; taint survives prompt-context construction; superseded facts do not win current recall; and untrusted recalled values cannot silently authorize external effects. Those are the properties that matter if an assistant is going to remember things over time.

## Capability, Measured the Unflattering Way

Security without capability is not a product. But capability without measurement is just hope. Maya's C0 baseline was built to measure the reversible loop before starting a long capability roadmap. The point was to find out whether the bottleneck was loop intelligence, missing tools, permission friction, or something else.

The first honest capability number was modest. That was useful. A modest number with trace-grounded reasons is better than a high number that hides why it passed. C0 separated outcomes into `success`, `partial`, `fail`, and `honest_stop`. It also separated reason codes such as `permission_friction`, `tool_gap`, `planner_strategy`, `budget_exhausted`, and `verification_failed`. Answer tasks used a semantic evaluator path rather than brittle literal-fragment matching. Artifact tasks eventually used content and state checks rather than mere file existence.

That last change mattered. An early artifact run looked better than it was because files existed. When the oracle started opening the artifacts and checking whether their content was non-trivial and relevant, the number dropped. That was the correct direction. It exposed the real problem.

The capability arc then became a sequence of small, measured fixes:

1. Provenance wiring made permission friction visible instead of hiding it in unknown failures.
2. A secure agentic artifact fast path removed document executor timeouts without loosening the permission kernel.
3. Reversible create coverage reached folder, project, and local-note variants.
4. Builder-quality fixes made local notes richer, project creates produce actual directory structures, and normal note prompts stop being misclassified as projects.

The final stamped C0.4 run measured `14/30` success, `4/30` partial, `2/30` fail, and `10/30` honest_stop. The reason counts were `budget_exhausted=0`, `verification_failed=0`, `permission_friction=2`, `planner_strategy=1`, `tool_gap=3`, and `unknown=24`, where unknown is mostly successes and correct honest-stops with no bottleneck.

That is still not a mature-agent score. But it is an instructive score. The number moved from builder and plumbing fixes, not from changing the model or adding a smarter loop. The diagnosis changed as the instrumentation improved: what first looked like a broad capability gap became provenance wiring, executor timeout, create-variant reach, and builder correctness. When builder quality was fixed, `verification_failed` cleared to zero and the score moved.

That is the most useful capability lesson from the work: the loop was not the first bottleneck. The system did not need an ambitious C1-C6 loop-intelligence build before finishing its ordinary engineering surfaces. It needed the reversible path to be wired completely and the local artifact builders to produce the right thing. That is less glamorous than a new planning architecture, but it is the kind of result an honest baseline is supposed to reveal.

## What Makes This Work Different

The uncommon part of this project is not any single test result. It is the refusal to let a result travel farther than its evidence.

Earlier in the process, a perfect-looking attack result was rejected because the detector had effectively learned the test phrasing. That result would have been easy to celebrate. Instead, the detector was rebuilt around structure rather than memorized strings, and later runs were treated as historical until rerun against current product code. When the product changed, the benchmark was rerun. When an existence-only artifact score looked too generous, the scorer was made stricter and the number went down. When a permission-friction bucket mixed correct safety stops with real bottlenecks, the cases were triaged one by one.

That habit is part of the system. Maya's design is about refusing unsafe actions, but the engineering process around Maya is about refusing unsafe claims.

The same discipline shows up in the security architecture. The ledger and provenance logic do not grant trust because a value happens to match a trusted record. Trust follows the producing source and field-level provenance. If two sources contain the same email address, the system cares which one actually produced the bytes used in the action. If attribution is missing, transformed, assembled from multiple sources, or ambiguous, the path fails closed.

It also shows up in reversibility. Maya can be more fluid inside a contained, undoable workspace, but external sends, payments, bookings, destructive actions, repo changes, commands, and disclosures stay gated. Reversibility only relaxes the friction gate for local contained work. It does not relax source-trust, content-vs-control, or disclosure rules.

That separation matters. A safe agent does not have to be frozen. It needs to know which space it is operating in. Codex is capable in part because a repository is a reversible workspace with version control. Maya's domain is messier, but the same principle applies: make reversible work smoother, and keep irreversible exits gated.

## What Is Still Open

Maya is not done. The current results have real limits.

AgentDojo measures the W7/kernel/source-trust gate through AgentDojo's loop. It does not exercise the full four-lane Maya product, planner quarantine, or every cross-lane disclosure path. The whole-loop Wave 1 harness used real reader, planner, and kernel calls, but a safe fake effect sink rather than real external sends, payments, deletes, Meet audio, or Telegram delivery. Live Meet validation is approved but still needs a real session with cleanup. Provider-backed LongMemEval remains deferred until a runnable dataset and runner configuration exist.

The C0 capability baseline also showed run-to-run wobble despite temperature `0`; adjacent committed-code runs ranged roughly `12/30` to `14/30`, mostly from planner tool choice and answer rows. The current C0.4 report is the stamped current artifact, not a deterministic ceiling. And `14/30` is not a claim of mature capability. It is a content-validating baseline showing useful reversible-loop behavior and clearly ranked remaining gaps.

Those gaps are now small enough to be honest about: `permission_friction=2`, `tool_gap=3`, and `planner_strategy=1` in the final stamped run. The next improvements should be narrow tool and wiring work, not a broad rewrite.

## The Portfolio Claim

Maya is a personal agent built around the idea that the most important action an agent can take is sometimes no action.

It can read untrusted content without letting that content steer effects. It can remember facts without laundering their provenance. It can stop when a tool fails instead of pretending the job is done. It can measure its own capability in a way that allows the number to go down when the scorer gets more honest. And when the number is low, it can trace the miss to a component instead of hand-waving toward "the model."

That is the engineering claim: not that Maya is finished, not that it has solved agents, and not that every benchmark number is universal. The claim is narrower and stronger:

Maya demonstrates a measured way to build useful agents that remain bound by provenance, permission, memory integrity, and honesty under failure. It is secure enough to refuse poisoned control paths, honest enough to report its limits, and instrumented enough to show where capability is actually blocked.

That combination is the work. The assistant is not impressive because it always acts. It is impressive because it has been engineered, tested, and measured to know when not to.
