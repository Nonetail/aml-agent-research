# Compact cycle matches with confidence

The new detector returns only ordered transaction IDs and an integer confidence percentage. Confidence means the model’s uncalibrated estimate that the listed transactions satisfy the cycle rule. Code independently verifies the complete path; confidence cannot override a failed check.

```json
{"matches":[{"transaction_ids":["T619281","T619283"],"confidence_percent":100}]}
```

## Same 100-row case

| Model / setting | Run | Cycles found | Reference found | Invalid claims | Final JSON characters | Seconds |
|---|---:|---:|---:|---:|---:|---:|
| NVIDIA Ultra / thinking off | 1 | 0/6 | 0/1 | 0 | 14 | 1.59 |
| NVIDIA Ultra / thinking off | 2 | 0/6 | 0/1 | 0 | 14 | 1.06 |
| GPT-6 Sol / medium | 1 | 6/6 | 1/1 | 0 | 417 | unavailable |

Both NVIDIA responses passed the format checks but returned an empty matches list. An empty list establishes no search coverage. The Sol response passed the schema and independent source verification. Its reported confidence percentages are self-estimates, not measured accuracy.

## Enforcement and scope

- `prototype/local-data/cycle_detection.py` supplies the compact system prompt, named function schema, and host validation. Extra fields, explanations, unknown IDs, duplicate matches, invalid paths and incomplete responses are rejected.
- This experimental profile permits at most eight matches, with two to four transaction IDs per match. Reaching eight is flagged. No answer establishes exhaustive coverage.
- The NVIDIA request profile uses a 1,024-token generation cap and thinking off. That setting is recorded for this experiment; the empty results do not support adopting it as a reliable detector.
- A short final answer and internal reasoning are separate controls. Sol retained medium reasoning while producing compact JSON. Its subagent interface does not expose provider token usage or enforce the NVIDIA generation cap.
- This adds a separate compact detector contract and evaluation runner. The existing economic-review workflow has not been migrated.

## Evaluation limits and accounting

The exact previous 100-row evidence was reused without labels or reference answers. The source oracle contains six two-edge cycles. Sol used one fresh isolated subagent, selected after the NVIDIA empty responses. It read the blind packet and wrote its answer; graph-search code was prohibited. Native function calling is emulated by final JSON arguments in that runtime. This is one constructed case, not population accuracy or a test of three- and four-edge paths.

Compared with the previous verbose contract, this changes the system prompt, schema, match cap and generation budget. It is not a response-format-only ablation. There were two NVIDIA calls with no hidden retries and one Sol subject.

Known NVIDIA usage: 17,652 tokens. Sol usage and dollar costs are unavailable. No claim of zero cost is made.

## Saved evidence

- [Exact NVIDIA request](../../prototype/local-data/generated/cycle-context-compact-v1/request.json) and [protocol](../../prototype/local-data/generated/cycle-context-compact-v1/protocol.json)
- [Sol blind protocol](../../prototype/local-data/generated/cycle-context-compact-v1/sol-medium-protocol.json), [answer](../../prototype/local-data/generated/cycle-context-compact-v1/sol-medium-response.json), and [verified result](../../prototype/local-data/generated/cycle-context-compact-v1/sol-medium-result.json)

Recompute the saved-result report without hosted calls:

```sh
python3 experiments/2026-10-24-cycle-context/report_compact_cycle_check.py
```
