# Memory Retrieval Eval — 2026-06-11

## Summary

Expanded the canonical-memory recall eval to 59 cases across:

- exact recall
- paraphrase recall
- Malay/Manglish recall
- noisy voice-style recall
- old memory recall
- association-neighbor recall
- forgotten-memory no-leak
- absent-fact no-false-direct-recall
- correction/supersede behavior

Result: lexical + association-neighbor + supersede handling remains the default.
Embedding rerank is still off by default because it produced no recall
improvement on the expanded eval.

## Commands Run

```bash
./venv/bin/python memory_recall_eval.py
./venv/bin/python memory_recall_eval_compare.py
```

## Baseline Result

Report:

`logs/evals/memory_recall_eval-20260611-151837.json`

Key metrics:

- exact recall@3: `1.0`
- paraphrase recall@3: `0.5`
- Malay/Manglish recall@3: `0.778`
- noisy voice recall@3: `0.875`
- old memory recall@3: `1.0`
- forgotten leaks: `0`
- absent false direct recalls: `0`
- reply preference supersede: newer value recallable, old value does not win direct recall

The embedding trigger fired because paraphrase recall is below the configured floor.

## Embedding Comparison Result

Report:

`logs/evals/memory_recall_eval_compare-20260611-151834.json`

Embedding rerank was available (`MEMORY_EMBED_RERANK_LIVE=1` with `GOOGLE_API_KEY`) and was compared against baseline.

Result:

- no hard failures in baseline
- no hard failures in embedding run
- no forgotten-memory leaks
- no absent-fact false direct recalls
- no recall improvement in exact, paraphrase, Malay/Manglish, noisy voice, or old-memory categories
- supersede/correction behavior held under both baseline and embedding modes

Recommendation from the eval:

`keep_embedding_rerank_off: no recall improvement`

## Nightly Flag Audit

`service_install.py` now sets `MEMORY_EMBED_RERANK_LIVE=0` for the nightly memory consolidation launch agent too.

Live/runtime and nightly default stay off unless the environment explicitly sets the flag. Do not enable embedding rerank broadly until the eval shows a measurable recall gain without leaks, latency problems, or cost issues.
