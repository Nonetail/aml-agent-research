# Context, expansion, and review boundaries

Research for the 23 October 2026 design discussion. This note proposes an experiment and architecture; it does not change the prototype, restart a run, or establish a safe model context size. Online sources were checked against the current project implementation. Historical results retain their original model and experimental scope.

The useful direction is to let code retrieve a substantial, relevant body of evidence between model decisions, then ask a specialist reviewer a narrow question. Make context rollover depend on the complete tokenized request. Make investigation and review boundaries depend on the rule's evidence requirements. Neither boundary should be a universal transaction count.

## What the current prototype actually does

The current [model adapter](../prototype/local-data/model.py) selects `nvidia/nemotron-3.5-lightning-30b-a3b` at NVIDIA's hosted chat-completions endpoint. It uses temperature zero and disables thinking. The [batch runner](../prototype/local-data/batch_agent.py) already separates direction selection from database pagination, but it still couples every retrieval burst to mandatory row-presentation review.

| Quantity | Current batch behavior | Meaning |
|---|---|---|
| SQL page | 250 requested rows | Database transport unit; duplicates can reduce new evidence |
| Retrieval burst | Up to 1,500 newly discovered rows or 100 pages by default | Scheduler checkpoint, not a context measurement |
| Reviewer packet | Configurable row ceiling, default 150; at most six paths | Model presentation and output-size constraint |
| Context allowance | Default 24,000 proxy units: serialized request bytes plus output/overhead allowances | Not tokenizer-measured input tokens |
| Navigator input | Frontier summaries and previous review receipt | Does not contain a full accumulating conversation |
| Candidate construction | All discovered evidence, earliest later continuation, at most six edges | Can join evidence across bursts but omits alternative continuations and longer patterns |
| No-candidate review | Must return an empty decision list | Row presentation cannot itself create a finding |

Each [model call](../prototype/local-data/global_agent.py) is rebuilt as a system message and a current payload. This is already largely stateless context reconstruction, rather than one ever-growing transcript. The immediate problem is therefore packet selection and review scheduling; adding a chunk wrapper alone will not fix it.

The older [chunk implementation](../prototype/local-data/CHUNKING.md) also persists evidence and cursors across context changes. Its current documentation explicitly says automatic token-pressure rollover is not implemented. The 150-row view, request-byte guard, six-edge candidate restriction, and case cost budgets are different limits.

## Verified model capacity and the one-third proposal

NVIDIA's official model card advertises **up to 1M tokens** for Lightning 3.5. That describes advertised model capacity, not measured graph-reasoning quality. The hosted API reference specifies `max_tokens` from 1 to 32,768, with a default of 16,384; this is the response-generation limit, not the input context window. The reviewed public references did not establish a separate exact input-plus-output acceptance limit for our hosted deployment or our account. No authenticated capacity probe was run. [NVIDIA model card](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/modelcard), [hosted API reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-5-lightning-30b-a3b-infer).

Using one-third as an initial operating ceiling is a reasonable **experimental policy**, not an established smart zone. One-third of the advertised decimal 1M is approximately 333,000 tokens, which would be a large unvalidated jump from today's packets. Use one-third of the verified effective endpoint window, further constrained by the task-specific quality and latency budget. Do not automatically fill to the model's advertised third.

For each request, preflight the actual rendered messages, tool definitions, chat-template overhead, and selected evidence using the model's tokenizer/chat template where available. Account for the response allowance separately. If the hosted template cannot be reproduced exactly, record the estimator and its margin, compare it with returned provider usage, and avoid describing the estimate as exact.

An admission policy can express two separate checks:

- Current input must fit the chosen task-quality budget, which is at most one-third of the effective deployment window while testing that policy.
- Input plus permitted output plus estimation margin must fit the hard deployment window. When retaining conversation history, also reserve space for the next allowed tool result before dispatching it.

Before the next call would cross the soft budget, persist the current state and render a fresh context from that state. If one complete evidence unit still does not fit a fresh context, explicitly partition the task with preserved dependencies or mark it as needing a different representation. Do not silently truncate its supporting evidence. Keep explicit response caps: the current continuous mode can omit `max_tokens`, so its effective provider default is distinct from a deliberate application reserve.

## Five boundaries to keep separate

| Boundary | Recommended definition |
|---|---|
| Retrieval page | A bounded SQL result with a continuation cursor; chosen for database efficiency |
| Investigation work unit | A rule-specific account/time/path scope with explicit completion conditions |
| Working view | Selected evidence and computed facts admitted to the current model request by token budget |
| Chunk lifespan | The period between fresh context renderings; can include several work units and model calls |
| Review trigger | Evidence readiness, material change, unresolved decision, or queue/latency pressure |

Cost, elapsed-time, query-time, and concurrency limits remain separate operational controls. They pause or defer work, not declare a neighborhood benign. Removing an arbitrary 1,500-row stop does not require unbounded queries or unlimited model spending.

A work unit can continue across several context rollovers without triggering a reviewer. Rollover saves and reconstructs the investigator's context; review happens when the applicable evidence contract is ready or an explicit partial assessment is useful. Conversely, several completed small candidates can be reviewed within one investigator chunk.

For a first cycle-oriented slice, a work unit might specify a starting edge, ordered time constraints, allowed currencies, an investigation window, and a tested maximum path length. These values are engineering hypotheses to validate, not asserted AUSTRAC thresholds. Code follows all eligible continuations within that declared search policy and records which branches remain unexplored. Choosing only the earliest outgoing edge is an incomplete search strategy even when its output is perfectly verified.

A closed cycle provides complete supporting edges for the claim that this cycle exists. It does not establish that funds were conserved, that the neighborhood was exhaustively searched, or that laundering occurred. A broader negative statement requires coverage of the corresponding search scope. Keep these claims separate in the review record.

For a rule with a 24-hour window, closure means exhausting the specified accounts and directions over that anchored window, including pagination. Reaching the reporting-period edge can mean missing context, not completion: the evidence contract must identify whether the full required window is available. Other families need other closure contracts; fan-in/out aggregation and historical behavioral comparisons cannot inherit a cycle's stopping rule.

## Aggressive expansion with meaningful movement

Give the navigator meaningful choices such as continuing a candidate's outgoing flow, checking incoming funding, testing a return path to the origin, or moving to an unexamined time window. Include compact degree/time/currency summaries, data-availability flags, and evidence references. The model chooses a direction and question; code validates and executes it.

Once selected, code should paginate, deduplicate, compute rule facts, and collect enough relevant evidence to make progress without another model call per page. A 10-row view can become a 300-row experimental view in one scheduler burst. It can also reach a complete small candidate after 20 rows and review then; adding 280 unrelated rows would not improve that candidate's evidence.

Fill toward the chosen capacity with eligible evidence while preserving full candidate support. When a high-degree hub exceeds capacity, retain its exact rows in storage, calculate source-verifiable aggregates, and divide the remaining work by explicit time/account/direction scopes. Do not let the first branch consume the entire capacity and starve all later branches without recording the tradeoff.

Moving the view a substantial distance is reasonable if unresolved dependencies survive outside context. An evicted row remains retrievable. More importantly, an unresolved path remains an explicit pending item with its source IDs and continuation requirements. A short narrative summary or arbitrary last-N-row overlap cannot guarantee that.

The review scheduler should enqueue newly ready candidates or candidates whose relevant evidence changed. It should not ask an assessor restricted to supplied candidates to review an empty candidate list simply to increment a row-presentation counter. If open-ended discovery is desired, give it a separate proposal contract that can name a candidate or request evidence, then verify the proposed structure before assessment.

Review backlog still needs backpressure. Permit navigation until a bounded queue or latency target is reached, then drain the queue. This reduces mechanical checkpoints while keeping newly discovered evidence and unresolved candidates visible. Preserve immutable receipts for an exact evidence version; re-review only when evidence changes a candidate's applicable facts or the rule version changes.

## State that must survive a chunk

Use the database as authoritative state. The checkpoint should reference it rather than attempt to replace it with prose. Persist:

- Source identity, case/rule version, authorized time range, cutoff, and account-key convention.
- Exact source row IDs and retrieval receipts, with query parameters, cursor, deduplication state, and completeness/truncation flags.
- Frontier items: account, direction, time window, cursor, priority/rationale, owning work unit, and status.
- Partial candidates: ordered edge IDs or relevant member IDs, endpoint/boundary accounts, temporal constraints, remaining eligible scopes, and explicit coverage limits.
- Computed facts with supporting rows, alternative explanations, pending evidence requests, and verified or rejected candidate status.
- Review queue, evidence fingerprints, committed decisions, observed provider usage, unknown consumption after interruptions, and resource budgets.

Commit successful page results and cursor advancement atomically. Make candidate and review identities deterministic for the same rule/evidence version. A restart may otherwise duplicate a request even if it cannot duplicate stored evidence; distinguish exactly-once committed work from unknown provider consumption.

A fresh context needs only the current frozen rule, the selected work unit, relevant evidence/facts, boundary dependencies, and a compact history of decisions. The same logical investigator continues; a new context does not require a new agent identity.

## What belongs to code and what belongs to the model

| Code | Model |
|---|---|
| Authorized database queries, pagination, deduplication, and resumable state | Prioritize among meaningful investigation directions |
| Exact bank/account identity, chronology, path closure, currency-aware arithmetic, and aggregation | Identify plausible explanations, contradictions, and the next useful evidence |
| Candidate search under an explicit coverage policy; verification of model proposals | Assess one narrow rule family against supplied computed facts and source evidence |
| Token admission, queue scheduling, evidence completeness, claim-reference validation | Write concise, qualified findings for a human reviewer |
| Source-linked metrics and benchmark evaluation | Express uncertainty and distinguish observation from hypothesis |

Return structured claims with evidence IDs and relevant computed fact IDs. Validate timing, identity, and amount assertions against those facts. Natural-language fluency and schema validity do not establish factual correctness. A reviewer can request more evidence; an underfilled or truncated scope must remain incomplete rather than become `not_supported` by default.

## What the existing results establish

The [historical threshold study](../prototype/local-data/THRESHOLD-RESULTS.md) found no passing factual-reading threshold among 40, 75, 150, 300, 750, and 1,500 rows. However, its [protocol](../prototype/local-data/THRESHOLD-PROTOCOL.md), saved `generated/thresholds-v2/manifest.json`, and frozen adapter all identify **Nemotron 3 Ultra 550B A55B**, not today's Lightning model. It is evidence against a universal row-based smart zone and evidence of past factual failures; it is not a Lightning capacity benchmark. The task was also exact greedy path tracing, not a focused reviewer supplied with verified facts.

The [batch prototype report](../prototype/local-data/BATCH-PROTOTYPE.md) documents a Lightning live run that confused bank and account fields and misstated a supplied path. Its separate constructed cycle/control sanity check also failed intended discrimination. The saved `batch-agent-live-v1/ledger.sqlite` response metadata confirms Lightning for that live batch. These are small development failures, not population precision/recall estimates.

The same report's 150/500/1,500-row packet comparison used scripted responses and 1,600 self-transfer rows. Larger packets reduced reviewer calls, with a byte allowance binding at 515 rows, but established no reasoning-quality threshold. The [fixed-scope page-size experiment](../prototype/local-data/BATCHED-EXPLORATION.md) recovered identical row IDs with 25- versus 250-row pages and fewer SQL pages. That supports decoupling pagination from model decisions; it does not prove a detection improvement.

## Next controlled experiment

Use one rule family and a frozen, label-withheld benchmark. Compare 300 and 1,000 rows as candidate **presentation conditions**, with a smaller baseline, rather than prescribing either as the answer. Keep complete target evidence and comparable hard negatives fixed; vary additional real neighborhood distractors. Separately vary path length, branching, density, hub degree, timestamp ambiguity, amount/currency compatibility, number of simultaneous candidates, and the position of decisive evidence. Rows alone do not describe reasoning difficulty.

Pin the model/version, endpoint, prompt, representation, rule definition, thinking mode, and output allowance. Compare fact-enriched candidate packets with raw-row discovery as different tasks, not pooled results. Separate retrieval recall, candidate-generation recall conditional on retrieval, and reviewer discrimination conditional on complete candidate evidence. Also report source-claim accuracy, missed cross-boundary candidates, human review burden, latency, provider tokens, calls per candidate, and cost per supported finding.

Include positives spanning pages and chunks, late closing edges, competing continuations, same account string at different banks, and plausible ordinary activity with a similar topology. Test interruption and resumption deterministically before using a live model. Score provider failures separately from factual errors while retaining both in end-to-end reliability denominators.

Choose the largest evidence workload that meets predefined factual and discrimination requirements at acceptable cost, not the largest packet the server accepts. If none passes, improve the facts, task contract, or model before increasing traffic. No current evidence justifies claiming 300, 1,000, or one-third of context is a validated optimum.

## Framework consequence

Context7 now successfully retrieves the AI SDK v7 documentation. It confirms that `prepareStep` can replace the messages before a step and that the replacement persists as the base for later steps. The runtime can therefore reconstruct a bounded view from the case database without an additional context engine. This confirms the recommendation in the existing [framework review](adaptive-graph-framework-review.md); its note that Context7 was unavailable describes that earlier lookup, not today's availability. [Versioned AI SDK loop-control documentation](https://github.com/vercel/ai/blob/ai@7.0.0/content/docs/03-agents/04-loop-control.mdx).

Keep Meterless optional. The [existing pinned-source audit](agent-frameworks.md) already distinguishes its generator chunk and lossy carryover from durable case state and exact token admission. No new evidence in this review establishes a need to replace the current persistent ledger or add another framework. Implement and measure the boundary policy first; evaluate a wrapper against the same evidence/state contract if it provides an additional demonstrated benefit.
