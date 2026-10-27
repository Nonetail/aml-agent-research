# IBM AML data and evaluation research

Research date: 23 October 2026. Scope: publisher documentation and paper, the current Kaggle release, a full HI-Small data audit, and independent evaluation-design suggestions for rule development plus adaptive investigation.

## Independent design suggestions

**HI-Small is a practical starting point for pipeline development**, using its primary 1–10 September 2022 period. A separate label-free investigation view and evaluator-only labels/patterns would support blinded evaluation. Comparing deterministic detection, agent-developed rules, and optional agent investigation under the same review budget would help identify where an agent adds value. These are design suggestions, not prescribed rule families or an established experiment plan. A full twenty-day experiment requires the **Large** variant because Small and Medium have shorter primary periods.

The current release includes **account-to-entity metadata**. This enables investigations at the synthetic entity level through ordinary database joins; a separate World Model store is not necessary for that relation alone.

## What was checked

Update: the [complete-component audit](../experiments/2026-10-23-full-components/README.md) also downloaded the entire HI-Large transaction file and measured 179,702,229 rows / 200,065 components. Its largest component contains 179,166,217 rows. The original HI-Small quality/label analysis below remains specific to HI-Small; HI-Large account metadata, pattern files and labels have not been profiled.

| Evidence | Result and qualification |
|---|---|
| Publisher GitHub and Kaggle metadata | Read directly. Kaggle API identifies version **8**, last updated **8 July 2025**. |
| `HI-Small_accounts.csv` | Downloaded and fully profiled: **34,053,187 bytes**. |
| `HI-Small_Patterns.txt` | Downloaded and fully profiled: **323,844 bytes**. |
| `HI-Small_Trans.csv` | Downloaded and fully stream-profiled: **475,664,283 bytes**, with a separate exact-duplicate audit. A small prefix is also retained for header evidence. |
| All six variants together | Not downloaded: current API totals approximately **41.61 GB** of uncompressed files. |

The publisher currently lists **18 files**, three per variant, although the dataset description still lists twelve. Use the actual release manifest rather than assuming the prose inventory is complete. [Current file manifest](https://www.kaggle.com/api/v1/datasets/list/ealtman2019/ibm-transactions-for-anti-money-laundering-aml) · [Current release metadata](https://www.kaggle.com/api/v1/datasets/view/ealtman2019/ibm-transactions-for-anti-money-laundering-aml)

## Dataset identity and practical selection

IBM AML-Data is a synthetic financial-transaction benchmark generated with AMLworld. It is not anonymized real banking data. The labels describe simulated transactions, not judicial findings or identified real offenders. AMLworld and IBM AMLSim are distinct projects; AML-Data is the dataset distribution, while IBM Multi-GNN supplies model code. [IBM AML-Data](https://github.com/IBM/AML-Data)

The publisher describes six independent datasets; Small is not a subset of Medium or Large. HI has more laundering activity than LI. Primary activity periods are:

| Variant size | Primary 2022 period | Published approximate transaction counts HI / LI | Suitability |
|---|---|---:|---|
| Small | 1–10 September; 10 days | 5M / 7M | Pipeline development; short-window experiments |
| Medium | 1–16 September; 16 days | 32M / 31M | Larger experiments, still insufficient for a full twenty-day window |
| Large | 1 August–5 November; 97 days | 180M / 176M | Twenty-day requests and more substantial time-based evaluation |

These six-variant figures are publisher descriptions. The publisher warns that transactions after the primary activity period are all laundering. **The current HI-Small raw file contradicts that exact wording:** records at or after **11 September 00:00** contain **655 positives among 1,108 rows (59.12%)**, not 100%. The cause of the discrepancy is unknown; do not assume version drift explains it. This remains an extreme distribution artifact compared with **0.08906%** in the primary period, so a tail-only test is still misleading. [Official dataset description](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml) · [Measured profile](evidence/evaluator-hi-small-profile.json)

For HI-Small the current manifest gives **475,664,283 bytes** for the transaction CSV, plus the account and pattern files above: approximately 510 MB uncompressed for all three. Individual public file downloads worked without credentials in this research session; that observation is not a guarantee about future access. Avoid downloading all six variants merely to start the project. [Manifest](https://www.kaggle.com/api/v1/datasets/list/ealtman2019/ibm-transactions-for-anti-money-laundering-aml)

The complete version-8 CSV contains **5,078,345 transactions / 5,177 positive labels**, independently counted in this audit. The full-file positive rate is **0.10194%**; an always-negative classifier would therefore score roughly 99.898% accuracy while finding nothing. All **3,209 pattern records match exactly once** in the complete CSV. These measurements describe the dataset and are not detection-performance results.

### Measured daily distribution

| September 2022 day | Transactions | Positive labels | Positive rate |
|---|---:|---:|---:|
| 1 | 1,114,921 | 322 | 0.0289% |
| 2 | 754,449 | 408 | 0.0541% |
| 3 | 207,382 | 391 | 0.1885% |
| 4 | 207,430 | 407 | 0.1962% |
| 5 | 482,650 | 471 | 0.0976% |
| 6 | 482,089 | 531 | 0.1101% |
| 7 | 482,751 | 497 | 0.1030% |
| 8 | 482,773 | 539 | 0.1116% |
| 9 | 654,467 | 514 | 0.0785% |
| 10 | 208,325 | 442 | 0.2122% |
| 11 | 396 | 232 | 58.59% |
| 12 | 281 | 170 | 60.50% |
| 13 | 184 | 106 | 57.61% |
| 14 | 121 | 70 | 57.85% |
| 15 | 46 | 28 | 60.87% |
| 16 | 46 | 26 | 56.52% |
| 17 | 23 | 15 | 65.22% |
| 18 | 11 | 8 | 72.73% |

The primary period has **5,077,237 rows and 4,522 positives**. Its 1,108-row tail contains **12.65% of all positive labels** despite only about 0.022% of all rows. Retain the tail separately for artifact/completion diagnostics rather than normal operational evaluation.

Daily transaction volumes vary substantially, so equal numbers of days do not produce equal numbers of rows. For seven-day held-out evaluations plus separate development, validation and lookback periods, Small is constrained. Medium offers sixteen primary days; Large supports twenty-day requests and a longer rolling-evaluation horizon. Select split boundaries only after defining the evaluation objective and inspecting coverage; no particular calendar split is prescribed here.

## What the actual files contain

### Transactions

The inspected header is:

```text
Timestamp,From Bank,Account,To Bank,Account,Amount Received,
Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering
```

There are **two columns named `Account`**. Rename them by position to sender and receiver account during ingestion; a dictionary parser that silently overwrites duplicate names is unsafe. There is **no transaction ID**. Create a stable ID from dataset version/file checksum and original data-row ordinal, and retain the original raw fields. The file prefix is not time-sorted: a 00:20 transaction precedes a 00:00 transaction. Preserve original row IDs before sorting. These are direct observations from the [official transaction file](https://www.kaggle.com/api/v1/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/HI-Small_Trans.csv), not assumptions about CSV order.

Use separate paid amount/currency and received amount/currency. Do not sum USD, rubles and yuan into one number, or infer conservation of the same funds from matching amounts and chronological edges. Store monetary values exactly, retaining their currency. The source timestamps have minute precision and no timezone declaration in the header; do not invent a timezone or strict ordering among equal-minute transactions.

Parallel edges are legitimate data: several transactions can connect the same two accounts. A complete duplicate audit found **nine distinct full rows that each occur twice**, verified by comparing the actual row bytes after grouping content digests. These are identical observations, but the absence of a source transaction ID prevents concluding whether they are erroneous duplicates or separate identical transactions. Retain stable row-instance IDs and declare the deduplication policy; do not silently collapse transactions into graph edges. [Duplicate audit](evidence/duplicate-profile.json)

Additional full-file checks found **591,212 self-transfers**, **72,170 rows with differing paid/received currency**, **15 currencies**, **7 payment formats**, no empty cells, and **2,418,736 adjacent timestamp regressions** in file order. Accordingly, chronological splitting requires explicit sorting, and self-transfers need a declared treatment rather than blanket deletion.

### Account metadata

The complete, directly inspected [account file](https://www.kaggle.com/api/v1/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/HI-Small_accounts.csv) has:

```text
Bank Name,Bank ID,Account Number,Entity ID,Entity Name
```

Computed profile:

| Statistic | Observed value |
|---|---:|
| Rows | 518,581 |
| Unique bank/account pairs | 518,581 |
| Unique account numbers alone | 518,573 |
| Unique entity IDs | 166,207 |
| Entities associated with multiple accounts | 63,518 |
| Missing values in those five fields | 0 |

There are eight repeated account-number occurrences across bank/account keys. **Account number alone is not a valid key.** The full transaction CSV contains **515,088 active composite accounts**, all of which join the metadata, representing **166,207 distinct entities**. The metadata contains **3,493 additional accounts** with no transaction occurrence in this CSV.

Entity names contain categories such as Corporation, Partnership, Sole Proprietorship and Individual. They are synthetic identifiers, not real personal names. This is enough to add an explicit relation `account → entity` and investigate activity across accounts of a recorded entity. It does not expose a beneficial-ownership/control chain, invoices, balances, addresses, contracts, or a formal country column.

Bank names contain geographic clues, but they are not a documented country field or evidence of a customer's country. Do not silently promote name parsing into an authoritative cross-border predicate.

**Join detail:** transaction/pattern bank IDs can retain leading zeros that are absent in the corresponding account metadata. Preserve the raw strings and maintain an explicit dataset-specific canonicalization mapping. Normalization removing leading zeros produced unique metadata bank/account keys and joined all **515,088 active transaction account keys** plus all **3,170 distinct pattern-file account endpoints**, with no misses. All transaction bank IDs were decimal strings. This validates the mapping for this pinned file; maintain collision and unmatched-row checks for future versions.

### Pattern answers

The complete [pattern file](https://www.kaggle.com/api/v1/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/HI-Small_Patterns.txt) contains **370 groups, 8 types, and 3,209 transaction records**, independently counted in this audit. All full pattern rows are unique within that file and each matches exactly one full CSV row.

| Pattern | Groups |
|---|---:|
| FAN-OUT | 48 |
| CYCLE | 54 |
| GATHER-SCATTER | 51 |
| STACK | 43 |
| RANDOM | 41 |
| BIPARTITE | 49 |
| FAN-IN | 40 |
| SCATTER-GATHER | 44 |

Observed pattern timestamps span **1 September 00:03 to 18 September 16:18**. The eight motifs do not cover every positive-label transaction: the generator also tracks illicit funds through other transactions. Therefore report motif recovery separately from transaction-label recall. [Publisher paper, sections 3.3–3.4](https://arxiv.org/html/2306.16424v3#S3.SS3)

## Independent evaluation-design suggestions

A useful separation is **rule development with feedback, followed by evaluation of a frozen system**. Within development, a chronological validation portion can support version selection. Final test labels should remain unavailable to both rule-development and investigation agents. This is an independent methodology suggestion, not a claimed capability of the dataset or libraries.

The publisher uses a 60/20/20 temporal split and evaluates later transactions with previous graph history available. It emphasizes minority-class F1 rather than overall accuracy. Its supervised baselines do not use account IDs as predictive features. These support the direction, but our split must match the intended product's cutoff semantics. [Paper, section 4](https://arxiv.org/html/2306.16424v3#S4)

### Define two time ranges, not one

For “review the last seven days as of cutoff T”:

1. **Scored window:** transactions/events being assessed, e.g. `[T−7 days, T)`.
2. **Permitted evidence window:** earlier history plus the scored window, ending at T. Its start depends on the maximum lookback needed by frozen rules.

Every query, aggregation, account profile, graph feature, and saved checkpoint must carry the cutoff. No transaction after T may influence the report. A batch investigation may legitimately use all records available before T, even if later than an individual target transaction. A real-time transaction classifier instead needs that transaction's own as-of time. Those are different benchmarks and must not share one ambiguous score.

Near the dataset beginning there may be insufficient history. Mark such windows as partial or impose a warm-up period; do not report “twenty days checked” when only ten primary days exist. Selecting all records through the last available timestamp is particularly dangerous here because the measured tail is abnormally label-enriched.

### Prevent three different forms of leakage

| Risk | Treatment |
|---|---|
| Direct answers in tools | Transaction tool views omit `Is Laundering`. Pattern files, labels, evaluator outputs and test-case identifiers are outside the investigation agent's accessible workspace/data sources. |
| Repeated tuning on the final test | Freeze rules, prompts, thresholds, query policy, model version and budgets before testing. Any post-score change creates a new version requiring fresh evaluation. |
| Episodes spanning partitions | Audit motif/account overlap. Distinguish deployment-style later activity on known accounts from generalization to unseen laundering episodes. Do not claim the latter from a temporal split alone. |

A random row split can scatter a connected episode across partitions. Audit episode overlap at the chosen temporal boundaries rather than assuming a time split makes all episodes independent. Allowing earlier unlabelled history into a later investigation is not itself leakage: that can be the intended operational setting. For an additional unseen-episode test, assign or purge whole known motif groups and report that restricted scope; do not sever the graph arbitrarily and call it representative. An independent dataset such as LI-Small can support transfer testing, with its different prevalence and laundering cadence reported separately.

Keep cases whose answers informed development out of claims of blind discovery. Such cases can still serve as regression fixtures. Pattern answers and any analysis of them should remain evaluator/development material, never an investigation tool.

### What the rule-development agent may do

The agent should propose structured rule specifications with source indicator, required fields, observable conditions, unsupported conditions, parameters, output unit and intended review budget. Code compiles and runs those specifications against development data. The evaluator returns aggregate scores and controlled development examples; the agent proposes a revision within a fixed experiment budget.

Retain the experiment history, including failed rules. Prevent arbitrary account IDs, exact known pattern values, source row numbers, or the tail date artifact becoming detection conditions. None generalizes into a meaningful AML rule. Repeated selection on validation data can also overfit, so cap experiments and use rolling validation cutoffs if coverage permits.

Do not impose one-to-one correspondence between a published risk indicator and a dataset motif. A policy-derived observable condition is a hypothesis; a motif is a benchmark structure; neither by itself proves intent or illegality.

### Report several units of success

| Unit | Recommended measurements |
|---|---|
| Transaction classification | Precision, recall, minority-class F1; PR-AUC only if meaningful numeric ranking scores exist. Score unique transaction IDs in the defined window. |
| Review workload | Unique cases per day, precision/recall at fixed K cases or a fixed review budget, duplicate-alert reduction. |
| Account/entity triage | Explicitly defined surrogate label such as “involved in a labeled transaction during the scored window”; do not call it a person-level offender label. |
| Motif recovery | At least one target edge found, transaction coverage, exact recovery, extra-edge burden, and time-to-detection. Report partial motifs separately. |
| Explanation | Evidence ID validity, reproducible temporal path, claimed fact support, retained uncertainty, and invented-relationship count. |
| Resources | Tool calls, rows/bytes returned, query time, tokens, cost, timeout/failure rate. |

Define case merging and deduplication before seeing final labels. One heavily connected account can produce many pairwise rule hits, so raw alert count is not unique investigations. Likewise, coverage of one motif is not global transaction recall or case precision.

For stochastic agents, repeat the same blinded cases under fixed budgets with several seeds/runs; report dispersion and failure rates. Dependence between transactions in an episode means a transaction-wise confidence interval can be misleading. Bootstrap by case/day or clearly qualify uncertainty with only a few days available.

## Possible first experiments

The following sequence is a design suggestion. It does not select rule families, parameter values or split dates.

1. **Ingestion implementation.** Use the downloaded, audited HI-Small version and reproduce the counts above in the project's data layer. Add stable original row IDs, exact monetary handling, declared timestamp semantics, label-free views and evaluator-only tables. Verify query results match the raw-file audit before optimizing rules.
2. **Correctness fixtures.** Create small, explicitly labeled development fixtures to verify query cutoffs, account joins, currency handling, parallel transactions and graph calculations. Keep fixture correctness separate from detection performance.
3. **Deterministic baseline.** Select observable candidate rules from independently sourced indicators and available fields. Declare their assumptions, output units, parameter search space, lookback limits and alert-merging policy. Tune only on development/validation data.
4. **Agent rule development.** Give the agent the same fields, permitted template language, query budgets and number of candidate evaluations. Compare its selected frozen rules against the deterministic grid search. If it only rediscovers the same thresholds, do not attribute improvement to “reasoning.”
5. **Separate investigation test.** Starting from exactly the same seed alerts, compare deterministic bounded graph expansion with an agent choosing additional queries. Measure additional labeled-transaction/motif recovery, false additions, explanation support and query cost.
6. **Transfer/longer horizon.** After the pipeline works, use untouched independent LI data as a separately reported transfer test. Move to Large for a full twenty-day use case and enough history for meaningful rolling evaluation. Do not concatenate independent datasets to fabricate a longer history of the same customers.

A useful factorial comparison is `manual/grid rules vs agent-developed rules` crossed with `deterministic vs agent investigation`. This distinguishes rule improvement from investigation improvement without bundling both into an uninterpretable score.

## Optional stronger baseline libraries

The current official **Snap ML GraphFeaturePreprocessor** exposes temporal graph features including fan-in/out, scatter-gather, cycles and vertex statistics, with edge IDs and rolling time windows. It is a deterministic graph-processing baseline, not a conversational agent. Its documented feature-state lifecycle and platform constraints need checking against the chosen deployment before adoption. Context7 returned no matching Snap ML entry in this session; the unrelated Canonical Snap result was not used. [Official API](https://snapml.readthedocs.io/en/latest/graph_preprocessor.html)

**IBM Multi-GNN** offers GIN, GAT, PNA and RGCN implementations with optional adaptations for directed multigraphs, plus a formatter for the Kaggle transaction files and training/inference workflows. It is a candidate later supervised baseline, not needed to demonstrate the first rule-plus-investigation loop. We inspected documentation, not installed or benchmarked these models. [Official README](https://github.com/IBM/Multi-GNN/blob/main/README.md)

## License and retained evidence

IBM distinguishes the repository's Apache-2.0 license from the **data's CDLA-Sharing-1.0 license**. The data license includes conditions when publishing original or enhanced data, including attribution, license preservation and change notices; it separately treats results of computational use. Keep those distinctions when packaging an eventual demo or derived dataset. No deployment/legal clearance is inferred here. [IBM license notice](https://github.com/IBM/AML-Data) · [License text](https://cdla.dev/sharing-1-0/)

Compact research evidence is in [evidence/](evidence/). Complete source files are in [../data/](../data/): [transactions](../data/HI-Small_Trans.csv), [accounts](../data/HI-Small_accounts.csv), and [patterns](../data/HI-Small_Patterns.txt). Relevant profiles:

- `accounts-profile.json`: account/entity counts and file hash.
- `patterns-profile.json`: motif counts, date span and hash.
- `join-validation.json`: pattern-to-account join checks.
- `hi-small-profile.json`: full-file aggregate profile without label counts.
- `evaluator-hi-small-profile.json`: full-file label/day counts and exact pattern match counts; evaluator material.
- `duplicate-profile.json`: aggregate exact duplicate audit.
- `download-manifest.json`: source URLs, downloaded paths, byte lengths and hashes.
- `kaggle-list.json`, `kaggle-view.json`, `kaggle-description.md`: publisher metadata snapshots.
- `HI-Small_Trans-prefix.csv`: complete lines from the first 65,536 bytes, for header/order evidence only.

`profile_hi_small.py` reproduces the complete profile using Python's standard library. `audit_duplicates.py` reproduces the duplicate audit with the system `sort` command and automatically cleaned temporary files. Both accept `--data-dir`; when running from this report's directory, pass `--data-dir ../data`. Their outputs are compact JSON under the evidence directory. The profile script expects the account and pattern files already present and downloads only the transaction CSV when missing.

Full downloaded transaction-file SHA-256: `b19d39f515523373f991b689c07e11e7b0b95c17a2c27a87d91584ae16c5b040`.

Full downloaded account-file SHA-256: `786808526e33cfc441212dd6fccda7edfc24172149bed59c6ef59b186836b014`.

Full downloaded pattern-file SHA-256: `2c546b5ce6009e73851f0139af053cf845f08bf92f3bc82fe1eb937dec2ef39b`.

Remaining uncertainties: why publisher prose overstates the tail's positive prevalence; whether exact repeated rows represent errors or legitimate repeated transactions; whether account entity IDs reflect direct ownership only or broader modeled control; a documented bank-to-country mapping; timestamp timezone semantics; and deployment-specific query throughput. These should become explicit scope constraints or source questions, not guessed facts.
