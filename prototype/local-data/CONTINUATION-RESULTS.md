# Context-driven continuation prototype

2026-10-23. The fixed three-expansion and three-chunk limits have been removed. A chunk now keeps expanding until its working view reaches 150 unique rows, its reachable frontier is empty, or a case-wide budget pauses it. Each branch still requests 25 rows, and the model chooses one to four branches per expansion. Final pages are capped to the remaining view capacity.

A full context produces a model checkpoint and starts another process for the same case. Summaries, boundary IDs, pending scopes, exact evidence and cursors survive the handoff. There is no fixed chunk-count policy. Each model call is reconstructed from bounded evidence and carryover; a chunk can involve many calls.

## Real NVIDIA run

The initial stage used a 48-page/48-model-call safety budget. It paused after 371 unique transactions, three chunks and 20 model calls. The same case then received 32 additional pages and 32 additional model calls; no counters or source state were reset.

| Chunk | Expansion calls | Rows in working view | Boundary reason |
|---|---:|---:|---|
| 1 | 8 | 150 | View full; continue |
| 2 | 4 | 150 | View full; continue |
| 3 | 5 | 101 | Case page budget; pause |
| 4 | 6 | 150 | View full; continue |
| 5 | 4 | 150 | View full; continue |
| 6 | 1 | 54 | Extended case page budget; pause |

Final totals: **637 unique source transactions, 80 query pages, 28 expansion calls plus six checkpoint calls, 368,784 provider-reported tokens, zero unknown-usage calls**. Dollar cost is unavailable. The underlying database contains the full HI-Small file; this was one bounded neighborhood investigation, not a population sweep.

The final case remains **incomplete, with 122 pending scopes**. The driver did not automatically review it or mark it complete. All retained evidence matches the source database, all query actions have receipts, cursor chains are valid, and all five handoffs retained prior evidence, pending cursors and anchors. Every requested branch size was 25 and every effective page was at most 25. Carryover rows count inside the 150-row limit.

This confirms that expansion can exceed three calls inside one context, continuation can exceed three chunks, and explicit budget extension resumes the same investigation. It does not establish that this particular network can be exhausted within a practical cost budget.

## Automated verification

**41 tests pass**, including the optional pinned-Meterless integration test:

- A narrow scripted navigator continues beyond three expansions before a small reachable frontier is exhausted.
- A larger connected fixture reaches genuine frontier exhaustion after more than three contexts; preceding full contexts each contain 150 rows.
- Page-budget and model-call-budget pauses save state and require sufficient budget extension to resume. One model call is reserved for checkpointing.
- Resume preserves exact evidence and cursors, and subsequent pages maintain receipt-backed cursor chains.
- A deferred review can receive more model-call budget without reopening completed exploration.
- The real pinned Meterless engine processes 35 scripted chunks across two engine runs (32 plus three). Its per-run ceiling does not limit the durable investigation. This test makes no model calls.

The direct live driver launches a fresh Python process for every chunk. The updated Meterless adapter was verified with its real engine and a scripted worker; the new live model run used the direct driver.

## What remains limited

The defaults are **120 case-wide query pages and 160 total model calls**, including checkpoints/review. They bound cost and can be explicitly extended; they do not define completion. Empty pages and duplicate evidence consume the query budget but do not fill the context. A reachable frontier is limited to the seed-connected account/time/direction scopes in the reporting interval, not disconnected transactions or all authorized history.

Context admission currently uses the 150-row limit plus a 45,000-byte request guard. Oversize requests fail before sending; adaptive token-based rollover is not implemented and 150 rows is not a validated model-quality threshold.

A useful weakness surfaced: **all six checkpoint summary strings were identical**, despite evidence growth. Resume-query choices changed and exact state stayed intact, but the summary did not add new observations. This is a handoff-quality concern, not data loss. A next experiment should supply an explicit new-evidence delta and evaluate whether the summary updates its observations and questions appropriately.

The separate reviewer cap remains 24 greedy paths of at most six edges. Removing exploration chunk caps does not remove that review-coverage limit. No detection-quality claim follows from these mechanics tests.

## Run and resume

```sh
python3 prototype/local-data/chunk_driver.py prototype/local-data/generated/my-continuous-run \
  --max-query-pages 48 --max-model-calls 48
python3 prototype/local-data/chunk_driver.py prototype/local-data/generated/my-continuous-run \
  --resume --additional-query-pages 32 --additional-model-calls 32
```

Review starts automatically only at frontier exhaustion. Add `--review-partial` to explicitly request an intermediate review after a budget pause. Partial findings are marked with `investigation_complete: false` and archived if exploration resumes. If a completed investigation cannot afford review, resume with additional model calls; it retains its completed frontier state.

Evidence: `generated/continuous-live-01/`, including `before-resume-state.json`, `before-resume-audit.json`, final `audit.json`, and `continuation-verification.json`. The preceding verified-path implementation is preserved in `generated/verified-review-v2/frozen-source/`. Earlier live reports describe historical behavior and remain unchanged.
