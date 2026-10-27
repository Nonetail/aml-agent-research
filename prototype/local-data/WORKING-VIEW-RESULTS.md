# Working-view eviction and persistent verified-path review

2026-10-23. This milestone keeps the 150-row working allowance and 25-row branch pages while separating active context from durable evidence and total review coverage.

## Implemented behavior

At a full view the model can choose a fresh-context handoff, or evict up to 100 visible non-seed rows and optionally restore up to 25 stored rows, leaving capacity for further expansion. Eviction never deletes evidence, advances a cursor, or completes a branch. The seed remains visible. Unknown/duplicate IDs and invalid revisions are rejected before mutation. Known stored IDs can be restored; up to 100 recent outside-view IDs are offered as examples. This is not yet a searchable memory catalog or automatic relevance-ranking system.

The active view and each revision's IDs/reason are persisted. Context management itself consumes the overall model-call budget. No fixed number of expansions or chunks is imposed. The 45,000-byte request guard still fails closed; token-based automatic rollover is not implemented.

Checkpoints now receive an explicit delta: new-evidence count and bounded ID tail, currently visible new evidence, completed scopes, pages fetched, recent view revisions and previous summary. Runtime counts are saved independently from the model's narrative.

The default 24-path cap is removed. Code still generates one earliest-later route per eligible starting edge, up to six edges, then independently verifies candidates against the source database. Contained non-cyclic subpaths are collapsed; closed cycles and partially overlapping routes remain distinct. Stable path IDs derive from the ordered edge IDs.

All resulting candidates enter a durable review queue. Each packet contains at most six paths and 150 supporting rows; remaining rows outside the paths are separate packets. Each successful assessment is committed immediately. When the model-call budget runs out, remaining packets stay queued. Resuming unchanged evidence skips committed packets. Changed evidence archives the old queue and builds a new one so judgments are not silently reused for expanded context.

## Real-model observations

Two separate experiments used the existing NVIDIA connection and full HI-Small database.

| Experiment | Evidence | Outcome |
|---|---|---|
| Working-view navigation | Fresh case, 40 pages then 12 more | At 150 rows, the model evicted 100 rows, kept them stored, and continued the same chunk. That chunk collected 243 unique transactions with a final view of 149. After budget extension, a second chunk brought the total to 375, with a final view of 145. |
| Queued review | Saved 637-row case from the prior continuation experiment | 178 eligible starts became 156 verified candidates after collapsing 22 subpaths. No candidate was omitted by a count cap. Review committed two batches, paused, then resumed for four more batches without repeating the first two. |

Navigation made 20 calls and used 237,079 provider-reported tokens. It remains incomplete with 70 pending scopes. Every request stayed within the 150-row evidence limit. All evicted rows remain stored; exact source equality, receipt chains, cursors and the handoff audit passed. The live model chose eviction, but did not request restoration; restoration was covered by automated tests.

The second handoff summary changed and explicitly referred to 132 new transactions, matching the runtime count. This is a small improvement over the prior repeated summaries, not a general factual-quality result. The prose still contains interpretations such as “cycles” that have not been independently established by the summary step, and it reaches the schema's length boundary. We do not treat that prose as verified evidence.

Review assessed **36 distinct paths in six committed batches**, exceeding the old 24-path cap. **120 paths remain queued in 23 packets** (including remaining non-path-row packets). All 156 queued candidate paths independently passed database verification; every packet includes its complete path support and stays within the row bound. Pending review work is explicitly reported, not discarded or counted as complete.

Across the new work: **26 model calls, 272,860 provider-reported tokens, no unknown-usage calls**. This excludes the old calls copied with the 637-row case; those calls were not repeated. Dollar cost is unavailable. Neither experiment is a detection-accuracy benchmark or a full-dataset investigation.

## Automated verification

**48 tests pass**, including the optional pinned Meterless integration test. New checks cover:

- Eviction and restoration preserve exact evidence and query/cursor state across reopening the case.
- Invalid revisions leave state unchanged; the seed cannot be evicted.
- Continued exploration with view revisions supplies an explicit checkpoint delta.
- More than 24 candidates are generated with no default count cap; contained paths collapse, while contained closed cycles remain available.
- Review pauses after a committed packet, resumes in a fresh case instance, and finishes without duplicated assessments. Re-running completed review consumes no additional calls.
- When evidence changes, the prior queue is archived instead of silently reusing its judgments.

## Remaining boundaries

This removes total path-count truncation, not the six-edge/earliest-continuation restriction. Alternative continuations, longer paths and branching motifs still require broader candidate generation. Relevance of eviction choices has not been scored; the mechanism being safe does not prove that the model retained the best evidence. Model-call interruption after a response but before committing its assessment can still incur a repeat call; committed packets are not repeated.

## Commands and evidence

```sh
python3 prototype/local-data/chunk_driver.py prototype/local-data/generated/my-view-run \
  --max-query-pages 40 --max-model-calls 40
python3 prototype/local-data/chunk_driver.py prototype/local-data/generated/my-view-run \
  --resume --additional-query-pages 12 --additional-model-calls 12
# Explicitly assess a partial case, using or extending its cumulative model budget:
python3 prototype/local-data/chunk_case.py review prototype/local-data/generated/my-view-run \
  --additional-model-calls 4
```

Navigation evidence is in `generated/working-view-live-01/`, including `view-verification.json` and `audit.json`. Review evidence is in `generated/review-queue-live-01/`, including the pre-review and paused states, `queue-verification.json`, persisted queue and audit. The prior continuation source is preserved in `generated/continuous-live-01/frozen-source/`. Source-only packaging excludes generated evidence, databases and credentials.
