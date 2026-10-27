# Independent replay audit

2026-10-23. The new auditor reconstructs saved runs without model calls and without importing the runtime's navigation, view-management, path-generation or verification functions.

## Results

Both saved live traces pass:

| Trace | Source rows checked | Query pages replayed | Navigation calls | Chunks | View changes | Committed review packets | Pending review packets |
|---|---:|---:|---:|---:|---:|---:|---:|
| working-view-live-01 | 375 | 52 | 20 | 2 | 1 | 0 | 0 |
| review-queue-live-01 | 637 | 80 | 34 | 6 | 0 | 6 | 23 |

The queued-review run inherited its navigation history from `continuous-live-01`; `--base-run` supplies those missing call artifacts. Without complete artifacts, the auditor refuses to certify full replay. These rows overlap across the two cases; their counts are not unique population coverage.

All **15 deliberate corruptions** of disposable copies were detected, with a specific failure location. Hash checks confirm the original run artifacts were unchanged. The source and receipt databases are opened read-only by the auditor. No inference calls or evaluator labels are used.

| Corruption | Failure |
|---|---|
| alter source amount | evidence/T137537: Source row differs |
| invent visible id | call/1/investigator: Visible row is not exact source evidence |
| drop stored evidence | evidence: Stored evidence does not equal seed plus fetched rows |
| break page cursor | page/2: Broken cursor chain |
| exceed view limit | call/1/investigator: Working-view limit or uniqueness violated |
| alter eviction result | call/10/view-manager: Recorded eviction/restoration differs |
| lose handoff scope | call/16/checkpoint: Checkpoint pending scopes/cursors differ |
| alter checkpoint counts | call/16/checkpoint: Checkpoint runtime delta differs |
| delete call artifact | artifact/01-investigator-request.json: Missing call artifact; full replay is unavailable |
| alter receipt rows | page/1: Receipt page differs from independent source query |
| remove queued packet | queue: Missing/extra/altered review packet |
| remove queued candidate | queue: Generated candidate inventory differs (missing/extra/reordered path) |
| duplicate committed batch | queue: Committed assessments do not match recorded review calls |
| alter saved assessment | review-packet/1: Saved assessment differs from model output |
| false review completion | queue: Review completion status differs |

## What is checked

- Exact source equality for every retained transaction, source identity metadata and authorized timestamps.
- Independent SQL reconstruction of each receipt-backed page, cursor/source/scope binding, effective page allowance, continuation and completion state.
- Evidence reconstructed as the seed plus fetched rows; query discovery and final frontier reconstructed from those rows. Deleted actions and unaccounted fetch receipts are rejected.
- Every recorded navigation request and response replayed in order. Visible rows must equal the reconstructed working view, and frontier entries must match the reconstructed scopes.
- Eviction/restoration IDs, seed retention, view bounds, recorded transitions, checkpoint boundaries, runtime delta counts and handoff evidence/cursors checked at each step.
- Queue candidates independently regenerated under the current six-edge greedy specification, with an independent containment-based deduplication implementation. Candidate inventory and packet construction must match, so a dropped candidate cannot hide behind a seemingly valid remaining queue.
- Every completed packet must be the next queued packet, contain the supplied evidence, and match the recorded model response with exactly one assessment per supplied path. Final completion must agree with queue progress.

The test suite has **54 tests**, including six new replay tests. The new tests include a genuine runtime-generated fixture with eviction and restoration, partial review, and a review resumed through completion. The existing optional Meterless test requires its pinned checkout; it is skipped in an extracted source-only package without that checkout.

## Limits of the certificate

This is executable structural verification, not formal verification of every possible execution. It does not certify whether an eviction was wise, whether summaries are factually sound, or whether a path indicates laundering. It proves consistency with recorded model outputs, not their truth.

The local source database is the trusted data authority for this audit. The source SHA is read from its import metadata; the auditor does not independently re-import or rehash the original CSV. The earlier import checks remain a separate evidence layer. A coordinated rewrite of source data and all logs is outside this threat model; logs are not cryptographically signed or externally anchored.

The current strict replay targets the saved current prototype format with one review-queue generation, completed navigation handoffs and successful committed calls. It rejects missing artifacts, failed/in-flight calls, open segments and older review formats rather than silently certifying partial evidence. Replaying multiple archived queue generations across changing evidence is not yet supported. These boundaries must be addressed before treating the auditor as a universal production recovery auditor.

The successful audit is the proposed gate for a bounded 100-case pilot. That pilot has not been launched by this task; these are checks of existing traces and disposable corruption copies, not new detection-quality measurements.

## Run

```sh
python3 prototype/local-data/replay_audit.py prototype/local-data/generated/working-view-live-01
python3 prototype/local-data/replay_audit.py prototype/local-data/generated/review-queue-live-01 \
  --base-run prototype/local-data/generated/continuous-live-01
python3 prototype/local-data/replay_corruptions.py
python3 -m unittest discover -s prototype/local-data -p 'test_*.py'
```

`replay_audit.py` prints a JSON result and exits nonzero on failure. Use `--output /path/to/report.json` to save it and `--database` to select an explicitly trusted test database. `replay_corruptions.py` writes `generated/replay-corruptions.json`; it mutates temporary copies and removes them afterward. It does not require credentials.

Source-only packaging includes the auditor, corruption harness, tests and this report. Raw evidence and databases remain excluded.
