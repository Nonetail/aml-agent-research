# Graph scope, context size and overlapping cases

23 October 2026. Follow-up to the [two-case probe](../2026-10-23-two-case-probe/README.md).

**The 76-row positive packet was complete for a bounded query, not a whole isolated transaction network.** A full-file connectivity audit shows why whole connected components are unsuitable as model-sized cases: the largest contains approximately 96% of all transactions. Both previously assessed packets belong to that same component within their shared observation window.

## What the 76 rows included and omitted

The earlier positive packet includes every transaction touching any of six chosen focus accounts in `[2022/09/02 01:07, 2022/09/05 21:21)`, a span of 92 hours 14 minutes. There is no row truncation within that query. The new full-file scan independently verified exact equality between all matching source-row IDs and the saved packet.

Those rows introduce 15 boundary accounts, giving 21 displayed accounts in total. The query does not retrieve all other transactions for the boundary accounts, or any earlier/later history. The known reference cycle determined the positive focus accounts; this was not a blind discovery pipeline.

| Expansion, in the same window | Positive packet | Negative packet |
|---|---:|---:|
| Original six-focus-account query | 76 rows / 21 accounts | 97 rows / 21 accounts |
| All transactions touching any of those 21 accounts | 258 rows / 56 accounts | 346 rows / 83 accounts |
| Complete weakly connected component | 1,492,740 rows / 290,027 accounts | The same component |

The original positive query also omitted nine self-account transaction rows on boundary accounts already displayed in the packet. It omitted no non-self rows between those displayed accounts. These nine rows are not nine additional inter-account relationships. The [machine-readable audit](graph-scope-results.json) records the breakdown; the original packet was not a complete induced graph over its displayed accounts.

“Complete weak component” here means following observed connections in either direction within the selected timestamp window. It does not establish chronological fund movement, shared ownership or common suspicious activity. Independence of the two model assessments did not mean their underlying networks were disconnected.

## Measured prompt size

The original runtime did not record the model's actual usage or exact tokenizer. We counted the preserved text with `tiktoken` 0.14.0 using two named reference encodings. These are reproducible counts of that text, not reconstructed provider billing or total context consumption.

| Saved text | Positive, 76 rows | Negative, 97 rows |
|---|---:|---:|
| Evidence Markdown only, `o200k_base` | 3,713 tokens | 4,630 tokens |
| Evidence plus common guidelines, `o200k_base` | **4,459 tokens** | **5,376 tokens** |
| Evidence plus common guidelines, `cl100k_base` | 4,480 tokens | 5,402 tokens |
| Saved request characters | 12,629 | 14,802 |

System/developer instructions, tool declarations, file-read wrappers, reasoning and response usage are not included in these request counts. Repeated tool retrieval would add further context. An exact context-window percentage or cost requires the selected model and actual usage telemetry.

The stored pretty-printed JSON packets count as 7,955 and 9,887 `o200k_base` tokens, respectively. Repeated field names, whitespace and some metadata differences contribute; this does not prove Markdown universally superior. [Detailed measurements](context-measurements.json)

Seventy transactions is one tested size, not a minimum or established optimum. Branching, temporal ambiguity, parallel edges, currencies and completeness can matter more than row count. A larger benchmark should vary those properties as well as input size before choosing a packet budget.

## Does the dataset divide into small, disjoint graphs?

For the audit, each normalized `(bank, account)` pair is a vertex and each original transaction row is an edge. Weak connectivity ignores direction, but every source row, including self-transfers and parallel/exactly repeated rows, remains counted. Unused account-metadata rows are excluded from component counts. No ownership edges or laundering labels are used to form components.

| Scope | Transaction rows | Weak components | Accounts in largest component | Transactions in largest component | Fraction of rows in largest |
|---|---:|---:|---:|---:|---:|
| Entire HI-Small file | 5,078,345 | 114,139 | 372,089 | 4,874,569 | **95.99%** |
| Primary period, September 1–10 | 5,077,237 | 114,244 | 371,915 | 4,873,162 | **95.98%** |
| Earlier probe's 92-hour window | 1,551,162 | 33,869 | 290,027 | 1,492,740 | **96.23%** |

The full-file count includes 92,354 one-account components with self-transfers. Therefore the number of components is not a count of candidate investigations or useful LLM jobs. Most transaction volume remains concentrated in one large component. Excluding the sparse tail does not materially change that conclusion.

Connected-component discovery is a straightforward connectivity operation; it does not enumerate all possible transaction paths. The local union-find scan and summaries took approximately 16 seconds on the initial run. That is not a benchmark for cycle enumeration, candidate generation, model inference or production latency. [Full measurements](graph-scope-results.json), [audit code](audit_graph_scope.py)

## Recommended design: unique work ownership with shared evidence

The system should maintain one authoritative transaction dataset. Investigation packets are bounded views over it. We cannot generally guarantee that every related transaction is included while simultaneously requiring every packet to be small and completely disjoint.

An implementation to evaluate would:

1. **Generate candidate rule hits.** Run defined temporal statistics and bounded graph queries over the eligible population. Emit exact supporting transaction IDs, rule version, triggering event and scope. This is not a request to list every conceivable subgraph.
2. **Deduplicate identical hits.** Use stable source IDs and a canonical evidence representation. Preserve distinct rule reasons while recognizing repeated discoveries of the same evidence.
3. **Group hits into bounded episodes.** Shared core transactions plus compatible timing can justify one case. A shared merchant, employer or other busy counterparty alone should not merge every case. Bound total episode duration; link related cases when merging would produce an oversized or incoherent case.
4. **Assign one owner per case version.** A registry reserves each new case/version for one initial model review. Repeated detections update or link to that record instead of silently creating duplicate reviews.
5. **Build a focused initial packet.** Preserve exact core evidence, add relevant context, and expose coverage metadata. When background exceeds the packet budget, summarize it and provide tools for retrieving details. Do not label that packet complete beyond its query predicate.
6. **Allow shared supporting evidence.** Case-to-transaction membership is many-to-many. Cache reusable query results and validated facts. Dataset metrics count distinct predicted source transaction IDs, not the sum of packet row counts.

Shared evidence is different from duplicate work. The same payment may legitimately help explain two episodes. Forcing it into only one case can remove a necessary link from the other.

For example, if two alerts refer to the same cycle from different starting accounts, canonical evidence IDs can group them into one episode. If separate episodes only share an ordinary payment hub, retain separate cases and record their common context. These are proposed grouping semantics that require validation, not a guaranteed discovery of real-world case boundaries.

## Parallel workers and time boundaries

Suppose an adopted rule requires at most `D` days of history and defines its trigger as the final event in the evidence pattern. Workers can own nonoverlapping trigger-time intervals while reading overlapping history:

```text
Worker 1 owns triggers in [day 5, day 6)
Worker 2 owns triggers in [day 6, day 7)

Each reads the historical range required by the rule.
Each emits only hits whose trigger belongs to its owned interval.
Canonical hit IDs make repeated searches/retries idempotent.
```

The overlapping read range protects sequences crossing the job boundary. An additional historical baseline may require longer lookback. An unbounded-duration rule cannot be covered by a finite fixed lookback. Equal-minute source timestamps cannot establish causal order; a stable ID can break an ownership tie without pretending to order events causally.

These guarantees concern trigger/output ownership. Supporting transactions can appear in multiple jobs and cases. Cross-shard graph queries must still be able to follow boundary connections; parallelism does not make omitted relationships harmless.

## What remains unknown

We have measured connectivity, saved-text size and packet expansion. We have not implemented a full candidate extractor, case grouper, parallel detection pipeline or larger model-quality benchmark. The number of model calls is consequently unknown and cannot be inferred by dividing five million transactions by 76.

A next extraction pilot should measure candidate counts before/after grouping, distinct covered transactions, evidence repetition, case-size/token percentiles, oversized cases and boundary-spanning findings. Coverage and detection quality must be evaluated independently of how efficiently jobs are deduplicated.

## Sources and reproduction

- [Original probe protocol](../2026-10-23-two-case-probe/PROTOCOL.md) and [source-file manifest](../../research/evidence/download-manifest.json).
- [NetworkX connected-components documentation](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.connected_components.html): component computation and complexity.
- [NetworkX weak components](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.weakly_connected_components.html): connectivity grouping for directed graphs.
- [NetworkX simple-cycle documentation](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.cycles.simple_cycles.html): cycle enumeration depends on the number of cycles, unlike component discovery.
- [IBM Graph Feature Preprocessor paper](https://arxiv.org/html/2402.08593v2#S2): indexed temporal multigraph processing and bounded pattern search.

`audit_graph_scope.py` uses Python's standard library and the bundled IBM files. Run it to regenerate component and boundary measurements. `measure_context.py` requires `tiktoken==0.14.0`; it recreates the named-encoding text counts. The original measurement used a disposable virtual environment, without installing packages into the system or bundled runtime. Tokenizer resources are downloaded when not cached. No model/provider call was made in this follow-up.
