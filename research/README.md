# AML research findings

Research snapshot: 23 October 2026. Read the [handoff](../HANDOFF.md) for the agreed goal, source basis and continuation plan.

This research concerns an agentic system for evidence-backed suspicious-transaction candidates in IBM synthetic data. Domain evidence comes from IBM and AUSTRAC. Framework capabilities come from official documentation and inspected source. Implementation suggestions remain hypotheses until evaluated.

## Family 1 implementation update

The selected first family now has [executable tools, prompts, an offline workflow and a smaller graph](../prototype/local-data/CYCLE-PROTOTYPE.md). The [dataset report](../prototype/local-data/CYCLE-DATASET.md) distinguishes the complete known-cycle catalogue from the ratio-matched 300,000-row smoke corpus. The separate [live context, grouping and overlap study](../experiments/2026-10-24-cycle-context/README.md) measured the current model and found no reliable background-containing view size. The design notes below remain the research basis.

## Latest discussion and implementation status

The current [rule-focused design research](2026-10-23-rule-focused-design.md) examines rule-family specialists, small source-preserving benchmarks, aggressive graph retrieval and token-driven continuation. Three supporting notes cover [rule families](2026-10-23-rule-family-slices.md), [benchmark construction](2026-10-23-small-rule-benchmark.md), and [context/review boundaries](2026-10-23-context-and-review-boundaries.md). The family-1 milestone above implements the focused rule, tools and offline workflow. The controlled live study is linked above; a validated operating threshold remains outstanding.

The latest batch run is paused at the user's request with 35,147 discovered rows and 154 assessed paths. Of 356 committed review receipts, 324 contain no decisions. Mandatory row presentation has not established detection value. The [handoff](../HANDOFF.md) records the authoritative stopped state and the distinction between historical Ultra experiments and the current Lightning adapter. No live investigation was resumed for this research.

## Reports and source hierarchy

| Report | Scope |
|---|---|
| [Investigation proposal, revision 2](../design/2026-10-23-investigation-proposal/PROPOSAL.md) | Earlier proposed role ordering, typed checks, support rubric and staged experiments; not the current batch implementation; external-review decisions recorded; earlier full reviews apply to revision 1 |
| [IBM data and evaluation](ibm-data-and-evaluation.md) | Publisher files, measured schemas/coverage/quality, label interpretation and evaluation design |
| [Indicators and investigation](indicators-rules-and-investigation.md) | AUSTRAC indicators, observable conditions, temporal/currency semantics, possible rule formulations and fair baselines |
| [Agent frameworks](agent-frameworks.md) | Meterless reference implementation, targeted probes, Vercel SDK capabilities and integration responsibilities |
| [Adaptive graph investigation](adaptive-graph-investigation.md) | Proposed batched navigation, context refresh, durable evidence, population coverage, branch workers and evaluation |
| [Adaptive graph framework review](adaptive-graph-framework-review.md) | Markovian versus an ordinary SDK loop; source-checked chunk, compaction and persistence semantics |
| [Zetaris integration](zetaris-integration.md) | Version-specific official SQL access, ingestion choices, query limits and optional adapter design |
| [Evidence](evidence/README.md) | Publisher snapshots, downloaded-file manifest, aggregate measurements and reproducible scripts |
| [Raw IBM files](../data/README.md) | Pinned transactions, accounts and evaluator patterns |

Core sources are [IBM AML-Data](https://github.com/IBM/AML-Data), the [published dataset](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml), the [AMLworld paper](https://arxiv.org/html/2306.16424v3), and [AUSTRAC banking-sector indicators](https://www.austrac.gov.au/industry-and-business/education-and-resources/publications-and-resources/indicators-suspicious-activity-banking-sector). Additional sources support optional implementation choices; they do not prescribe the detection rules.

## Measured IBM findings

A [context-budget experiment](../experiments/2026-10-23-context-budget/README.md) compares equivalent table and JSON representations of real, label-independent HI-Small samples. A 70k evidence allowance fits 1,659 CSV rows or 1,478 Markdown rows in the measured high-degree star, including account dictionaries and schema/scope metadata. This is a token-capacity result under a reference encoding; no model-quality experiment was run. The report distinguishes input-only from combined context budgets and reserves room for reasoning/output and agent-loop growth.

A subsequent [full-component audit](../experiments/2026-10-23-full-components/README.md) downloaded and counted HI-Large: 179,702,229 transactions, 200,065 fully expanded components, and 99.70% of rows in one giant component. Complete HI-Small and HI-Large inventories are available there. The original detailed quality and label findings in the table below describe **HI-Small**.

| Finding | Evidence |
|---|---|
| 5,078,345 transaction rows; 5,177 positive labels | [Full evaluator profile](evidence/evaluator-hi-small-profile.json) |
| 515,088 active bank/account pairs; all join metadata | [Transaction profile](evidence/hi-small-profile.json) |
| 518,581 metadata accounts; 166,207 synthetic entities; 63,518 entities have multiple accounts | [Account profile](evidence/accounts-profile.json) |
| Eight excess account-number occurrences across composite bank/account identities | [Account profile](evidence/accounts-profile.json) |
| 370 publisher pattern groups, eight types, 3,209 rows | [Pattern profile](evidence/patterns-profile.json) |
| Every publisher pattern row matches exactly one full transaction row | [Full evaluator profile](evidence/evaluator-hi-small-profile.json) |
| Nine exact repeated-row pairs, verified against source bytes | [Duplicate audit](evidence/duplicate-profile.json) |
| 591,212 self-transfer rows; 72,170 rows with differing paid/received currencies | [Transaction profile](evidence/hi-small-profile.json) |

The transaction CSV has duplicate `Account` headers, no source transaction-ID column, minute-resolution timestamps, and substantial out-of-order records. Parse duplicate headers by position, retain raw identifiers, and assign source-version/record-position IDs before sorting. Bank-ID normalization is a validated dataset-specific join operation; account numbers must remain strings. Treat exact repeated records as separate source row instances unless a justified deduplication policy is adopted.

The account metadata enables synthetic entity grouping through an ordinary validated join. It does not supply verified beneficial ownership, economic purpose, a country classification or historical validity intervals. Static use of that mapping is a benchmark assumption that must be reported.

## Coverage and evaluation limitations

Publisher primary activity spans ten days for Small, sixteen for Medium and ninety-seven for Large. Small and Medium therefore cannot support a complete twenty-day primary-activity window. HI/LI and size variants are independently generated datasets, not simple nested samples. [Data research](ibm-data-and-evaluation.md)

The downloaded HI-Small file has a sparse tail beyond the primary period. September 1–10 contains 5,077,237 rows with 4,522 positive labels (0.0891%); September 11–18 contains 1,108 rows with 655 positive labels (59.12%). The publisher description says tail rows are all laundering, which does not match this file. The cause is unknown; preserve this discrepancy rather than resolving it by assumption. [Measurements](evidence/evaluator-hi-small-profile.json), [publisher snapshot](evidence/kaggle-description.md)

Select evaluation partitions before tuning. Chronological separation can model later activity in a known network, but recurring accounts and boundary-spanning episodes mean it does not establish unseen-entity or unseen-episode generalization. Preserve authorized earlier history while excluding future events, and report complete versus partial reference-pattern recovery separately. No development/test dates are designated here.

The label column and publisher patterns belong to an evaluator. The full transaction population defines overall recall; seeded-case recovery is a different measure. Pattern absence is not a negative label. Evaluate review burden and resource usage alongside precision and recall. The research archive itself contains answer-bearing material, so future runtime access requires restricted views/tools.

## Turning guidance into executable rules

AUSTRAC supplies qualitative indicators and contextual requirements. Translate selected indicators into versioned rule specifications with clear field dependencies, temporal boundaries, units, distinct-party semantics and explicitly chosen parameters. Missing prerequisites must remain visible. IBM reference labels measure agreement with a simulator, not compliance with every AUSTRAC indicator.

Candidate formulations in the [indicator report](indicators-rules-and-investigation.md) are illustrative and source-linked. They do not establish a mandatory rule list or numeric search grid. Every retained rule needs a defensible interpretation and measured behavior, including false positives and unsupported interpretations.

Use deterministic code to verify evidence identity, time ordering, composite account joins, currencies, query completeness and proposed graph paths. Currency-compatible amounts and connected edges alone cannot establish criminal purpose or conserved funds.

## Optional implementation findings

| Option | Confirmed capability or finding | Implication |
|---|---|---|
| Zetaris | Official examples expose SQL through REST/JDBC and support file/external-data integration; deployed version matters | Evaluate if available and useful; live access, query semantics and server limits remain untested |
| Vercel AI SDK | Model/tool loops, schemas, loop control, context hooks and subagent patterns | A possible orchestration layer; exact evidence/state and evaluation remain application responsibilities |
| Meterless Markovian | Generator chunks and carryover; probes found no provider-cap enforcement or crash-resume facility, and omitted a late goal constraint on continuation | Optional measured context-policy experiment; enforce constraints in tools and preserve exact state separately |
| Meterless World Model | Default open-relationship replacement closed an earlier branch in a toy transaction mapping | Do not adopt a naive mapping for parallel outgoing transaction relationships |
| Meterless H-MEM | Memory mining and ranked recall; reference persistence/embeddings are minimal | Optional memory research; not an authoritative case store or rule-version selector |

Framework findings are scoped to the versions and probes described in the [framework report](agent-frameworks.md). The Meterless probe uses mock generators; it is not a real-model cost or performance benchmark. No backend or framework is selected.

## Suggested experimental comparisons

Separate rule development from investigation so their contribution can be measured:

1. Deterministic rule selection with fixed bounded investigation.
2. Agent-assisted rule development, evaluated and frozen, with the same investigator.
3. The same frozen rules/seeds with adaptive agent investigation.

Make search spaces, evaluation budgets, query budgets and review capacity comparable. Record model costs separately. An agent trying the same finite candidates as ordinary search needs to justify any added cost. Optional context-management experiments should keep model, tools, state, seeds and budgets fixed while measuring evidence retention and actual usage.

Completed work includes the data audit, framework checks, several navigation/review prototypes and small model probes. A validated detection benchmark, live Zetaris integration and production-scale agent remain future work. The [handoff](../HANDOFF.md) describes open decisions and a proposed sequence without preselecting rules, thresholds or split dates.
