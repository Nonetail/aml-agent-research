# Batched exploration experiment

The earlier fine-grained global-agent run was stopped at the user's request at 291 pages, 1,389 discovered rows and 132 logged model requests. The ledger and stopped-ledger.sqlite snapshot remain under generated/global-agent-live-v1/. No requests were in flight at the stop snapshot. Do not resume that run automatically.

## What the first experiment establishes

`batch_retrieval_experiment.py` reads the first 100 account/direction scopes from that ledger and exhausts the identical scopes with 25-row and 250-row SQL pages. Both return exactly 1,761 unique row IDs (2,134 occurrences, 373 duplicates). Page counts are 146 versus 100, a 31.5% reduction. There are zero model calls. Result: generated/batch-retrieval-experiment-v1/result.json.

The scopes come from one partially explored component and are not a representative benchmark. The second pass benefits from warm caches, so elapsed times are not a defensible speedup estimate. This experiment proves identical retrieval for these fixed scopes; it does not prove improved detection or persisted batch recovery. It also does not measure the number of model calls a complete investigation would require.

Increasing page size alone is insufficient. The principal change is to stop requiring model decisions for pagination, deduplication and view eviction.

## Proposed next prototype

1. Code presents a compact frontier summary: account identity, incoming/outgoing direction, query cursor, newly retrieved counts, amounts grouped by currency, observed time range and evidence references. The model chooses up to four investigation directions and a rationale. It need not receive the whole working view merely to advance a database cursor. An explicit continue-all option permits systematic traversal.
2. Code executes those directions with 250-row SQL pages. A burst stops at 1,500 newly discovered unique rows or 100 SQL pages, whichever comes first. These are initial experimental checkpoint values, not validated optimal settings. Rows beyond the unique-row checkpoint remain in a durable queue; retrieval page size is independent of model context size. Pending cursors survive the checkpoint.
3. A mandatory review phase runs before another expansion burst. Reviewer packets contain at most 150 rows and explicitly named columns, plus source-verified paths and computed observations. All queued rows receive packet coverage; rows without a candidate are recorded as such, not declared benign. A reviewer or provider failure prevents navigation from silently outrunning review.
4. Candidate generation queries persistent evidence, not only the next 150 IDs. Each candidate packet includes its complete supporting path. Paths spanning batches must be tested. Retrieval completeness, row presentation coverage, candidate assessment and detection findings remain separate metrics.
5. A compact checkpoint returns to the navigator: what changed, what was assessed, unresolved candidates and remaining directions. Exhausted components lead to new unvisited seeds. No hard count of chunks is needed.

The 150-row context is a presentation boundary, not a retrieval cap. Evidence eviction should usually be deterministic packet replacement; the model should request extra supporting evidence when needed, rather than manage arrays of IDs on every navigation call.

In the earlier global-agent implementation, component revision invalidated every old row review whenever new evidence arrived. That preserved caution but would cause repeated full re-review under mandatory checkpoints. The subsequently implemented batch prototype preserves immutable receipts for exactly what was reviewed, and queues newly discovered rows and new candidate path IDs. It does not yet reassess every previously reviewed path whose surrounding evidence changes. Old judgments must not be labelled current comprehensive graph assessments.

## Verification before another large live run

Use a fixture with duplicate incoming/outgoing retrieval, a path spanning two bursts, a disconnected component, and interruption between source retrieval and receipt commit. Assert exact row IDs, no repeated committed pages, durable overflow, complete path packet references and mandatory review before the next burst. Source-check every aggregate. Keep synthetic ground-truth labels out of navigator/reviewer prompts.

Then run a small live comparison on the same seed and source scope. Measure unique new rows per navigator call, tokens by role, pending review depth, candidate coverage and source-audit failures. Establish detection usefulness against withheld synthetic labels, including a legitimate fast-transfer example, before another full-scale run. A structurally valid trace alone does not establish suspicious-pattern detection.

The bounded implementation and experiments are now described in BATCH-PROTOTYPE.md. A later full-source batch run reached 35,147 discovered rows and was stopped for design discussion. The old global-agent ledger is separate and preserved. See BATCH-PROTOTYPE.md and ../../HANDOFF.md for current state; the proposed fixed-burst review schedule above is historical and is being reconsidered in ../../research/2026-10-23-rule-focused-design.md.
