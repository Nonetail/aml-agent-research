"""Two fresh Ultra calls using the compact, source-verified cycle contract."""
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'prototype/local-data'))
from cycle_detection import accept_response, request_for
from cycle_context_scoring import oracle_cycles
from cycle_tools import CycleTools
from model import Model

SOURCE = ROOT / 'prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1/rows-100-r1'
OUT = ROOT / 'prototype/local-data/generated/cycle-context-compact-v1'


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


if not OUT.exists():
    OUT.mkdir()
    original = json.loads((SOURCE / 'request.json').read_text())
    request = request_for(original['messages'][1]['content'], original['model'])
    save(OUT / 'request.json', request)
    (OUT / 'evaluator.json').write_bytes((SOURCE / 'evaluator.json').read_bytes())
    save(OUT / 'protocol.json', {'model': request['model'], 'repetitions': 2,
        'reasoning_requested': False, 'max_output_tokens': request['max_tokens'], 'timeout_seconds': 90,
        'confidence_meaning': 'Uncalibrated model confidence in structural cycle match; not laundering probability.',
        'comparison_limits': 'Same 100-row evidence, but shorter detection-only system prompt, new schema, eight-match cap and lower output budget. Not a response-format-only ablation.',
        'estimated_tokens': 'Approximately 20000 or less additional tokens; dollar tariff unavailable.',
        'request_sha256': hashlib.sha256((OUT / 'request.json').read_bytes()).hexdigest(),
        'contract_sha256': hashlib.sha256((ROOT / 'prototype/local-data/cycle_detection.py').read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})

protocol = json.loads((OUT / 'protocol.json').read_text())
assert hashlib.sha256((OUT / 'request.json').read_bytes()).hexdigest() == protocol['request_sha256']
request = json.loads((OUT / 'request.json').read_text())
evaluator = json.loads((OUT / 'evaluator.json').read_text())
oracle = set(map(tuple, oracle_cycles(evaluator['rows'])))
targets = set(map(tuple, evaluator['targets']))
ids = [r['transaction_id'] for r in evaluator['rows']]
metadata = json.loads(request['messages'][1]['content'].split('\n', 1)[0])
verifier = CycleTools(ROOT / 'prototype/local-data/generated/transactions.sqlite',
                      metadata['start'], metadata['end'], metadata['max_edges'], metadata['max_duration_minutes'])


def verify(path):
    return verifier.verify_cycle([verifier.sha + ':' + ident[1:] for ident in path])


client = Model()
for repetition in (1, 2):
    directory = OUT / f'run-{repetition}'
    if directory.exists():
        continue
    directory.mkdir()
    save(directory / 'attempt.json', {'status': 'started', 'usage': None, 'started_unix': time.time()})
    result = {'repetition': repetition, 'oracle_cycle_count': len(oracle), 'target_count': len(targets)}
    started = time.monotonic()
    try:
        response = client.complete(request['messages'], request['tools'], request['tool_choice'],
            request['max_tokens'], model_name=request['model'], enable_thinking=False, timeout=90)
        save(directory / 'response.json', response)
        result.update(status='received', usage=response['usage'], finish_reason=response['finish_reason'],
                      model=response['model'])
        try:
            checked = accept_response(response, ids, verify)
            save(directory / 'verified.json', checked)
            answer = json.loads(response['message']['tool_calls'][0]['function']['arguments'])
            save(directory / 'answer.json', answer)
            found = {tuple(match['transaction_ids']) for match in answer['matches']}
            result.update(contract_valid=True, cycles_found=len(found & oracle),
                          target_found=len(found & targets), invalid_claims=len(found - oracle),
                          confidence_percent=[match['confidence_percent'] for match in answer['matches']],
                          answer_characters=len(json.dumps(answer, separators=(',', ':'))),
                          candidate_limit_reached=checked['candidate_limit_reached'])
        except (ValueError, TypeError, KeyError) as error:
            result.update(status='rejected_response', contract_valid=False, error=str(error))
    except Exception as error:
        result.update(status='response_unavailable', error_type=type(error).__name__, usage=None)
    result['seconds'] = time.monotonic() - started
    save(directory / 'result.json', result)
    save(directory / 'attempt.json', {'status': 'finished', 'result': 'result.json'})
    print(json.dumps(result), flush=True)
verifier.close()
