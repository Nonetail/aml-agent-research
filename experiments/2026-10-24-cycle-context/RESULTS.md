# Live cycle context experiment results

Snapshot: 2026-10-24T01:25:06.452167+11:00 (Australia/Sydney). State: **completed_with_provider_errors**.

105 saved planned calls (9 post-hoc diagnostics); 105 attempted, 104 responses returned, 1 provider errors, 0 in flight or interrupted. Provider errors are operationally inconclusive; returned schema failures and truncations are quality failures. Execution is finished when all saved planned attempts have terminal outcomes; provider errors can still leave quality gates inconclusive. An unfinished or absent follow-up matrix remains incomplete.

Before whole-response acceptance, 102 scored responses contain **3 raw valid cycle claims and 3 raw reference recoveries**; 0 valid claims were excluded by the whole-response contract. Excluding core-only sanity checks, 99 scored responses contain 0 raw valid cycles and 0 raw reference recoveries. These counts exclude 2 returned responses that could not be scored, and count each repeat separately.

## Screening gates

| Cohort / view | Returned / 6 | Reference recoveries / 6 | Invalid true / unknown IDs | Decision |
|---|---|---|---|---|
| dev / single-300 | 6 | 0 | 4 / 0 | fail |
| dev / single-750 | 6 | 0 | 8 / 1 | fail |
| dev / single-1500 | 5 | 0 | 7 / 2 | incomplete |
| holdout / single-1500 | 6 | 0 | 5 / 6 | fail |
| holdout grouped / graph-2 | 6 | 0 | 2 / 0 | fail |

Pass requires at least five of six reference recoveries, all six returned response slots, and zero invalid-edge or unsupported-ID claims. Passing is provisional evidence on these constructed cases.

## Positive cases: individual repetitions

| Case | View | Repeat | Rows | Outcome | Reference | Cycles recovered / oracle | Invalid true / unknown | Provider total |
|---|---|---|---|---|---|---|---|---|
| Development 2-edge | single-1500 | 1 | 1500 | invalid factual claim | 0/1 | 0/6 | 1/0 | 122,105 |
| Development 2-edge | single-1500 | 2 | 1500 | invalid factual claim | 0/1 | 0/6 | 1/0 | 122,127 |
| Development 2-edge | single-300 | 1 | 300 | valid incomplete discovery | 0/1 | 0/6 | 0/0 | 25,947 |
| Development 2-edge | single-300 | 2 | 300 | invalid factual claim | 0/1 | 0/6 | 1/0 | 26,134 |
| Development 2-edge | single-750 | 1 | 750 | valid incomplete discovery | 0/1 | 0/6 | 0/0 | 61,968 |
| Development 2-edge | single-750 | 2 | 750 | invalid factual claim | 0/1 | 0/6 | 1/0 | 62,130 |
| Development 2-edge | input-150000 | 1 | 1849 | invalid factual claim | 0/1 | 0/6 | 1/0 | 150,136 |
| Development 2-edge | input-190000 | 1 | 2348 | invalid factual claim | 0/1 | 0/6 | 1/0 | 190,211 |
| Development 3-edge | single-1500 | 1 | 1500 | invalid factual claim | 0/1 | 0/1 | 3/0 | 122,346 |
| Development 3-edge | single-1500 | 2 | 1500 | invalid factual claim | 0/1 | 0/1 | 1/1 | 122,349 |
| Development 3-edge | single-300 | 1 | 300 | invalid factual claim | 0/1 | 0/1 | 2/0 | 26,266 |
| Development 3-edge | single-300 | 2 | 300 | output truncation | 0/1 | 0/1 | 0/0 | 29,935 |
| Development 3-edge | single-750 | 1 | 750 | output truncation | 0/1 | 0/1 | 0/0 | 65,961 |
| Development 3-edge | single-750 | 2 | 750 | invalid factual claim | 0/1 | 0/1 | 3/1 | 62,745 |
| Development 3-edge | input-150000 | 1 | 1850 | invalid factual claim | 0/1 | 0/1 | 1/0 | 150,104 |
| Development 3-edge | input-190000 | 1 | 2349 | invalid factual claim | 0/1 | 0/1 | 1/0 | 190,248 |
| Development 4-edge | single-1500 | 1 | 1500 | invalid factual claim | 0/1 | 0/219 | 1/1 | 122,999 |
| Development 4-edge | single-1500 | 2 | 1500 | provider_error | 0/1 | 0/219 | 0/0 | — |
| Development 4-edge | single-300 | 1 | 300 | valid incomplete discovery | 0/1 | 0/219 | 0/0 | 26,668 |
| Development 4-edge | single-300 | 2 | 300 | invalid factual claim | 0/1 | 0/219 | 1/0 | 27,007 |
| Development 4-edge | single-750 | 1 | 750 | invalid factual claim | 0/1 | 0/219 | 1/0 | 63,011 |
| Development 4-edge | single-750 | 2 | 750 | invalid factual claim | 0/1 | 0/219 | 3/0 | 63,532 |
| Development 4-edge | input-150000 | 1 | 1840 | invalid factual claim | 0/1 | 0/219 | 1/1 | 150,406 |
| Development 4-edge | input-190000 | 1 | 2339 | invalid factual claim | 0/1 | 0/219 | 1/0 | 190,284 |
| Held-out 2-edge | single-1500 | 1 | 1500 | invalid factual claim | 0/1 | 0/1 | 1/0 | 122,219 |
| Held-out 2-edge | single-1500 | 2 | 1500 | invalid factual claim | 0/1 | 0/1 | 1/0 | 122,194 |
| Held-out 3-edge | single-1500 | 1 | 1500 | invalid factual claim | 0/1 | 0/1 | 1/0 | 122,345 |
| Held-out 3-edge | single-1500 | 2 | 1500 | valid incomplete discovery | 0/1 | 0/1 | 0/0 | 122,052 |
| Held-out 4-edge | single-1500 | 1 | 1500 | invalid factual claim | 0/1 | 0/4 | 1/3 | 122,104 |
| Held-out 4-edge | single-1500 | 2 | 1500 | invalid factual claim | 0/1 | 0/4 | 1/3 | 122,100 |

## Controls and accepted-cycle labels

| Case | Repeat | Outcome | Positive rows | Cycles recovered / oracle | Zero / all-positive / mixed / unknown | Control check | Investigate positive / zero rows |
|---|---|---|---|---|---|---|---|
| Zero-label cycle control | 1 | invalid factual claim | 2 | 0/1 | 0 / 0 / 0 / 0 | False | 0 / 0 |
| Zero-label cycle control | 2 | invalid factual claim | 2 | 0/1 | 0 / 0 / 0 / 0 | False | 0 / 0 |
| Constructed acyclic control | 1 | invalid factual claim | 2 | 0/0 | 0 / 0 / 0 / 0 | False | 0 / 0 |
| Constructed acyclic control | 2 | invalid factual claim | 2 | 0/0 | 0 / 0 / 0 / 0 | False | 0 / 0 |
| Natural-window control | 1 | invalid factual claim | 1 | 0/0 | 0 / 0 / 0 / 0 | natural sample | 0 / 0 |
| Natural-window control | 2 | invalid factual claim | 1 | 0/0 | 0 / 0 / 0 / 0 | natural sample | 0 / 0 |

Valid zero-label cycles are structural successes. A zero oracle denominator has undefined recall; valid empty output can still be exact. Hidden labels do not establish whether an economic concern was justified.

## Grouping: union recovery and retention

| Case | Policy / repeat | View rows | Reference recovered / visible / original | Cycles recovered / visible / original | Union rows / duplicates | Returned / planned | Δ reference / cycles vs baseline | Total tokens / peak input |
|---|---|---|---|---|---|---|---|---|
| Development 2-edge | chronological-3 / 1 | 500/500/500 | 0/1/1 | 0/6/6 | 1500 / 0 | 3/3 | +0 / +0 | 126,316 / 42,103 |
| Development 2-edge | graph-2 / 1 | 750/750 | 0/1/1 | 0/6/6 | 1500 / 0 | 2/2 | +0 / +0 | 123,936 / 61,967 |
| Development 2-edge | graph-3 / 1 | 500/500/500 | 0/1/1 | 0/6/6 | 1500 / 0 | 3/3 | +0 / +0 | 126,253 / 42,308 |
| Development 2-edge | graph-4 / 1 | 376/375/375/374 | 0/1/1 | 0/6/6 | 1500 / 0 | 4/4 | +0 / +0 | 128,110 / 32,088 |
| Development 3-edge | chronological-3 / 1 | 500/500/500 | 0/1/1 | 0/1/1 | 1500 / 0 | 3/3 | +0 / +0 | 126,129 / 42,074 |
| Development 3-edge | graph-2 / 1 | 750/750 | 0/1/1 | 0/1/1 | 1500 / 0 | 2/2 | +0 / +0 | 124,315 / 61,897 |
| Development 3-edge | graph-3 / 1 | 500/500/500 | 0/1/1 | 0/1/1 | 1500 / 0 | 3/3 | +0 / +0 | 125,880 / 42,246 |
| Development 3-edge | graph-4 / 1 | 375/375/375/375 | 0/1/1 | 0/1/1 | 1500 / 0 | 4/4 | +0 / +0 | 128,301 / 32,038 |
| Development 4-edge | chronological-3 / 1 | 500/500/500 | 0/0/1 | 0/57/219 | 1500 / 0 | 3/3 | +0 / +0 | 126,941 / 42,369 |
| Development 4-edge | graph-2 / 1 | 750/750 | 0/1/1 | 0/219/219 | 1500 / 0 | 2/2 | +0 / +0 | 124,653 / 62,681 |
| Development 4-edge | graph-3 / 1 | 500/500/500 | 0/1/1 | 0/219/219 | 1500 / 0 | 3/3 | +0 / +0 | 126,690 / 42,562 |
| Development 4-edge | graph-4 / 1 | 375/375/375/375 | 0/1/1 | 0/219/219 | 1500 / 0 | 4/4 | +0 / +0 | 128,845 / 32,693 |
| Held-out 2-edge | graph-2 / 1 | 750/750 | 0/1/1 | 0/1/1 | 1500 / 0 | 2/2 | +0 / +0 | 124,175 / 62,011 |
| Held-out 2-edge | graph-2 / 2 | 750/750 | 0/1/1 | 0/1/1 | 1500 / 0 | 2/2 | +0 / +0 | 123,919 / 62,011 |
| Held-out 3-edge | graph-2 / 1 | 750/750 | 0/1/1 | 0/1/1 | 1500 / 0 | 2/2 | +0 / +0 | 124,017 / 62,020 |
| Held-out 3-edge | graph-2 / 2 | 750/750 | 0/1/1 | 0/1/1 | 1500 / 0 | 2/2 | +0 / +0 | 124,007 / 62,020 |
| Held-out 4-edge | graph-2 / 1 | 750/750 | 0/1/1 | 0/4/4 | 1500 / 0 | 2/2 | +0 / +0 | 124,109 / 61,900 |
| Held-out 4-edge | graph-2 / 2 | 750/750 | 0/1/1 | 0/4/4 | 1500 / 0 | 2/2 | +0 / +0 | 123,833 / 61,900 |

Visible counts are deduplicated supports wholly contained in at least one view. Original counts use the whole common 1,500-row packet. Loss of support across a cut is a grouping retention loss. Smaller peak context can require more total calls and tokens.

Saved development selection: **2 graph views**. Max development complete-episode recovery, then structural recall, then fewer invalid/unavailable calls, then fewer reported tokens, then fewer groups.
No development grouping recovered a reference: selection is diagnostic, with **no demonstrated grouping advantage**.

## Post-hoc lower-boundary diagnostics

These conditions were added after observing the frozen experiment. They are reported separately and do not retroactively change its gates. Core-only packets test minimal format and prompt understanding, not discovery amid ordinary background.

| Case | Condition | Repeat | Rows | Outcome | Reference | Cycles recovered / oracle | Provider total |
|---|---|---|---|---|---|---|---|
| Development 2-edge | single-32 | 1 | 32 | invalid factual claim | 0/1 | 0/6 | 4,933 |
| Development 2-edge | single-32 | 2 | 32 | invalid factual claim | 0/1 | 0/6 | 4,899 |
| Development 2-edge | core-only | 1 | 2 | valid exact | 1/1 | 1/1 | 2,343 |
| Development 3-edge | single-32 | 1 | 32 | invalid factual claim | 0/1 | 0/1 | 4,806 |
| Development 3-edge | single-32 | 2 | 32 | invalid factual claim | 0/1 | 0/1 | 4,827 |
| Development 3-edge | core-only | 1 | 3 | valid exact | 1/1 | 1/1 | 2,515 |
| Development 4-edge | single-32 | 1 | 32 | invalid factual claim | 0/1 | 0/11 | 4,965 |
| Development 4-edge | single-32 | 2 | 32 | invalid factual claim | 0/1 | 0/11 | 5,028 |
| Development 4-edge | core-only | 1 | 4 | valid exact | 1/1 | 1/1 | 2,559 |

| Post-hoc screen | Returned / 6 | Recovered / 6 | Invalid / unknown IDs | Decision |
|---|---|---|---|---|
| dev / single-32 | 6 | 0 | 6 / 0 | fail |

Held-out 32-row confirmation: **not selected**. 32-row development screen did not pass


## Next-view movement and overlap

| Case | Next view | Anchor | New / union / duplicated rows | Cycles second visible / sequence visible / whole union | Recovered union / new | Reference union / new | Returned / 2 | Sequence tokens |
|---|---|---|---|---|---|---|---|---|
| Development 2-edge | overlap-0 | degree fallback | 1499 / 2999 / 1 | 0 / 6 / 6 | 0 / 0 | 0 / 0 | 2/2 | 244,040 |
| Development 2-edge | overlap-25 | degree fallback | 1125 / 2625 / 375 | 6 / 6 / 6 | 0 / 0 | 0 / 0 | 2/2 | 244,245 |
| Development 2-edge | overlap-50 | degree fallback | 750 / 2250 / 750 | 6 / 6 / 6 | 0 / 0 | 0 / 0 | 2/2 | 243,654 |
| Development 2-edge | overlap-75 | degree fallback | 375 / 1875 / 1125 | 6 / 6 / 6 | 0 / 0 | 0 / 0 | 2/2 | 243,608 |
| Development 3-edge | overlap-0 | degree fallback | 1499 / 2999 / 1 | 0 / 1 / 1 | 0 / 0 | 0 / 0 | 2/2 | 244,031 |
| Development 3-edge | overlap-25 | degree fallback | 1125 / 2625 / 375 | 1 / 1 / 1 | 0 / 0 | 0 / 0 | 2/2 | 244,517 |
| Development 3-edge | overlap-50 | degree fallback | 750 / 2250 / 750 | 1 / 1 / 1 | 0 / 0 | 0 / 0 | 2/2 | 243,876 |
| Development 3-edge | overlap-75 | degree fallback | 375 / 1875 / 1125 | 1 / 1 / 1 | 0 / 0 | 0 / 0 | 2/2 | 244,082 |
| Development 4-edge | overlap-0 | degree fallback | 1499 / 2999 / 1 | 0 / 219 / 219 | 0 / 0 | 0 / 0 | 2/2 | 244,687 |
| Development 4-edge | overlap-25 | degree fallback | 1125 / 2625 / 375 | 219 / 219 / 219 | 0 / 0 | 0 / 0 | 2/2 | 245,818 |
| Development 4-edge | overlap-50 | degree fallback | 750 / 2250 / 750 | 219 / 219 / 219 | 0 / 0 | 0 / 0 | 2/2 | 245,322 |
| Development 4-edge | overlap-75 | degree fallback | 375 / 1875 / 1125 | 219 / 219 / 219 | 0 / 0 | 0 / 0 | 2/2 | 245,493 |

Sequence cost includes the reused first response for each paired comparison; the overall total charges that call only once. “New” recovery excludes every support already recovered in the first response. Whole-union oracle cycles can cross snapshots and be absent from both individual views. Actual duplicated rows are shown even when nominal overlap is zero. Whole-path retention is available only after a model-discovered valid path.

## Accepted-cycle label composition

| Condition | Zero-positive | All-positive | Mixed | Unknown |
|---|---|---|---|---|
| chronological-3 | 0 | 0 | 0 | 0 |
| core-only | 0 | 3 | 0 | 0 |
| graph-2 | 0 | 0 | 0 | 0 |
| graph-3 | 0 | 0 | 0 | 0 |
| graph-4 | 0 | 0 | 0 | 0 |
| input-150000 | 0 | 0 | 0 | 0 |
| input-190000 | 0 | 0 | 0 | 0 |
| overlap-0 | 0 | 0 | 0 | 0 |
| overlap-25 | 0 | 0 | 0 | 0 |
| overlap-50 | 0 | 0 | 0 | 0 |
| overlap-75 | 0 | 0 | 0 | 0 |
| single-1500 | 0 | 0 | 0 | 0 |
| single-300 | 0 | 0 | 0 | 0 |
| single-32 | 0 | 0 | 0 | 0 |
| single-750 | 0 | 0 | 0 | 0 |

Counts are per returned response, so repeats and shared evidence can count the same cycle again. Grouping and movement recovery tables separately deduplicate exact supports.

## Execution and token cost

| Condition | Planned / attempted / returned | Provider errors / quality failures | Input / output / total | Peak provider / local input | Provider − local |
|---|---|---|---|---|---|
| chronological-3 | 9 / 9 / 9 | 0 / 3 | 377,816 / 1,570 / 379,386 | 42,369 / 42,370 | [-1, -1] |
| core-only | 3 / 3 / 3 | 0 / 0 | 6,427 / 990 / 7,417 | 2,237 / 2,238 | [-1, -1] |
| graph-2 | 18 / 18 / 18 | 0 / 3 | 1,114,939 / 2,025 / 1,116,964 | 62,681 / 62,682 | [-1, -1] |
| graph-3 | 9 / 9 / 9 | 0 / 1 | 377,816 / 1,007 / 378,823 | 42,562 / 42,563 | [-1, -1] |
| graph-4 | 12 / 12 / 12 | 0 / 3 | 383,513 / 1,743 / 385,256 | 32,693 / 32,694 | [-1, -1] |
| input-150000 | 3 / 3 / 3 | 0 / 3 | 449,840 / 806 / 450,646 | 149,959 / 149,960 | [-1, -1] |
| input-190000 | 3 / 3 / 3 | 0 / 3 | 569,862 / 881 / 570,743 | 189,980 / 189,981 | [-1, -1] |
| overlap-0 | 3 / 3 / 3 | 0 / 1 | 364,920 / 388 / 365,308 | 121,643 / 121,644 | [-1, -1] |
| overlap-25 | 3 / 3 / 3 | 0 / 3 | 366,137 / 993 / 367,130 | 122,549 / 122,550 | [-1, -1] |
| overlap-50 | 3 / 3 / 3 | 0 / 0 | 365,220 / 182 / 365,402 | 122,273 / 122,274 | [-1, -1] |
| overlap-75 | 3 / 3 / 3 | 0 / 2 | 365,146 / 587 / 365,733 | 122,275 / 122,276 | [-1, -1] |
| single-1500 | 18 / 18 / 17 | 1 / 16 | 2,074,034 / 5,386 / 2,079,420 | 122,658 / 122,659 | [-1, -1] |
| single-300 | 6 / 6 / 6 | 0 / 4 | 156,652 / 5,305 / 161,957 | 26,604 / 26,605 | [-1, -1] |
| single-32 | 6 / 6 / 6 | 0 / 6 | 27,126 / 2,332 / 29,458 | 4,643 / 4,644 | [-1, -1] |
| single-750 | 6 / 6 / 6 | 0 / 5 | 372,766 / 6,581 / 379,347 | 62,627 / 62,628 | [-1, -1] |

Known provider usage: **7,402,990 tokens** across 104 calls. Unknown usage: 1 calls, with 130,851 reserved token units retained separately. Sum of call latency: 977.0 seconds; this is not parallel wall time. No dollar cost is asserted because the account tariff is unknown.

## Limits and outstanding work


### Output-capacity confound

| Base case | Oracle cycles | Tiny-content tool XML tokens | API argument JSON tokens | Output reserve | Exceeds reserve |
|---|---|---|---|---|---|
| Constructed acyclic control | 0 | 53 | 18 | 4096 | False |
| Zero-label cycle control | 1 | 104 | 63 | 4096 | False |
| Natural-window control | 0 | 53 | 18 | 4096 | False |
| Development 2-edge | 6 | 349 | 278 | 4096 | False |
| Development 3-edge | 1 | 114 | 72 | 4096 | False |
| Development 4-edge | 219 | 13,854 | 12,227 | 4096 | True |
| Held-out 2-edge | 1 | 104 | 63 | 4096 | False |
| Held-out 3-edge | 1 | 114 | 72 | 4096 | False |
| Held-out 4-edge | 4 | 337 | 270 | 4096 | False |

These measured oracle answers use one-character reasons and empty limitations, so they are an illustrative tiny-content schema cost, not useful economic assessments or a proved mathematical lower bound. When even this output exceeds the fixed reserve, exhaustive structural recall is confounded by output capacity. Known-reference recovery remains measurable; poor exhaustive recall cannot be attributed solely to input-context size. The report distinguishes output truncation, valid incomplete discovery, invalid factual claims and invalid contracts.

Saved outcomes: `{'received': 102, 'invalid_response': 2, 'provider_error': 1}`. Unavailable interventions: 3.

| Unavailable scenario | Reason |
|---|---|
| Development 2-edge / overlap-boundary | No valid model-discovered path in initial response |
| Development 3-edge / overlap-boundary | No valid model-discovered path in initial response |
| Development 4-edge / overlap-boundary | No valid model-discovered path in initial response |

Base packets share rows in 36/36 case pairs (maximum 1494 rows and 2664 accounts). Distinct reference episodes do not make the shared backgrounds independent; the JSON records every pair.

- Constructed reference-enriched stress cases; not population precision/recall.
- Repeats share exact evidence and are not independent source cases.
- Provider failures are operationally inconclusive for model quality.
- Known token usage excludes unknown provider usage; reservations are separate.
- No dollar cost: actual account tariff is unavailable.
- Topology, hidden-label recovery, economic concern and laundering verdict are distinct.

Full metrics, view-level records, saved policy selection, movement provenance and incomplete identities are in [results.json](../../prototype/local-data/generated/cycle-context-v1/results.json).
