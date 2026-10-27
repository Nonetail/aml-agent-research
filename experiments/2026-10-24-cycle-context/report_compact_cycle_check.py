"""Score the saved compact control and report results without model calls."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'prototype/local-data'))
from cycle_context_scoring import oracle_cycles
from cycle_detection import validate_matches
from cycle_tools import CycleTools

OUT = ROOT / 'prototype/local-data/generated/cycle-context-compact-v1'
evaluator = json.loads((OUT / 'evaluator.json').read_text())
request = json.loads((OUT / 'request.json').read_text())
protocol = json.loads((OUT / 'sol-medium-protocol.json').read_text())
packet_path = OUT / 'sol-medium-packet.json'
assert hashlib.sha256(packet_path.read_bytes()).hexdigest() == protocol['packet_sha256']
packet = json.loads(packet_path.read_text())
assert packet['messages'] == request['messages']
assert packet['tools'] == request['tools']
assert packet['tool_choice'] == request['tool_choice']
metadata = json.loads(request['messages'][1]['content'].split('\n', 1)[0])
oracle = set(map(tuple, oracle_cycles(evaluator['rows'])))
targets = set(map(tuple, evaluator['targets']))
answer_path = OUT / 'sol-medium-response.json'
answer = json.loads(answer_path.read_text())
verifier = CycleTools(ROOT / 'prototype/local-data/generated/transactions.sqlite',
                      metadata['start'], metadata['end'], metadata['max_edges'], metadata['max_duration_minutes'])
try:
    checked = validate_matches(answer, [r['transaction_id'] for r in evaluator['rows']],
        lambda ids: verifier.verify_cycle([verifier.sha + ':' + ident[1:] for ident in ids]))
finally:
    verifier.close()
found = {tuple(m['transaction_ids']) for m in answer['matches']}
sol = {'model': protocol['model'], 'reasoning_effort': protocol['reasoning_effort'],
       'contract_valid': True, 'oracle_cycle_count': len(oracle), 'cycles_found': len(found & oracle),
       'target_count': len(targets), 'target_found': len(found & targets),
       'invalid_claims': len(found - oracle), 'usage': None,
       'confidence_percent': [m['confidence_percent'] for m in answer['matches']],
       'answer_characters': len(json.dumps(answer, separators=(',', ':'))),
       'response_sha256': hashlib.sha256(answer_path.read_bytes()).hexdigest(),
       'verification': checked}
(OUT / 'sol-medium-result.json').write_text(json.dumps(sol, indent=2) + '\n')
nvidia = [json.loads((OUT / f'run-{i}/result.json').read_text()) for i in (1, 2)]
lines = ['# Compact cycle matches with confidence', '',
    'The new detector returns only ordered transaction IDs and an integer confidence percentage. Confidence means the model’s uncalibrated estimate that the listed transactions satisfy the cycle rule. Code independently verifies the complete path; confidence cannot override a failed check.', '',
    '```json', json.dumps({'matches': answer['matches'][:1]}, separators=(',', ':')), '```', '',
    '## Same 100-row case', '',
    '| Model / setting | Run | Cycles found | Reference found | Invalid claims | Final JSON characters | Seconds |',
    '|---|---:|---:|---:|---:|---:|---:|']
for r in nvidia:
    lines.append(f"| NVIDIA Ultra / thinking off | {r['repetition']} | {r['cycles_found']}/{r['oracle_cycle_count']} | {r['target_found']}/{r['target_count']} | {r['invalid_claims']} | {r['answer_characters']} | {r['seconds']:.2f} |")
lines.append(f"| GPT-6 Sol / medium | 1 | {sol['cycles_found']}/{sol['oracle_cycle_count']} | {sol['target_found']}/{sol['target_count']} | {sol['invalid_claims']} | {sol['answer_characters']} | unavailable |")
lines += ['', 'Both NVIDIA responses passed the format checks but returned an empty matches list. An empty list establishes no search coverage. The Sol response passed the schema and independent source verification. Its reported confidence percentages are self-estimates, not measured accuracy.', '',
    '## Enforcement and scope', '',
    '- `prototype/local-data/cycle_detection.py` supplies the compact system prompt, named function schema, and host validation. Extra fields, explanations, unknown IDs, duplicate matches, invalid paths and incomplete responses are rejected.',
    '- This experimental profile permits at most eight matches, with two to four transaction IDs per match. Reaching eight is flagged. No answer establishes exhaustive coverage.',
    '- The NVIDIA request profile uses a 1,024-token generation cap and thinking off. That setting is recorded for this experiment; the empty results do not support adopting it as a reliable detector.',
    '- A short final answer and internal reasoning are separate controls. Sol retained medium reasoning while producing compact JSON. Its subagent interface does not expose provider token usage or enforce the NVIDIA generation cap.',
    '- This adds a separate compact detector contract and evaluation runner. The existing economic-review workflow has not been migrated.', '',
    '## Evaluation limits and accounting', '',
    'The exact previous 100-row evidence was reused without labels or reference answers. The source oracle contains six two-edge cycles. Sol used one fresh isolated subagent, selected after the NVIDIA empty responses. It read the blind packet and wrote its answer; graph-search code was prohibited. Native function calling is emulated by final JSON arguments in that runtime. This is one constructed case, not population accuracy or a test of three- and four-edge paths.', '',
    'Compared with the previous verbose contract, this changes the system prompt, schema, match cap and generation budget. It is not a response-format-only ablation. There were two NVIDIA calls with no hidden retries and one Sol subject.', '',
    f"Known NVIDIA usage: {sum(r['usage']['total_tokens'] for r in nvidia):,} tokens. Sol usage and dollar costs are unavailable. No claim of zero cost is made.", '',
    '## Saved evidence', '',
    '- [Exact NVIDIA request](../../prototype/local-data/generated/cycle-context-compact-v1/request.json) and [protocol](../../prototype/local-data/generated/cycle-context-compact-v1/protocol.json)',
    '- [Sol blind protocol](../../prototype/local-data/generated/cycle-context-compact-v1/sol-medium-protocol.json), [answer](../../prototype/local-data/generated/cycle-context-compact-v1/sol-medium-response.json), and [verified result](../../prototype/local-data/generated/cycle-context-compact-v1/sol-medium-result.json)', '',
    'Recompute the saved-result report without hosted calls:', '',
    '```sh', 'python3 experiments/2026-10-24-cycle-context/report_compact_cycle_check.py', '```', '']
Path(__file__).with_name('COMPACT-CYCLE-DETECTION.md').write_text('\n'.join(lines))
print(json.dumps({k: v for k, v in sol.items() if k != 'verification'}, indent=2))
