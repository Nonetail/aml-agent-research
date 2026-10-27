# Persistent whole-dataset traversal prototype

The scanner answers a coverage question: can a single continuing workflow enumerate every transaction in a pinned source/time scope, cross disconnected components, and resume without repeating committed pages? It makes no model calls and does not claim that retrieved transactions were reviewed.

## Running

From this directory:

```
python3 global_scan.py run generated/global-scan-v1/ledger.sqlite --max-pages 1000
python3 global_scan.py run generated/global-scan-v1/ledger.sqlite
python3 global_scan.py status generated/global-scan-v1/ledger.sqlite
python3 coverage_verify.py generated/global-scan-v1/ledger.sqlite --database generated/transactions.sqlite
```

The first command pauses after 1,000 pages. The second resumes the same ledger. `--seed` selects an arbitrary initial source row on a new scan; subsequent seeds are the lowest unvisited source IDs. Start/end parameters are half-open and pinned on creation. By default, the offline scan covers the entire timestamp range in the source CSV, including dates outside the existing model runner's reporting window. The separate global model runner below also uses the full source range; the original case runner retains its narrower reporting window.

Account identity is `(bank, account)`. Traversal follows incoming and outgoing transfers, so components mean weakly connected components within the selected time range, not temporal paths or laundering schemes. Each discovered account creates two uniquely keyed query scopes. Stable timestamp/row-ID cursors page each scope to exhaustion. A new seed is selected only after all current pending scopes are exhausted.

SQLite stores unique discovered transaction IDs, components, pending/completed scopes, cursor/page history and review work. The source remains read-only. Page size defaults to 25; no total-page or component-count cap is required. `--max-pages` pauses work without declaring completion. A single-writer lock protects each ledger. FULL-synchronous WAL transactions commit up to 100 pages together; interruption rolls back the unfinished transaction, so up to 99 page reads can repeat without duplicate committed work.

## Review is separate

`claim_review()` allocates at most 150 rows, with source/scope/component/evidence-revision identity. It returns the same pending job for resumption. New component evidence changes its revision: older pending or completed jobs remain historical, and their rows become eligible for fresh review.

Review completion requires a case bound before reviewer execution, a matching time scope and frozen case evidence, and an independently replayable reviewer trace covering the allocated rows. Merely importing an old assessment is insufficient. Completion means rows appeared in completed reviewer packets; it does not mean every possible relationship was assessed. `graph_review_complete` therefore remains false: no exhaustive relationship-review policy has been established.

`global_agent.py` now routes model-selected navigation and verified-path review through the same global ledger. It uses a separate ledger from the completed offline traversal. Requests and responses are journaled before applying effects; source pages, view changes and review receipts are independently replayable. Provider failures pause with persisted cooldown and unfinished work.

```
python3 global_agent.py generated/global-agent-live-v1 --seed 100003
python3 global_agent_audit.py generated/global-agent-live-v1
# Resume the same workflow; extend cumulative allowances only when desired:
python3 global_agent.py generated/global-agent-live-v1 --add-pages 12 --add-calls 40
```

The initial allowance is 12 pages, 40 model requests and 500,000 conservatively charged tokens. Failed requests retain a token reservation because provider usage is unknown. The working view holds at most 150 rows; navigation selects 1–4 scopes with at most 25 rows per page. Budget exhaustion pauses without declaring exploration complete. Received responses survive restart without repeating their provider request.

Review groups contain at most 150 rows from one component revision. Candidate paths are generated and source-verified in code, then assessed by the model. Paths crossing review-group boundaries are currently omitted: complete row-review coverage is not exhaustive graph investigation. A new component revision makes prior review coverage historical and eligible for reassessment.

The first live attempt on 2026-10-23 returned NVIDIA HTTP 500 on its first request. Its partial-state audit passed, but no navigation pages or reviewer calls completed. Scripted integration tests cover disconnected components, budget/resume, provider pause and publication at the call limit. The subsequent Lightning-model retry passed a bounded live E2E: 12 pages, 100 unique rows, four navigation calls and four reviewer calls, with independent replay passing. It paused at the page allowance with 33 scopes pending. The adapter omits unsupported provider-schema uniqueItems while preserving local validation. This proves bounded workflow execution, not complete graph investigation or detection quality.

## Independent verification

The verifier streams source rows and independently reconstructs connected components. It checks exact transaction coverage, account/direction scope inventory, cursor continuity, page totals and component membership. It uses account-sized memory rather than retaining millions of transaction objects. Its limits are explicit: it trusts the local source metadata hash, does not replay every page digest, and cannot certify model interpretation or detection quality.


## Full live run

`python3 global_agent.py generated/global-agent-live-v1 --full` resumes the same ledger and persists full-run mode. This bypasses cumulative page, request and token allowances; it preserves the 150-row view, 25-row page size, request-size guard, local validation and provider-error pauses. It is intended to continue to source exhaustion and row-review completion, with potentially substantial provider usage. Resume with the same command after resolving a failure. Full-run mode remains enabled on that ledger on subsequent invocations. Existing model handoffs determine review timing; review-group path limitations still apply. The bounded result is preserved under `before-full-run/`.
