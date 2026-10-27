# GPT-6 medium: 1,500-row evaluation

The two 1,500-row runs recovered 4 and 6 of 6 structural cycles, with 0 invalid claims. The incomplete recovery triggered the predeclared grouping comparison. Every grouped repetition recovered all six cycles with no invalid claims. Two groups matched three and four groups on this case while requiring fewer calls.

The reference is the return from account `(15231, 80266F880)` to `(23691, 8021353D0)` at 09:06 on 1 September 2022, followed by the reverse transaction at 11:02: `T619282 → T619283`. Hidden reference IDs and laundering labels were available only to the scorer.

| Condition | Repeat | Completed views | Rows per view | Structural recovery | Reference recovery | Invalid claims |
|---|---:|---:|---|---:|---:|---:|
| single-1500 | 1 | 1/1 | 1500 | 4/6 | 1/1 | 0 |
| single-1500 | 2 | 1/1 | 1500 | 6/6 | 1/1 | 0 |
| graph-2 | 1 | 2/2 | 750, 750 | 6/6 | 1/1 | 0 |
| graph-2 | 2 | 2/2 | 750, 750 | 6/6 | 1/1 | 0 |
| graph-3 | 1 | 3/3 | 500, 500, 500 | 6/6 | 1/1 | 0 |
| graph-3 | 2 | 3/3 | 500, 500, 500 | 6/6 | 1/1 | 0 |
| graph-4 | 1 | 4/4 | 376, 375, 375, 374 | 6/6 | 1/1 | 0 |
| graph-4 | 2 | 4/4 | 376, 375, 375, 374 | 6/6 | 1/1 | 0 |

Structural recovery uses the original 1,500-row denominator, deduplicated across views. Raw valid paths are also saved separately from whole-response acceptance.

## Design and controls

Requested model: `gpt-6-sol`, reasoning `medium`, fresh subagents with `fork_turns="none"`. Two repetitions use identical input. These are repeats of one constructed case, not independent source cases. The baseline contains 1,500 exact source transactions, including six qualifying structural cycles. All source fields were audited and all six oracle paths were independently verified with the runtime verifier.

The supplied task system instructions, CSV evidence and function schema reuse the saved Nemotron requests. No expected paths, cycle counts, labels, other agents’ answers or conversation history are supplied. Subjects are instructed to read only their assigned packet, solve with model reasoning, and write only their response; code-based graph search is prohibited.

To avoid tool-output truncation, each view is delivered as instructions plus consecutive files of up to 150 rows. These are transport chunks retained in one agent context, not independently evaluated groups. Subjects must read the whole view before answering. This transport differs from the original one-message API call.

The existing graph partitioner uses ordinary account connectivity and keeps source-account bundles together, without hidden labels or known paths. Each split covers the same 1,500 unique rows exactly once. In this case all six cycles and the reference remain wholly visible under every split. Grouping changes row ordering as well as view size; those effects are not isolated.

## Conditional grouping

Grouping is triggered if either completed baseline is not structurally exact, misses the reference, or makes invalid claims. Each group is examined by a separate fresh agent, with two repetitions per policy. Incomplete arms remain inconclusive.

## Economic assessment, reported separately

| Condition | Repeat | Assessment of the reference cycle |
|---|---:|---|
| single-1500 | 1 | insufficient_evidence |
| single-1500 | 2 | insufficient_evidence |
| graph-2 | 1 | investigate |
| graph-2 | 2 | investigate |
| graph-3 | 1 | insufficient_evidence |
| graph-3 | 2 | insufficient_evidence |
| graph-4 | 1 | insufficient_evidence |
| graph-4 | 2 | insufficient_evidence |

These statuses are model judgments, not validated laundering predictions. Changes in assessment with grouping should be calibrated separately from structural discovery.

## Interpretation and accounting

Cycle detection is separate from laundering classification. A recovered reference with `insufficient_evidence` still counts as a structural detection. Free-text economic reasoning is not certified by this scorer. All six cycles in this case have two edges; three- and four-edge detection remains untested by this run. This case does not estimate population precision/recall, establish a universal 1,500-row boundary, or test graph screenshots and autonomous navigation.

The baseline CSV request previously consumed 121,913 input tokens under the Nemotron tokenizer/provider. That is a historical reference, not a GPT-6 token count. Provider tokens, reasoning tokens, output limits and dollar tariff are unavailable through the subagent interface. No zero-cost claim is made. The subagent runtime has ambient instructions and returns JSON instead of a natively forced function call.

Saved responses: 20. Planned maximum: 20 subjects. Original baselines and paused full-source runs are unchanged.

## Evidence and reproduction

- [Machine-readable results](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/results.json)
- [Frozen protocol, exact packet hashes and input files](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/protocol.json)
- [Source audit](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/input-audit.json)
- [Results audit](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/results-audit.json) and [subject execution record](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/execution.json)
- [Baseline response 1](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/single-1500-p0/run-1-response.json)
- [Baseline response 2](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/single-1500-p0/run-2-response.json)

Recompute scores and this report without model calls:

```sh
python3 experiments/2026-10-24-cycle-context/score_gpt6_medium.py
```
