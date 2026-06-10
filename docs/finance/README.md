# Finance & Credit Analysis Knowledge Base

Truth layer for Maya's finance and credit analysis skill. Answers about
institution analysis, credit quality, liquidity, earnings reliability, and
funding instruments must be grounded in a recipe or concept doc from this tree
when one exists.

## Rules

1. Numbers are computed, never asserted. Every quantitative claim in an answer
   must show its formula and inputs, exactly as the recipes do.
2. Recipes are the worked units. Each recipe is retrieved whole: method without
   its interpretation thresholds and limitations is not an answer.
3. Honesty bar: content here is analyst-method knowledge, written carefully but
   not a substitute for audited data or professional advice. Maya must say when
   an answer leans on general model knowledge instead of a recipe, and must
   note that the analysis is informational, not professional financial advice.
4. No client-identifying data, account numbers, or credentials ever enter this
   tree or any artifact built from it.

## Mandatory recipe format

Every file under `recipes/` follows this contract:

- `## Intent` — the question this recipe answers.
- `## Inputs Required` — the data needed, with placeholders in CAPS.
- `## Method` — numbered steps with explicit formulas.
- `## Worked Example` — a complete pass with realistic numbers.
- `## Interpretation` — thresholds and what results mean.
- `## Red Flags` — the patterns an experienced analyst would catch.
- `## Limitations` — what this method cannot tell you.

## Layout

| Path | Use |
| --- | --- |
| `recipes/analysis/` | Worked analysis recipes (gap analysis, earnings quality, instrument feasibility) |
| `concepts/` | Reference docs on credit classification, earnings quality, liquidity risk |

## Verified bar

A recipe is "verified" when its worked example has been recomputed in a
spreadsheet and reviewed. Until then Maya may use it but should not present
its outputs as independently verified.
