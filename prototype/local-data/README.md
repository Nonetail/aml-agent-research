# Local AML data tools — disposable prototype

Current family-specific work: [short temporal-cycle prototype](CYCLE-PROTOTYPE.md), including its rule, prompts, tools, persistent offline workflow and prepared graph. A separate [live context/grouping/overlap evaluation](../../experiments/2026-10-24-cycle-context/README.md) now tests the current model. It did not establish a reliable working-view size.

Previous batch entry point: [batch-led prototype and stopped run](BATCH-PROTOTYPE.md), with [latest rule-focused design discussion](../../research/2026-10-23-rule-focused-design.md). The batch run is paused at the user's request. Current `model.py` targets `nvidia/nemotron-3.5-lightning-30b-a3b`; older sections below describe their original runners and models. Recovery and persistence capabilities differ between those runners. No detector quality or optimal model-view size has been established.

The original data-access milestone follows. It imports HI-Small into local SQLite files and supplies bounded Python tools for navigation. No dependencies beyond Python 3.9+ with SQLite; no database server or package installation. The optional real-model runner requires an NVIDIA credential and makes hosted inference calls. Everything generated stays in this folder. It includes a bounded investigator/reviewer mechanics runner; it is not a validated detector or a complete crash-resumable runtime.

## Run from the research folder

```sh
python3 prototype/local-data/import_data.py
python3 -m unittest discover -s prototype/local-data -p 'test_*.py'
python3 prototype/local-data/verify_import.py
python3 prototype/local-data/tools.py fetch_transactions '{"bank":"10","account":"8000EBD30","start":"2022/09/01 00:00","end":"2022/09/11 00:00","direction":"outgoing","limit":5}'
```

The import refuses to overwrite `generated/`. Run cleanup before rebuilding. Interrupted or failed imports leave disposable output; they are not resumable. Successful completion writes `generated/manifest.json`. Source hashes must match the pinned Kaggle v8 files. The importer reads `../../data/HI-Small_Trans.csv` and `../../data/HI-Small_accounts.csv` relative to its own location; a recipient may instead pass `--data-dir /path/to/data`. It does not download files.

`verify_import.py` is a developer-only audit of the bundled layout. It compares 52 distributed source rows field-for-field, checks full row count and SQLite integrity, verifies account/time index plans, and times five calls each on an ordinary and the busiest outgoing account. These repeated local measurements are not cold-cache performance guarantees. It writes `generated/verification.json` and query receipts. It does not inspect labels or measure detection quality.

## Files and cleanup

- `import_data.py`: pinned import, normalization, indexes and full account-join validation.
- `tools.py`: tool service and single-call JSON CLI.
- `test_tools.py`: synthetic behavior fixtures, independent of downloaded data.
- `verify_import.py`: real-data source crosscheck and timing.
- `tool-contracts.json`: function-tool schemas for a future model-loop adapter.
- `generated/transactions.sqlite`: label-free transaction and account tables plus source manifest.
- `generated/evaluator.sqlite`: source-row labels, **evaluator only**.
- `generated/receipts.sqlite`: automatically committed request/result receipts, including exact returned rows and source hash.
- `generated/manifest.json`, `verification.json`: import and validation evidence.

```sh
python3 prototype/local-data/manage.py pack
python3 prototype/local-data/manage.py clean
```

`pack` produces `generated/local-data-prototype.zip` containing code/docs/tests only. No CSVs, databases, labels, credentials, receipts, or account-specific results are included. The recipient unzips it, runs the fixture tests, supplies the two source CSVs, and imports with `--data-dir`. Source data remains subject to its publisher's CDLA-Sharing-1.0 license. `clean` deletes only this prototype's generated folder and bytecode cache. It preserves `.private/` credentials; `manage.py forget-key` removes those separately. Deleting `prototype/local-data/` removes the entire prototype without touching research or raw data.

## Agent integration

A trusted host creates `Tools(...)`, accepts only the six named tools, and calls `dispatch(name, arguments)`. Responses are JSON-compatible and successful/error receipts are committed before return. `run_case.py` registers a smaller subset of these definitions with the NVIDIA model using standard-library HTTP. No model SDK dependency is required.

| Tool | Purpose |
|---|---|
| `fetch_transactions` | One account/direction/time range, 1–500 rows, stable continuation cursor |
| `get_transactions` | 1–500 exact source-qualified transaction IDs, preserving request order |
| `get_accounts` | 1–100 composite account keys and their recorded synthetic entity metadata |
| `expand_frontier` | Up to 8 independent branch queries and 500 total requested rows |
| `summarize_activity` | Exact decimal totals by currency, external counterparties, time bounds; scans at most 10,000 rows |
| `verify_path` | 2–100 edges; source existence, connectivity, strict/non-decreasing time, optional closure and elapsed minutes |

The default authorized data interval is `[2022/09/01 00:00, 2022/09/11 00:00)`, including the proposal's preceding history. The host must distinguish reporting rows from historical support when scoring later. Constructor scope is trusted configuration and is not an agent tool. All retrieval, including exact-ID lookup and path checks, enforces that interval. The tail is stored for reproducibility but unavailable under this scope.

SQLite opens read-only for queries. A 5-second SQLite progress deadline bounds database computation; row caps bound Python summary work. Summaries that hit 10,000 rows are explicitly partial and cannot support whole-period claims. Empty scope results are complete; an unfinished page is not. Cursors bind to source hash and canonical query scope; they are continuation tokens, not authenticated security credentials. `complete` on a fetched page means no rows remain *after that page*, not that the caller has consumed all preceding pages.

Amounts remain source decimal strings and Python Decimal computes totals (100-digit working precision). Incoming sums use received currency/amount; outgoing sums use paid currency/amount. Self-transfers remain present but do not increase external-counterparty counts. Source hash + original data-row ordinal identifies each transaction, including exact duplicates. `(timestamp,row_id)` makes pagination stable without inventing chronology between equal-time rows. Account identity includes normalized bank ID; raw bank values remain available. No FX conversion or same-funds assertion is made.

## Boundary and next milestone

Label exclusion is a tool/database boundary, not an OS sandbox: any process with broad filesystem access can still read the research archive and evaluator database. A future runtime must expose only these tools and must not grant its agents shell/filesystem or arbitrary SQL access. Do not treat the CLI alone as access isolation.

Receipts provide an audit log, not exactly-once actions or full crash-resumable case state. The live runner now persists reviewer proposals/checks/decisions and provider token usage, verifies basic count aggregates and paths, and caps calls/context bytes. Durable reopening, candidate revisions, complete coverage tracking, token-based input limits, and crash recovery remain future work. `verify_path` validates the declared walk; it does not enforce a simple-cycle rubric or decide suspiciousness. The live-run report establishes model integration only; no detection-performance claim is made.

Implementation references: [SQLite multi-column query planning](https://www.sqlite.org/queryplanner.html), [Python sqlite3 documentation](https://docs.python.org/3/library/sqlite3.html).


## Historical first NVIDIA model run

```sh
python3 prototype/local-data/model.py      # tiny native tool-calling connection check
python3 prototype/local-data/run_case.py   # one bounded development case
```

Model used for this historical run: `nvidia/nemotron-3-ultra-550b-a55b`, hosted at `https://integrate.api.nvidia.com/v1/chat/completions`. The adapter reads `NVIDIA_API_KEY` from the process environment, or `.private/nvidia-key` beside the scripts. The local key file is owner-readable only and excluded from packaging and Git. Recipients supply their own credential; do not paste it into source or command history. `manage.py forget-key` removes the local credential folder. Ordinary generated-output cleanup preserves it.

The model receives only explicitly supplied synthetic transaction evidence through allowed tools. It has no filesystem, shell, SQL, evaluator or Slack access. System prompts, tool definitions, requests/responses, immutable receipts, and run settings are saved under `generated/runs/<timestamp>/`. The key and authorization headers are never included. Extended thinking is disabled and temperature is zero for this mechanics experiment.

The seed is the first original row at or after ordinal 100003 within the seven-day reporting window, excluding self-transfers. This is an arbitrary, label-free mechanics seed, not a prioritized detector or representative sample. The investigator has four model turns; the reviewer gets one tool-request round, then submits typed candidates through native tool calling. Application code checks paths and complete count aggregates; the reviewer finalizes each candidate. Investigator narrative is omitted from the reviewer's initial context. Both roles use the same underlying model, so they are not independent models.

Limits: at most 10 admitted model requests, 12 model-requested tool calls, 2048 output tokens per request, 110,000 serialized request bytes, 30 fetched rows per tool call, and 480 seconds before admitting another model request (an in-flight HTTP call can take another 90 seconds). Database checks retain the existing 5-second query deadline and summary row cap. Input bytes are an engineering memory bound, not exact token accounting. Each successful response records actual provider token counts. There are no automatic retries; failed calls may incur unreported provider usage. Monetary charges are unknown.

All findings remain **exploratory/provisional** because there is no frozen operational rule mapping or confirmatory protocol yet. A passing fact check does not approve a laundering prediction. The runtime downgrades a proposed provisional decision when required factual checks fail. Missing decisions, malformed output, exhausted limits and truncated output produce an explicit incomplete report, preserving available work. Restarting creates a new run; it does not resume an interrupted one. An exhausted investigator can still leave a packet for the separately budgeted reviewer.

The first live attempt hit the reviewer's 2048-token output cap and was retained as incomplete. A second attempt with native candidate submission and a 4096-token limit timed out at the provider. The current runner removes duplicated evidence from the reviewer packet and uses short transaction aliases (`T123` maps to the run source hash plus row 123), with a 2048-token generation limit. Canonical full IDs remain in evidence and verification records; aliases are expanded before tool execution and checking. Treat runs as development evidence, not untouched evaluation samples. Do not aggregate them into detection accuracy.

## Next prototype: broader expansion and continuation

The newer [chunked prototype](CHUNKING.md) adds multi-branch batches, persisted pending queries, fresh-process context handoffs, and an optional adapter using the actual pinned Meterless Markovian engine. [Live results](CHUNK-RESULTS.md) verify three chunks and two handoffs for each scheduler, with 81/83 cumulative transactions under a deliberately small 40-row working allowance. The current suite has 19 tests. This remains mechanics evidence, not detection validation.

## Threshold evaluation

[Measured results](THRESHOLD-RESULTS.md) and the [reproduction protocol](THRESHOLD-PROTOCOL.md) cover retrieval size, branch breadth, context-size probes, and broad/cautious/adaptive comparisons. The current evidence supports 25-row starting pages but establishes no reliable model-context row threshold. Current runtime defaults are now 25 rows per branch, one to four branches, and 150-row investigator/reviewer views. The reviewer assesses code-constructed, database-verified paths; see [current flow](CHUNKING.md). This does not promote 150 rows to a validated safe threshold. Prior experiment code is preserved in `generated/thresholds-v2/frozen-source/`. The source package includes evaluator-only reference IDs and generated summary results; raw source data and detailed run evidence remain excluded. Reproduction expects this research folder layout, the pinned pattern file under `data/`, and the imported local databases.

## Verified-path milestone

See [verification results and full-dataset readiness](VERIFIED-PATH-RESULTS.md) for the current change, limitations, and the remaining work before a dataset-wide detection test.

## Context-driven continuation

The current scheduler expands until its row allowance is full, with no fixed expansion or chunk count. Case-wide page/model-call budgets pause unfinished work, and the direct driver can resume it with additional budget. Review runs automatically only after the reachable frontier is exhausted. See [continuation behavior and commands](CHUNKING.md) and [live continuation results](CONTINUATION-RESULTS.md).

## Working-view and review-queue milestone

At a full context the model can now evict visible rows while retaining durable evidence, restore known stored rows, or request a handoff. Checkpoints receive explicit evidence deltas. All generated verified paths enter a persistent batched review queue; the default 24-path cap is removed. See [tests and live results](WORKING-VIEW-RESULTS.md).

## Independent replay audit

`replay_audit.py` independently reconstructs saved navigation and review traces from source rows, receipts and call artifacts. `replay_corruptions.py` checks deliberate corruption of disposable copies. See [results, commands and certification boundaries](REPLAY-AUDIT-RESULTS.md).
