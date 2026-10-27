# Return-cycle catalogue and ratio smoke corpus

Prepared 24 October 2026, Australia/Sydney. Dataset preparation and local deterministic checks; no hosted-model calls or live investigation restart.

## Preferred corpus: v2, distinct short-cycle account clusters

Use [v2/runtime/transactions.sqlite](generated/cycle-family-v2/runtime/transactions.sqlite) and [v2/runtime/nodes.csv](generated/cycle-family-v2/runtime/nodes.csv). **V2 has 300,000 source edges and 217,148 source account nodes.** Its [manifest](generated/cycle-family-v2/evaluator/manifest.json), [catalogue](generated/cycle-family-v2/evaluator/catalogue.json), [answer database](generated/cycle-family-v2/evaluator/evaluator.sqlite), and [source verification](generated/cycle-family-v2/evaluator/verification.json) are evaluator-only.

V2 keeps the same seed and all three v1 count targets: **306 positives, 17 publisher-CYCLE rows, 5 eligible-short rows**, with the same rounding errors in the ratio table below. It adds one explicit selection constraint: the included short episodes must come from different connected account-overlap clusters, computed across all 29 eligible publisher episodes before sampling. Whole context is still retained; no evidence was dropped to satisfy that constraint.

The resulting short episodes are a 2-edge cycle (group 39) and a 3-edge cycle (group 367), in different eligible-episode account clusters. Group 218 supplies the complete 12-edge broad-family episode. There are 26 complete publisher motifs and zero partial supplied motifs. Two episodes are still only a smoke test; distinct target clusters do not prove globally disjoint context/background or statistical independence.

**The 3-edge episode crosses 11 September.** Its transfers run from 10 September 21:28 through 13 September 16:02. Use the complete supplied scope, with an exclusive cutoff of `2022/09/19 00:00`; the old primary-period cutoff would omit most of this target. Runtime metadata explicitly limits completeness to the sampled database and does not imply source-wide graph completeness.

| V2 scope | Rows | Positive labels |
|---|---:|---:|
| Before 11 September | 299,931 | 266 |
| From 11 September | 69 | 40 |
| Complete sample | 300,000 | 306 |

V2 selection provenance: 17 selected-episode rows, 332 incident-context rows, 22 motif-completion rows, 265 positive-background rows and 299,364 negative-background rows. These roles partition the corpus, not its labels.

Independent full-size verification compared all 300,000 v2 transaction rows and 217,148 account records with the source, and every sample label with the original evaluator database: **zero mismatches and zero missing labels**, with a passing SQLite integrity check. Source database, evaluator, and pattern-file hashes match v1's recorded hashes. V1's runtime checksum remains unchanged.

Reproduce v2 in a new directory:

```sh
python3 cycle_benchmark.py --output /tmp/aml-cycle-family-v2-reproduction --independent-short-episodes
```

The default seed remains `20261024`, and `--independent-short-episodes` is the only selection-policy change. Omitting that flag reproduces v1's original selection policy; an existing output directory is always rejected. Seven tests now also verify transitive account clustering and rejection of two episodes from the same cluster.

## Original v1 corpus, retained for provenance

V1 remains available and unchanged. The following artifact list documents v1; later sections explicitly identify shared information and version-specific results. V2 is the preferred integration input.

### What exists in v1

- [Runtime transaction graph](generated/cycle-family-v1/runtime/transactions.sqlite): **300,000 unchanged source transactions and 217,131 source account nodes**. The `transactions`, `accounts`, and `metadata` schemas match the original database. Account identity remains `(bank, account)`; individual transaction row IDs remain original source ordinals. Parallel rows are not merged.
- [Nodes CSV](generated/cycle-family-v1/runtime/nodes.csv): one source account record for every endpoint present in the sample. The transaction table is the edge list.
- [Evaluator catalogue](generated/cycle-family-v1/evaluator/catalogue.json): all 370 publisher groups resolved to exact source rows, including all 54 named CYCLE groups. Every supplied pattern record had exactly one exact source match and a positive evaluator label.
- [Separate answers](generated/cycle-family-v1/evaluator/evaluator.sqlite): sample labels, per-row source mapping/selection provenance, and all publisher pattern memberships. The runtime database contains none of these tables or label fields.
- [Manifest](generated/cycle-family-v1/evaluator/manifest.json): source hashes, seed, selections, count targets, ratios, primary/tail composition, and limitations.
- [Source verification](generated/cycle-family-v1/evaluator/verification.json): every sample edge and account matched every source field; no missing sample labels; SQLite integrity passed.

The directory is new; no existing runtime, source data, receipts, investigation ledger, or prior generated corpus was changed. Existing output directories are rejected on rebuild.

## Known cycle population: full source, shared by v1 and v2

| Predicate / scope | Complete publisher groups | Unique member transactions |
|---|---:|---:|
| Publisher CYCLE, all lengths | 54 | 287 |
| Simple directed closed cycles | 54 | 287 |
| Strictly increasing timestamps after cyclic rotation, all lengths | 49 | 252 |
| Simple, strict temporal, 2–4 edges | 29 | 79 |
| Publisher CYCLE groups wholly before 11 September | 43 | 200 |
| Eligible short groups wholly before 11 September | 27 | 72 |

All 54 named cycles have 2–12 edges. Five groups (publisher ordinals 38, 72, 129, 232, 295) fail the strict temporal predicate. Equal timestamps would fail strict order; account identity includes bank. No maximum duration or currency-equality requirement is imposed for this structural eligibility calculation. These are engineering predicates, not AUSTRAC thresholds or conclusions about intent.

Across individual cycle rows, 243 fall before 11 September and 44 in the tail. For eligible short rows, those counts are 74 and 5. These row counts differ from the wholly-primary episode counts because some complete episodes straddle the boundary.

**This is complete for the publisher's CYCLE answer file, not an exhaustive census of positive cycles in the transaction graph.** The source has 5,177 positive rows; 3,209 belong to the 370 published patterns, and 1,968 have no supplied pattern-family classification. Their cycle membership remains unknown. The complete original graph has not been enumerated for structural cycles.

The completed **v2 structural baseline** separately enumerated 29 exact cycles within its two-to-four-edge predicate and sampled database. A subsequent evaluator comparison classified 21 as containing zero positive labels, five as all-positive, and three as mixed; both eligible v2 publisher reference groups were recovered. An independent SQL audit returned exactly the same 29 cycles. These are structural recovery and label-composition results, not model-quality measurements or proof of laundering. See [the cycle prototype and baseline workflow](CYCLE-PROTOTYPE.md).

## Ratios and integer limits: both versions

The baseline is the complete 5,078,345-row file as requested. Both corpora preserve overall label prevalence, known broad-cycle prevalence, and strict-short-cycle prevalence by nearest integer counts. The extra short-cycle target prevents selecting only short motifs while quietly inflating their population share.

| Quantity | Full source | Each smoke corpus (v1 and v2) | Rounding deviation | Relative rate error |
|---|---:|---:|---:|---:|
| All positive transaction labels | 5,177 / 5,078,345 (0.10194266%) | 306 / 300,000 (0.10200000%) | +0.172019 row | +0.0562% |
| Publisher CYCLE transaction membership | 287 / 5,078,345 (0.00565145%) | 17 / 300,000 (0.00566667%) | +0.045658 row | +0.2693% |
| Eligible 2–4-edge temporal-cycle membership | 79 / 5,078,345 (0.00155562%) | 5 / 300,000 (0.00166667%) | +0.333125 row | +7.1381% |

All three count deviations are below **0.5 transaction**, the declared tolerance. The eligible-short relative error is still 7.14% because the target is only 4.67 transactions; this is not an exact preservation claim. Broad CYCLE's share of positive rows is 287/5,177 = **5.543751%** in the source and 17/306 = **5.555556%** here.

Keeping all 287 known cycle rows at their full-source rate would require the original 5,078,345 rows. A genuinely smaller ratio-matched corpus must sample whole episodes instead of including every known cycle. All episodes remain in the separate evaluator catalogue.

## How both samples were made: common recipe

Both versions use the following steps. V2 additionally requires distinct short-episode account clusters, as described in its introductory section; v1 does not impose that constraint.

1. Resolve every publisher pattern record against all original fields, retaining source row-instance IDs. Refuse ambiguous or repeated matches instead of silently deduplicating.
2. Compute cycle closure, simple-node structure, chronology, length and source-period coverage from the observed records.
3. Use seed `20261024` to select whole episode/context bundles that meet the three integer quotas. Retrieve **all incoming and outgoing rows incident to selected episode accounts from 24 hours before the earliest episode timestamp through 24 hours after the latest, inclusive**. This padding is a context-extraction choice, not a risk threshold.
4. Complete every publisher motif touched by that context. Retain its hidden-positive and label-zero rows without pruning to make a ratio fit. Search for a feasible bundle combination instead.
5. Fill the remaining positive quota from source-positive rows, including a whole known publisher motif whenever one is encountered. Exclude unselected CYCLE groups so the cycle quota remains fixed. Uncatalogued positives remain individual row units with unknown episode completeness.
6. Fill the remaining row quota with a deterministic uniform sample without replacement of source label-zero rows. Copy exact source edges and every endpoint's original account record. Never invent nodes or noise transfers.

### V1 selection outcome

V1 contains complete 2-edge and 3-edge cycles (publisher groups 65 and 178), plus a complete 12-edge cycle (group 218). Group 65 arrived through the real context of group 178. **V1's two short cycles share accounts and form one account-overlap cluster**, so they are not independent cases. V2 uses groups 39 and 367 in distinct clusters instead. Both versions retain the 12-edge episode to preserve broad-family composition; it is outside the first 2–4-edge detector's scope and must not be relabelled benign.

V1 has **26 complete publisher motifs and zero partial supplied motifs**. There may still be incomplete uncatalogued patterns and changed account degrees because most source activity was not selected.

The v1 selection ledger records 15 intentional episode rows, 331 incident-context rows, 25 motif-completion rows, 252 positive-background rows and 299,377 negative-background rows. These are mutually exclusive provenance roles, not classes: the context roles also contain positive transactions, including the additional short cycle.

## V1 primary period and tail

V2's period counts appear in its introductory section. The historical v1 counts are:

| Scope | Full-source rows | Full-source positives | V1 rows | V1 positives |
|---|---:|---:|---:|---:|
| Before 11 September 2022 | 5,077,237 | 4,522 | 299,941 | 274 |
| From 11 September 2022 | 1,108 | 655 | 59 | 32 |

The full-file baseline includes an unusually label-rich tail. In both versions, primary/tail proportions were measured, not separately constrained. V1's two sampled short cycles and its 12-edge cycle lie in the primary period; v2's 3-edge cycle crosses into the tail. Any performance report must distinguish its scored period.

## Appropriate use and isolation: both versions

Both are **ratio smoke corpora for development and integration**, each containing only two eligible reference episodes. V1's episodes share an account cluster; v2's occupy distinct eligible-episode account clusters. Neither corpus can establish detection precision, operational alert workload, population representativeness, or generalization. Label-informed positive selection, whole-motif completion and random background alter other-family proportions, graph connectivity and degree distributions. Neither version includes a publisher-labelled eligible four-edge reference episode; test its recovery and other correctness cases with independent fixtures.

The runtime metadata explicitly states that query completeness applies only inside the sample database. A missing edge here is not proof of source-wide absence. Both labels and the target-selection catalogue must be unavailable to a blind detector. Their placement in a sibling evaluator directory is a storage separation, **not an OS security boundary**. The preparing agent has seen answers and must not run a supposedly blind evaluation in the same context.

## Reproduce v1 and verify the shared builder

Run from `prototype/local-data`. The tests cover both selection policies; the build command below reproduces v1. Use the `--independent-short-episodes` command in the introductory section for v2.

```sh
python3 -m unittest test_cycle_benchmark.py
python3 cycle_benchmark.py --output /tmp/aml-cycle-family-reproduction
```

Use a fresh destination. The default v1 run uses the original read-only databases, the complete publisher pattern file, 300,000 rows, seed `20261024`, and 24-hour context padding. Seven tests cover exact rounding and infeasible quotas; bank/account identity; strict timing and ties; repeated nodes/backward legs; ambiguous parallel-record matches; context-positive preservation; complete cycles; reproducibility; exact source edges/nodes; separate labels; source-file immutability; non-overwrite behavior; and v2's transitive account-cluster constraint.

V1's full-size verification independently compared all **300,000 transaction rows** and **217,131 account records** to the source: zero mismatches. It found 306 evaluator positives, zero missing labels, and a passing SQLite integrity check. V2's separate verification, including its 217,148 account records, is recorded in the introductory section. No model quality result is claimed for either version.
