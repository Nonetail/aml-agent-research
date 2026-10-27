"""Score frozen first responses and check their cited IDs and reviewed factual claims."""
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
truth = json.loads((ROOT / 'evaluator/truth.json').read_text())
structure = json.loads((ROOT / 'evaluator/structural-checks.json').read_text())
claimed_gaps = {
    'case-c193': [('T021', 'T022', 4), ('T066', 'T067', 20), ('T041', 'T043', 200), ('T043', 'T046', 123)],
    'case-7b4e': [('T074', 'T075', 2), ('T077', 'T078', 3), ('T012', 'T013', 40), ('T067', 'T068', 46)],
}
gather_examples = {
    'case-c193': [(['T002', 'T020'], ['T022', 'T025'])],
    'case-7b4e': [(['T011', 'T021'], ['T028', 'T029']), (['T001', 'T042'], ['T050', 'T054'])],
}
results = {'scope': 'Two selected cases; estimates uncalibrated; no general accuracy claim.', 'cases': {}}
for name, private in truth['cases'].items():
    assessment = json.loads((ROOT / 'assessments' / f'{name}.json').read_text())
    packet = json.loads((ROOT / 'inputs' / f'{name}.json').read_text())
    txs = {t['id']: t for t in packet['transactions']}
    ids = set(assessment['strongest_supporting_transaction_ids'])
    assert sorted(g['guideline'] for g in assessment['guideline_assessments']) == list(range(1, 7))
    for g in assessment['guideline_assessments']:
        ids.update(g['evidence_ids'])
    assert ids <= txs.keys()
    probability = assessment['subjective_probability_any_laundering_percent']
    assert 0 <= probability <= 100
    assert assessment['predicted_label'] == int(probability >= 50)
    def time(t):
        return datetime.strptime(t['time'], '%Y/%m/%d %H:%M')
    for incoming, outgoing, minutes in claimed_gaps[name]:
        a, b = txs[incoming], txs[outgoing]
        assert a['to'] == b['from']
        assert (time(b) - time(a)).total_seconds() / 60 == minutes
    for incoming, outgoing in gather_examples[name]:
        a, b = [txs[i] for i in incoming], [txs[i] for i in outgoing]
        assert len({t['from'] for t in a}) >= 2 and len({t['to'] for t in b}) >= 2
        assert len({t['to'] for t in a} | {t['from'] for t in b}) == 1
        assert max(time(t) for t in a) < min(time(t) for t in b)

    graph, indegree = defaultdict(set), {a['id']: 0 for a in packet['accounts']}
    for t in txs.values():
        a, b = t['from'], t['to']
        if a != b and b not in graph[a]:
            graph[a].add(b)
            indegree[b] += 1
    queue = deque(a for a, degree in indegree.items() if degree == 0)
    removed = 0
    while queue:
        a = queue.popleft()
        removed += 1
        for b in graph[a]:
            indegree[b] -= 1
            if indegree[b] == 0:
                queue.append(b)
    acyclic = removed == len(indegree)
    if name == 'case-7b4e':
        assert acyclic
        repeated = [t for t in txs.values() if t['from'] == 'A19' and t['to'] == 'A06']
        by_day = defaultdict(set)
        for t in repeated:
            by_day[t['time'][:10]].add((t['amount_paid'], t['paid_currency'], t['format']))
        assert len(by_day) == 4 and all(len(v) == 4 for v in by_day.values())
        assert len({frozenset(v) for v in by_day.values()}) == 1
    else:
        claimed_cycle = next(g['evidence_ids'] for g in assessment['guideline_assessments'] if g['guideline'] == 4)
        actual_cycles = structure['cases'][name]['simple_temporal_cycles_up_to_8_edges']
        matching = [c for c in actual_cycles if c['transaction_ids'] == claimed_cycle]
        assert len(matching) == 1 and matching[0]['duration_minutes'] == 68 * 60 + 14
        assert set(claimed_cycle) == set(structure['cases'][name]['reference_pattern_ids'])
    results['cases'][name] = {
        'packet_rows': len(txs), 'positive_rows': private['positive_rows'],
        'derived_packet_label': private['derived_packet_label'],
        'predicted_label': assessment['predicted_label'],
        'prediction_matches_target': assessment['predicted_label'] == private['derived_packet_label'],
        'subjective_probability_any_laundering_percent': probability,
        'confidence_in_assessment': assessment['confidence_in_assessment'],
        'recommend_further_review': assessment['recommend_further_review'],
        'cited_ids_all_exist': True, 'four_claimed_time_gaps_verified': True,
        'cited_gather_then_disperse_examples_verified': True,
        'static_nonself_account_graph_acyclic': acyclic,
    }
results['verification_limit'] = 'Checks cover source identity/fields/statistics, cited IDs, four stated gaps per case, cited gather/disperse examples, positive cycle and duration, negative no-cycle claim and one recurring-payment example. Business-purpose hypotheses and confidence are not verified facts.'
(ROOT / 'evaluator/results.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
