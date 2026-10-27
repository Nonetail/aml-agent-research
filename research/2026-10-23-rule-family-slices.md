# Rule families and a first graph investigation slice

Research begun 23 October 2026; reviewed 24 October 2026, Australia/Sydney. Design recommendation only: no detector, model run or investigation was started. Existing local evidence was read alongside the primary sources below. Numerical examples here are proposed engineering limits, not official thresholds or measured optima.

## Source separation

AUSTRAC's banking indicators page is current as of this review; it states a last update of 18 September 2026. It motivates examining fast or complex transfers across accounts, receipts from multiple parties, outgoing payments after receipts, and activity inconsistent with the customer's circumstances. Some indicators require geography, economic purpose, ownership or customer information that these transaction rows cannot establish. The list is non-exhaustive; one indicator alone may not establish suspicion. It describes reasons to investigate, rather than eight executable detection rules. [AUSTRAC banking indicators](https://www.austrac.gov.au/industry-and-business/education-and-resources/publications-and-resources/indicators-suspicious-activity-banking-sector)

The number eight belongs to the IBM benchmark's standard graph motifs: fan-out, fan-in, gather-scatter, scatter-gather, cycle, random, bipartite and stack. AMLworld also generates illicit activity outside those motifs. The motif taxonomy is useful for experiment design; finding every motif would not imply finding every laundering-labelled transaction. [IBM AMLworld paper, sections 3.2–3.4](https://arxiv.org/html/2306.16424v3#S3.SS2)

IBM's Graph Feature Preprocessor separately supports simple and temporal cycles, fan-in/out, gather-scatter and scatter-gather. Its pattern windows and cycle-length constraints show how graph searches can be bounded, but its results do not establish a useful LLM context size or our detector's accuracy. [GFP paper, section 2.2](https://arxiv.org/html/2402.08593v2#S2.SS2)

The source chain should therefore be explicit for every implemented rule:

```text
qualitative concern → observable graph predicate → chosen parameters → evidence-backed assessment
       AUSTRAC           engineering / IBM         development study       investigator
```

Calling a 24-hour, four-hop cycle detector an “AUSTRAC rule” would hide the middle two steps. A clear name would be “time-ordered short-cycle candidate, version 1”.

## Recommended first slice

Start with **short, time-ordered return cycles** as one tightly scoped investigation task. Use rapid onward movement and same-currency amount comparisons as supporting measurements, rather than adding unrelated rule objectives to the same review. An illustrative first technical scope is two to four transfers returning to the starting bank/account. Select the actual hop and duration bounds using development evidence before implementation is frozen.

This recommendation is about making the experiment interpretable. A cycle has a precise completion condition, compact decisive support, and strong counterexamples: a missing closing edge, reversed direction, wrong bank/account identity, or out-of-order timestamps. It directly tests the project's existing traversal and evidence-verification machinery. It is not a claim that cycles are the easiest query, the most prevalent motif, or the best detector of laundering.

Build structural cycle fixtures first, then add a separately tested temporal condition. Publisher cycle membership, a static observed cycle and a strictly time-ordered cycle are three different facts. Equal timestamps in the minute-resolution data cannot be ordered by their source row IDs. A duration such as 24 hours should be measured and compared, not silently built into the definition; likewise, same-currency compatibility should qualify amount interpretation without excluding a topologically valid cycle from the base structural test.

**The cheapest structural baseline is simpler:** account-level fan counts and two-edge pass-through joins. Run those deterministically when comparing alternatives. If a development audit finds too few eligible short cycles, use rapid pass-through as the first slice instead, while keeping its much weaker meaning and larger plausible-benign workload explicit.

Proposed first-slice contract:

| Part | Proposed contract |
|---|---|
| Unit | One temporal cycle candidate, with exact transaction support and relevant surrounding activity |
| Predicate | Directed external transfers; distinct transaction IDs; no repeated internal accounts; return to the initial bank/account; strictly increasing recorded times |
| Parameters | Maximum hops, maximum whole-cycle duration, optional maximum adjacent gap; keep these separate |
| Discovery | A deterministic temporal query supplies the baseline; adaptive navigation may choose additional bounded queries under the same access and cost rules |
| Investigator contribution | Identify missing support or contrary evidence, choose useful context, and explain why the observable cycle warrants or does not yet warrant human review |
| Completion | Reviewable candidate, unresolved with named missing evidence, or no qualifying cycle within explicitly checked ranges |
| Evidence | All cycle edges, chronology and duration calculated by code, compatible-currency comparisons, coverage status, and relevant alternative transactions |
| Claim limit | A confirmed sequence of transactions does not establish the same money moved along every edge, common criminal control, or laundering |

Do not close a case as negative merely because a view or context chunk ended. Persist its frontier and unfinished predicate checks. Equally, do not keep asking a reviewer to reassess an unchanged candidate after each small retrieval.

## Group families by the evidence they require

The grouping below is an engineering recommendation. A specialist means a rule configuration, query policy and focused assessment rubric. It need not mean a separate model provider or an always-running process.

| Family | Evidence shape and useful navigation | Observable now | Difficulty and main failure modes |
|---|---|---|---|
| Time-ordered return cycles | Follow directed later transfers while preserving the starting account and elapsed-time budget; query directly for possible return edges | Account keys, times, parallel edges; amount/currency context | Moderate search cost, compact final support. Static cycles or equal-minute ties can fabricate sequence. Short-hop/time limits miss longer or slower schemes. Refunds, repayments and treasury movements are plausible alternatives |
| Rapid pass-through | Collect incoming and outgoing activity around a focal account and time interval; pair earlier receipts with later payments | Endpoints and elapsed time; compatible account-side amounts | Easy joins, potentially huge output. With m receipts and n payments there can be m×n pairs over only m+n transactions. Settlement and routine trading create many matches; no balances means funding attribution is unresolved |
| Fan-in, fan-out and gather-scatter | Retrieve a complete bounded account neighbourhood in both directions; aggregate distinct counterparties, then inspect the transition from receipts to payments | Counts, times, per-currency totals; optional synthetic-entity grouping | Easy counts; account-centred temporal episodes are manageable. Merchants, payroll and settlement create similar shapes. Arbitrary row truncation corrupts counts and absence claims. Gather-scatter should specify whether incoming activity must precede outgoing activity |
| Scatter-gather / split-and-reconverge | Expand several outgoing branches from an origin, then intersect their reachable destinations under time bounds | Shared origin, intermediaries and destination with transaction support | More complex than one path: a greedy traversal can miss the second branch. Ordinary pooled payments and parallel business flows can look similar. One incomplete branch should remain pending rather than invalidate all other evidence |
| Multi-layer distributions: bipartite, stack, random paths | Compare multiple sources, intermediaries and sinks across layers; maintain a branching subgraph | Transaction topology and timing | High branching and evidence volume; weak purpose inference. Defer until the simpler slices expose how coverage and deduplication work |
| Activity change, dormant-account reactivation, unusual amount/frequency | Query the account's prior comparable periods and compare with the focal period | Limited observed history, transaction amounts and frequencies | Different navigation axis: history rather than neighbours. Short observation history, seasonality and new accounts can create false alerts; observed inactivity does not establish dormancy |
| Ownership, jurisdiction, business-purpose and documentary concerns | Join verified customer/ownership data or obtain relevant documentation, then inspect related transfers | Synthetic Entity ID groups accounts; most required contextual fields are absent | Transaction-only approximation is insufficient. Currency or bank ID does not establish country; a name category does not establish transaction purpose; synthetic entity grouping is not independently verified ultimate ownership |

The local field and identity claims above come from the [full transaction profile](evidence/hi-small-profile.json), [account profile](evidence/accounts-profile.json) and [existing observability analysis](indicators-rules-and-investigation.md). They are capabilities of this downloaded dataset, not promises about another database integration.

Cash structuring should also wait for a validated cash-event and jurisdiction contract. A `Cash` payment-format value does not by itself establish a particular deposit/withdrawal event or an applicable reporting obligation. A generic numeric amount threshold across multiple currencies would be unsound.

## One reviewer per rule, or per family?

Use **one explicit hypothesis per assessment**, with a shared specialist for closely related hypotheses that need the same evidence and navigation. For example, a concentration specialist can share incoming/outgoing account retrieval across fan-in, fan-out and gather-scatter, while still producing separate rule results. A temporal-cycle specialist has a different completion test and should initially have its own rubric. Scatter-gather deserves its own query policy because preserving competing branches is essential.

This keeps focus without multiplying independent retrieval, state and duplicated alerts for every threshold variant. A shared case store should deduplicate evidence and merge overlapping candidate cases across specialists, while retaining every rule hit and its provenance. A transaction may legitimately support more than one family.

The reviewer should receive a short versioned rule card: source rationale, exact predicate, unavailable prerequisites, scope already checked, computed facts, supplied evidence IDs and allowed next queries. It should return observed facts, hypothesis, contrary evidence, missing evidence, and disposition. Source mapping belongs in the configuration, not in a vague instruction to “follow AUSTRAC”. A citation in the prompt cannot replace an executable predicate or evidence validation.

For the first comparison, keep the distinction explicit between a reviewer that assesses supplied candidates and an investigator that can request more evidence or propose a new candidate. If new proposals are allowed, code must verify every proposed edge, identity and time condition before accepting them. An empty candidate list means the current generator produced none in its checked scope; it is neither a clean bill of health nor a useful occasion for a mandatory assessment call.

## What determines a useful view boundary?

A rule's **minimum decisive support** and its **search neighbourhood** are different sizes. A three-edge cycle needs three supporting rows, but the surrounding account activity may contain hundreds or thousands of rows. Fan counts require the complete declared account/time scope or exact aggregation with a retrievable supporting ledger. Scatter-gather needs several branches shown together. Consequently, there is no source-backed universal answer such as 300 or 1,000 rows for all families.

For cycle assessment, pack several complete candidate supports plus relevant counterevidence into the available token budget; never split the only closing edge away from its path. For navigation, batch enough queries to resolve a meaningful hypothesis or fill the measured evidence allowance. Trigger assessment after a candidate becomes complete or materially changes, a bounded search finishes, or there is a concrete uncertainty requiring the investigator. Context rollover is a state-management event, not an automatic review event.

The existing [threshold results](../prototype/local-data/THRESHOLD-RESULTS.md) did not establish a reliable raw-row size: every tested view size had an invalid-edge counterexample. A smaller slice with explicit verified supports could behave differently, but that requires a new experiment rather than extrapolation from token capacity.

## Verification and unresolved decisions

Before claiming the first slice works, verify structural correctness independently on positive structures and near-miss controls, then test retrieval completeness under its declared scope. Measure case quality separately against held-out benchmark labels: a correctly found cycle can still be benign, and a label-positive transaction may have no eligible cycle. Compare fixed retrieval with adaptive retrieval using equal access and budgets. Report missed patterns, duplicate cases, unsupported claims, evidence recovery, model/query cost and human review volume.

The current evidence does not establish the best hop limit, time window, amount tolerance, token allowance, review frequency, or model. It also does not establish that an LLM improves detection over deterministic queries. These are the decisions the first slice should resolve. New data selected from known answers is development material, even if the investigator is not shown its labels.

The older indicator research remains substantively aligned with the current AUSTRAC page. The needed change is to make one selected operational rule and its source mapping concrete; eight official rules or a validated universal row threshold should not be inferred from that document.
