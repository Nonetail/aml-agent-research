# Threshold evaluation protocol, v2

Frozen before live execution, 23 October 2026. This is a deliberately selected HI-Small development study, not a detector benchmark or a population-level accuracy estimate. The prior prototype established mechanics; its approximate 1,500-row capacity estimate did not measure comprehension.

The first configuration pilot was stopped because an inherited 45,000-byte request guard rejected intended 300-row views. Its records and source snapshot remain under generated/thresholds-v1. Version 2 sets an explicit 500,000-byte guard for all navigation/review requests. No scoring gate, task prompt, case selection, or retrieval allowance changed. All conditions are rerun; pilot outputs are not pooled into quality scores. Global provider accounting includes the pilot, including interrupted unknown-usage requests.

## Questions and controls

1. With the same seed, 300-row working view, 599 returned-row allowance (including duplicate returns), 24 database pages and 12 expansion decisions, how do breadth and page size change reference-pattern recovery and duplicate retrieval?
2. Under those same maximum allowances, how do fixed broad (four scopes, 100 rows each), fixed cautious (one scope, 25 rows), and model-adaptive (one to four scopes, one to 500 rows) navigation compare? Actual costs may differ; equal caps do not imply equal consumption.
3. Can the real model recover an exact chronological three-edge continuation from 150, 300, 750 and 1,500-row tables? Does performance differ between chronological and shuffled row order?

The threshold runner reuses the prototype's read-only tools, identity/cursor enforcement, compact row format, NVIDIA adapter, typed model-call validation and reviewer. It has its own fixed evaluation scheduler: full views roll to the seed plus the last six rows, with a short previous investigative question retained. The same deterministic carryover rule applies to all policies. It does not use model-written handoff summaries or Meterless, and its results must not be represented as a measurement of those components. The first 16 pending queries remain selectable. Scope is the reporting window [2022/09/04, 2022/09/11).

## Development cases

The preparation script selects the first fully in-scope, strictly chronological publisher cycles of lengths three and seven that pass exact source matching and path verification; an ordinary label-zero seed with no later external destination outflow in scope; and the label-free maximum-outgoing-degree account. It saves exact selections, source hashes and reference IDs in evaluator-only fixtures. A label-zero seed does not make the retrieved neighborhood benign. These four cases deliberately cover two positive networks, a missing-continuation control and a large-account stress case. They are too few and too selected to estimate production performance.

The model never receives labels, reference groups, case descriptions or expected trace answers. Source rows have stable source-qualified IDs, shortened to T-prefixed ordinals in requests. Preparation and post-run scoring can read evaluator labels; runtime navigation and review cannot query them through the tools.

## Experiments

- Offline expansion grid: breadth 1, 2, 4 × page size 25, 100, 250, 500 × four cases. Fixed pending-order traversal; no model calls. Also repeat broad 4×100 at all four working-view ceilings. These 64 runs measure retrieval behavior, not model quality.
- Live navigation: all three policies × four cases × two repetitions. Baselines use no investigator model calls; every run uses the same real-model reviewer. Adaptive uses at most 12 investigator calls. Reviewer views are capped at 300 with five-row overlap, followed by factual path checks and finalization. Failure is retained as failure, never retried invisibly or omitted from denominators.
- Live context: four cases × four sizes × two orders, 32 calls. Each packet contains fixed real core rows and increasing real high-degree-account distractors. Distractor source accounts cannot replace the core's next edges. Positive packets contain three connected edges. The ordinary control has no continuation. The hub core follows its real earliest qualifying outgoing continuation, if any. This constructed packet experiment measures exact reading under clutter, not natural neighborhood prevalence.

The context task is precisely defined: start at the supplied seed; append the earliest strictly later external outgoing transaction from its destination; break timestamp ties by numeric row ID; repeat to three transactions or stop if none exists in the supplied table. The oracle performs that operation deterministically. A valid alternative path is not an exact answer. Missing-context claims are restricted to the supplied table. No LLM judge is used.

The frozen runner embeds the exact model task, and saved requests preserve its rendered form. Independent scoring tests cover bank identity, strict timestamps, numeric tie breaks, self-transfers, missing continuations, unknown IDs and valid-but-wrong alternatives.

## Decision rules declared before live runs

- Context screening gate: at least 7/8 exact answers at a size, no invalid-edge answers, and no more than one failed/invalid-format request. A failure counts as non-exact. A passing screen is provisional evidence on eight constructed probes, not a reliability guarantee. Report chronological/shuffled results separately. Do not relax this gate after seeing outcomes.
- Expansion candidate: identify configurations within five percentage points of the best mean *additional* reference recall (excluding the supplied seed); prefer fewer returned rows, then fewer query pages. Report each reference case separately, and include the hub's duplicate/cost behavior. Only two known networks contribute reference recall, so the result is a development default, not an optimal universal threshold.
- Working-view default: among the sizes that pass context screening, prefer the smallest whose offline broad-policy additional reference recall is within five points of the best tested view. Show whether larger views materially alter retrieval or only token/latency cost.
- Live navigation: report repeated case-level coverage, candidate factual validity, completion, tokens, duplicate rows and handoff counts. If adaptive does not improve coverage at acceptable cost, do not recommend it as the default merely because it is agentic. No statistical significance claim from two repetitions.
- A failed context gate or uniformly invalid reviewer paths is an actionable negative result; do not reinterpret token fit as a quality pass. Navigation/reference recall and reviewer path validity are separate outcomes.

## Budget, provenance and outputs

Up to two independent jobs run concurrently, with a shared ceiling of 240 provider requests and six million reported tokens plus conservative allowance for in-flight or unknown-usage calls. Estimated use is 120–200 calls and 2–4 million tokens; the actual account dollar rate is unavailable. Unknown usage remains explicit. The endpoint is https://integrate.api.nvidia.com/v1/chat/completions; model is nvidia/nemotron-3-ultra-550b-a55b with thinking disabled. No local web-service port is involved.

Source-code hashes, packet hashes, source-data identity, model, endpoint and fixed limits are in generated/thresholds-v2/manifest.json. The runner refuses changed frozen source/fixtures. Requests, responses, receipts, failures and global provider usage are retained under that directory, excluded from the handover ZIP. The source-only ZIP contains the runner, protocol and scoring tests. Reports must be generated from stored results and include all failed attempts.

Run from the research root:

```sh
python3 prototype/local-data/threshold_eval.py prepare  # once; refuses overwriting frozen fixtures
python3 prototype/local-data/threshold_eval.py offline
python3 prototype/local-data/threshold_eval.py live
```

A later live invocation skips existing completed or incomplete directories; it never silently retries a failed condition. A deliberate repeat must have a new recorded run identity. The current study is not a holdout: later confirmation needs new cases and a frozen configuration.


## Follow-up sensitivity checks

The first two reference networks did not discriminate page sizes, so a separate offline sweep selected the first four fully scoped publisher groups of 3–12 edges in each CYCLE, RANDOM, FAN-IN and FAN-OUT family. Its manifest and 240 results are in `generated/thresholds-v2/reference-sweep/`; it adds shape diversity without changing the live protocol or claiming an independent holdout.

After each original context size produced an invalid-edge answer, a downward bracket tested 40 and 75 rows with the same four cases, two orders and unchanged screening gate. The 16 extra calls stayed within the same cumulative API budget. A further 64 offline runs measured the lower views on the 16 reference networks with four branches and page sizes 25/100. Six smaller-context calls received HTTP 429: do not interpret rate-limit failures as model-comprehension failures. No original output or failed condition was overwritten.

Additional commands:

```sh
python3 prototype/local-data/threshold_sweep.py
python3 prototype/local-data/threshold_lower_context.py offline
# Run only after the primary live batch has stopped; shares its provider budget.
python3 prototype/local-data/threshold_lower_context.py live
python3 prototype/local-data/threshold_report.py
python3 prototype/local-data/threshold_verify.py
```

`threshold-golden-evaluator.json` is the small source-package golden reference manifest (IDs and expected traces only), explicitly evaluator-only. Full packets and receipts stay in generated output. `threshold-results.json` and `THRESHOLD-RESULTS.md` are generated summaries, included in the source handover; the full report HTML remains beside the local evidence.
