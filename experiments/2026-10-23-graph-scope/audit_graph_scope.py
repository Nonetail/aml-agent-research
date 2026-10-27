"""Measure weak components and the boundary of the saved packets; never enumerate paths."""
import csv
import hashlib
import json
import time
from array import array
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[1]
DATA = PACKAGE / 'data'
PREVIOUS = ROOT.parent / '2026-10-23-two-case-probe'


def key(bank, account):
    return bank.lstrip('0') or '0', account


class Components:
    def __init__(self, count):
        self.parent = array('I', range(count))
        self.size = array('I', [1]) * count
        self.active = bytearray(count)
        self.source_rows = array('I', [0]) * count
        self.rows = 0

    def find(self, node):
        parent = self.parent
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def add(self, source, destination):
        self.rows += 1
        self.source_rows[source] += 1
        self.active[source] = self.active[destination] = 1
        a, b = self.find(source), self.find(destination)
        if a != b:
            if self.size[a] < self.size[b]:
                a, b = b, a
            self.parent[b] = a
            self.size[a] += self.size[b]

    def summary(self):
        accounts, transactions = Counter(), Counter()
        for node, active in enumerate(self.active):
            if active:
                root = self.find(node)
                accounts[root] += 1
                transactions[root] += self.source_rows[node]
        assert sum(transactions.values()) == self.rows
        total_accounts = sum(accounts.values())
        ranked = sorted(accounts, key=lambda r: (-accounts[r], -transactions[r], r))
        bins = Counter()
        for count in accounts.values():
            band = ('1' if count == 1 else '2-9' if count < 10 else '10-99' if count < 100
                    else '100-999' if count < 1000 else '1000-9999' if count < 10000 else '10000+')
            bins[band] += 1
        output = {'transactions': self.rows, 'active_accounts': total_accounts,
                  'weak_components': len(accounts), 'component_count_by_account_size': dict(bins),
                  'largest_components': [{'accounts': accounts[r], 'transactions': transactions[r],
                      'account_fraction': accounts[r] / total_accounts,
                      'transaction_fraction': transactions[r] / self.rows} for r in ranked[:10]]}
        return output, accounts, transactions


begin = time.perf_counter()
index = {}
with (DATA / 'HI-Small_accounts.csv').open(newline='') as f:
    for row in csv.DictReader(f):
        account = key(row['Bank ID'], row['Account Number'])
        assert account not in index
        index[account] = len(index)
graphs = {name: Components(len(index)) for name in ['full_file', 'primary_period', 'probe_window']}
private = json.loads((PREVIOUS / 'evaluator/truth.json').read_text())
start = private['selection']['window_start_inclusive']
end = private['selection']['window_end_exclusive']
cases = {}
for name, case in private['cases'].items():
    packet = json.loads((PREVIOUS / 'inputs' / f'{name}.json').read_text())
    alias_index = {a: index[(v['canonical_bank'], v['account'])] for a, v in case['account_mapping'].items()}
    cases[name] = {'focus': {alias_index[a] for a in packet['scope']['focus_accounts']},
                  'nodes': set(alias_index.values()), 'focus_rows': set(),
                  'expected_rows': {t['source_row_number_excluding_header'] for t in case['transactions']},
                  'incident_rows': 0, 'extra_interior_rows': 0, 'extra_interior_self_rows': 0, 'expanded_nodes': set()}

with (DATA / 'HI-Small_Trans.csv').open(newline='') as f:
    reader = csv.reader(f)
    next(reader)
    for row_id, row in enumerate(reader, 1):
        source, destination = index[key(row[1], row[2])], index[key(row[3], row[4])]
        graphs['full_file'].add(source, destination)
        if '2022/09/01' <= row[0] < '2022/09/11':
            graphs['primary_period'].add(source, destination)
        if start <= row[0] < end:
            graphs['probe_window'].add(source, destination)
            for case in cases.values():
                focus_match = source in case['focus'] or destination in case['focus']
                if focus_match:
                    case['focus_rows'].add(row_id)
                if source in case['nodes'] or destination in case['nodes']:
                    case['incident_rows'] += 1
                    case['expanded_nodes'].update((source, destination))
                if source in case['nodes'] and destination in case['nodes'] and not focus_match:
                    case['extra_interior_rows'] += 1
                    case['extra_interior_self_rows'] += source == destination
        if row_id % 1000000 == 0:
            print(f'Processed {row_id:,} rows in {time.perf_counter() - begin:.1f}s', flush=True)

result = {'source': 'IBM HI-Small pinned local files', 'definition':
          'Weak account components of observed transactions: ignore edge direction for connectivity, retain every row for transaction counts. No temporal path constraint. No entity ownership edges. Inactive metadata accounts excluded.',
          'probe_window': {'start_inclusive': start, 'end_exclusive': end}, 'graphs': {}, 'cases': {}}
summaries = {}
for name, graph in graphs.items():
    output, nodes, rows = graph.summary()
    result['graphs'][name] = output
    summaries[name] = (nodes, rows)
case_roots = {}
for name, case in cases.items():
    assert case['focus_rows'] == case['expected_rows'], name
    roots = {graphs['probe_window'].find(n) for n in case['nodes']}
    assert len(roots) == 1
    root = next(iter(roots))
    case_roots[name] = root
    node_counts, row_counts = summaries['probe_window']
    result['cases'][name] = {
        'packet_rows': len(case['expected_rows']), 'all_focus_incident_rows': len(case['focus_rows']),
        'complete_for_declared_focus_query': True, 'packet_accounts': len(case['nodes']),
        'all_packet_account_incident_rows_in_window': case['incident_rows'],
        'additional_rows_when_expanding_to_all_packet_accounts': case['incident_rows'] - len(case['expected_rows']),
        'accounts_after_that_one_expansion': len(case['expanded_nodes']),
        'omitted_rows_between_already_displayed_accounts': case['extra_interior_rows'],
        'omitted_self_rows_on_already_displayed_accounts': case['extra_interior_self_rows'],
        'omitted_nonself_rows_between_already_displayed_accounts': case['extra_interior_rows'] - case['extra_interior_self_rows'],
        'whole_weak_component_in_same_window': {'accounts': node_counts[root], 'transactions': row_counts[root]}}
result['probe_cases_share_weak_component'] = len(set(case_roots.values())) == 1
result['elapsed_seconds'] = round(time.perf_counter() - begin, 3)
for file in ['HI-Small_Trans.csv', 'HI-Small_accounts.csv']:
    digest = hashlib.sha256()
    with (DATA / file).open('rb') as f:
        while chunk := f.read(4 * 1024 * 1024):
            digest.update(chunk)
    result.setdefault('source_sha256', {})[file] = digest.hexdigest()
(ROOT / 'graph-scope-results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2), flush=True)
