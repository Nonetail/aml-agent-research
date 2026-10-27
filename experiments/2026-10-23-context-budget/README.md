# Transaction evidence within a 120k-token operating budget

Research and local token measurements, 23 October 2026.

## Question and assumptions

How many real IBM transaction records can an investigator receive while leaving room for its instructions, rules, tool use and response?

We treat **120,000 tokens as an assumed combined per-request operating budget**, including input and generated reasoning/output. This is a planning assumption, not a measured quality threshold or the maximum context of a selected model. No provider or model has been selected, and this experiment makes no model inference calls.

If “120k” instead means an input-only quality target, the calculation changes: generated tokens must still fit the model's separate total-context and output limits, but should not also be deducted from that input-only target. State which definition an experiment uses.

## A concrete initial allocation

| Purpose | Tokens | Meaning |
|---|---:|---|
| Instructions, rules, tool schemas and retained conversation | 10,000 | Planning allowance; measure the actual complete request scaffold |
| Additional retained tool results and messages | 10,000 | Allows an initial investigation request to grow before a context refresh |
| Generated reasoning and visible answer | 25,000 | One combined reserve, subject to the chosen model's accounting |
| Operating margin | 5,000 | Slack for request formatting and variation |
| **Graph evidence packet** | **70,000** | Transaction table, account dictionary, schema and coverage metadata together |
| **Total** | **120,000** | Hypothetical operating cap |

These are allocations, not measured requirements. Our earlier short research prompt was only 745 tokens under `o200k_base`; that does not include a future agent's complete instructions, tool definitions, history or request wrappers. [Earlier measurements](../2026-10-23-graph-scope/context-measurements.json)

The general calculation is:

```text
evidence budget = min(model total-context limit, chosen operating cap)
                  - complete request scaffold and retained history
                  - allowance for additional retained messages/tool results
                  - combined generated reasoning/output reserve
                  - operating margin
```

For a single request with no follow-up tool use, the additional-message allowance can be zero. An agent must recalculate before every model request: a packet that fits initially may cease to fit after tool results or earlier responses are retained.

OpenAI documents input, output and reasoning as sharing context, with a separate output limit. Its reasoning guide suggests starting experiments with at least 25,000 tokens reserved for reasoning and output, then adjusting to observed usage. That is an initial vendor guideline, not a universal workload requirement. `max_output_tokens` already includes hidden reasoning and visible output for those models; do not subtract another reasoning reserve on top of it. Earlier reasoning retention also depends on model and configuration. [Context accounting](https://developers.openai.com/api/docs/guides/conversation-state#managing-the-context-window), [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)

## Measurements

We scanned all **5,078,345 HI-Small transaction rows**, chose the account with the most incident rows without reading labels for selection, and measured chronological prefixes of its activity. That account has 169,756 incident rows. The samples contain 500, 1,000, 2,000, 3,000 and 5,000 rows. Every sample is truncated. A row cap can split tied timestamps; these prefixes do not establish complete time windows or complete connected components.

All four formats encode the same information: scope and schema, account/bank/recorded-entity aliases, and nine transaction fields. Both original paid and received amount/currency pairs are preserved. Raw identifiers resolve through a private source mapping. There are no labels, pattern answers or entity names in the public packets.

The whole evidence packet measured under `tiktoken 0.14.0`, encoding `o200k_base`:

| Transactions | Compact CSV tables | Markdown tables | Positional JSON arrays | Minified JSON objects |
|---:|---:|---:|---:|---:|
| 500 | 22,421 | 25,259 | 25,245 | 37,889 |
| 1,000 | 43,266 | 48,525 | 48,511 | 73,190 |
| 2,000 | 83,535 | 92,742 | 92,728 | 139,987 |
| 3,000 | 124,237 | 137,662 | 137,648 | 207,937 |
| 5,000 | 206,178 | 228,483 | 228,469 | 345,558 |

Counts include the account dictionary and coverage/schema header. They exclude instructions/rules, tools, chat wrappers and output, which have separate allowances above. The second reference encoding, `cl100k_base`, and section-level counts are retained in the [machine-readable results](measurement/benchmark.json). Neither encoding is claimed to be the actual tokenizer of a future selected model.

At 1,000 rows, CSV uses about 41% fewer tokens than JSON objects and 11% fewer than Markdown. Positional arrays save almost nothing over Markdown in this particular comparison. Repeated keys are expensive, but removing them does not guarantee that every remaining punctuation choice is cheaper. Smaller serialization does not by itself establish equal model comprehension.

This is specifically a **high-degree, single-currency star**. Its 2,000-row prefix has 1,059 accounts, 1,058 directed account pairs and 942 additional transfers over already represented pairs. All rows are US Dollar, with no self-transfer or currency-conversion rows, and only Cash, Cheque and Credit Card formats. The source time spans just 25 minutes. Token cost may change with other currencies, longer aliases, denser account reuse, additional metadata or different graph structure.

All 20 packets round-trip to their canonical evidence; 5,000 source rows were reread and checked. An independent reviewer also decoded each packet and verified the shared fields and provenance mappings. Reproducible code, packet examples and checks are in [measurement](measurement/README.md).

### How many transactions fit the 70k evidence allowance?

We rebuilt and counted prefixes around the budget boundary, including their changing account dictionaries and metadata:

| Format | Verified fitting prefix | Whole packet tokens | Tokens with one more row |
|---|---:|---:|---:|
| Compact CSV tables | 1,659 transactions | 69,965 | 70,003 |
| Markdown tables | 1,478 transactions | 69,994 | 70,045 |
| Positional JSON arrays | 1,478 transactions | 69,980 | 70,031 |
| Minified JSON objects | 953 transactions | 69,938 | 70,015 |

These are concrete fitting examples under `o200k_base`, found by binary search within the audited 5,000-row prefix. Each selected packet and its immediate successor were counted. This does not prove a globally maximal prefix for arbitrary data, metadata or tokenizer behavior. Reproduction and results: [budget-fit script](measurement/fit_budgets.py), [budget-fit results](measurement/budget-fits.json).

For initial planning, **roughly 1,500 compact table rows per request** is a more defensible number for this 70k evidence allocation than tens of thousands. It is not a recommended minimum or a proven reliable reasoning limit. A first quality experiment can begin at 500 and 1,000 rows, then increase toward the measured capacity while checking evidence recovery and false positives. Do not pad small cases to a target row count.

The same fixture produced fitting examples of 2,037 CSV rows at an 85k evidence allowance and 2,421 at 100k. Those are evidence-only budgets; within the assumed 120k combined cap, they leave only 35k and 20k respectively for every other purpose. They therefore cannot retain all the reserves in our initial allocation.

## What the budget does and does not establish

An edge table is a valid graph representation: each row identifies a directed transaction between two account aliases, and the account dictionary supplies bank and recorded-entity relationships. Preserve self-transfers, repeated transfers and separate source row instances. A table avoids spelling every possible path out in text, which would duplicate evidence and grow combinatorially.

Token fit is only a capacity check. A repeated star-shaped graph may tokenize compactly while a similarly sized network with branching paths, several currencies and widely separated relevant transfers is harder to investigate. The measurements do not establish that the model can reliably recover laundering patterns at the maximum fitting row count.

Long-context research supports testing the actual task. RULER evaluates multi-hop tracing and aggregation as well as retrieval; LongPiBench investigates the spacing between related evidence. Their results do not establish a universal 120k safe zone for a current, untested model. [RULER](https://arxiv.org/abs/2404.06654), [LongPiBench](https://aclanthology.org/2025.findings-acl.28/)

For this project, test increasing evidence sizes while varying distractor volume, branching, path length, position and distance between linked transactions. Preserve frozen development/evaluation separation. Evaluate cited transaction IDs, temporal/currency consistency, numeric calculations, recovery of relevant evidence, false-positive burden, cost and completion rate. A plausible narrative or subjective confidence percentage is insufficient.

## Application behavior

1. Select a coherent candidate neighborhood using label-free deterministic queries. Record its scope, exclusions and truncation. A token limit alone cannot define a meaningful investigation boundary.
2. Build a schema-described transaction table and account dictionary, with stable aliases and a private source mapping. Do not expose evaluator labels or reference pattern files to the investigator.
3. Count the complete intended request using the chosen provider/model's supported counting method. Local reference encodings compare formats; they are not exact provider usage or billing counts.
4. If the packet exceeds its allowance, retrieve a narrower, explicitly declared view or split investigation work while retaining links to exact evidence. Preserve the ability to retrieve omitted neighboring transfers. Do not silently drop arbitrary rows or infer that a partial view is a complete episode.
5. Request concise findings with supporting transaction IDs and limitations. Keep exact records outside the context, and fetch additional evidence within the remaining budget.
6. Before the next model call, account for retained tool results and prior responses again. Refresh context from durable investigation state when needed; retain the governing rules and evidence references.

OpenAI's input-counting API can count messages, instructions and tools together, including request formatting that local plain-text tokenization may omit. Actual generated-token usage must be recorded after inference. [Token-counting documentation](https://developers.openai.com/api/docs/guides/token-counting)

## Evidence and reproduction

- [Measurement procedure, scripts and results](measurement/README.md)
- [Independent measurement review](measurement/REVIEW.md) and [final verification](verification.json)
- [Primary-source accounting notes](context-accounting-sources.md)
- [Previous small-packet measurements](../2026-10-23-graph-scope/context-measurements.json)
- [IBM source inventory](../../data/README.md)

This research uses IBM data and current primary technical sources. It does not use the excluded original proposal or its suggested rule list. No inference request or model-quality evaluation is part of this capacity experiment.
