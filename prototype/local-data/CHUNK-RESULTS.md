# Live batched-expansion and handoff results

These are the original fixed-page-size runs. See [adaptive expansion](ADAPTIVE-RESULTS.md) for the subsequent model-selected page sizes and configurable views.

23 October 2026. NVIDIA `nvidia/nemotron-3-ultra-550b-a55b`, thinking disabled. One arbitrary label-free seed, the same source/window in both runs. This tests execution and evidence continuity; it is not a controlled detection-quality or framework-efficiency comparison.

| Measurement | Direct scheduler | Actual Meterless Markovian |
|---|---:|---:|
| Chunks | 3 | 3 |
| Model calls, including checkpoint/review | 14 | 14 |
| Model-selected expansion batches | 7 | 7 |
| Underlying query pages | 28 | 28 |
| Distinct transactions retained/presented | 81 | 83 |
| Working-view rows per chunk | 36, 36, 39 | 36, 37, 38 |
| Unfinished account/time/direction scopes | 26 | 26 |
| Provider-reported input tokens | 66,240 | 67,788 |
| Provider-reported output tokens | 5,231 | 5,055 |
| Total tokens, completed run only | 71,471 | 72,843 |
| Candidate paths passing checks | 0 of 6 | 0 of 6 |

Every expansion batch selected four scopes. One model tool call therefore led to four bounded database page queries. The remaining seven model calls in each run were three checkpoint calls, three bounded reviewer-view calls and one reviewer finalization.

The small 40-row working allowance caused each chunk to stop at 36–40 rows, leaving room before another batch. **81/83 is the cumulative case size, not the size of any one prompt.** The next chunk began in a new Python process with the same seed, selected boundary evidence, saved questions and pending cursor states. Constraints were reinstated independently of the engine's compacted prompt.

## What was verified

For both transitions (1→2 and 2→3) in both runs:

- All prior working-view evidence remained in the durable case store.
- All pending query IDs and exact cursors survived unchanged into the next chunk.
- Selected boundary records appeared in the next initial working view.
- The next chunk actually executed saved pending queries, including model-requested resume priorities.

Every retained row matches the source database. Every page action has a receipt, and cursor chains are consistent. All retained rows were included in investigator requests and in bounded reviewer views. Those presentation counts do not prove comprehension or complete path coverage.

The Markovian wrapper used the real pinned reference engine at `1742dec56a66e58eef9dda2d2b865823758ca8cd`, with a generator that ran the same Python segment worker. It recorded three chunks and a `completed` engine status. The application correctly retained **`deferred_by_chunk_budget`** as the investigation status. Neither status means all branches were investigated.

## What this does not establish

The engine did not discover or preserve evidence by itself: the application persisted exact records, enforced scope and maintained cursor state. The direct scheduler achieved the same handoff invariants. The small difference in rows/tokens does not establish an advantage; these are single development runs with provider variability and implementation fixes during development, not frozen repeated comparative trials. Markovian's character-based savings estimates are not used as measured cost.

The reviewer again proposed disconnected or invalid paths. All six candidates per run failed factual checks, and the reviewer marked them unsupported. This demonstrates the rejection path, not useful detection or benign account status. No hidden labels were consulted. A later experiment must examine reasoning quality and supported rule semantics before claiming AML value.

The 40-row allowance was selected to force context transitions cheaply. It does not validate a several-hundred-row smart zone. Summaries can be incomplete or stale; exact IDs and pending work are authoritative. Cross-view review can miss chains spanning distant views.

## Failures retained

- `chunks-direct-01`: checkpoint output hit its generation cap before a valid checkpoint was saved. Retrieved records and attempted usage remain stored. The subsequent run used a bounded short checkpoint format.
- `chunks-markovian-01`: the provider emitted the identical expansion tool call twice. The initial strict single-call check rejected it before any query ran. Identical calls are now coalesced; distinct competing calls remain rejected. A fixture verifies one batch executes once.

The completed-run token totals above exclude those earlier attempts; use their saved usage records when accounting for total development cost. Currency cost was not established.

## Local evidence

- [Direct audit](generated/chunks-direct-02/audit.json)
- [Markovian audit](generated/chunks-markovian-02/audit.json)
- [Actual engine result](generated/chunks-markovian-02/meterless-result.json)
- [Direct case state](generated/chunks-direct-02/state.json)
- [Markovian case state](generated/chunks-markovian-02/state.json)
- [Usage and reproduction instructions](CHUNKING.md)

The source-only handover includes this summary and runnable scripts. Generated case evidence, databases, credentials and the optional upstream checkout remain local. Nineteen tests pass, including restart/receipt recovery, cursor/anchor preservation, duplicate-call handling and single-writer exclusion.
