# Family 1 context and navigation evaluation

Latest: [Compact cycle matches with confidence](COMPACT-CYCLE-DETECTION.md) enforces transaction IDs plus a bounded confidence percentage. On the same 100-row case, one fresh Sol medium subject found all six cycles with no invalid claims; both NVIDIA Ultra thinking-off calls returned empty matches. Compact output alone does not solve detection quality.

Completed 24 October 2026. Start with [results](RESULTS.md), [model/token accounting](model-context.md), the [frozen protocol](PROTOCOL.md), and [independent results audit](results-audit.md).

Follow-up: [GPT-6 Ultra replication](GPT6-COMPARISON.md) recovered all six structural cycles, including the reference target, in both fresh runs of the exact 32-row case. This qualifies the configuration-specific failures below; it does not yet establish a larger operating boundary or laundering-classification accuracy.

Further follow-up: [GPT-6 medium at 1,500 rows](GPT6-MEDIUM-1500.md) found the reference in both unsplit repeats, recovering four and six of the six structural cycles. All 2-, 3- and 4-group repeats recovered six of six with no invalid claims. This used 20 isolated subjects on one constructed two-edge-cycle case; it does not establish population accuracy or a universal context boundary.

[NVIDIA Ultra with thinking requested, 38/100 rows](NVIDIA-ULTRA-MINI.md) recovered six and four of six cycles at 38 rows. At 100 rows, the initial calls truncated or timed out; a separate larger-output-budget diagnostic produced one truncation and one valid four-of-six response. All three completed, scored responses found the reference without invalid claims. Six attempts reported 94,474 known tokens plus unknown usage from one timeout. The mini-evaluation uses explicit model/reasoning overrides; other callers retain their existing defaults.

[Timeout investigation](NVIDIA-TIMEOUT-DIAGNOSIS.md) inspected the truncated content and ran two identical 100-row requests with only thinking disabled. Both completed in about six seconds, but missed the reference; one found two valid cycles and the other made invalid claims. This implicates the thinking-enabled generation path in the long-output behavior without establishing the hosted backend cause or a satisfactory detection fix.

The experiment completed 105 hosted attempts using the current NVIDIA Nemotron 3.5 Lightning 30B-A3B configuration with thinking disabled. None of the background-containing requests produced a valid cycle, even before whole-response rejection. The three core-only controls recovered their exact 2-, 3- and 4-edge cycles. This does not establish a useful context boundary or a laundering classifier.

The model advertises one million tokens; the largest successful input here was 189,980. Token admission used the pinned public tokenizer, a 200,000 total ceiling, 4,096 output reserve and 4,096 safety margin. Every returned provider input count differed from the local count by one token. Actual positive-case 1,500-row CSV inputs were about 122,000 tokens, so a row limit must not substitute for counting the final request.

Known provider usage was 7,402,990 tokens. One failed request has unknown provider usage; its 130,851-unit conservative reservation is separate from reported usage. Two returned responses were truncated. The account dollar tariff is unavailable.

## Interpretation

- A larger advertised context did not imply reliable cycle discovery in this configuration. The 32/300/750-row screens failed; 1,500-row development results include one unavailable response and no recovery in the other five. The separate six held-out 1,500-row responses also recovered no reference.
- Graph grouping preserved the reference supports but did not improve model recovery. Chronological grouping split the four-edge reference, showing why a grouping policy needs its own retention check.
- The 0/25/50/75 percent overlap experiment measured coverage within a prebuilt source pool. No first response supplied a valid cycle, so every anchor used the declared degree fallback and whole-path carryover was unavailable. It cannot establish model-guided navigation quality or an optimal overlap.
- The four-edge development packet contains 219 cycles. Exhaustive output is also constrained by the fixed output reserve; target recovery and output truncation are separate measures.
- Three successful core-only controls are a minimal sanity check, not a reliable operating point. The selected stress cases and shared backgrounds cannot estimate population precision or recall.

For this family, retain deterministic cycle discovery and exact verification in code. Treat the model as an evaluator of small, complete candidate evidence while its interpretation quality is tested separately. Broad database retrieval can remain aggressive because retrieval size and model-view size are different boundaries. Preserve exact pending paths and candidate supports across views; do not choose a low-overlap default from these failed discovery results.

## Reproduce without spending

From the research root:

```sh
python3 prototype/local-data/cycle_context_report.py
python3 -m unittest discover -s prototype/local-data -p 'test_cycle*.py'
```

The report generator reads saved results and performs no hosted calls. The [context measurements](model-context.md#reproduce) also run locally. The original source database and paused full-source batch ledger were not modified.

## Recorded execution

The runner reused the existing NVIDIA transport and fixed family-1 reviewer, with a frozen CSV format instruction and no supplied candidate supports. Public tokenizer/config/template files are pinned and hashed. Model requests receive no case labels, reference IDs, evaluator answers, files or tools for reading local data. Each hosted call starts a fresh context.

The executed commands were `cycle_context_eval.py prepare`, `probe`, `initial`, and `followup`, then `cycle_context_diagnostics.py` and its conditional `--confirm` selection. The 32-row screen failed, so confirmation at that size was not selected. Use `/tmp/aml-nemotron-tokenizer-venv/bin/python` after installing the pinned requirements documented in the model report. Live commands reuse the saved manifest and skip existing attempts; they are not needed to inspect these results.

[Generated evidence](../../prototype/local-data/generated/cycle-context-v1/manifest.json) includes exact packets, requests, responses, raw and accepted scores, source snapshots and accounting. `cycle-context-preflight-v1` preserves an earlier preparation before final audit fixes; it made no hosted calls and is not part of the reported experiment. The diagnostic protocol and job manifest explicitly record their post-screen selection.
