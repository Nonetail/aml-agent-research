"""Independently verify prepared evidence against source rows and enumerate bounded temporal cycles."""
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[1] / 'data'
truth = json.loads((ROOT / 'evaluator/truth.json').read_text())
manifest = json.loads((ROOT / 'evaluator/input-manifest.json').read_text())
for name, digest in manifest['files'].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name

expected = {}
for case in truth['cases'].values():
    for t in case['transactions']:
        expected[t['source_row_number_excluding_header']] = t['raw_row']
matched = set()
with (DATA / 'HI-Small_Trans.csv').open(newline='') as f:
    reader = csv.reader(f)
    next(reader)
    for row_number, row in enumerate(reader, 1):
        if row_number in expected:
            assert row == expected[row_number], row_number
            matched.add(row_number)
assert matched == set(expected)

account_metadata = {}
with (DATA / 'HI-Small_accounts.csv').open(newline='') as f:
    for row in csv.DictReader(f):
        account_metadata[(row['Bank ID'].lstrip('0') or '0', row['Account Number'])] = row['Entity ID']

result = {'source_rows_rechecked': len(matched), 'input_hashes_unchanged': True, 'cases': {}}
for case_id, private in truth['cases'].items():
    packet = json.loads((ROOT / 'inputs' / f'{case_id}.json').read_text())
    txs = {t['id']: t for t in packet['transactions']}
    for record in private['transactions']:
        row = record['raw_row']
        t = txs[record['id']]
        assert t['time'] == row[0]
        assert [t['amount_received'], t['received_currency'], t['amount_paid'], t['paid_currency'], t['format']] == row[5:10]
        for alias, bank, account in [(t['from'], row[1], row[2]), (t['to'], row[3], row[4])]:
            mapped = private['account_mapping'][alias]
            assert (mapped['canonical_bank'], mapped['account']) == (bank.lstrip('0') or '0', account)
            assert mapped['entity_id'] == account_metadata[(mapped['canonical_bank'], account)]
        assert record['label'] == int(row[10])
    public_entities = {a['id']: a['entity'] for a in packet['accounts']}
    private_entities = {a: v['entity_id'] for a, v in private['account_mapping'].items()}
    for a in public_entities:
        for b in public_entities:
            assert (public_entities[a] == public_entities[b]) == (private_entities[a] == private_entities[b])
    for s in packet['focus_account_statistics']:
        a = s['account']
        incoming = [t for t in txs.values() if t['to'] == a and t['from'] != a]
        outgoing = [t for t in txs.values() if t['from'] == a and t['to'] != a]
        assert s['incoming_transactions'] == len(incoming)
        assert s['outgoing_transactions'] == len(outgoing)
        assert s['distinct_senders'] == len({t['from'] for t in incoming})
        assert s['distinct_receivers'] == len({t['to'] for t in outgoing})
        assert s['self_transactions'] == sum(t['from'] == a == t['to'] for t in txs.values())

    adjacency = defaultdict(list)
    for t in txs.values():
        if t['from'] != t['to']:
            adjacency[t['from']].append(t)
    cycles = []
    def walk(origin, current, seen, path, last_time):
        if len(path) >= 8:
            return
        for t in adjacency.get(current, []):
            if t['time'] <= last_time:
                continue
            next_path = path + [t['id']]
            if t['to'] == origin:
                if len(next_path) >= 2:
                    cycles.append(next_path)
            elif t['to'] not in seen:
                walk(origin, t['to'], seen | {t['to']}, next_path, t['time'])
    for start in list(adjacency):
        walk(start, start, {start}, [], '')
    results = []
    for ids in cycles:
        first, last = txs[ids[0]], txs[ids[-1]]
        duration = (datetime.strptime(last['time'], '%Y/%m/%d %H:%M') - datetime.strptime(first['time'], '%Y/%m/%d %H:%M')).total_seconds() / 60
        results.append({'transaction_ids': ids, 'account_path': [first['from']] + [txs[i]['to'] for i in ids], 'duration_minutes': duration})
    reference_ids = [t['id'] for t in private['transactions'] if t['reference_group_member']]
    result['cases'][case_id] = {'transactions': len(txs), 'accounts': len(public_entities),
        'entities': len(set(public_entities.values())), 'positive_rows': private['positive_rows'],
        'reference_pattern_ids': reference_ids, 'simple_temporal_cycles_up_to_8_edges': results,
        'cycle_search_scope': 'All displayed non-self edges only; strict time increase; distinct internal accounts; no claim outside packet or above 8 edges.'}
(ROOT / 'evaluator/structural-checks.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({name: {'rows': c['transactions'], 'accounts': c['accounts'], 'entities': c['entities'],
                        'positives': c['positive_rows'], 'bounded_cycles': len(c['simple_temporal_cycles_up_to_8_edges']),
                        'reference_ids': c['reference_pattern_ids']}
                  for name, c in result['cases'].items()}, indent=2))
