"""Two fresh calls changing only enable_thinking in the original 100-row request."""
import hashlib
import json
from pathlib import Path
import time

from run_nvidia_ultra_mini import OUT, ROOT, Model, save, extract_answer, score_answer

DEST = ROOT / 'prototype/local-data/generated/cycle-context-nvidia-thinking-off-v1'
if not DEST.exists():
    DEST.mkdir()
    jobs = []
    for repetition in (1, 2):
        source = OUT / f'rows-100-r{repetition}'
        directory = DEST / f'rows-100-r{repetition}'
        directory.mkdir()
        original = json.loads((source / 'request.json').read_text())
        request = json.loads(json.dumps(original))
        request['chat_template_kwargs']['enable_thinking'] = False
        assert {k:v for k,v in original.items() if k!='chat_template_kwargs'} == {
            k:v for k,v in request.items() if k!='chat_template_kwargs'}
        save(directory / 'request.json', request)
        (directory / 'evaluator.json').write_bytes((source / 'evaluator.json').read_bytes())
        jobs.append({'id': directory.name, 'repetition': repetition,
                     'request_sha256': hashlib.sha256((directory / 'request.json').read_bytes()).hexdigest()})
    save(DEST / 'protocol.json', {'purpose': 'Post-hoc thinking-flag ablation after truncations and timeout.',
        'jobs': jobs, 'model': original['model'], 'enable_thinking': False,
        'max_tokens': original['max_tokens'], 'timeout_seconds': 90, 'max_calls': 2,
        'changed_request_fields': ['chat_template_kwargs.enable_thinking'],
        'limits': 'Historical thinking-on comparator; no randomization or backend-version visibility. Cannot establish provider parser bug.',
        'estimated_token_allowance': 'Approximately 36000 additional input/output tokens; dollar tariff unavailable.',
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'adapter_sha256': hashlib.sha256((ROOT / 'prototype/local-data/model.py').read_bytes()).hexdigest()})

protocol = json.loads((DEST / 'protocol.json').read_text())
client = Model()
for job in protocol['jobs']:
    directory = DEST / job['id']
    if (directory / 'attempt.json').exists():
        continue
    assert hashlib.sha256((directory / 'request.json').read_bytes()).hexdigest() == job['request_sha256']
    request = json.loads((directory / 'request.json').read_text())
    evaluator = json.loads((directory / 'evaluator.json').read_text())
    save(directory / 'attempt.json', {'status': 'started', 'started_unix': time.time(), 'usage': None})
    result = dict(job)
    start = time.monotonic()
    try:
        response = client.complete(request['messages'], request['tools'], request['tool_choice'],
            request['max_tokens'], model_name=request['model'], enable_thinking=False, timeout=90)
        save(directory / 'response.json', response)
        result.update(status='received', model=response['model'], usage=response['usage'],
                      finish_reason=response['finish_reason'])
        try:
            answer = extract_answer(response)
            save(directory / 'answer.json', answer)
            result['score'] = score_answer(evaluator['rows'], answer, evaluator['targets'], evaluator['labels'])
        except (ValueError, TypeError, KeyError) as error:
            result.update(status='unscorable_response', error=str(error))
    except Exception as error:
        result.update(status='response_unavailable', error_type=type(error).__name__,
                      http_status=getattr(error, 'status', None), usage=None)
    result['seconds'] = time.monotonic() - start
    save(directory / 'result.json', result)
    save(directory / 'attempt.json', {'status': 'finished', 'result': 'result.json'})
    score = result.get('score', {})
    print(json.dumps({'id': job['id'], 'status': result['status'], 'seconds': result['seconds'],
        'cycles_found': score.get('structural_recovered'), 'target_found': score.get('target_recovered'),
        'invalid_claims': score.get('invalid_true_claims'), 'usage': result.get('usage')}), flush=True)
