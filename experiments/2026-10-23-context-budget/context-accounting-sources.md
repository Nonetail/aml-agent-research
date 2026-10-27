# Context accounting: verified sources and budgeting assumptions

Snapshot date: **2026-10-23**. Official OpenAI documentation was searched and fetched through the OpenAI Docs connector. Research papers were opened at their primary publication pages. No inference calls, token-count API calls, or data uploads were made for this source review.

## What “120k” means

**120,000 tokens is a proposed operating threshold to evaluate, not a verified universal “smart zone.”** The sources below do not establish that threshold for AML reasoning or an unspecified model.

Keep two possible interpretations separate:

1. **Combined-request cap:** 120k covers input plus the tokens generated during the request, including reasoning where applicable. Output and reasoning reserves reduce the space available for transactions.
2. **Input-only cap:** 120k limits the input presented to the model. Generation still needs separate room inside the model's hard context window. This interpretation is feasible only if the selected model and configuration permit the resulting combined total.

These are planning assumptions, not interchangeable definitions of the model's advertised context window.

## Planning formula

Define:

| Symbol | Meaning |
| --- | --- |
| `C` | Selected model snapshot's hard context-window limit |
| `D` | Serialized transaction and graph evidence tokens |
| `F` | System/developer instructions, rules, schema descriptions, tool definitions, and request-formatting overhead |
| `H` | Retained history already present, including any retained reasoning represented in the actual context |
| `E` | Allowance for additional retained tool results and intermediate messages before the next context refresh |
| `O` | Reserve for the next request's generated tokens: visible output, reasoning, and relevant non-visible formatting |
| `M` | Operational headroom |

For **120k combined**:

```text
D_max = max(0, min(C, 120000) - F - H - E - O - M)
```

For **120k input-only**:

```text
D_max = max(0, min(120000, C - O) - F - H - E - M)
```

These are conservative engineering formulas, not vendor formulas or quality guarantees. The generation reserve must also respect the model's separate output limit. For one call, `E = 0`. In an agent loop, re-count the actual complete input before every call; once anticipated growth is in `H`, do not count that same material again in `E`. Reserve `O` for the next generation, rather than summing unused maximum output allowances from every previous call. Only content retained for subsequent calls contributes to subsequent input.

If `O` is an API output cap that already includes reasoning, **do not subtract another reasoning reserve**. An empirically estimated reserve is useful for planning but does not enforce an upper bound; the request's configured generation limit and remaining context determine that bound.

## Verified primary sources

### OpenAI: context-window definition

[Conversation state — Managing the context window](https://developers.openai.com/api/docs/guides/conversation-state#managing-the-context-window)

OpenAI describes context capacity per request as including input, output, and reasoning tokens. The output-token limit is a separate model constraint. Large prompts can leave insufficient room for completion. Model-specific limits must be checked for the chosen snapshot. This supports reserving generation space rather than assigning the full combined cap to transaction input.

### OpenAI: reasoning and generation accounting

[Reasoning models](https://developers.openai.com/api/docs/guides/reasoning)

Reasoning uses context even though its raw text is not exposed. `max_output_tokens` covers reasoning, visible output, and non-visible formatting. Exhausting generation or context capacity can yield an incomplete response before visible text appears. The guide suggests an initial 25,000-token allowance for reasoning and outputs during experimentation, adjustable after observing usage; this is not an AML-specific requirement or guaranteed optimum.

Prior reasoning retention is model/configuration dependent. The current guide distinguishes `reasoning.context` modes `current_turn`, `all_turns`, and `auto`, with supported values and defaults varying by model. Compatible reasoning can remain available across calls when history is supplied. Do not assume that all earlier reasoning always disappears, or that it always persists. Preserve the required reasoning, function-call, and function-output items in a tool sequence according to the API's model-specific guidance.

### OpenAI: count the complete request

[Counting tokens](https://developers.openai.com/api/docs/guides/token-counting)

The input-count endpoint accepts request inputs including instructions, messages, tools, files, and conversations. Its count includes formatting such as message roles and boundaries that plain-text tokenization may omit. Local tokenizers are useful for plain text but do not fully account for tools, schemas, images, files, or every model-specific behavior. Use the complete intended payload for final request accounting.

Reported generated usage includes non-visible structural tokens as well as content, and can exceed the visible text count even with zero reported reasoning. Output limits cover these generated tokens. Thus local text counts should be labelled as serialization comparisons, not automatically exact request totals. Avoid converting all transaction data with a fixed characters-per-token ratio.

### Research: evidence position

[Liu et al., *Lost in the Middle: How Language Models Use Long Contexts*, TACL 2024](https://aclanthology.org/2024.tacl-1.9/)

The tested models' multi-document QA and retrieval performance depended on where relevant information appeared, often weakening in the middle. This motivates position-sensitive evaluation. Its historical model results do not establish a safe limit for a newer model or AML tasks.

### Research: retrieval is not sufficient evidence of reasoning quality

[Hsieh et al., *RULER: What's the Real Context Size of Your Long-Context Language Models?*, COLM 2024](https://arxiv.org/abs/2404.06654)

RULER tests multiple-needle retrieval, multi-hop tracing, and aggregation across lengths and complexity levels. In its evaluated models, strong simple retrieval did not prevent deterioration on harder long-context tasks. This supports testing linked evidence and aggregation rather than relying on a single-needle score. Its numerical results should not be transferred to an untested model.

### Research: spacing between several relevant facts

[Tian et al., *Distance between Relevant Information Pieces Causes Bias in Long-Context LLMs*, ACL Findings 2025](https://aclanthology.org/2025.findings-acl.28/)

LongPiBench found that several tested models were more robust to the classic middle-position problem, while distance between relevant information pieces still affected performance. This both motivates spacing-sensitive evaluation and cautions against presenting the older failure pattern as universal or immutable.

## Implications for the AML experiment

The following are engineering inferences from the accounting rules and research, not findings directly established for this dataset:

- Tokenize the exact candidate evidence formats, including realistic IDs, timestamps, amounts, field names, and text language, using the intended model's tokenizer where available.
- Account for rules, prompt text, graph descriptions, tools, history, and generation separately from transaction rows.
- Evaluate length, distractor volume, evidence location, spacing between linked transactions, hop count, and aggregation demands.
- Score recovered evidence, graph paths, and numerical answers, in addition to the written explanation.
- Establish the operating cap from measured quality on representative AML cases; a request fitting inside the hard context limit is only a capacity check.

This note recommends no specific model. API accounting details must be rechecked if the provider, model snapshot, reasoning configuration, or context-management strategy changes.
