"""Separate, post-screen 100-row output-budget/timeout diagnostic; two calls."""
import hashlib
import json
from pathlib import Path
import time

from run_nvidia_ultra_mini import OUT, ROOT, MODEL, Model, save, extract_answer, score_answer

protocol_path = OUT / 'extended-protocol.json'
if not protocol_path.exists():
    jobs = []
    for repetition in (1, 2):
        source = OUT / f'rows-100-r{repetition}'
        prior = json.loads((source / 'result.json').read_text())
        assert prior['status'] in ('unscorable_response', 'response_unavailable')
        directory = OUT / f'rows-100-extended-r{repetition}'
        directory.mkdir(exist_ok=False)
        request = json.loads((source / 'request.json').read_text())
        request['max_tokens'] = 16384
        save(directory / 'request.json', request)
        (directory / 'evaluator.json').write_bytes((source / 'evaluator.json').read_bytes())
        jobs.append({'id': directory.name, 'rows': 100, 'repetition': repetition,
                     'request_sha256': hashlib.sha256((directory / 'request.json').read_bytes()).hexdigest()})
    save(protocol_path, {'selection': 'Post-screen diagnostic after 100-row truncation and timeout. Not pooled with original 8192-token arm.',
        'jobs': jobs, 'max_calls': 2, 'max_output_tokens_per_call': 16384, 'timeout_seconds': 240,
        'model_requested': MODEL, 'enable_thinking_requested': True,
        'planned_token_allowance': 'Approximately 52000 additional input/output tokens; unknown usage on earlier timeout remains separate.',
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'adapter_sha256': hashlib.sha256((ROOT / 'prototype/local-data/model.py').read_bytes()).hexdigest()})

protocol = json.loads(protocol_path.read_text())
client = Model()
for job in protocol['jobs']:
    directory = OUT / job['id']
    if (directory / 'attempt.json').exists():
        continue
    assert hashlib.sha256((directory / 'request.json').read_bytes()).hexdigest() == job['request_sha256']
    request = json.loads((directory / 'request.json').read_text())
    evaluator = json.loads((directory / 'evaluator.json').read_text())
    save(directory / 'attempt.json', {'status': 'started', 'started_unix': time.time(), 'usage': None})
    result = dict(job, output_cap=16384, timeout_seconds=240)
    started = time.monotonic()
    try:
        response = client.complete(request['messages'], request['tools'], request['tool_choice'],
            request['max_tokens'], model_name=request['model'], enable_thinking=True, timeout=240)
        save(directory / 'response.json', response)
        result.update(status='received', usage=response['usage'], model_returned=response['model'],
                      finish_reason=response['finish_reason'])
        try:
            answer = extract_answer(response)
            save(directory / 'answer.json', answer)
            result['score'] = score_answer(evaluator['rows'], answer, evaluator['targets'], evaluator['labels'])
        except (ValueError, KeyError, TypeError) as error:
            result.update(status='unscorable_response', error=str(error))
    except Exception as error:
        result.update(status='response_unavailable', error_type=type(error).__name__,
                      http_status=getattr(error, 'status', None), usage=None)
    result['seconds'] = time.monotonic() - started
    save(directory / 'result.json', result)
    save(directory / 'attempt.json', {'status': 'finished', 'result': 'result.json'})
    score = result.get('score', {})
    print(json.dumps({'id': job['id'], 'status': result['status'], 'model': result.get('model_returned'),
                      'cycles': score.get('structural_recovered'), 'oracle': score.get('oracle_cycle_count'),
                      'target': score.get('target_recovered'), 'invalid': score.get('invalid_true_claims'),
                      'usage': result.get('usage'), 'seconds': result['seconds']}), flush=True)
