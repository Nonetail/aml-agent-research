# From indicators to executable rules and investigation

Research date: 23 October 2026, Australia/Sydney. Scope: an agentic system that detects reviewable candidates in IBM synthetic transaction data using explicit, validated rules grounded in AUSTRAC guidance. This note contains independently sourced research, references to downloaded-data measurements, and clearly labeled engineering suggestions. No particular rule family, threshold, split date or agent framework is a predetermined requirement.

## Findings that change the design

1. **There is no single official algorithm to detect a money launderer.** The relevant guidance describes observable concerns and contextual prerequisites. We must define and test our own operational approximations, preserving what each approximation cannot establish.
2. **The first useful baseline is deterministic temporal graph analysis.** Fan-in, fan-out, rapid pass-through and time-ordered cycles can be detected using SQL and graph algorithms. The agent's value should be measured against that baseline, not against doing nothing.
3. **Rule development and case investigation are different agent tasks.** Development can use training labels through an evaluator; blind investigation must not receive the labels or publisher pattern files. Only the former can change rules during experiments.
4. **A promising agent role is bounded experimental research:** translate indicators to supported templates, diagnose failure modes, propose constrained changes, and explain the evidence. Repeated threshold search alone is usually simpler as a deterministic grid.
5. **Reconstruction and discovery are different evaluation tasks.** A fixture selected from publisher answers can test query mechanics, but only a blind run over the eligible dataset can measure candidate discovery.

## What primary sources establish

### AUSTRAC guidance

The banking indicators page, last updated 18 September 2026, includes “makes rapid or complex funds transfers through multiple accounts.” It also identifies multiple-party receipts, rapid outgoing transfers after receipts, and inconsistencies with expected customer activity. Some indicators require information about ownership, business purpose, geography or trade documentation. AUSTRAC says an isolated indicator may be insufficient and further examination may be necessary. It does not supply a complete executable detector or the numerical parameters needed to operationalize those descriptions. [Official banking indicators](https://www.austrac.gov.au/industry-and-business/education-and-resources/publications-and-resources/indicators-suspicious-activity-banking-sector)

The implementation implication is to label each rule **observable transaction pattern**, **partial approximation**, or **unsupported with current data**. Do not silently remove an unavailable prerequisite and present the result as the complete official indicator.

### The IBM benchmark and deterministic alternatives

IBM describes AML-Data as wholly synthetic transactions produced by a simulated economy, with transaction laundering labels. Its public repository distinguishes this dataset from AMLSim. The available CSV is not an export of all knowledge in the simulator. [IBM AML-Data](https://github.com/IBM/AML-Data)

The AMLworld paper includes benign and illicit activity beyond the standard graph motifs. It uses temporal train/validation/test splits, retains earlier transactions as context for later predictions, and emphasizes minority-class performance because overall accuracy is uninformative for this imbalance. Consequently, matching a graph motif cannot be equated with classifying every illicit transaction. [Original dataset paper, sections 3–4](https://arxiv.org/html/2306.16424v3)

IBM's Graph Feature Preprocessor research demonstrates an alternative to LLM traversal: temporal multigraph feature extraction followed by gradient boosting. It enumerates fan-in/out, gather/scatter structures and cycles, and evaluates these on AML datasets. The paper's existence supports a strong non-LLM comparator; its benchmark scores are not predictions for our proposed rules or data split. [GFP paper](https://arxiv.org/html/2402.08593v2)

The documented Snap ML implementation accepts uniquely identified timestamped edges, maintains an in-memory multigraph, and has configurable time windows and cycle lengths. It outputs pattern counts and account statistics, not a complete evidence-backed investigation report. The docs describe `fit`, `partial_fit` and `transform`; there is an [IBM example notebook](https://github.com/IBM/snapml-examples/blob/main/examples/graph_feature_preprocessor/graph_feature_preprocessor.ipynb). Optional later benchmarking is reasonable; dependency, license and deployment compatibility would need checking before adoption. [Official GFP API documentation](https://snapml.readthedocs.io/en/latest/graph_preprocessor.html)

## Observability map for this project

This table is an engineering assessment distinguishing the transaction CSV from the separately available account metadata. The account file supplies `Bank Name`, `Bank ID`, `Account Number`, `Entity ID` and `Entity Name`. The parallel data audit found unique composite bank/account keys, repeated account numbers across banks, and multiple accounts attached to synthetic entity IDs. Thus entity grouping is available after a validated join; the transaction CSV alone does not expose it. These are simulator identities, not independently verified real-world beneficial ownership. See the [downloaded account profile](evidence/accounts-profile.json), [join validation](evidence/join-validation.json), and [data/evaluation research](ibm-data-and-evaluation.md).

| Candidate question | Observable input | What remains unobservable or uncertain |
|---|---|---|
| Does an account receive from many accounts or synthetic entities? | Transaction endpoints/times; account metadata maps those endpoints to synthetic entity IDs | Transaction-only rules count accounts. Entity-enriched rules can count distinct simulator entities, but cannot establish unrelatedness or ultimate control from that alone |
| Does an account pay many accounts or synthetic entities? | Transaction destinations/times plus optional validated entity join | Payroll, merchant settlement, supplier or other economic purpose |
| Does receipt precede a rapid outgoing transfer? | Incoming/outgoing account join and time difference | Which funds financed the outgoing payment; prior balances and other assets |
| Does a time-ordered path return to its starting account? | Ordered directed transaction edges | Common ownership, criminal purpose, or conservation of the same funds |
| Is activity new or substantially higher than recent history? | Earlier records for that account and comparable time windows | Account opening date, expected activity, seasonality, occupation and customer profile |
| Does an amount resemble another amount? | Amount/currency on the relevant account side | Whether similarity is economically meaningful; missing FX rates, fees and funding attribution |
| Is it an international or high-risk-jurisdiction transfer? | Not established by this CSV | Country mappings and jurisdiction classification; bank IDs and currencies are insufficient |
| Is there trade over/under-invoicing, a connected company network, or a business/personal mismatch? | Account metadata supplies synthetic entity identities/names and supports grouping their accounts; transfers give observed links | Invoices, goods, contracts, ultimate ownership/control, addresses, declared business and intended account use remain absent or unverified. Entity-name categories do not establish the economic purpose of a transaction |

We can compute observed payment-channel frequencies, but should not infer cash deposits, branch/ATM activity, or reporting-threshold avoidance from a generic transfer record without confirming the field semantics. A dollar-shaped numeric threshold is not automatically an AUD cash threshold.

## Exact semantics before thresholds

The following are proposed implementation decisions, not requirements copied from the guidance.

### Identity, evidence and numerical representation

- Retain raw bank/account values as strings for evidence. Build a separate validated join key: the full-file audit found bank-ID leading-zero differences between files and verified normalized joins for all 515,088 active transaction accounts and all 3,170 pattern-file account endpoints, with no misses. Do not directly equate differently padded strings, discard the raw form, or cast account numbers to numbers. Repeat collision and join-coverage checks when changing source versions. Account identity is not beneficial-owner identity; joined `Entity ID` supports explicitly labeled synthetic-entity grouping. [Full transaction profile](evidence/hi-small-profile.json), [pattern-endpoint checks](evidence/join-validation.json)
- Give every transaction a stable ID tied to source version and original record position. A row number after sorting is not provenance. Preserve separate parallel transactions; do not deduplicate by matching endpoints and time.
- Use a directed **multigraph**: accounts are vertices, transactions are edges. A simple account graph can summarize connectivity, but must point to every supporting edge.
- Use decimal amounts and explicit currencies. For a focal account, incoming value is the received amount/currency and outgoing value is the paid amount/currency. Aggregate only compatible currency units. Cross-currency edges can support a topological path without supporting a money-value reconciliation.
- Preserve same-account records as background. Exclude them from distinct-counterparty fan counts and external multi-account path edges. A same-account record with different currencies can support an observation about currency change, not proof of the causal link between two external transfers.

### Reporting time, history time and knowledge cutoff

Keep three concepts explicit in every run:

```text
reporting window = [S, T)       # transactions/events requested by the user
history window   = [S-L, S)     # context needed to detect sequences near S
knowledge cutoff = T           # no record at or after T may be retrieved
```

Define how a pattern is attributed to the reporting window. A useful first convention is **its final/triggering transaction is in `[S,T)`**, while earlier supporting edges can lie in the permitted history. Emit both the new trigger and all supporting records. Score only the declared target transactions; do not accidentally count old support as new discoveries.

An instruction such as “last N days” resolves against a chosen simulated cutoff, not the computer's current date. Return actual data coverage alongside the requested period. If the requested history is unavailable or incomplete, record that limitation rather than treating missing observations as zero activity.

The independently downloaded [transaction prefix](evidence/HI-Small_Trans-prefix.csv) displays timestamps at minute resolution. For a strict temporal path require `t1 < t2 < ...`; equal timestamps have unknown order. A stable row ID can break sort ties for reproducibility, but cannot manufacture chronology. If we later support non-decreasing-time paths, name and evaluate that alternative separately. Confirm the timestamp contract against the complete dataset before implementation.

For retrospective batch analysis, all evidence before T may be available to all investigations. For online detection, each alert additionally has an alert-time cutoff. Those are distinct experiments and must not be conflated.

## Illustrative rule families to evaluate

The possibilities below are newly proposed operational definitions, not selected requirements. The AUSTRAC indicators motivate examining receipt/dispersal and rapid multi-account transfers; the IBM dataset and GFP papers independently describe graph motifs including fan-in/out and cycles. The definitions and parameters still require validation against the available data and the intended review workload. [AUSTRAC indicators](https://www.austrac.gov.au/industry-and-business/education-and-resources/publications-and-resources/indicators-suspicious-activity-banking-sector) · [IBM motif definitions](https://arxiv.org/html/2306.16424v3#S3.SS2) · [GFP research](https://arxiv.org/html/2402.08593v2)

### Multiple-counterparty receipts (fan-in)

For each focal account `v` and anchor transaction time `t`, inspect non-self incoming transactions within `(t-W,t]`, all before the run cutoff. Count distinct source account keys. Trigger when the count is at least `k`. Emit the full supporting transaction IDs, counterparties, count, window boundaries, and per-currency sums.

The threshold counts counterparties, not rows: repeated payments from one account do not establish additional payers. Collapse overlapping hits into episodes by a declared rule, while retaining which transactions satisfied each hit. Retail receipts, collections and settlement activity are plausible benign alternatives, not automatically exculpatory facts.

### Multiple-counterparty payments (fan-out)

Reverse the receipt rule's direction and count distinct destinations. This describes an observed concentration of outgoing counterparties; it is not inherently a laundering finding. Payroll, payouts, refunds and supplier payments can create the same shape. An optional variant can require a preceding receipt, but that is a separate rule with separate parameters.

### Rapid receipt followed by outgoing transfer (pass-through candidate)

Join incoming `u→v` and outgoing `v→w` on focal account `v`. Require both edges to be external, and `0 < t_out - t_in <= Δ`. Make `u=w` an explicit feature (round trip), not an accidental exclusion. If a payment-channel filter is proposed, specify whether it applies to both edges or one and validate its effect on coverage. No particular channel restriction is assumed here.

Emit **candidate temporal pairs**, not matched units of money. If `m` incoming and `n` outgoing rows all qualify, a join produces `m × n` pairs over only `m + n` distinct transactions. For evaluation, deduplicate transaction IDs. For workloads, group the pairs into focal-account episodes. A frequent trading or settlement account may have many ordinary qualifying pairs, so raw pair count is a poor priority score.

An amount-retention variant needs a separate specification: account-side currencies must match, a matching/allocation method must be chosen, and reused amounts must not be counted repeatedly across all possible pairs. Begin without this stronger claim. Do not repair missing currency information by borrowing the hidden labels.

### Time-ordered cycle as investigation finding

Find a path `v0→v1→...→vk=v0` with no repeated internal vertices, distinct transaction edges, strictly increasing times, an explicit maximum hop count, an explicit total duration, and optionally a maximum per-hop gap. These are independent bounds. Return the account path plus every plausible parallel-edge alternative in scope.

A bound on every adjacent time gap does not imply the same bound on total path duration. Store per-hop and whole-path limits as distinct parameters and test their boundary behavior separately.

A cycle in the static graph is not necessarily a time-ordered cycle. A time-ordered cycle is not proof that the same funds returned. Refunds, repayments, intercompany treasury movements and other ordinary activity can produce loops. With the supplied fields, report a confirmed transaction structure and unresolved economic explanation.

### Other possible families

Gather-scatter, scatter-gather and longer paths are further possibilities described in the graph research. Compare their additional cost and detection value against simpler rules. Historical anomaly features should state the available baseline duration and what happens for new or rare accounts; short histories cannot establish long-period behavioral patterns. Graph-based model scores are another benchmark, not a substitute for an auditable evidence set.

## Suggested development experiment

This is a new methodological suggestion. It separates exploratory rule development, system selection and final evaluation without prescribing dates, proportions, thresholds or a numerical search budget.

1. **Freeze the data contract.** Inspect dates, missing fields, currency semantics, key uniqueness and positive support by period. Record which raw files and hashes define this experiment. An evaluator has the labels; transaction tools expose a label-free view.
2. **Select supported rule hypotheses and verify their implementations with hand-constructed examples.** Check boundary inclusivity, self-transfers, parallel rows, equal times, multi-currency sums, and lookback support. Validate graph structure with code, not model narration. The illustrative families above are possibilities, not a mandatory initial set.
3. **Define a reproducible search space.** Choose parameters from the observed data coverage, indicator semantics and review capacity using development data only. Record allowed operators, ranges, combinations and a resource budget. Use exhaustive enumeration when practical, or a declared automated search method otherwise.
4. **Let the development agent analyze the development results.** Provide aggregate metrics and a bounded set of labeled development examples. It can propose supported changes with a causal hypothesis and a predicted trade-off. Choose an experiment budget before comparison and log every proposal, rejected proposal and evaluation.
5. **Use chronological validation to select a fixed system.** Pick a primary objective such as recall at a predeclared maximum review workload; report precision, recall and workload together. Choose the workload cap as a product requirement, not after inspecting the best test score. Account for combination search as well as individual-rule tuning.
6. **Freeze templates, parameters, prompts, model version/settings, query tools, grouping, ranking and budgets.** Run once on the untouched test period, then reveal labels. Feedback-driven test changes require another held-out evaluation.

Development and validation both influence the final design. The final test must not be used as a repeated reward signal. Any example examined during development is a known example even if its labels are hidden from the model during a later run; maintain a record of data used for debugging and system selection.

**Make the search baseline competitive.** For a small finite parameter space, compare agent search with exhaustive enumeration under the same selection objective. For a larger space, compare with a suitable non-LLM search over the same allowed proposals and the same number of evaluations. If the agent can introduce new feature logic, separate that capability from threshold selection, preserve the code/specification for every proposal, and show both quality and total experimentation cost.

To reduce memorization, forbid rule predicates containing particular account IDs, row ranges, case-specific dates or exact observed amounts. The rule DSL should allow generic fields and predeclared operators. This is especially useful if the agent sees development examples with labels.

### Metrics and attribution

- **Transaction precision/recall and PR curves**, with exact definitions of which candidate IDs are scored. Compare at fixed review capacity. Do not lead with overall accuracy.
- **Case count, duplication and case-level coverage**, using declared grouping. Account-day grouping is convenient but may merge unrelated episodes or split a cross-midnight case; document it and retain original alerts.
- **Pattern-family recovery**, only where the publisher provides a matching reference group, with incomplete/boundary-spanning groups reported separately. Pattern-file absence must not become a negative transaction label.
- **Evidence correctness**, independently verify row existence, cutoff, identity joins, chronology and derived counts. Separate “all cited rows are real” from “the conclusion follows from those rows.”
- **Compute and analyst workload**, queries, returned rows, wall time, model calls/tokens and candidates/day.

For overall transaction metrics, let `P` be all unique transaction IDs in the reporting interval, `Y` all label-positive IDs in `P`, and `C` the output candidate IDs intersected with `P`. Then `recall = |C ∩ Y| / |Y|` and `precision = |C ∩ Y| / |C|` (report undefined precision explicitly when no candidates are emitted). **Do not shrink the global recall denominator to seeded cases, published pattern members, or transactions whose motifs are already complete by the cutoff.** Conditional investigation recall within the seed-reachable search region is useful as a separate diagnostic, not a replacement.

For the separate pattern-recovery metric, an eligible complete group can require its final reference edge to fall in the reporting interval and all required edges to be visible within the permitted history and cutoff. Report partially visible and right-censored groups separately. This eligibility restriction belongs only to the pattern metric: early illicit edges that are hard to recognize before their cycle closes still count in overall transaction recall.

Transaction labels and pattern membership answer different questions. Membership in a particular publisher pattern is not equivalent to transaction-level correctness across the dataset. A candidate outside that group must be checked against its transaction label rather than automatically counted as a false positive.

Temporal split boundaries also need sequence treatment. It is legitimate to retrieve earlier development-period transactions as factual context for a later case, but not their hidden truth labels. For motifs straddling an evaluation boundary, score a declared trigger/eligible subset or report truncation. Estimate uncertainty across days or cases rather than pretending correlated transactions are independent.

A temporal test can contain later members of schemes whose earlier members supplied development feedback. That can be appropriate for future monitoring of the same network, but does not establish generalization to unseen schemes or entities. After choosing a split, measure how many publisher groups straddle its boundaries. If unseen-scheme generalization matters, add a separately defined group/entity-disjoint stress test, with the evaluator controlling group membership and the agent never receiving reference-pattern IDs.

## Where an agent can add value

| Activity | Deterministic baseline | Plausible LLM contribution | How to test its contribution |
|---|---|---|---|
| Translate guidance | Human-authored template mapping | Draft mappings and identify missing prerequisites | Compare against a reviewed rubric; reject invented fields/claims |
| Tune thresholds | Grid/random search | Explain failure cases, propose a new justified feature | Equal experiment budget, untouched validation/test |
| Find graph motifs | SQL and bounded graph traversal | Little necessary for fixed traversal | Same data, cutoff and search bounds |
| Investigate a candidate | Fixed upstream/downstream expansion | Choose which branch or explanation merits the next query | Equal query/row budget; compare evidence and coverage |
| Write findings | Structured report renderer | Clear narrative, uncertainty and follow-up suggestions | Automated factual checks plus blinded review |

An LLM that merely chooses every value in a small threshold grid is not a demonstrated improvement. Conversely, discovery that “high-degree payroll-like hubs dominate false alerts” could motivate a testable feature, but the data does not prove payroll unless the relevant evidence exists.

For adaptive investigations, expose a small action vocabulary such as `inspect_account`, `expand_incoming`, `expand_outgoing`, `summarize_activity`, `check_temporal_path`, and `finish_case`. Their arguments include account keys, time bounds and a purpose. Compile actions to validated read-only SQL. The service enforces cutoff, pagination and budget; the prompt is not the enforcement mechanism. Arbitrary SQL generation is unnecessary for the first version.

Persist explicit case state: discovered accounts, transaction IDs, checked account/time/direction ranges, pending hypotheses, query receipts and budget. A “visited account” boolean is too coarse: checking an account's incoming transactions is not the same as checking its outgoing transactions or a different time interval. Save the full evidence separately from the LLM's compact summary.

Proposed comparison:

```text
A: fixed rules + fixed graph investigation
B: agent-developed frozen rules + same fixed investigation
C: B's rules + adaptive investigation, with the same query/row budget
```

The B−A difference measures rule-development contribution; C−B measures investigation contribution. Reuse the exact seed candidates for the B/C investigation comparison. If ranking changes are allowed, report separately whether the apparent improvement is from selecting better cases or investigating each case better. Include repeat runs for stochastic agents and show variability.

This workflow does not require H-MEM or a separate World Model. The transaction graph and case tables already represent the necessary evidence and state. Markovian could later coordinate long investigations if ordinary bounded tool loops need compaction; it is not part of the detector's mathematical validity.

## Proposed case-report contract

```yaml
case_id: stable identifier
run:
  dataset_version: source hash/version
  reporting_window: [start, end]
  history_window: [start, end]
  knowledge_cutoff: timestamp
  rule_versions: [ids]
  investigator_version: prompts/model/tools/settings
seed:
  rule_hits: [id, measured_value, configured_threshold]
  focal_accounts: [bank-and-account keys]
evidence:
  transaction_ids: [immutable raw-source ids]
  query_receipts: [query-template, parameters, cutoff, result ids]
  confirmed_structures: [path/motif and supporting alternatives]
  calculations: [time gaps, counts, same-currency summaries]
assessment:
  observed_facts: [claims with evidence ids]
  hypotheses: [possible explanation, supporting/contrary facts]
  unresolved: [missing ownership/purpose/FX/balance evidence]
  priority: score or category with reproducible rationale
coverage:
  ranges_checked: [account, direction, start, end, pagination status]
  budget_used: queries/rows/model calls
  stop_reason: completed | insufficient_data | budget_exhausted | error
  pending_actions: [what remains]
```

Do not label a budget-exhausted investigation “no suspicious activity.” If the report includes a confidence number, distinguish empirical calibrated probability from model-generated self-confidence. Prefer a verifiable priority calculation and explicit unresolved questions for the first prototype.

## Separate implementation checks from discovery tests

As a new testing suggestion, create small independently constructed fixtures for each selected rule. Include matching examples, nonmatching counterexamples, boundary timestamps, parallel transactions and currency mismatches. These verify implementation mechanics; they are not evidence of benchmark discovery performance.

Evaluate discovery by running the frozen rule engine over all eligible transactions without preselected suspicious identifiers or access to publisher answers. Log generated cases, prioritization and investigation resource consumption. This tests detection and triage across the actual search space.

Use genuinely unexamined data for the final evaluation. The useful research objective is measurable improvement in supported candidate discovery and investigation efficiency, with false positives, missed positives and resource cost reported together.

## Recommended next implementation unit

Select a supported rule hypothesis from the source-to-field analysis, specify its semantics and validation plan, and implement a small end-to-end pipeline with label isolation and verifiable evidence. Extend to a declared baseline search space. Add a bounded rule-development agent and measure its contribution against the corresponding non-LLM search before investing in adaptive investigation or a separate memory framework.

This is a methodological recommendation, not a claim that a particular configuration has already achieved a measured detection result. Framework selection remains optional and should follow demonstrated requirements.
