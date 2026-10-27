# Adaptive expansion prototype

23 October 2026. Model: NVIDIA `nvidia/nemotron-3-ultra-550b-a55b`; same pinned HI-Small seed and reporting scope as earlier runs.

The model now selects 1–4 scopes and a separate 1–500 row limit per scope. The runtime caps those requests to the remaining working-view allowance, in request order, reserving one row for each later query. Receipts retain requested and effective sizes. Subsequent requests include remaining row/page budgets and recent page results. Both drivers accept independent investigator/reviewer view sizes and a request-byte bound. Defaults remain 40 rows; see [usage](CHUNKING.md).

## Completed live run

Local evidence: [audit](generated/chunks-adaptive-04/audit.json), [state](generated/chunks-adaptive-04/state.json). These generated files are excluded from the source ZIP.

| Measurement | Result |
|---|---:|
| Investigator / reviewer row ceiling | 1,500 / 1,500 |
| Serialized request-byte bound | 500,000 |
| Chunks | 3 |
| Actual investigator view sizes | 77, 178, 107 |
| Distinct retrieved / investigator-presented / reviewer-presented rows | 299 / 299 / 299 |
| Expansion batches / underlying query pages | 9 / 36 |
| Model calls including checkpoint/review | 14 |
| Pending scopes at stop | 49 |
| Provider input / output / total tokens | 134,098 / 3,641 / 137,739 |
| Candidate paths passing checks | 0 of 2 |

Each chunk stopped at its three-expansion limit, not its row ceiling. The case stopped as `deferred_by_query_page_budget`; all pending work remains saved. Every retained row matched the source database; receipts and cursor chains passed audit. Both handoffs preserved exact evidence, pending cursors and boundary rows, and actually resumed requested scopes. Both proposed paths were unsupported after factual checks. This is a mechanics result, not a detection-quality result.

The model chose four scopes per batch and requested 500 rows for every scope. Runtime effective page limits ranged from 1 to 500. This demonstrates aggressive requests and enforced caps, **not** evidence-sensitive switching between cautious and aggressive behavior. The selectable frontier still contains at most 16 pending scopes.

The largest live investigator view was 178 rows; the reviewer saw 299 rows. A synthetic test fills a 1,500-row investigator view and checks the hard ceiling and complete reviewer coverage. Neither result validates reasoning quality at 1,500 rows.

## Development failures and checks

Three earlier attempts are retained under `generated/chunks-adaptive-01` through `03`: expansion output truncation, multiple distinct expansion calls in one response, and checkpoint truncation. The runtime rejected invalid outputs without executing their proposed batches. Expansion now uses named function choice with parallel calls disabled; checkpoint/reviewer calls retain required-tool mode. The checkpoint prompt asks for a single short summary sentence. These controls do not guarantee that future model outputs will be valid.

The completed run's token total excludes those failed attempts. This was iterative development, not a frozen comparison against earlier runs. Request logging was extended during development to record call-mode/output settings; earlier saved requests lack those extra fields.

All 24 tests pass, including unequal requested sizes, runtime clipping, invalid-batch rejection before any page executes, page-budget handoff, full 1,500-row synthetic views, smaller independent reviewer views, and the existing continuation/recovery/model tests. The Markovian wrapper forwards the same size flags and passes syntax checking; the new adaptive flow was live-tested with the direct driver only.
