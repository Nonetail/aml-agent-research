# NVIDIA Ultra: 38- and 100-row mini-evaluation

Recorded attempts: 6/6. Model requested: `nvidia/nemotron-3-ultra-550b-a55b`; thinking requested on; temperature zero. The initial output ceiling is 8,192 tokens; a separately selected 100-row diagnostic uses 16,384 tokens and a 240-second timeout.

Among 3 scored responses, the reference target was recovered in 3; the complete cycle set was recovered in 1. Invalid cycle claims: 0.

| Rows | Output cap | Repeat | Result | Cycles found | Reference found | Invalid claims | Input tokens | Output tokens | Seconds |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 38 | 8192 | 1 | received | 6/6 | 1/1 | 0 | 4971 | 7127 | 60.3 |
| 38 | 8192 | 2 | received | 4/6 | 1/1 | 0 | 4971 | 7138 | 56.5 |
| 100 | 8192 | 1 | unscorable_response | unavailable | unavailable | unavailable | 9881 | 8192 | 66.1 |
| 100 | 8192 | 2 | response_unavailable | unavailable | unavailable | unavailable | unknown | unknown | 90.4 |
| 100 | 16384 | 1 | unscorable_response | unavailable | unavailable | unavailable | 9881 | 16384 | 112.2 |
| 100 | 16384 | 2 | received | 4/6 | 1/1 | 0 | 9881 | 16048 | 148.2 |

## What was tested

The larger NVIDIA model previously used in this workspace is Nemotron 3 Ultra. The user’s phrase “super one” was interpreted as this model, rather than the separate NVIDIA Super model. This experiment explicitly overrides the shared adapter’s model and thinking flag; the default for other callers remains Lightning with thinking disabled.

Initially each size uses two fresh API requests with identical messages. The first 100-row call hit its 8,192-token output limit, and the second timed out after 90 seconds. Two further fresh 100-row calls were therefore explicitly selected with a larger output allowance and timeout; these are a separate diagnostic, not pooled repetitions of the initial profile. Their messages, rows and tool schema are unchanged.

Both snapshots are nested subsets of the same constructed development pool used in previous cycle tests, shuffled by the existing fixed ID-hash ordering. These are exactly 38 and 100 rows, not the earlier 32-row input. All rows were checked against the source database. Both contain six valid two-edge cycles and the reference `T619282 → T619283`; source-based verification independently accepted every oracle path.

The fixed family-1 system instructions, CSV columns and response schema are reused. Hidden labels, reference paths, expected cycle counts, prior answers and graph tools are excluded from model input. Responses are parsed as one native `assess_cycle_evidence` call and scored using the existing independent oracle. Invalid whole responses receive zero accepted recovery; raw valid claims remain in the saved scores.

[NVIDIA documents the thinking switch](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-ultra-550b-a55b). The request flag is recorded, but this does not independently establish how much reasoning the provider performed. The adapter stores final messages and usage, excluding separate reasoning text.

## Accounting and limits

Known provider usage: 39,585 input + 54,889 output = 94,474 total tokens. Attempts with unknown usage: 1. Account dollar tariff is unavailable; no zero-cost claim is made.

Provider errors or timeouts are operational failures with no assessable detection result. They are not scored as missed cycles. No automatic retries are made. Existing started attempts are skipped to prevent replay after an unknown outcome.

This is a small test of one constructed two-edge-cycle case. It does not establish reliability at 1,500 rows, performance on three- or four-edge cycles, population accuracy, graph-image interpretation, or laundering classification. Compared with the earlier Lightning test, model, thinking flag, output allowance and row count changed together. Results cannot isolate any one change.

## Evidence and reproduction

- [Protocol, configuration and request hashes](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/protocol.json)
- [Post-screen output-budget/timeout diagnostic protocol](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/extended-protocol.json)
- [Machine-readable results and usage](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/results.json)

- [38 rows, repeat 1: result](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/rows-38-r1/result.json)
- [38 rows, repeat 2: result](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/rows-38-r2/result.json)
- [100 rows, repeat 1: result](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/rows-100-r1/result.json)
- [100 rows, repeat 2: result](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/rows-100-r2/result.json)
- [100 rows, repeat 1: result](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/rows-100-extended-r1/result.json)
- [100 rows, repeat 2: result](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/rows-100-extended-r2/result.json)

Offline report regeneration:

```sh
python3 experiments/2026-10-24-cycle-context/report_nvidia_ultra_mini.py
```

Live execution uses `run_nvidia_ultra_mini.py run`; the separate diagnostic uses `run_nvidia_ultra_mini_extended.py`. Both skip recorded attempts. `prepare` refuses to overwrite an existing experiment. The original full-source run remains paused.
