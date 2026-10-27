"""Build a label-conditioned two-case illustration; never use it as a holdout benchmark."""
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[1] / 'data'
SEED = 20261023
FMT = '%Y/%m/%d %H:%M'


def key(bank, account):
    return (bank.lstrip('0') or '0', account)


def endpoints(row):
    return key(row[1], row[2]), key(row[3], row[4])


def records():
    with (DATA / 'HI-Small_Trans.csv').open(newline='') as f:
        reader = csv.reader(f)
        next(reader)
        for row_id, row in enumerate(reader, 1):
            if row_id % 1000000 == 0:
                print(f'Scanned {row_id:,} source rows', flush=True)
            yield row_id, row


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


for directory in ['inputs', 'assessments', 'evaluator']:
    (ROOT / directory).mkdir(parents=True, exist_ok=True)
if (ROOT / 'evaluator' / 'truth.json').exists():
    raise SystemExit('Inputs already frozen; do not overwrite an assessed experiment.')

groups = []
for line in (DATA / 'HI-Small_Patterns.txt').read_text().splitlines():
    if line.startswith('BEGIN'):
        groups.append({'name': line, 'rows': []})
    elif line.startswith('2022/'):
        groups[-1]['rows'].append(next(csv.reader([line])))

eligible = []
for index, group in enumerate(groups):
    rows = sorted(group['rows'], key=lambda r: r[0])
    if ' - CYCLE:' not in group['name'] or len(rows) != 6:
        continue
    times = [datetime.strptime(r[0], FMT) for r in rows]
    pairs = [endpoints(r) for r in rows]
    valid_cycle = (len({p[0] for p in pairs}) == 6
                   and all(pairs[i][1] == pairs[(i + 1) % 6][0] for i in range(6))
                   and all(times[i] < times[i + 1] for i in range(5)))
    if (valid_cycle and times[0] >= datetime(2022, 9, 2)
            and times[-1] < datetime(2022, 9, 10)
            and times[-1] - times[0] <= timedelta(days=3)):
        eligible.append((index, group, times[0], times[-1]))
if not eligible:
    raise SystemExit('No eligible reference group; revise protocol openly before assessment.')
pattern_index, positive_group, first_time, last_time = random.Random(SEED).choice(eligible)
start = (first_time - timedelta(hours=12)).strftime(FMT)
end = (last_time + timedelta(hours=12)).strftime(FMT)
positive_focus = {p for r in positive_group['rows'] for p in endpoints(r)}
pattern_content = {tuple(r) for r in positive_group['rows']}
positive_rows = []
pattern_matches = Counter()
anchors = []
seen = 0
rng = random.Random(SEED)
print(f'Stage 1: source window [{start}, {end}); {len(eligible)} eligible positive groups', flush=True)
for row_id, row in records():
    if not start <= row[0] < end:
        continue
    source, dest = endpoints(row)
    if source in positive_focus or dest in positive_focus:
        positive_rows.append((row_id, row))
    if tuple(row) in pattern_content:
        pattern_matches[tuple(row)] += 1
    if row[10] == '0' and row[9] == 'ACH' and source != dest:
        seen += 1
        if len(anchors) < 64:
            anchors.append((row_id, row))
        else:
            slot = rng.randrange(seen)
            if slot < 64:
                anchors[slot] = (row_id, row)
assert len(pattern_matches) == 6 and all(n == 1 for n in pattern_matches.values())
if len(positive_rows) > 150:
    raise SystemExit('Positive context exceeds predeclared display budget; no assessment performed.')

roots = {endpoints(row)[0] for _, row in anchors}
root_rows = defaultdict(list)
print(f'Stage 2: retrieve context for {len(roots)} candidate roots', flush=True)
for row_id, row in records():
    if not start <= row[0] < end:
        continue
    for account in set(endpoints(row)) & roots:
        root_rows[account].append((row_id, row))

candidates = []
for anchor_id, anchor in anchors:
    source, dest = endpoints(anchor)
    focus = [source, dest]
    for _, row in sorted(root_rows[source], key=lambda x: (x[1][0], x[0])):
        for account in endpoints(row):
            if account not in focus:
                focus.append(account)
        if len(focus) >= 6:
            break
    if len(focus) >= 6:
        candidates.append({'anchor_id': anchor_id, 'focus': set(focus[:6]), 'rows': []})
key_cases = defaultdict(set)
for i, candidate in enumerate(candidates):
    for account in candidate['focus']:
        key_cases[account].add(i)
print(f'Stage 3: retrieve complete incident context for {len(candidates)} candidates', flush=True)
for row_id, row in records():
    if not start <= row[0] < end:
        continue
    source, dest = endpoints(row)
    for i in key_cases.get(source, set()) | key_cases.get(dest, set()):
        candidates[i]['rows'].append((row_id, row))

eligible_negative = [c for c in candidates
                     if max(6, len(positive_rows) // 2) <= len(c['rows']) <= min(150, len(positive_rows) * 2)
                     and all(r[10] == '0' for _, r in c['rows'])]
if not eligible_negative:
    save(ROOT / 'evaluator' / 'selection_diagnostic.json', {
        'positive_context_rows': len(positive_rows),
        'candidate_sizes': [len(c['rows']) for c in candidates],
        'zero_label_candidates': [len(c['rows']) for c in candidates if all(r[10] == '0' for _, r in c['rows'])]})
    raise SystemExit('No eligible negative context; no assessment performed.')
negative = eligible_negative[0]

accounts = {}
with (DATA / 'HI-Small_accounts.csv').open(newline='') as f:
    for row in csv.DictReader(f):
        accounts[key(row['Bank ID'], row['Account Number'])] = row['Entity ID']

case_specs = [(positive_focus, positive_rows), (negative['focus'], negative['rows'])]
case_names = ['case-7b4e', 'case-c193']
random.Random(SEED + 1).shuffle(case_names)
truth = {'selection': {
    'seed': SEED, 'eligible_positive_groups': len(eligible),
    'positive_pattern_zero_based_index': pattern_index,
    'positive_group_name': positive_group['name'],
    'negative_anchor_candidates': len(anchors),
    'negative_eligible_contexts': len(eligible_negative),
    'negative_anchor_source_row': negative['anchor_id'],
    'selected_negative_position': candidates.index(negative),
    'window_start_inclusive': start, 'window_end_exclusive': end,
    'context_policy': 'Every source transaction touching one of six focus accounts in the same time window; no channel filter or row truncation.',
    'negative_matching': 'Same six focus accounts count and window; total packet rows between half and twice positive packet size, maximum 150; all packet labels zero. No restriction on graph topology or motifs.',
    'graph_truth_definition': 'At least one displayed transaction has publisher Is Laundering=1; this is a derived packet-level target.',
}, 'cases': {}}
for case_name, (focus, source_rows) in zip(case_names, case_specs):
    source_rows = sorted(source_rows, key=lambda x: (x[1][0], x[0]))
    keys = sorted({p for _, row in source_rows for p in endpoints(row)})
    aliases = {p: f'A{i:02}' for i, p in enumerate(keys, 1)}
    entity_aliases = {e: f'E{i:02}' for i, e in enumerate(sorted({accounts[p] for p in keys}), 1)}
    txs, mapping = [], []
    for i, (row_id, row) in enumerate(source_rows, 1):
        source, dest = endpoints(row)
        tx_id = f'T{i:03}'
        txs.append({'id': tx_id, 'time': row[0], 'from': aliases[source], 'to': aliases[dest],
                    'amount_paid': row[7], 'paid_currency': row[8],
                    'amount_received': row[5], 'received_currency': row[6], 'format': row[9]})
        mapping.append({'id': tx_id, 'source_row_number_excluding_header': row_id,
                        'raw_row': row, 'label': int(row[10]), 'reference_group_member': tuple(row) in pattern_content})
    account_info = [{'id': aliases[p], 'entity': entity_aliases[accounts[p]], 'focus': p in focus} for p in keys]
    stats = []
    for p in sorted(focus):
        alias = aliases[p]
        incoming = [t for t in txs if t['to'] == alias and t['from'] != alias]
        outgoing = [t for t in txs if t['from'] == alias and t['to'] != alias]
        stats.append({'account': alias, 'incoming_transactions': len(incoming),
                      'outgoing_transactions': len(outgoing),
                      'distinct_senders': len({t['from'] for t in incoming}),
                      'distinct_receivers': len({t['to'] for t in outgoing}),
                      'self_transactions': sum(t['from'] == alias == t['to'] for t in txs)})
    packet = {'case_id': case_name, 'source': 'IBM AML-Data HI-Small synthetic transactions and account metadata',
              'scope': {'start_inclusive': start, 'end_exclusive': end,
                        'timezone': 'Unspecified by source; preserve simulation timestamps.',
                        'focus_accounts': sorted(aliases[p] for p in focus),
                        'coverage': 'All transactions touching focus accounts within this window. Boundary accounts may have additional transactions outside this view. Earlier/later history is not included.',
                        'returned_rows': len(txs), 'truncated': False},
              'identity_note': 'Aliases preserve account and recorded synthetic-entity equality. Entity mapping is static metadata, not verified ultimate control.',
              'accounts': account_info, 'focus_account_statistics': stats,
              'transactions': txs,
              'missing_context': ['Business purpose', 'Account balances', 'Verified ultimate beneficial control',
                                  'Invoices or customer explanations', 'FX rates', 'Activity outside this query']}
    save(ROOT / 'inputs' / f'{case_name}.json', packet)
    lines = [f'# Evidence packet {case_name}', '', 'Real rows from IBM synthetic AML data. Account/entity/transaction IDs are stable local aliases; amounts, currencies, timestamps and payment formats are unchanged.', '',
             f'Window: [{start}, {end}); source timezone unspecified.',
             f'Focus accounts: {", ".join(packet["scope"]["focus_accounts"])}.',
             packet['scope']['coverage'], f'Returned rows: {len(txs)}. Truncated: false.', '',
             '## Account identities', '', '| Account | Recorded entity | Focus |', '|---|---|---|']
    lines += [f'| {a["id"]} | {a["entity"]} | {a["focus"]} |' for a in account_info]
    lines += ['', 'The entity mapping is static synthetic metadata, not verified ultimate beneficial control.', '',
              '## Code-computed account statistics (whole displayed window)', '',
              '| Account | Incoming rows | Outgoing rows | Distinct senders | Distinct receivers | Self rows |', '|---|---:|---:|---:|---:|---:|']
    lines += [f'| {s["account"]} | {s["incoming_transactions"]} | {s["outgoing_transactions"]} | {s["distinct_senders"]} | {s["distinct_receivers"]} | {s["self_transactions"]} |' for s in stats]
    lines += ['', '## Transactions', '', '| ID | Time | From | To | Paid | Paid currency | Received | Received currency | Format |', '|---|---|---|---|---:|---|---:|---|---|']
    lines += [f'| {t["id"]} | {t["time"]} | {t["from"]} | {t["to"]} | {t["amount_paid"]} | {t["paid_currency"]} | {t["amount_received"]} | {t["received_currency"]} | {t["format"]} |' for t in txs]
    lines += ['', '## Missing context', '', ', '.join(packet['missing_context']) + '.', 'Do not infer any of these missing facts from a transaction pattern alone.', '']
    (ROOT / 'inputs' / f'{case_name}.md').write_text('\n'.join(lines))
    truth['cases'][case_name] = {'positive_rows': sum(x['label'] for x in mapping),
        'total_rows': len(mapping), 'derived_packet_label': int(any(x['label'] for x in mapping)),
        'account_mapping': {aliases[p]: {'canonical_bank': p[0], 'account': p[1], 'entity_id': accounts[p]} for p in keys},
        'transactions': mapping}
save(ROOT / 'evaluator' / 'truth.json', truth)
print(json.dumps({name: {'rows': case['total_rows'], 'positives': case['positive_rows']}
                  for name, case in truth['cases'].items()}, indent=2), flush=True)
