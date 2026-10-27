# Independent prepared-input audit

Audit UTC: 2026-10-23T14:15:12.616646+00:00. Result: PASS.

Compared all 54,000 runtime row instances (15,691 distinct source rows) against the original read-only source database: 0 field mismatches, 0 evaluator-label mismatches, 0 missing source rows.

Verified 21 frozen input hashes and 30 current/snapshot implementation hashes. Six reference groups occupy six distinct eligible-episode account clusters; no other selected reference-cluster account appears in any positive case pool. Previously live group 127 is excluded.

| Case | Pool rows | Baseline cycles | Baseline positive rows | Reference group |
|---|---:|---:|---:|---:|
| control-acyclic | 6000 | 0 | 2 | — |
| control-cycle | 6000 | 1 | 2 | — |
| control-natural | 6000 | 0 | 1 | — |
| dev-2 | 6000 | 6 | 7 | 24 |
| dev-3 | 6000 | 1 | 5 | 74 |
| dev-4 | 6000 | 219 | 37 | 68 |
| holdout-2 | 6000 | 1 | 4 | 143 |
| holdout-3 | 6000 | 1 | 5 | 167 |
| holdout-4 | 6000 | 4 | 6 | 155 |

All development reference supports are present in nested 300/750/1,500-row views. Repeated jobs use identical ordered row IDs. SQL joins independently matched every saved baseline oracle, including the zero-labelled structural-cycle control and acyclic control.

| Grouping | View sizes | Retained cycles / whole packet | Retained reference |
|---|---|---:|---:|
| dev-2-graph-2 | 750, 750 | 6/6 | 1/1 |
| dev-2-graph-3 | 500, 500, 500 | 6/6 | 1/1 |
| dev-2-graph-4 | 376, 375, 375, 374 | 6/6 | 1/1 |
| dev-2-chronological-3 | 500, 500, 500 | 6/6 | 1/1 |
| dev-3-graph-2 | 750, 750 | 1/1 | 1/1 |
| dev-3-graph-3 | 500, 500, 500 | 1/1 | 1/1 |
| dev-3-graph-4 | 375, 375, 375, 375 | 1/1 | 1/1 |
| dev-3-chronological-3 | 500, 500, 500 | 1/1 | 1/1 |
| dev-4-graph-2 | 750, 750 | 219/219 | 1/1 |
| dev-4-graph-3 | 500, 500, 500 | 219/219 | 1/1 |
| dev-4-graph-4 | 375, 375, 375, 375 | 219/219 | 1/1 |
| dev-4-chronological-3 | 500, 500, 500 | 57/219 | 0/1 |

Every grouping contains exactly the original 1,500 unique edges, with no duplicate assignments. Graph views preserve source-account bundles; chronological views may split them. Retention above is recomputed from independent whole-packet SQL cycles, without trusting grouping annotations.

At the snapshot there were 42 admitted attempts and 0 held-out attempts. Inspected 42 saved requests: fresh two-message contexts, ordinary CSV fields, no labels, targets or advertised scopes. This is a point-in-time audit while initial execution continues.

**Interpretation limits:** dev-4 has 219 baseline cycles but only 4,096 output tokens. Exhaustive output capacity is therefore a material confound; use the separate output-capacity audit and report exact reference recovery alongside exhaustive structural recall. The acyclic control is selected by topology; the natural ordinal window is a single sanity check. Positive cases share background and are not population prevalence samples.

A subsequent read-only rendering check compared all ten displayed source fields on 34,196 saved-request row instances against the source-verified runtime rows: 0 mismatches.
