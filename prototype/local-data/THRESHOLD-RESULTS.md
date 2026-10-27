# Threshold study: measured development results

Status: all planned conditions have a completed result or an explicit failure.

This study tests retrieval and exact graph reading on four deliberately selected IBM HI-Small cases. It does not estimate production detection quality. Failed conditions remain in denominators. The frozen protocol is in `THRESHOLD-PROTOCOL.md`.

## Practical settings supported by this study

| Setting | Development recommendation | Evidence |
|---|---|---|
| Rows per branch | 25 | Larger fixed pages did not improve the best reference recovery under the tested budgets |
| Cautious expansion | 1 branch × 25 rows | Lowest-cost candidate within the declared five-point tolerance: 66.8% additional reference recall |
| Broader expansion | 4 branches × 25 rows | Highest observed macro additional recall: 71.7%; lower returned-row cost among tied settings |
| Reliable working-view threshold | None established | No passing quality screen; do not present a row limit as a reliable smart zone. |
| Autonomous review | Not established | Most proposed paths failed deterministic checks; keep factual verification mandatory |

These are retrieval presets, not evidence of reliable laundering detection. Runtime defaults were not silently changed. No row setting is promoted as a model-quality default. Fixed budgets (599 returned rows, 24 pages, 12 decisions) were experimental controls, not optimized thresholds.

## What one case means

The three-edge-cycle case starts with one known reference edge, but the model sees only its ordinary transaction fields. Finding its other two reference edges gives additional-reference recall 1.0. The seven-edge-cycle case has six further edges to find. Labels and reference membership are used only for case preparation and post-run scoring. The ordinary control has a label-zero seed, not a certified benign neighborhood; the hub is selected by degree without labels.

| Case | Meaning |
|---|---|
| case-1 | Publisher 3-edge cycle; development selection uses reference labels |
| case-2 | Publisher 7-edge cycle; development selection uses reference labels |
| case-3 | Label-zero seed with no later external destination outflow in scope; not an all-benign neighborhood |
| case-4 | Label-free maximum-outgoing-degree account (112066 reporting-period rows) |

## Context screening

Each size has eight constructed probes: four cases in chronological and shuffled order. PASS requires at least 7/8 exact greedy traces and zero invalid-edge answers; at most one failed/invalid-format request. A pass on eight probes is not a guarantee.

| Rows | Finished / 8 | Exact / 8 | Chronological / 4 | Shuffled / 4 | Invalid edges | Failed calls | Screen | Mean input tokens | Mean seconds |
|---|---|---|---|---|---|---|---|---|---|
| 40 | 8 | 4 | 2 | 2 | 2 | 2 | FAIL | 3683.000 | 2.114 |
| 75 | 8 | 3 | 1 | 2 | 1 | 4 | FAIL | 6451.500 | 6.554 |
| 150 | 8 | 6 | 3 | 3 | 2 | 0 | FAIL | 12355.500 | 11.720 |
| 300 | 8 | 5 | 2 | 3 | 3 | 0 | FAIL | 24153.750 | 6.056 |
| 750 | 8 | 6 | 2 | 4 | 1 | 1 | FAIL | 59814.286 | 3.799 |
| 1500 | 8 | 5 | 2 | 3 | 2 | 1 | FAIL | 119151.429 | 6.034 |

## Expansion grid (no model calls)

Same 300-row view, 599 returned rows including repeats, 24 page queries and 12 decisions. Additional recall is the unweighted mean over the two reference cycles; the supplied seed is excluded. Other columns average all four cases.

| Branches | Rows/page | Additional recall | Mean returned rows | Mean pages | Mean repeat fraction |
|---|---|---|---|---|---|
| 1 | 25 | 0.750 | 142.000 | 12.000 | 0.084 |
| 1 | 100 | 0.750 | 262.250 | 11.250 | 0.066 |
| 1 | 250 | 0.750 | 329.250 | 10.500 | 0.061 |
| 1 | 500 | 0.750 | 338.500 | 10.250 | 0.060 |
| 2 | 25 | 0.750 | 326.500 | 24.000 | 0.080 |
| 2 | 100 | 0.750 | 378.250 | 19.000 | 0.079 |
| 2 | 250 | 0.750 | 359.000 | 17.750 | 0.074 |
| 2 | 500 | 0.750 | 348.000 | 19.500 | 0.066 |
| 4 | 25 | 0.750 | 230.000 | 24.000 | 0.122 |
| 4 | 100 | 0.750 | 359.500 | 23.750 | 0.086 |
| 4 | 250 | 0.750 | 272.500 | 22.250 | 0.078 |
| 4 | 500 | 0.750 | 222.500 | 23.500 | 0.118 |

The predeclared recall-within-five-points, then lowest-returned-rows rule selects 1 branch(es) × 25 rows for a **development candidate**, not a universal optimum.

Large-page results depend on the current scheduler: requests are capped in listed order, so an early large page can leave only one row for a later branch. This is a comparison within the fixed row/page/decision budgets, not evidence that 500-row pages are universally inferior.

## Working-view sensitivity of fixed broad navigation

| View limit | Additional recall | Mean returned rows | Mean pages |
|---|---|---|---|
| 150 | 0.750 | 235.000 | 24.000 |
| 300 | 0.750 | 359.500 | 23.750 |
| 750 | 0.750 | 378.250 | 20.500 |
| 1500 | 0.750 | 378.250 | 20.500 |

Smallest view meeting both the context screen and retrieval rule: none established. This comparison holds the broad policy fixed; it does not establish an adaptive-policy optimum.

## Live navigation comparison

Two repetitions per policy and case. All policies share maximum retrieval/decision allowances and a real-model reviewer. Fixed policies require no investigator model calls. Coverage includes partial evidence from failed runs; factual path counts below include completed reviews only. A failure is not silently retried.

| Policy | Completed / 8 | Failed | Pending | Mean additional recall (partial included) | Mean rows | Mean model calls | Total reported tokens | Valid/proposed paths |
|---|---|---|---|---|---|---|---|---|
| broad | 7 | 1 | 0 | 0.750 | 341.000 | 2.750 | 290687 | 1/26 |
| cautious | 7 | 1 | 0 | 0.750 | 135.500 | 2.000 | 100367 | 3/16 |
| adaptive | 8 | 0 | 0 | 0.750 | 364.500 | 10.500 | 907434 | 1/28 |

| Policy | Case | Repeat | Status | Additional recall | Rows | Calls | Tokens | Valid paths | Proposed paths |
|---|---|---|---|---|---|---|---|---|---|
| broad | case-1 | 0 | completed | 1.000 | 89 | 2 | 11459 | 0 | 2 |
| broad | case-1 | 1 | completed | 1.000 | 89 | 2 | 12164 | 1 | 2 |
| broad | case-2 | 0 | completed | 0.500 | 500 | 3 | 51392 | 0 | 4 |
| broad | case-2 | 1 | completed | 0.500 | 500 | 3 | 51466 | 0 | 4 |
| broad | case-3 | 0 | completed | — | 181 | 2 | 20063 | 0 | 2 |
| broad | case-3 | 1 | failed | — | 181 | 2 | 17261 | — | — |
| broad | case-4 | 0 | completed | — | 594 | 4 | 62961 | 0 | 6 |
| broad | case-4 | 1 | completed | — | 594 | 4 | 63921 | 0 | 6 |
| cautious | case-1 | 0 | completed | 1.000 | 64 | 2 | 9869 | 1 | 2 |
| cautious | case-1 | 1 | completed | 1.000 | 64 | 2 | 9696 | 1 | 2 |
| cautious | case-2 | 0 | completed | 0.500 | 107 | 2 | 14129 | 0 | 2 |
| cautious | case-2 | 1 | completed | 0.500 | 107 | 2 | 13623 | 0 | 2 |
| cautious | case-3 | 0 | completed | — | 71 | 2 | 10166 | 0 | 2 |
| cautious | case-3 | 1 | completed | — | 71 | 2 | 9645 | 1 | 2 |
| cautious | case-4 | 0 | completed | — | 300 | 3 | 33239 | 0 | 4 |
| cautious | case-4 | 1 | failed | — | 300 | 1 | 0 | — | — |
| adaptive | case-1 | 0 | completed | 1.000 | 75 | 9 | 48856 | 0 | 2 |
| adaptive | case-1 | 1 | completed | 1.000 | 89 | 8 | 41106 | 1 | 2 |
| adaptive | case-2 | 0 | completed | 0.500 | 587 | 11 | 158131 | 0 | 4 |
| adaptive | case-2 | 1 | completed | 0.500 | 550 | 15 | 213932 | 0 | 4 |
| adaptive | case-3 | 0 | completed | — | 232 | 10 | 99983 | 0 | 2 |
| adaptive | case-3 | 1 | completed | — | 189 | 9 | 74002 | 0 | 2 |
| adaptive | case-4 | 0 | completed | — | 597 | 11 | 135795 | 0 | 6 |
| adaptive | case-4 | 1 | completed | — | 597 | 11 | 135629 | 0 | 6 |

## Actual provider usage

| Requests | Input tokens | Output tokens | Total tokens | Unknown-usage requests |
|---|---|---|---|---|
| 223 | 3946249 | 41493 | 3987742 | 12 |

Account dollar pricing is unavailable. Reported tokens include failed calls when the provider returned usage; unknown consumption is not treated as zero. Two concurrent jobs and network variability make elapsed times observational, not controlled latency benchmarks.

## What these results cannot establish

Only two deliberately selected reference networks contribute known-pattern recall. The context test contains controlled distractors and a specific three-edge tracing instruction; passing it does not prove reliable open-ended investigation, aggregation, suspicion judgments, or 1,500-row review. The navigation experiment uses deterministic seed-plus-six-row carryover, not the earlier model-summary/Meterless choreography. Repeated same-prompt runs on the same cases are not independent population samples. Valid connectivity does not establish laundering or conserved funds. Unfinished branches remain unknown.

## Recorded navigation failures

| Policy | Case | Repeat | Error |
|---|---|---|---|
| broad | case-3 | 1 | The read operation timed out |
| cautious | case-4 | 1 | NVIDIA HTTP 500 |

## Broader offline sensitivity check

After the first two reference networks gave identical recovery across settings, a separate deterministic sweep selected the first four fully in-scope publisher groups of 3–12 edges from each of CYCLE, RANDOM, FAN-IN and FAN-OUT. These 16 enriched development cases add shape diversity; they are not an independent holdout and do not change the live scoring gates. All values below are additional reference recall, excluding the seed.

| Branches | Page | View | Macro recall | Cycle | Random chain | Fan-in | Fan-out | Mean returned | Mean pages |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 25 | 300 | 0.668 | 0.542 | 0.130 | 1.000 | 1.000 | 127.062 | 12.000 |
| 1 | 100 | 300 | 0.674 | 0.567 | 0.130 | 1.000 | 1.000 | 207.562 | 11.812 |
| 1 | 250 | 300 | 0.674 | 0.567 | 0.130 | 1.000 | 1.000 | 207.562 | 11.500 |
| 1 | 500 | 300 | 0.674 | 0.567 | 0.130 | 1.000 | 1.000 | 207.562 | 11.375 |
| 2 | 25 | 300 | 0.717 | 0.633 | 0.235 | 1.000 | 1.000 | 272.062 | 23.938 |
| 2 | 100 | 300 | 0.717 | 0.633 | 0.235 | 1.000 | 1.000 | 353.438 | 22.438 |
| 2 | 250 | 300 | 0.704 | 0.608 | 0.208 | 1.000 | 1.000 | 304.875 | 22.625 |
| 2 | 500 | 300 | 0.704 | 0.608 | 0.208 | 1.000 | 1.000 | 251.625 | 22.812 |
| 4 | 25 | 300 | 0.717 | 0.633 | 0.235 | 1.000 | 1.000 | 254.312 | 24.000 |
| 4 | 100 | 300 | 0.711 | 0.608 | 0.235 | 1.000 | 1.000 | 255.188 | 23.750 |
| 4 | 250 | 300 | 0.678 | 0.542 | 0.172 | 1.000 | 1.000 | 188.625 | 24.000 |
| 4 | 500 | 300 | 0.678 | 0.542 | 0.172 | 1.000 | 1.000 | 169.875 | 24.000 |
| 4 | 100 | 150 | 0.678 | 0.542 | 0.172 | 1.000 | 1.000 | 149.438 | 24.000 |
| 4 | 100 | 750 | 0.717 | 0.633 | 0.235 | 1.000 | 1.000 | 376.125 | 23.250 |
| 4 | 100 | 1500 | 0.717 | 0.633 | 0.235 | 1.000 | 1.000 | 376.125 | 23.250 |

The same within-five-points then lowest-returned-rows rule selects 1 × 25. The full per-case results and selection manifest are under reference-sweep/. This tolerance explicitly permits some loss of recovery in exchange for lower retrieval cost; inspect family-level losses before choosing a default.

## Downward context bracket

After every original size produced invalid-edge answers, the same task and screening gate were applied at 40 and 75 rows (16 additional calls within the same cumulative budget). These are follow-up development probes on the same cases, not independent confirmation. The context table above includes them. The offline table below holds four branches fixed on the broader 16-reference set.

| View | Page size | Additional recall | Mean returned rows | Mean pages |
|---|---|---|---|---|
| 40 | 25 | 0.662 | 88.812 | 24.000 |
| 40 | 100 | 0.662 | 82.438 | 24.000 |
| 75 | 25 | 0.658 | 124.125 | 23.812 |
| 75 | 100 | 0.678 | 102.188 | 24.000 |

## Context transport/format failures

HTTP 429 and HTTP 500 are service failures, not evidence that a row count exceeded model comprehension. They remain in the end-to-end screen. The smaller-size accuracy comparison is inconclusive where rate limits prevented responses; separately, every tested size produced an invalid-edge counterexample, so none satisfies the zero-invalid-edge requirement.

| Condition | Failure |
|---|---|
| context-case-1-40-0 | NVIDIA HTTP 429 |
| context-case-1-40-1 | NVIDIA HTTP 429 |
| context-case-2-75-0 | NVIDIA HTTP 429 |
| context-case-3-75-0 | NVIDIA HTTP 429 |
| context-case-3-75-1 | NVIDIA HTTP 429 |
| context-case-4-1500-0 | NVIDIA HTTP 500 |
| context-case-4-75-0 | NVIDIA HTTP 429 |
| context-case-4-750-0 | NVIDIA HTTP 500 |

## Usage by study phase

| Phase | Requests | Reported tokens | Unknown usage |
|---|---|---|---|
| thresholds-v1-configuration-pilot | 53 | 1095366 | 2 |
| thresholds-v2 | 170 | 2892376 | 10 |
