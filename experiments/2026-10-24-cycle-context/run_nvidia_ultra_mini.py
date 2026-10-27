"""Four fresh NVIDIA Ultra calls on frozen 38/100-row cycle snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'prototype/local-data'))
from cycle_context_eval import request_for, ordered, extract_answer
from cycle_context_scoring import score_answer, oracle_cycles
from cycle_tools import CycleTools
from model import Model, ENDPOINT

SOURCE = ROOT / 'prototype/local-data/generated/cycle-context-v1'
OUT = ROOT / 'prototype/local-data/generated/cycle-context-nvidia-ultra-mini-v1'
MODEL = 'nvidia/nemotron-3-ultra-550b-a55b'


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def prepare():
    OUT.mkdir(exist_ok=False)
    pool = json.loads((SOURCE / 'runtime/dev-2.json').read_text())
    gold = json.loads((SOURCE / 'evaluator/dev-2.json').read_text())
    verifier = CycleTools(ROOT / 'prototype/local-data/generated/transactions.sqlite',
                          '2022/09/01 00:00', '2022/09/19 00:00')
    jobs = []
    for size in (38, 100):
        rows = ordered(pool[:size])
        canonical = [verifier.sha + ':' + r['transaction_id'][1:] for r in rows]
        source = verifier.get_transactions(canonical)
        assert not source['unavailable_ids']
        assert all(v == actual[k] for row, actual in zip(rows, source['rows'])
                   for k, v in row.items() if k != 'transaction_id')
        oracle = oracle_cycles(rows)
        assert all(verifier.verify_cycle([verifier.sha + ':' + i[1:] for i in path])['valid']
                   for path in oracle)
        request = request_for(rows, verifier.sha)
        request.update(model=MODEL, max_tokens=8192, chat_template_kwargs={'enable_thinking': True})
        for repetition in (1, 2):
            name = f'rows-{size}-r{repetition}'
            directory = OUT / name
            directory.mkdir()
            save(directory / 'request.json', request)
            save(directory / 'evaluator.json', {'rows': rows, 'targets': gold['targets'],
                 'labels': gold['labels'], 'oracle_cycles': oracle, 'source_field_mismatches': 0})
            jobs.append({'id': name, 'rows': size, 'repetition': repetition,
                         'request_sha256': hashlib.sha256((directory / 'request.json').read_bytes()).hexdigest()})
    verifier.close()
    save(OUT / 'protocol.json', {
        'model_requested': MODEL, 'endpoint': ENDPOINT, 'enable_thinking_requested': True,
        'reasoning_documentation': 'https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-ultra-550b-a55b',
        'max_calls': 4, 'max_output_tokens_per_call': 8192, 'temperature': 0,
        'jobs': jobs, 'selection': 'Same constructed development case as prior tests; first 38/100 source-pool rows, then fixed ID-hash shuffle. Nested sets, not population samples.',
        'isolation': 'Fresh API messages per call; no labels, reference answers, previous responses, or graph-solving tools supplied.',
        'comparison_limits': 'Model, thinking flag and output ceiling differ from Lightning. Two repeats of one two-edge-cycle case; no population inference or laundering-classification claim.',
        'estimated_usage': 'Roughly 20,000–70,000 total tokens for four calls, depending on model tokenization and thinking; account dollar tariff unavailable.',
        'retries': 'None. Existing attempt records are skipped, including unknown-outcome attempts.',
        'source_sha256': request['messages'][1]['content'].split('"')[3],
        'system_sha256': hashlib.sha256(request['messages'][0]['content'].encode()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'adapter_sha256': hashlib.sha256((ROOT / 'prototype/local-data/model.py').read_bytes()).hexdigest(),
    })
    print(json.dumps({'prepared': len(jobs), 'model': MODEL, 'sizes': [38, 100]}), flush=True)


def run():
    protocol = json.loads((OUT / 'protocol.json').read_text())
    client = Model()
    for job in protocol['jobs']:
        directory = OUT / job['id']
        if (directory / 'attempt.json').exists():
            continue
        assert hashlib.sha256((directory / 'request.json').read_bytes()).hexdigest() == job['request_sha256']
        request = json.loads((directory / 'request.json').read_text())
        evaluator = json.loads((directory / 'evaluator.json').read_text())
        save(directory / 'attempt.json', {'status': 'started', 'started_unix': time.time(), 'usage': None})
        started = time.monotonic()
        result = dict(job)
        try:
            response = client.complete(request['messages'], request['tools'], request['tool_choice'],
                request['max_tokens'], model_name=request['model'],
                enable_thinking=request['chat_template_kwargs']['enable_thinking'])
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'run'))
    args = parser.parse_args()
    prepare() if args.mode == 'prepare' else run()
