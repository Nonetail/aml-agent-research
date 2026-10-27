"""Evaluator-only source catalogue and ratio-matched development corpus. No model calls."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random
import sqlite3

HERE = Path(__file__).resolve().parent
CUTOFF = '2022/09/11 00:00'
TIME_FORMAT = '%Y/%m/%d %H:%M'


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def nearest_count(size, count, total):
    """Nearest integer, with exact arithmetic and half-up ties."""
    if not 0 <= count <= total or total <= 0 or size < 0:
        raise ValueError('Invalid population or sample counts')
    return (2 * size * count + total) // (2 * total)


def ratio_report(actual, size, source_count, source_size):
    expected = Fraction(size * source_count, source_size)
    return {'source_count': source_count, 'source_denominator': source_size,
            'source_rate': source_count / source_size,
            'expected_sample_count': float(expected),
            'nearest_integer_target': nearest_count(size, source_count, source_size),
            'actual_count': actual, 'sample_denominator': size,
            'sample_rate': actual / size,
            'count_error': float(actual - expected),
            'relative_rate_error': float(Fraction(actual, 1) / expected - 1)
            if expected else None}


def parse_patterns(path):
    groups = []
    for line in path.read_text().splitlines():
        if line.startswith('BEGIN LAUNDERING ATTEMPT - '):
            groups.append({'group_id': len(groups) + 1,
                           'family': line.split(' - ', 1)[1].split(':', 1)[0], 'raw_rows': []})
        elif line.startswith('2022/'):
            if not groups:
                raise ValueError('Pattern record before group header')
            groups[-1]['raw_rows'].append(next(csv.reader([line])))
    if not groups or any(not g['raw_rows'] for g in groups):
        raise ValueError('Empty pattern catalogue/group')
    return groups


def cycle_properties(rows):
    """Check actual directed edges; a publisher name alone is not eligibility."""
    def account(row, side):
        return row[f'{side}_bank'], row[f'{side}_account']
    times = [r['timestamp'] for r in rows]
    closed = len(rows) >= 2 and all(account(a, 'destination') == account(b, 'source')
                                   for a, b in zip(rows, rows[1:] + rows[:1]))
    simple = closed and len({account(r, 'source') for r in rows}) == len(rows)
    ties = len(set(times)) != len(times)
    temporal = closed and not ties and sum(a > b for a, b in zip(times, times[1:] + times[:1])) == 1
    rotation = times.index(min(times))
    return {'closed': closed, 'simple': simple, 'equal_timestamps': ties,
            'strict_temporal': temporal,
            'eligible_short': simple and temporal and 2 <= len(rows) <= 4,
            'temporal_row_ids': [r['row_id'] for r in rows[rotation:] + rows[:rotation]] if temporal else [],
            'span_hours': (datetime.strptime(max(times), TIME_FORMAT) -
                           datetime.strptime(min(times), TIME_FORMAT)).total_seconds() / 3600}


def resolve_catalogue(db, patterns, positives):
    groups = parse_patterns(patterns)
    old_factory = db.row_factory
    db.row_factory = sqlite3.Row
    seen = set()
    for g in groups:
        resolved = []
        for r in g.pop('raw_rows'):
            if len(r) != 11 or r[10] != '1':
                raise ValueError('Expected eleven fields and positive publisher record')
            matches = db.execute('''SELECT * FROM transactions WHERE source_bank=? AND source_account=?
                AND timestamp=? AND destination_bank=? AND destination_account=? AND received_amount=?
                AND received_currency=? AND paid_amount=? AND paid_currency=? AND payment_format=?
                AND raw_source_bank=? AND raw_destination_bank=?''',
                (str(int(r[1])), r[2], r[0], str(int(r[3])), r[4], *r[5:10], r[1], r[3])).fetchall()
            if len(matches) != 1:
                raise ValueError(f'Group {g["group_id"]}: exact source match count {len(matches)}')
            row = dict(matches[0])
            if row['row_id'] not in positives:
                raise ValueError('Pattern row is not positive in evaluator labels')
            if row['row_id'] in seen:
                raise ValueError('Overlapping/repeated publisher records need explicit multiplicity handling')
            seen.add(row['row_id'])
            resolved.append(row)
        g['rows'] = resolved
        g['row_ids'] = [r['row_id'] for r in resolved]
        g['edge_count'] = len(resolved)
        g['wholly_primary'] = all(r['timestamp'] < CUTOFF for r in resolved)
        g['primary_row_count'] = sum(r['timestamp'] < CUTOFF for r in resolved)
        g['tail_row_count'] = len(resolved) - g['primary_row_count']
        g['accounts'] = sorted({(r[f'{s}_bank'], r[f'{s}_account'])
                                for r in resolved for s in ('source', 'destination')})
        if g['family'] == 'CYCLE':
            g.update(cycle_properties(resolved))
    db.row_factory = old_factory
    return groups


def catalogue_summary(groups):
    def summarize(chosen):
        return {'groups': len(chosen), 'unique_rows': len({r for g in chosen for r in g['row_ids']}),
                'primary_rows': sum(g['primary_row_count'] for g in chosen),
                'tail_rows': sum(g['tail_row_count'] for g in chosen),
                'lengths': dict(sorted(Counter(g['edge_count'] for g in chosen).items()))}
    cycles = [g for g in groups if g['family'] == 'CYCLE']
    return {'all_patterns': summarize(groups), 'publisher_cycles': summarize(cycles),
            'wholly_primary_publisher_cycles': summarize([g for g in cycles if g['wholly_primary']]),
            'simple_closed_cycles': summarize([g for g in cycles if g['simple']]),
            'strict_temporal_cycles_all_lengths': summarize([g for g in cycles if g['strict_temporal']]),
            'eligible_short_cycles': summarize([g for g in cycles if g['eligible_short']]),
            'wholly_primary_eligible_short_cycles': summarize(
                [g for g in cycles if g['eligible_short'] and g['wholly_primary']]),
            'non_temporal_cycle_group_ids': [g['group_id'] for g in cycles if not g['strict_temporal']]}


def incident_bundle(db, group, memberships, context_hours):
    times = [r['timestamp'] for r in group['rows']]
    start = (datetime.strptime(min(times), TIME_FORMAT) - timedelta(hours=context_hours)).strftime(TIME_FORMAT)
    end = (datetime.strptime(max(times), TIME_FORMAT) + timedelta(hours=context_hours)).strftime(TIME_FORMAT)
    incident = set(group['row_ids'])
    for bank, account in group['accounts']:
        for side in ('source', 'destination'):
            incident.update(r[0] for r in db.execute(f'''SELECT row_id FROM transactions
                WHERE {side}_bank=? AND {side}_account=? AND timestamp>=? AND timestamp<=?''',
                (bank, account, start, end)))
    complete = set(incident)
    for row_id in incident:
        if row_id in memberships:
            complete.update(memberships[row_id]['row_ids'])
    return {'group_id': group['group_id'], 'seed_rows': set(group['row_ids']),
            'incident': incident, 'complete': complete, 'window_start': start, 'window_end_inclusive': end}


def short_account_clusters(groups):
    """Connected components across all eligible episode accounts, before sampling."""
    eligible = [g for g in groups if g.get('eligible_short')]
    parents = {g['group_id']: g['group_id'] for g in eligible}
    def root(group_id):
        while parents[group_id] != group_id:
            group_id = parents[group_id]
        return group_id
    owners = {}
    for g in eligible:
        for account in g['accounts']:
            key = tuple(account)
            if key in owners:
                a, b = root(g['group_id']), root(owners[key])
                parents[max(a, b)] = min(a, b)
            owners[key] = g['group_id']
    return {g['group_id']: root(g['group_id']) for g in eligible}


def choose_bundles(bundles, cycle_ids, short_ids, positive_ids, targets, seed, independent_short=None):
    """Bounded deterministic search; never prune evidence from an accepted bundle."""
    ordered = list(bundles)
    random.Random(seed).shuffle(ordered)
    ordered.sort(key=lambda b: (not bool(b['seed_rows'] & short_ids), -len(b['seed_rows'])))
    visited = 0
    def search(start, selected, rows):
        nonlocal visited
        visited += 1
        if visited > 100000:
            raise ValueError('Whole-episode selection exceeded search bound; choose another size/seed')
        counts = (len(rows & cycle_ids), len(rows & short_ids), len(rows & positive_ids))
        if counts[0] > targets['cycle'] or counts[1] > targets['short'] or counts[2] > targets['positive']:
            return None
        if independent_short:
            clusters = [cluster for group_rows, cluster in independent_short if group_rows <= rows]
            if len(clusters) != len(set(clusters)):
                return None
        if counts[:2] == (targets['cycle'], targets['short']):
            return selected, rows
        for i in range(start, len(ordered)):
            b = ordered[i]
            if b['seed_rows'] <= rows:
                continue
            found = search(i + 1, selected + [b], rows | b['complete'])
            if found:
                return found
        return None
    result = search(0, [], set())
    if not result or targets['short'] < 2:
        raise ValueError('Requested ratios cannot include a complete eligible short cycle at this size')
    return result


def select_rows(db, groups, positive_ids, source_rows, size, seed, context_hours, independent_short_episodes=False):
    if not 0 < size <= source_rows:
        raise ValueError('Sample size must be within the source population')
    memberships = {r: g for g in groups for r in g['row_ids']}
    cycle_ids = {r for g in groups if g['family'] == 'CYCLE' for r in g['row_ids']}
    short_ids = {r for g in groups if g.get('eligible_short') for r in g['row_ids']}
    targets = {'positive': nearest_count(size, len(positive_ids), source_rows),
               'cycle': nearest_count(size, len(cycle_ids), source_rows),
               'short': nearest_count(size, len(short_ids), source_rows)}
    bundles = [incident_bundle(db, g, memberships, context_hours) for g in groups if g['family'] == 'CYCLE']
    cluster_ids = short_account_clusters(groups)
    independent_short = [(set(g['row_ids']), cluster_ids[g['group_id']]) for g in groups if g.get('eligible_short')] if independent_short_episodes else None
    chosen, selected = choose_bundles(bundles, cycle_ids, short_ids, positive_ids, targets, seed, independent_short)
    if len(selected) > size:
        raise ValueError('Whole context exceeds requested corpus size')
    reasons = {r: 'motif_completion' for r in selected}
    for b in chosen:
        reasons.update({r: 'incident_context' for r in b['incident']})
    for b in chosen:
        reasons.update({r: 'selected_episode' for r in b['seed_rows']})
    rng = random.Random(seed + 1)
    remaining = sorted(positive_ids - cycle_ids - selected)
    rng.shuffle(remaining)
    for row_id in remaining:
        if len(selected & positive_ids) == targets['positive']:
            break
        if row_id in selected:
            continue
        group = memberships.get(row_id)
        unit = set(group['row_ids']) if group else {row_id}
        additions = unit - selected
        if additions & cycle_ids or len((selected | additions) & positive_ids) > targets['positive']:
            continue
        selected.update(additions)
        reasons.update({r: 'positive_background' for r in additions})
    if len(selected & positive_ids) != targets['positive']:
        raise ValueError('Unable to fill positive quota without splitting publisher episodes')
    if len(selected) > size:
        raise ValueError('Whole context plus positive quota exceeds requested corpus size')
    # Source row IDs are checked contiguous before this source-uniform rejection sample.
    while len(selected) < size:
        row_id = rng.randrange(1, source_rows + 1)
        if row_id not in positive_ids and row_id not in selected:
            selected.add(row_id)
            reasons[row_id] = 'negative_background'
    if len(selected & cycle_ids) != targets['cycle'] or len(selected & short_ids) != targets['short']:
        raise AssertionError('Cycle ratio changed during background selection')
    partial = [g['group_id'] for g in groups if set(g['row_ids']) & selected and not set(g['row_ids']) <= selected]
    if partial:
        raise AssertionError(f'Publisher groups were split: {partial}')
    return selected, reasons, chosen, targets


def write_runtime(source, path, selected, source_hash):
    db = sqlite3.connect(path)
    for table in ('metadata', 'accounts', 'transactions'):
        db.execute(source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0])
    rows = sorted(selected)
    nodes = set()
    time_counts = Counter()
    for offset in range(0, len(rows), 500):
        batch = rows[offset:offset + 500]
        found = source.execute('SELECT * FROM transactions WHERE row_id IN (' + ','.join('?' * len(batch)) + ') ORDER BY row_id', batch).fetchall()
        if len(found) != len(batch):
            raise ValueError('Selected source row missing')
        db.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', found)
        for r in found:
            nodes.update(((r[2], r[3]), (r[4], r[5])))
            time_counts['primary' if r[1] < CUTOFF else 'tail'] += 1
    for bank, account in sorted(nodes):
        row = source.execute('SELECT * FROM accounts WHERE bank=? AND account=?', (bank, account)).fetchone()
        if row is None:
            raise ValueError('Source endpoint has no account record')
        db.execute('INSERT INTO accounts VALUES(?,?,?,?,?,?)', row)
    for (sql,) in source.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='transactions' AND sql IS NOT NULL ORDER BY name"):
        db.execute(sql)
    scope = {'schema_version': 1, 'rows': len(rows), 'accounts': len(nodes),
             'timestamp_range': list(db.execute('SELECT MIN(timestamp),MAX(timestamp) FROM transactions').fetchone()),
             'scope': 'Source-derived development subset; queries are complete only within this database.',
             'graph_completeness': 'Source edges outside this database are unavailable; absence is not source-wide absence.',
             'id_format': 'original source transaction row ordinal; account identity is bank+account'}
    db.executemany('INSERT INTO metadata VALUES(?,?)', [('source_sha256', source_hash), ('manifest', json.dumps(scope, sort_keys=True))])
    db.execute('ANALYZE')
    db.commit()
    if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        raise ValueError('Runtime database integrity check failed')
    with (path.parent / 'nodes.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([r[1] for r in db.execute('PRAGMA table_info(accounts)')])
        writer.writerows(db.execute('SELECT * FROM accounts ORDER BY bank,account'))
    db.close()
    return scope, dict(time_counts)


def build(source_path, labels_path, patterns_path, output, size=300000, seed=20261024, context_hours=24, independent_short_episodes=False):
    # Never overwrite an earlier corpus, including a partially completed build.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'runtime').mkdir()
    (output / 'evaluator').mkdir()
    source, labels = readonly(source_path), readonly(labels_path)
    count, lo, hi, primary = source.execute('''SELECT COUNT(*),MIN(row_id),MAX(row_id),
        SUM(timestamp < ?) FROM transactions''', (CUTOFF,)).fetchone()
    if (lo, hi) != (1, count):
        raise ValueError('Source row IDs must be contiguous 1..N for uniform sampling')
    if labels.execute('SELECT COUNT(*) FROM labels').fetchone()[0] != count:
        raise ValueError('Evaluator/source population mismatch')
    positive_ids = {r[0] for r in labels.execute('SELECT row_id FROM labels WHERE is_laundering=1')}
    positive_times = {}
    for row_id in sorted(positive_ids):
        row = source.execute('SELECT timestamp FROM transactions WHERE row_id=?', (row_id,)).fetchone()
        if row is None:
            raise ValueError('Evaluator row absent from source')
        positive_times[row_id] = row[0]
    groups = resolve_catalogue(source, patterns_path, positive_ids)
    summary = catalogue_summary(groups)
    selected, reasons, chosen, targets = select_rows(source, groups, positive_ids, count, size, seed, context_hours, independent_short_episodes)
    source_hash = source.execute("SELECT value FROM metadata WHERE key='source_sha256'").fetchone()[0]
    runtime_path = output / 'runtime' / 'transactions.sqlite'
    scope, periods = write_runtime(source, runtime_path, selected, source_hash)
    evaluator = sqlite3.connect(output / 'evaluator' / 'evaluator.sqlite')
    evaluator.executescript('''CREATE TABLE labels(row_id INTEGER PRIMARY KEY,is_laundering INTEGER NOT NULL);
        CREATE TABLE selection(row_id INTEGER PRIMARY KEY,source_row_id INTEGER NOT NULL,selection_role TEXT NOT NULL);
        CREATE TABLE pattern_memberships(source_row_id INTEGER PRIMARY KEY,group_id INTEGER NOT NULL,
            family TEXT NOT NULL,in_sample INTEGER NOT NULL,eligible_short INTEGER NOT NULL);''')
    evaluator.executemany('INSERT INTO labels VALUES(?,?)', ((r, int(r in positive_ids)) for r in sorted(selected)))
    evaluator.executemany('INSERT INTO selection VALUES(?,?,?)', ((r, r, reasons[r]) for r in sorted(selected)))
    evaluator.executemany('INSERT INTO pattern_memberships VALUES(?,?,?,?,?)',
        ((r, g['group_id'], g['family'], int(r in selected), int(g.get('eligible_short', False))) for g in groups for r in g['row_ids']))
    evaluator.commit()
    evaluator.close()
    cycle_ids = {r for g in groups if g['family'] == 'CYCLE' for r in g['row_ids']}
    short_ids = {r for g in groups if g.get('eligible_short') for r in g['row_ids']}
    selected_positive = selected & positive_ids
    primary_positive = sum(t < CUTOFF for t in positive_times.values())
    sample_primary_positive = sum(positive_times[r] < CUTOFF for r in selected_positive)
    complete_groups = [g['group_id'] for g in groups if set(g['row_ids']) <= selected]
    catalogue = {'scope': 'Evaluator only. All publisher groups matched exactly; not an exhaustive graph-cycle census.',
                 'summary': summary, 'groups': [{k: v for k, v in g.items() if k != 'rows'} for g in groups]}
    (output / 'evaluator' / 'catalogue.json').write_text(json.dumps(catalogue, indent=2, sort_keys=True) + '\n')
    sample_short_groups = [g['group_id'] for g in groups if g.get('eligible_short') and g['group_id'] in complete_groups]
    cluster_ids = short_account_clusters(groups)
    manifest = {'schema_version': 1, 'recipe': 'whole episodes + all incident rows in fixed padded windows + whole publisher motif completion + source-positive/negative background',
                'seed': seed, 'requested_rows': size, 'context_hours_each_side': context_hours,
                'independent_short_episodes': independent_short_episodes,
                'sample_short_account_clusters': {str(g): cluster_ids[g] for g in sample_short_groups},
                'source': {'transactions': str(source_path.resolve()), 'labels': str(labels_path.resolve()),
                           'patterns': str(patterns_path.resolve()), 'transaction_csv_sha256': source_hash,
                           'transaction_sqlite_sha256': digest(source_path), 'labels_sqlite_sha256': digest(labels_path),
                           'patterns_sha256': digest(patterns_path)},
                'population': {'rows': count, 'positive_rows': len(positive_ids), 'unclassified_positive_rows': len(positive_ids) - summary['all_patterns']['unique_rows'],
                               'primary': {'rows': primary, 'positive_rows': primary_positive},
                               'tail': {'rows': count - primary, 'positive_rows': len(positive_ids) - primary_positive}},
                'catalogue_summary': summary, 'runtime_scope': scope, 'integer_targets': targets,
                'ratios': {'overall_positive': ratio_report(len(selected_positive), size, len(positive_ids), count),
                           'publisher_cycle': ratio_report(len(selected & cycle_ids), size, len(cycle_ids), count),
                           'eligible_short_cycle': ratio_report(len(selected & short_ids), size, len(short_ids), count)},
                'cycle_share_of_positives': {'source': len(cycle_ids) / len(positive_ids), 'sample': len(selected & cycle_ids) / len(selected_positive)},
                'sample_primary': {'rows': periods.get('primary', 0), 'positive_rows': sample_primary_positive},
                'sample_tail': {'rows': periods.get('tail', 0), 'positive_rows': len(selected_positive) - sample_primary_positive},
                'selected_episode_group_ids': [b['group_id'] for b in chosen],
                'selected_episode_windows': [{k: b[k] for k in ('group_id', 'window_start', 'window_end_inclusive')} for b in chosen],
                'included_complete_pattern_group_ids': complete_groups, 'partial_publisher_groups': [],
                'sample_eligible_short_groups': sample_short_groups,
                'selection_role_counts': dict(Counter(reasons.values())),
                'tolerance': 'Each of three per-transaction rates uses nearest integer count, absolute deviation <=0.5 row; exact population rates generally require a much larger rational multiple.',
                'limitations': ['Development ratio smoke corpus, not a random population sample or blind precision evaluation.',
                    f'{len(sample_short_groups)} short eligible episodes included; their inclusion and context are answer-informed.',
                    'All incident evidence inside selected windows is retained, including positives; whole touched publisher motifs are completed.',
                    'Background is stratified using hidden labels and complete publisher motifs; other-family proportions and source degree distribution are not preserved.',
                    'Uncatalogued positive rows can be parts of unknown episodes; their completeness is not established.',
                    'Full-file baseline includes a label-rich tail; primary and tail proportions are reported, not independently constrained.',
                    'Source account identifiers and exact row instances are preserved; missing source edges can break uncatalogued motifs.',
                    'Distinct short-episode account clusters do not establish disjointness of all context/background accounts or statistical independence.',
                    'Catalogue covers publisher CYCLE membership, not every positive cycle or every zero-label cycle in the five-million-row graph.',
                    'Runtime/answer files are separated on disk, not protected by an OS sandbox. A blind detector must receive access only to runtime/.'],
                'artifacts': {'runtime_database_sha256': digest(runtime_path),
                              'nodes_csv_sha256': digest(output / 'runtime' / 'nodes.csv')}}
    (output / 'evaluator' / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    source.close()
    labels.close()
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=HERE / 'generated' / 'transactions.sqlite')
    parser.add_argument('--labels', type=Path, default=HERE / 'generated' / 'evaluator.sqlite')
    parser.add_argument('--patterns', type=Path, default=HERE.parents[1] / 'data' / 'HI-Small_Patterns.txt')
    parser.add_argument('--output', type=Path, default=HERE / 'generated' / 'cycle-family-v1')
    parser.add_argument('--rows', type=int, default=300000)
    parser.add_argument('--seed', type=int, default=20261024)
    parser.add_argument('--context-hours', type=int, default=24)
    parser.add_argument('--independent-short-episodes', action='store_true')
    args = parser.parse_args()
    result = build(args.source, args.labels, args.patterns, args.output, args.rows, args.seed, args.context_hours, args.independent_short_episodes)
    print(json.dumps({k: result[k] for k in ('integer_targets', 'ratios', 'selected_episode_group_ids', 'sample_primary', 'sample_tail', 'runtime_scope')}, indent=2))
