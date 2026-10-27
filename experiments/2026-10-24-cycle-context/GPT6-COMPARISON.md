# GPT-6 Ultra: exact 32-row replication

Completed 24 October 2026. Both isolated GPT-6 subagents with ultra reasoning recovered the reference cycle and all six valid structural cycles in the same 32-row packet that the earlier Nemotron configuration failed.

| Configuration | Repetition | Valid cycles recovered | Reference recovered | Invalid cycle claims |
|---|---:|---:|---:|---:|
| Nemotron 3.5 Lightning, thinking disabled | 1 | 0/6 | 0/1 | 1 |
| Nemotron 3.5 Lightning, thinking disabled | 2 | 0/6 | 0/1 | 1 |
| GPT-6 (`gpt-6-sol`), ultra reasoning | 1 | 6/6 | 1/1 | 0 |
| GPT-6 (`gpt-6-sol`), ultra reasoning | 2 | 6/6 | 1/1 | 0 |

## What was held constant

The supplied system instructions, user evidence, transaction order and function schema were copied exactly from `dev-2--single-32--r1/request.json`. All 32 rows were checked against the source-backed runtime data, with no field mismatches. The family rule explicitly specifies simple, strictly chronological, two-to-four-edge return cycles using exact bank/account identities, excluding self-transfers. Neither subject received hidden labels, expected paths, expected cycle counts or previous responses.

Each subagent started with `fork_turns="none"`. Its wrapper allowed reading only the blind packet and prohibited graph-solving code, other files, browsing and communication. The requested model setting was `gpt-6-sol` with `reasoning_effort="ultra"`; this is a Codex subagent run, not a test of the ChatGPT user interface.

## Exact result

Both responses returned these six ordered supports, all accepted by the existing deterministic scorer:

- `T619281 → T619283`
- `T619282 → T619283` — the hidden reference target
- `T619281 → T887448`
- `T619282 → T887448`
- `T619283 → T1229276`
- `T887448 → T1229276`

The reference is `T619282`, 1 September 2022 at 09:06, from `(15231, 80266F880)` to `(23691, 8021353D0)`, followed by `T619283` at 11:02 in the reverse direction. Both models found that return structure. Both assigned this particular observation `insufficient_evidence` for the economic assessment: detecting the cycle does not establish laundering. Rationale quality and laundering classification were not validated by this structural score.

## What this establishes

The earlier miss is specific to the tested configuration; it does not demonstrate that 32 rows are inherently too difficult for a model. GPT-6 with ultra reasoning succeeded twice on this case. These are two repetitions of one packet, not two independent cases, and provide no measured operating boundary at 1,500 rows or estimate of population precision/recall.

The comparison changes model, reasoning settings and runtime together. The prior API run used native function forcing and a fixed output limit. The subagents received the same task instructions inside a file, alongside ambient runtime instructions, and returned JSON rather than making the native function call. Output limits were not matched. Provider token counts and dollar cost are unavailable through the subagent interface; unknown usage is not zero usage.

## Saved evidence

- [Protocol and input hashes](../../prototype/local-data/generated/cycle-context-gpt6-ultra-v1/protocol.json)
- [Exact blind packet](../../prototype/local-data/generated/cycle-context-gpt6-ultra-v1/packet.json)
- [Evaluator, parsed rows and oracle](../../prototype/local-data/generated/cycle-context-gpt6-ultra-v1/evaluator.json)
- [Results](../../prototype/local-data/generated/cycle-context-gpt6-ultra-v1/results.json)
- [Run 1 response](../../prototype/local-data/generated/cycle-context-gpt6-ultra-v1/run-1-response.json) and [score](../../prototype/local-data/generated/cycle-context-gpt6-ultra-v1/run-1-score.json)
- [Run 2 response](../../prototype/local-data/generated/cycle-context-gpt6-ultra-v1/run-2-response.json) and [score](../../prototype/local-data/generated/cycle-context-gpt6-ultra-v1/run-2-score.json)
- [Prior Nemotron run 1](../../prototype/local-data/generated/cycle-context-v1/calls/dev-2--single-32--r1/result.json) and [run 2](../../prototype/local-data/generated/cycle-context-v1/calls/dev-2--single-32--r2/result.json)

Subjects: `/root/blind_gpt6_ultra_1` and `/root/blind_gpt6_ultra_2`. The original NVIDIA results remain unchanged.
