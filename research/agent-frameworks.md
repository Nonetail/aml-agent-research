# Agent frameworks: Meterless and Vercel AI SDK

Research date: 23 October 2026 (Australia/Sydney). Scope: optional implementation tools for an agentic system evaluated on IBM synthetic AML data and grounded in AUSTRAC indicators.

**Implementation option:** Vercel AI SDK can support rule-research and case-investigation loops with deterministic query/verification tools and explicit experiment/case records. No framework is selected or required by this research. Treat Meterless Markovian as an optional context-management experiment. H-MEM and World Model are not necessary to store this project's progress or transaction graph.

## Evidence and reproducibility

- Inspected Meterless commit [`1742dec56a66e58eef9dda2d2b865823758ca8cd`](https://github.com/Meterless/Meterless/tree/1742dec56a66e58eef9dda2d2b865823758ca8cd), dated 19 October 2026. The probes used an unmodified sparse checkout. Reproduction requires this pinned source version; the checkout itself is not bundled.
- Read official AI SDK v7 documentation and its repository package metadata. The fetched main-branch `ai` package reported `7.0.150`; this is a source snapshot, not a claim that we verified the npm registry's latest release. Pin the chosen installed version when implementing. [Package metadata](https://github.com/vercel/ai/blob/main/packages/ai/package.json)
- Executed [engine-probe.mjs](evidence/engine-probe.mjs) with Node v24.16.0 against that Meterless checkout. [Raw results](evidence/engine-probe-results.json). These are targeted behavioral probes with mock generator responses, not a full conformance run or real-model benchmark.
- Reproduce with `node --experimental-transform-types --disable-warning=ExperimentalWarning evidence/engine-probe.mjs /absolute/path/to/pinned/Meterless`. The probe writes only a temporary history directory.

## What Meterless actually distributes

The open engines are implementation contracts, examples, conformance material, and reference source. They are not published `@meterless/*` npm dependencies. Their references are marked private and explicitly describe non-production limitations. Adopting one means adapting/vendoring code or implementing the contract and maintaining that integration. The open source uses Apache-2.0; that does not establish the licensing or access conditions of separately shipped Nightshift applications. [Engine overview](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/README.md), [license](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/LICENSE)

| Component | Useful capability | Project decision |
|---|---|---|
| H-MEM | Mine and retrieve selected memories; provenance, corrections, maintenance | Defer. Exact case progress and evidence belong in explicit records. Consider only for a measured need for reusable analyst preferences or generalized procedures. |
| World Model | Event-backed entities, facts, relationships, and views | Defer. Transaction tables plus a temporal multigraph already represent the investigation; account/entity lookup can be a normal join. |
| Markovian | Generator loop, compact carryover, markers, limits, progress, completed-run history | Optional context-policy experiment if investigations become long. It is not a ready-made agent tool runtime or durability engine. |
| Scout Intent | Intent/risk/routing contract | Out of scope at the user's request. Typed request parsing and tools are sufficient for the first version. |
| Nightshift | Separate application/runtime for local model serving and repeated work | Not required to integrate the open engines. Local hardware/model selection is a separate benchmark decision. |

## Markovian: confirmed behavior and integration gaps

The orchestrator calls an injected generator once per work chunk. It parses returned text, saves chunk output in the run, computes carryover, and checks completion/custom stopping. A generator can call a model directly or wrap a bounded tool loop. The engine itself does not execute SQL or dispatch tools. A `NEEDS_TOOL` marker is parsed, but the inspected orchestrator does not execute or pause for that tool. Our probe returned such a marker and observed the next generator call without any tool execution. [Orchestrator](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/orchestrator.ts), [marker parser](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/markers.ts)

The default prompt includes initial context/attachments on the first call. Later prompts contain a goal shortened to 200 characters, carryover, and optional previous-output overlap. A late cutoff constraint in our test goal disappeared from the second prompt. This is not evidence every integration loses constraints: a custom callback can reinsert them. **For AML, enforce cutoff, allowed dataset, and permissions in backend tools on every call, independently of prompt summaries.** [Prompt builder](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/promptBuilder.ts)

Carryover uses an explicit valid state block, then an optional compression callback, then phrase heuristics, finally tail truncation. It is lossy and cannot certify preservation of evidence or unfinished tasks. Source transaction IDs and the pending query frontier should live in structured case state. A compact narrative can accompany them. [Carryover implementation](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/carryover.ts)

`chunkSize` is validated in configuration, but is not a provider-side output cap in the generator contract. The probe returned 3,125 estimated output tokens with `chunkSize: 2400`; the run accepted it. You must set provider output limits, SQL row/time limits, and any inner-loop budget separately. [Types](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/types.ts), [configuration](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/configManager.ts)

The facade records history after orchestration returns. Our probe found no history file while the second call was running, but found it after completion. There is no `resume()` on the inspected class, despite richer workshop examples. Completed-run JSON history is not crash-safe checkpoint execution. Persist each successful tool result and case-state transition yourself, or choose a durable workflow runtime. [Facade](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/index.ts), [history](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/history.ts), [workshop sketch](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/workshops/04-reflect-and-resume.md)

Completion markers are model claims, not evidence validation. The final reflection is another model call and does not replace timestamp, graph, amount, and citation checks. Token reporting is estimated rather than a complete provider billing measurement; the reference's demonstration uses a mock generator. Do not carry the advertised savings into our project forecast. Measure actual input/output/cache usage, compression calls, latency, and investigation quality. [Reference README](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/README.md)

Independent source review identified two adapter obligations: a custom `stopWhen` ending the run leaves its status as `completed`, so budget termination needs a separate domain status; and default final reflection invokes the same generator again. If that generator wraps a tool-using investigator, reflection could trigger another entire investigator run. Use `reflect: false` initially, or explicitly route reflection to a separately budgeted read-only call. [Orchestrator control flow](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/markovian/reference/src/orchestrator.ts)

## Why not directly use World Model for transactions?

The relevant data is a **temporal directed multigraph**: bank/account pairs are vertices; individual transactions are edges; several edges can connect the same accounts; distinct recipients must coexist.

In the inspected reference, adding an open relationship with the same source/type/context and a different target closes the previous open relationship. Our probe added `A → B` and `A → C` under the same relationship type/context. The default current-neighbor query returned only C. That behavior is useful for a replaceable assignment, but is unsuitable for directly representing fan-out without redesigning the mapping or relationship semantics. No transfer evidence was deleted from the event log, but a naive current-neighbor query lost the earlier branch. [World Model store](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/world-model/reference/src/store.ts)

The reference's ID matching, in-memory/JSON storage, and basic similarity methods are intentionally minimal. Use explicit source IDs, not fuzzy names, for bank accounts. The convenience `buildPromptContext()` shown in composition sketches is absent from the inspected facade; it would be application work. [Reference README](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/world-model/reference/README.md), [facade](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/world-model/reference/src/index.ts)

## Why not use H-MEM as the case database?

The reference uses a deterministic hash embedder and in-memory/JSON persistence, with selectable mining and ranked recall. These are useful demonstrations, not guaranteed transaction/account retrieval. Investigation state has exact requirements: preserve every evidence ID, frontier item, query and cutoff, not whichever records rank in top-N. [H-MEM reference](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/hmem/reference/README.md)

The actual convenience API includes `mine(event, text)` and `query(text, options)`; some cross-engine examples use different illustrative APIs. Superseded memories receive a ranking penalty rather than being categorically excluded. We should not let approximate recall choose which version of a frozen rule is active. Pin rule IDs and versions explicitly. [Facade](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/hmem/reference/src/index.ts), [retrieval](https://github.com/Meterless/Meterless/blob/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/hmem/reference/src/memoryRetrieval.ts)

If optional reusable memory is later evaluated, reset/isolate it across dataset splits. Test answers must not be written to a shared memory store and then recalled by later test cases.

## Vercel AI SDK: an available agent-loop integration

The SDK provides a real model/tool loop. Tools have input schemas and executable handlers; `ToolLoopAgent` coordinates model requests and tool results. Provider adapters permit direct model connections; provider selection is independent of Zetaris. We still implement transaction queries, case state, and evaluation. [Tool calling](https://ai-sdk.dev/docs/ai-sdk-core/tools-and-tool-calling), [provider management](https://ai-sdk.dev/docs/ai-sdk-core/provider-management)

`stopWhen` and `prepareStep` provide step limits and per-step changes. In the fetched v7 docs, a returned message override becomes the base for subsequent steps, so custom compaction can happen inside one loop. That means a second outer loop is not inherently needed. `pruneMessages` removes selected material; removal alone is not semantic evidence preservation. Preserve authoritative case state and rehydrate the needed subset. [Loop control](https://ai-sdk.dev/docs/agents/loop-control), [context compaction recipe](https://ai-sdk.dev/cookbook/guides/agent-context-compaction)

Subagents are supported through a tool that calls another agent and returns selected output. Use parallel subagents only for genuinely independent candidate investigations with isolated case state and bounded query capacity. Do not turn every SQL call into another model call. [Subagents](https://ai-sdk.dev/docs/agents/subagents)

Typed structured output is useful for candidate rules and evidence reports, but schema validity does not establish semantic validity. Reject non-existent fields, unsupported rule conditions, unknown evidence IDs, and invalid currency comparisons in application code. [Structured data](https://ai-sdk.dev/docs/ai-sdk-core/generating-structured-data)

The ordinary agent runtime is not durable on its own. The separate `@ai-sdk/workflow` integration documents resumable agent execution and workflow-backed tool steps. Evaluate that only if the deployment needs process restart recovery; a persistent case store is still necessary. Retries of writes need idempotency. [WorkflowAgent](https://ai-sdk.dev/docs/agents/workflow-agent)

## Proposed tools and state (application design)

Rule-development tools:

- `getIndicator(id)` returns the exact source excerpt and observability mapping.
- `getDataProfile(splitId)` returns allowed-column profiles and coverage, not held-out labels.
- `evaluateRuleProposal(spec, splitId)` validates a bounded rule grammar, compiles SQL, runs it, and returns evaluator-controlled development feedback.
- `compareExperiments(ids)` compares recall/precision/review burden and resource usage.
- `saveRuleCandidate(spec, evidence)` stores a versioned, reproducible candidate. Final selection/freeze occurs outside the unrestricted model loop.

Investigation tools:

- `getCase(caseId)` returns seed evidence, cutoff, known accounts, and pending questions.
- `getAccountActivity(accountKey, from, to, cursor)` and `expandNeighbors(...)` return bounded evidence, counts, and truncation/pagination metadata.
- `verifyPath(transactionIds)` checks endpoint continuity, chronology, self-transfers, and exact source existence deterministically.
- `saveFinding(caseId, claim, evidenceIds, limitations)` stores a validated record.
- `finalizeCase(caseId, recommendation)` validates required evidence and records completion or budget exhaustion separately.

The tools enforce the dataset, cutoff, label exclusion and query budget. Agent prompts explain those constraints but are not their enforcement mechanism. The evidence table retains all returned transaction IDs; the model receives compact summaries plus selected rows and can page for more. Omitting an edge due to a row cap must remain visible.

A case record should include request range/cutoff, frozen rule version, source file/version, seed evidence, discovered accounts and entities, transaction IDs, query history, frontier, findings with sources, alternatives/unresolved questions, budget counters, and explicit status. A checkpoint is a compact rendering of this record, not the only copy of it.

## Framework evaluation gate

First run the same case tools, model, seeds and budgets using an ordinary SDK loop. If context growth is observed, compare:

1. Full-history baseline with bounded results.
2. SDK loop with structured-state rehydration/compaction.
3. Markovian-wrapped loop using the same state and tool contracts.

Measure evidence retention, missed frontier items, invalid/repeated queries, correctness of final claims, actual token usage and time. Select Markovian only if it improves those outcomes enough to justify the extra adapter and maintenance. Do not tune any option against final test labels.
