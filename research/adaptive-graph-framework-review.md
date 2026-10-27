# Framework support for adaptive graph investigation

Reviewed 23 October 2026. This is source research, not an implementation or a model-quality benchmark. It excludes the original project proposal. Context7 was attempted but returned unavailable; the fallback was the GitHub connector and official SDK documentation.

## Recommendation

The proposed bounded graph investigation is feasible as an application design. Start with one Vercel AI SDK tool loop, an authoritative case database, bounded graph-query tools, and context reconstruction before each model request. Compare Markovian only after establishing that baseline. Context rollover does not require another agent identity: the same logical investigator can continue with a fresh rendering of its saved case state.

Neither framework establishes detection coverage, identifies good starting transactions, or guarantees that removing evidence from context preserves every relationship. Those are application and evaluation responsibilities.

## What Markovian actually does

Rechecked reference source at commit [`1742dec56a66e58eef9dda2d2b865823758ca8cd`](https://github.com/Meterless/Meterless/tree/1742dec56a66e58eef9dda2d2b865823758ca8cd). The fetched main-branch orchestrator showed the same relevant control flow, but this note makes no claim that the pinned commit is the latest release.

- One chunk is one invocation of an injected generator, followed by marker parsing and carryover construction. That generator may wrap several model/tool turns, but the adapter must implement them. There is no SQL executor or graph navigator in the orchestrator. [Orchestrator](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/orchestrator.ts)
- `chunkSize` means a target generation budget; it does **not** mean 1,000 transactions, an input-context cap, or a provider-enforced output limit. The generator receives prompt, attachments, optional system prompt, stream callback and abort signal—not a numeric output-limit argument. Token accounting uses characters divided by four. The application must enforce query, input, output, wall-clock and cumulative budgets. [Types](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/types.ts)
- Carryover prefers a valid state marker, otherwise an injected compressor, heuristic phrases, then tail truncation. The compressor is shown only the last 2,000 characters of the latest chunk plus previous carryover. Consequently it cannot promise to preserve all evidence from an investigation. [Carryover](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/carryover.ts)
- Continuation prompts omit original attachments and memory context and shorten the goal to 200 characters. Inject the complete investigation constraints independently on every request; enforce dataset and time scope in backend tools. [Prompt builder](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/promptBuilder.ts)
- Generated chunks are appended to an in-memory run object. The facade records history only after orchestration returns; it exposes no resume method. Thus a text checkpoint marker is not a durable execution checkpoint. [Facade](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/index.ts)
- Final reflection invokes the same generator again. If the generator wraps an investigator, either disable reflection initially or route that invocation to a separately budgeted reflection call. A custom stop condition sets completion without distinguishing budget exhaustion; keep a separate domain status. [Orchestrator](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/orchestrator.ts)

These findings reinforce, rather than reverse, the earlier [framework audit](agent-frameworks.md). The newly important detail for this proposal is that 1,000 input rows and Markovian's chunk size are different quantities.

## Ordinary tool loop alternative

Official documentation fetched during this review identifies itself as AI SDK v7. Source fetched from main corroborates that `ToolLoopAgent` delegates to generateText/streamText and coordinates model calls and executable tools. This is a source/documentation snapshot; no package was installed or registry version verified. [Agent source](https://github.com/vercel/ai/blob/main/packages/ai/src/agent/tool-loop-agent.ts)

`prepareStep` can replace the message array before a call, and that replacement persists as the base for subsequent steps. We can therefore rebuild context from saved case state inside one loop. `pruneMessages` is removal, not proof of semantic preservation; use it only alongside explicit evidence/state retention. The recipe's characters/4 example is not an exact accounting method. [Compaction recipe](https://ai-sdk.dev/cookbook/guides/agent-context-compaction)

Explicit stop conditions bound model steps. ToolLoopAgent currently defaults to 20 steps; set a deliberate limit rather than inherit it. Context budget, query output size and cumulative investigation cost need separate application controls. [Loop control](https://ai-sdk.dev/docs/agents/loop-control)

The ordinary agent runs in memory. The separate `WorkflowAgent` integration provides durable workflow execution and retries; its docs say it has no default step limit, so configure one. Durability is distinct from context management, and retryable writes still need idempotency. A case database is useful with either runtime. [WorkflowAgent](https://ai-sdk.dev/docs/agents/workflow-agent)

## Application contract to evaluate

Keep four concepts separate: a model call, a bounded investigation segment, the full case, and the global campaign across seeds. A segment may inspect multiple evidence packets and perform several query calls. Ending a segment does not necessarily end its case.

Before a call, construct a packet containing frozen scope/rule versions, a compact account dictionary, selected transaction rows, findings with source IDs, unresolved hypotheses and the pending query frontier. Limit the complete serialized request by tokens; use 1,000 rows as an initial experimental target rather than a universal safe threshold.

At each successful query, save its parameters, scope, result IDs, completeness/truncation metadata and pagination cursor. At each checkpoint, save evidence references, verified findings, alternative explanations, pending queries and consumed budgets. Context can drop displayed rows while the evidence store keeps them retrievable. Preserve boundary accounts and unresolved paths explicitly so the next segment can reconnect evidence across a context reset.

Use statuses such as resolved, needs-more-evidence, deferred-by-budget and failed. Budget exhaustion must not silently become a negative AML verdict. A global queue and query cache can manage overlap across cases; a local agent's summary cannot establish that the entire giant component was examined.

Subagents can investigate independently scoped hypotheses, with their own budgets and source-linked results. They should share an authoritative evidence/query store and an overall cost ceiling; unconstrained parallel exploration simply multiplies duplicate work. Whether parallelism improves quality remains an experiment.

Compare the same seeds, tools, model and total budgets under (1) an SDK loop with context reconstruction and (2) a Markovian adapter around bounded SDK segments. Measure retrieval coverage, citation validity, preserved frontier items, repeated queries, detection quality, actual provider usage and restart recovery. Do not interpret Markovian's estimated token savings as measured project savings.
