"""Render the mini-evaluation from saved evidence without model calls."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1'
protocol = json.loads((OUT / 'protocol.json').read_text())
jobs = list(protocol['jobs'])
extended_path = OUT / 'extended-protocol.json'
if extended_path.exists():
    jobs += json.loads(extended_path.read_text())['jobs']
records = []
for job in jobs:
    result = OUT / job['id'] / 'result.json'
    if result.exists():
        records.append(json.loads(result.read_text()))
usage = {key: sum((r.get('usage') or {}).get(key, 0) or 0 for r in records)
         for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
unknown_usage = sum(r.get('usage') is None for r in records)
summary = {'model_requested': protocol['model_requested'], 'thinking_requested': True,
           'records': records, 'known_usage': usage, 'unknown_usage_attempts': unknown_usage,
           'planned_calls': len(jobs), 'completed_attempts': len(records), 'dollar_cost': None}
(OUT / 'results.json').write_text(json.dumps(summary, indent=2) + '\n')
scored = [r['score'] for r in records if 'score' in r]
lines = ['# NVIDIA Ultra: 38- and 100-row mini-evaluation', '',
         f"Recorded attempts: {len(records)}/{len(jobs)}. Model requested: `{protocol['model_requested']}`; thinking requested on; temperature zero. The initial output ceiling is {protocol['max_output_tokens_per_call']:,} tokens; a separately selected 100-row diagnostic uses 16,384 tokens and a 240-second timeout.", '',
         f"Among {len(scored)} scored responses, the reference target was recovered in {sum(s['target_recovered'] == s['target_count'] for s in scored)}; the complete cycle set was recovered in {sum(s['structural_exact'] for s in scored)}. Invalid cycle claims: {sum(s['invalid_true_claims'] for s in scored)}.", '',
         '| Rows | Output cap | Repeat | Result | Cycles found | Reference found | Invalid claims | Input tokens | Output tokens | Seconds |',
         '|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|']
for r in records:
    s, u = r.get('score'), r.get('usage') or {}
    cycles = f"{s['structural_recovered']}/{s['oracle_cycle_count']}" if s else 'unavailable'
    target = f"{s['target_recovered']}/{s['target_count']}" if s else 'unavailable'
    invalid = s['invalid_true_claims'] if s else 'unavailable'
    lines.append(f"| {r['rows']} | {r.get('output_cap', 8192)} | {r['repetition']} | {r['status']} | {cycles} | {target} | {invalid} | {u.get('prompt_tokens', 'unknown')} | {u.get('completion_tokens', 'unknown')} | {r['seconds']:.1f} |")
lines += ['', '## What was tested', '',
          'The larger NVIDIA model previously used in this workspace is Nemotron 3 Ultra. The user’s phrase “super one” was interpreted as this model, rather than the separate NVIDIA Super model. This experiment explicitly overrides the shared adapter’s model and thinking flag; the default for other callers remains Lightning with thinking disabled.', '',
          'Initially each size uses two fresh API requests with identical messages. The first 100-row call hit its 8,192-token output limit, and the second timed out after 90 seconds. Two further fresh 100-row calls were therefore explicitly selected with a larger output allowance and timeout; these are a separate diagnostic, not pooled repetitions of the initial profile. Their messages, rows and tool schema are unchanged.', '',
          'Both snapshots are nested subsets of the same constructed development pool used in previous cycle tests, shuffled by the existing fixed ID-hash ordering. These are exactly 38 and 100 rows, not the earlier 32-row input. All rows were checked against the source database. Both contain six valid two-edge cycles and the reference `T619282 → T619283`; source-based verification independently accepted every oracle path.', '',
          'The fixed family-1 system instructions, CSV columns and response schema are reused. Hidden labels, reference paths, expected cycle counts, prior answers and graph tools are excluded from model input. Responses are parsed as one native `assess_cycle_evidence` call and scored using the existing independent oracle. Invalid whole responses receive zero accepted recovery; raw valid claims remain in the saved scores.', '',
          '[NVIDIA documents the thinking switch](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-ultra-550b-a55b). The request flag is recorded, but this does not independently establish how much reasoning the provider performed. The adapter stores final messages and usage, excluding separate reasoning text.', '',
          '## Accounting and limits', '',
          f"Known provider usage: {usage['prompt_tokens']:,} input + {usage['completion_tokens']:,} output = {usage['total_tokens']:,} total tokens. Attempts with unknown usage: {unknown_usage}. Account dollar tariff is unavailable; no zero-cost claim is made.", '',
          'Provider errors or timeouts are operational failures with no assessable detection result. They are not scored as missed cycles. No automatic retries are made. Existing started attempts are skipped to prevent replay after an unknown outcome.', '',
          'This is a small test of one constructed two-edge-cycle case. It does not establish reliability at 1,500 rows, performance on three- or four-edge cycles, population accuracy, graph-image interpretation, or laundering classification. Compared with the earlier Lightning test, model, thinking flag, output allowance and row count changed together. Results cannot isolate any one change.', '',
          '## Evidence and reproduction', '',
          '- [Protocol, configuration and request hashes](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/protocol.json)',
          '- [Post-screen output-budget/timeout diagnostic protocol](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/extended-protocol.json)',
          '- [Machine-readable results and usage](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/results.json)', '']
for r in records:
    lines.append(f"- [{r['rows']} rows, repeat {r['repetition']}: result](../../prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/{r['id']}/result.json)")
lines += ['', 'Offline report regeneration:', '', '```sh',
          'python3 experiments/2026-10-24-cycle-context/report_nvidia_ultra_mini.py', '```', '',
          'Live execution uses `run_nvidia_ultra_mini.py run`; the separate diagnostic uses `run_nvidia_ultra_mini_extended.py`. Both skip recorded attempts. `prepare` refuses to overwrite an existing experiment. The original full-source run remains paused.', '']
(Path(__file__).parent / 'NVIDIA-ULTRA-MINI.md').write_text('\n'.join(lines))
print(json.dumps({'attempts': len(records), 'known_usage': usage, 'unknown_usage_attempts': unknown_usage}))
