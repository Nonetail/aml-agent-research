# Batched expansion and verified-path review

Current development defaults are 150 rows per investigator/reviewer view and 25 requested rows per branch. The model chooses one to four branches per expansion. The runtime caps pages in listed order to the remaining view capacity, reserving one row for each later branch. A final page can therefore be smaller than 25. These are experimental settings, not a validated reasoning threshold.

## Flow

1. Start from an arbitrary label-free reporting-period transaction in the full HI-Small database.
2. The investigator chooses saved account/direction/time scopes. Each fetched page persists exact rows and its continuation cursor.
3. Within a chunk, expansion continues until the reachable frontier is exhausted, the model chooses a handoff at a full view, or a case-wide budget pauses execution. At a full view, `manage_view` lets the model evict visible non-seed rows, optionally restore known stored rows, and continue with newly freed capacity, or choose a fresh-context handoff. There is no expansion-count cap and no case chunk-count cap. A model-selected handoff triggers a summary/checkpoint, then a fresh process continues the same case with seed, boundary IDs, notes and unfinished scopes. Carryover rows count toward the new view. Empty/duplicate results consume query budget without filling the view.
4. On frontier exhaustion the driver starts review. Budget-paused cases remain incomplete and are audited without automatic review; `--review-partial` explicitly requests an intermediate assessment. Code constructs candidate paths across **all collected evidence**, independently of investigator chunk boundaries. For each external starting edge in chronological/numeric-ID order it follows the earliest strictly later external outgoing edge, stopping at closure or six edges. All generated candidates enter a persistent queue after verification. There is no default path-count cap. Contained non-cyclic subpaths are collapsed; closed cycles and partially overlapping routes are preserved. Alternative continuations are not exhaustively enumerated.
5. The existing `verify_path` tool independently checks each candidate against the source database: existence, authorized scope, distinct edges, composite bank/account identity, strict time ordering, no self-transfer, and closure when claimed. Failed paths are withheld from the model.
6. The reviewer receives complete supporting rows for verified paths, at most six paths and 150 unique rows per request. Remaining collected rows are presented separately with no path to assess. It returns one assessment per supplied path ID; it cannot submit a new path or change its edges. Missing/duplicate IDs fail validation. There is no subsequent path-construction/finalization call.

Passing a path check establishes connectivity and time order only. It does not prove conserved funds, suspiciousness or laundering. Reviewer reasons remain unverified hypotheses. No path is not evidence of benign activity. Fan-in/fan-out structures and alternative branches need additional candidate generation before this can become a general detector.

## Run

```sh
python3 prototype/local-data/chunk_driver.py prototype/local-data/generated/my-verified-run
python3 prototype/local-data/prepare_meterless.py
node --experimental-transform-types prototype/local-data/markovian_driver.mjs prototype/local-data/generated/my-markovian-run
```

Both drivers accept `--view-rows`, `--review-view-rows`, `--max-request-bytes`, `--max-query-pages`, and `--max-model-calls`. Defaults are 150, 150, and 45,000. The independent byte guard rejects oversize requests before sending. Investigator views require at least eight rows and reviewer views at least six to hold a complete generated path. Case-wide defaults are 120 query pages and 160 total model calls, including checkpoint/review calls. These are cost guards, not completion criteria. One model call is reserved for the final checkpoint before model-budget pause. A deterministic checkpoint is available when no calls remain. Review commits one packet at a time and pauses when the remaining model-call budget is exhausted. Completed packets are retained and skipped on resumption. Output limits are 800 tokens for expansion, 1,200 for checkpointing, and 2,400 for view management and review. Provider timeout is 90 seconds; database work has a separate five-second deadline.

`state.json` stores exact evidence, cursors, actions, notes, limits and usage. Receipts support replay of interrupted page commits without repeating queries. A single-writer lock protects the case. Requests/responses are credential-free; `verified-paths.json` records candidates, checks and selection coverage; `review-*.json` records complete reviewer packets and assessments. `audit.json` checks source equality, receipts, cursors, handoffs and presentation counts. All rows presented does not mean all relationships considered.

This is not a fully crash-resumable dataset scheduler: model calls may have unknown consumption after interruption, and interruption between receiving a model response and committing its validated packet can still repeat that uncommitted call. Committed review packets are not repeated. Previous result documents describe historical implementations. Frozen threshold source lives in `generated/thresholds-v2/frozen-source/`; its local `generated` symlink references the existing data and runs. Run the frozen `threshold_verify.py` there to audit the prior experiment without changing its implementation hashes. Re-running model experiments needs an explicit credential and a separate experiment directory.

## Validation

```sh
python3 -m unittest discover -s prototype/local-data -p 'test_*.py'
python3 prototype/local-data/verify_review.py
# Optional four real-model reviews of the earlier 150-row development fixtures:
python3 prototype/local-data/verify_review.py --live
python3 prototype/local-data/chunk_case.py audit prototype/local-data/generated/my-verified-run
python3 prototype/local-data/manage.py pack
```

Live fixture directories must be new; failures remain recorded and are not silently retried. Tests cover page limits, handoffs, exact path support across boundaries, strict chronology, bank identity, self transfers, truncation accounting and withholding failed checks from the model. `verify_review.py` reuses evaluator-only expected traces for assertions but sends only evidence and code-verified paths to the reviewer. It is a development regression check, not a detection benchmark.


## Continuing a budget-paused case

```sh
python3 prototype/local-data/chunk_driver.py prototype/local-data/generated/my-continuous-run \
  --max-query-pages 48 --max-model-calls 48
python3 prototype/local-data/chunk_driver.py prototype/local-data/generated/my-continuous-run \
  --resume --additional-query-pages 32 --additional-model-calls 32
```

The resume command extends the existing cumulative budgets. It does not reset usage, evidence, query identities, cursors or chunk numbering. It requires enough remaining budget for at least one page and two model calls. A partial review is archived when exploration resumes, so it cannot masquerade as the current final assessment.

Only an empty reachable frontier means `frontier_exhausted`. This covers the accounts and time/direction scopes reachable from the seed under the current reporting interval; it is not a sweep of disconnected transactions or historical scopes. Budget stops are `deferred_by_query_page_budget` or `deferred_by_model_call_budget`. The direct driver is the resumable entry point, including for cases originally started through Meterless.

The pinned Meterless engine allows at most 32 chunks in one engine run. The adapter opens another engine run when that ceiling is reached and the durable case is still active. The case carries its own exact evidence and handoff state across engine runs; there is no 32-chunk investigation limit. An offline test drives 35 scripted chunks through the real engine to check this behavior.

Context admission still uses a 150-row allowance and a separate request-byte hard guard (45,000 by default). The byte guard fails closed before a request; it is not an adaptive tokenizer or automatic byte-based rollover. No model-specific safe token threshold is claimed. The six-edge, earliest-continuation generator remains a candidate-coverage limitation; the total 24-path cap has been removed. The queue is not an enumeration of every possible graph path.


## Working-view changes and durable review queues

`manage_view` runs when the evidence view is full. Its choices are `continue` (evict visible IDs and optionally restore stored IDs) or `handoff` (leave the view intact and checkpoint). Evicting the seed, unknown IDs, duplicates, or revisions that fail to free space are rejected before state mutation. Eviction changes neither source evidence nor query/cursor state. `active_view` and `view_events` persist the selection and rationale. Any known stored ID can be restored; the payload supplies up to 100 recent outside-view IDs as examples, not a full searchable memory catalog.

The checkpoint receives a bounded delta: new-evidence count and ID tail, currently visible new rows, completed scopes, pages fetched, recent view revisions and previous summary. Its instruction asks for updated observations and questions. Runtime counts are attached independently to the saved checkpoint; the model's prose remains a hypothesis. Active-view maintenance has no fixed revision count; every management call consumes the global model-call budget. Automatic token-pressure rollover is not implemented.

`review_queue` in `state.json` stores the evidence fingerprint, verified findings, ordered bounded packets and committed assessments. Every successful packet is saved immediately. Re-running review on unchanged evidence skips completed packets. It can be explicitly extended while exploration is paused:

```sh
python3 prototype/local-data/chunk_case.py review prototype/local-data/generated/my-continuous-run \
  --additional-model-calls 4
```

This adds four calls to the cumulative case budget and processes as many remaining packets as fit. It does not reopen exploration. Queue counts appear in `audit.json`; review can remain partial independently of investigation completion. If evidence changes after resumed exploration, a new queue is built and the previous queue is archived; earlier judgments are not silently treated as assessments of the expanded evidence. Deterministic path IDs remain stable for identical ordered edge lists.

See `WORKING-VIEW-RESULTS.md` for this milestone's tests and live experiments. Earlier reports retain their historical settings.
