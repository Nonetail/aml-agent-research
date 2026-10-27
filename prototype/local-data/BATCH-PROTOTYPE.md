# Batch-led investigation prototype

The new runner separates model direction selection from source retrieval and requires review after every retrieval burst. The old global full run remains stopped and is not reused or altered by these experiments.

## Latest stopped run

The later full-source batch run in `generated/batch-agent-full-500-v1/` is stopped at the user's request, with ledger status `paused_user`. Read-only inspection confirms 35,147 discovered rows, 183 pages, 34,954 rows presented in completed reviews, 154 assessed paths, 33 complete checkpoints and checkpoint 34 in review. Of 356 committed review receipts, 324 contain no decisions. The current path-only review interface cannot originate findings from a no-path packet. Neither presentation coverage nor an `investigate` flag certifies detection quality.

There are 448 logged calls, 56 recovery incidents and 4,114,006 provider-reported tokens. One admitted request has an unknown outcome; the ledger additionally reserves 21,498 accounting units for it. Do not equate that reservation with reported or billed usage. The stopped backup and admitted history must be preserved. The heartbeat is paused, and neither run nor heartbeat should be resumed by documentation work.

The current adapter uses `nvidia/nemotron-3.5-lightning-30b-a3b`. The earlier 40–1,500-row threshold study used Ultra and does not establish this model's review capacity. The [latest design discussion](../../research/2026-10-23-rule-focused-design.md) proposes rule-focused evidence and independent context/review boundaries; it is not implemented here.

## Running

```
python3 batch_agent.py generated/new-batch-run --seed 100003 --rows 500 --burst-pages 8 --batches 2
python3 batch_audit.py generated/new-batch-run
```

Use a new directory for a new configuration. Existing directories resume saved configuration, pending retrieval, packet preparation or review. `--batches` counts additional completed checkpoints. Default SQL page size is 250, default burst limits are 1,500 newly discovered rows or 100 SQL pages, and the default row ceiling is 150. Rows beyond the burst target in the last SQL page are retained and reviewed. The small live experiment used an eight-page burst limit. Model request and charged-token budgets remain bounded (40 calls and 500,000 units by default). In ordinary bounded mode provider failures pause. `--continuous` removes cumulative call/token/checkpoint caps, omits explicit API `max_tokens`, and retries rejected outputs and transient timeout/408/429/5xx failures with persisted backoff. Repeated invalid outputs can split pending packets without truncating complete paths or altering completed receipts. Credentials and source/invariant failures still require attention; provider limits still apply. The fixed two-second local inter-call delay remains.

The model selects an empty scope list for systematic traversal or up to four explicit scopes. Code follows the scopes and records pages/cursors atomically. Every resulting row is placed into a review packet before the next direction request. Reviews are immutable receipts for their particular evidence; expansion does not invalidate all prior receipts. New candidate path IDs are queued separately. This is evidence presentation and candidate assessment coverage, not a comprehensive graph-level judgment.

Paths are generated from all persisted discovered evidence, not one presentation group. Complete source-verified paths remain together in packets even when their rows came from different bursts. Candidate generation still chooses only the earliest later continuation, up to six edges, so alternative routes are omitted. The in-memory rebuild is suitable for bounded experiments, not five-million-row production scaling.

## Working-view budget

The row ceiling is configurable (150, 500 or 1,500 in the comparison). Each review request is packed under a separate conservative context allowance: serialized UTF-8 bytes plus 2,400 output-token units and 2,048 overhead units. This is a byte-based token proxy, not an exact NVIDIA tokenizer measurement or a model context-window claim. Defaults use 24,000 units. The capacity experiment uses 60,000. No complete evidence unit is truncated to fit. A unit that cannot fit pauses explicitly.

Packets cap at six paths to bound reviewer output; path-heavy workloads may therefore see little benefit from a higher row ceiling. Navigator requests contain frontier summaries and the preceding review receipt instead of the full working view. Summaries currently contain query identities/cursors/counts, not the proposed richer currency aggregates.

## Earlier bounded experiments

The source-capacity fixture has 1,600 self-transfer rows and scripted responses. All three variants covered exactly the same rows and passed source audits. This is a sizing experiment, not a realistic detection benchmark.

| Row ceiling | Largest actual packet | Reviewer calls | Navigator calls |
|---|---:|---:|---:|
| 150 | 150 | 11 | 2 |
| 500 | 500 | 4 | 2 |
| 1,500 | 515 | 4 | 2 |

At a 1,500-row ceiling the 60,000-unit context allowance became binding first. Results are in generated/batch-view-comparison-v1/result.json. These are scripted calls; they establish coverage and packing behavior, not model accuracy at large views.

The real-source live experiment completed two checkpoints, retrieving and presenting 92 unique rows in six SQL pages, with 14 verified paths assessed. It used two successful navigator calls and four reviewer calls, plus one rejected initial navigator response before the tool was simplified. Reported usage was 17,379 tokens across those seven requests. Independent structural source audit passed. These are not matched row sets against the previous 100-row experiment, so no numerical end-to-end speedup is asserted.

Review quality remains a blocker. For example, the model described account IDs 800FB5B40/802C02570 as bank IDs and described a two-edge path as a single transaction with no onward transfer. Source rows contradict those explanations. A structural audit validates the evidence supplied and receipt identity, not arbitrary natural-language assertions. Do not treat investigate labels as validated suspicious findings.

## Verification and limits

Tests exercise cross-checkpoint cycle discovery, restart without repeating committed pages, disconnected reseeding, rollback after partial retrieval, reuse of a persisted provider response, reviewer-failure backpressure, source-prompt corruption, and view-budget compliance. A separate live constructed-pattern fixture with withheld evaluator notes tests a rapid near-amount-preserving cycle against a currency/amount-mismatched control. This is a tiny sanity check, not a calibrated detection evaluation.

The remaining quality work, now also demonstrated by the stopped larger run, is to improve claim grounding: supply named per-path source facts and require structured evidence references for timing, amounts and account identities. Compare those claims to code-computed facts. Then test real-model accuracy at different context sizes with withheld pattern labels. The current result supports the batch/checkpoint architecture; it does not establish model reliability or full-graph scalability.


The live constructed fixture presented all five rows and assessed both paths across four checkpoints (six calls, 5,737 reported tokens); source audit passed. The reviewer correctly described the cycle and flagged it for investigation, but also flagged the mismatched control with unsupported structuring/mule speculation. This failed the intended discrimination sanity check. It is not an estimate of precision or recall on the real dataset.

Before the later continuous-recovery changes, 112 tests passed. After those changes, 26 focused tests passed; the full suite has not been rerun after all latest edits. The investigation remains stopped. These historical checks were not rerun for the documentation update. The first live batch result retains a stale error string from its initial rejected direction response despite subsequently completing both checkpoints; error-hint clearing is fixed in the current runner and regression tests pass. Treat status, completed checkpoints and audit receipts as the outcome of that run.
