"""Independent read-only SQL audit of a completed short-cycle discovery ledger.

This oracle does not import navigation, workflow, prompt or evaluator modules.
It joins source transaction facts directly and compares exact ordered edge tuples.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import time


def cycle_query(edges):
    if type(edges) is not int or not 2 <= edges <= 4:
        raise ValueError('edges must be 2..4')
    aliases = [f't{i}' for i in range(edges)]
    joins = []
    for left, right in zip(aliases, aliases[1:]):
        joins.append(f'''JOIN transactions {right} ON
            {right}.source_bank={left}.destination_bank AND
            {right}.source_account={left}.destination_account AND
            {right}.timestamp>{left}.timestamp''')
    conditions = [f'{name}.timestamp>=? AND {name}.timestamp<?' for name in aliases]
    conditions.append(f'''{aliases[-1]}.destination_bank=t0.source_bank AND
                          {aliases[-1]}.destination_account=t0.source_account''')
    for index, left in enumerate(aliases):
        for right in aliases[index+1:]:
            conditions.append(f'''({left}.source_bank<>{right}.source_bank OR
                                  {left}.source_account<>{right}.source_account)''')
    return (f"SELECT {','.join(name+'.row_id' for name in aliases)} FROM transactions t0 " +
            ' '.join(joins)+' WHERE '+' AND '.join(conditions))


def read_only(path):
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)


def bounded_query(db, sql, parameters, timeout_seconds):
    started = time.monotonic()
    db.set_progress_handler(lambda: int(time.monotonic()-started >= timeout_seconds), 1000)
    try:
        return db.execute(sql, parameters).fetchall()
    finally:
        db.set_progress_handler(None, 0)


def audit(database, ledger, start='2022/09/01 00:00', end='2022/09/19 00:00', timeout_seconds=30):
    for value in (start, end):
        if datetime.strptime(value, '%Y/%m/%d %H:%M').strftime('%Y/%m/%d %H:%M') != value:
            raise ValueError('Use YYYY/MM/DD HH:MM timestamps')
    if start >= end or timeout_seconds <= 0:
        raise ValueError('Require start<end and a positive query timeout')
    started = time.monotonic()
    source, saved = read_only(database), read_only(ledger)
    report = {'audit_version': 1, 'database': str(Path(database).resolve()),
              'ledger': str(Path(ledger).resolve()), 'scope': [start, end],
              'predicate': '2..4 edges; exact bank/account closure; pairwise distinct source nodes; strictly increasing minute timestamps',
              'max_duration_minutes': None, 'query_timeout_seconds': timeout_seconds,
              'provider_calls': 0, 'evaluator_data_used': False, 'inputs_opened_read_only': True,
              'complete': False, 'passed': False, 'oracle_by_length': {}, 'errors': [],
              'limitation': 'Checks scoped structural enumeration and coverage counters; not laundering detection or model quality.'}
    try:
        metadata = dict(saved.execute('SELECT key,value FROM meta'))
        source_sha = source.execute("SELECT value FROM metadata WHERE key='source_sha256'").fetchone()[0]
        config = json.loads(metadata['config'])
        report['source_sha256'] = source_sha
        report['config_matches'] = all(config.get(key) == value for key, value in {
            'source_sha256': source_sha, 'start': start, 'end': end,
            'max_edges': 4, 'max_duration_minutes': None,
        }.items())
        oracle = set()
        for length in (2, 3, 4):
            query_started = time.monotonic()
            try:
                paths = bounded_query(source, cycle_query(length), [start, end]*length, timeout_seconds)
                oracle.update(paths)
                report['oracle_by_length'][str(length)] = {'complete': True, 'cycles': len(paths),
                    'seconds': round(time.monotonic()-query_started, 6)}
            except sqlite3.Error as error:
                report['oracle_by_length'][str(length)] = {'complete': False, 'error': str(error),
                    'seconds': round(time.monotonic()-query_started, 6)}
                report['errors'].append(f'{length}-edge oracle incomplete: {error}')
        ledger_paths = set()
        ledger_rows = saved.execute('SELECT path FROM candidates').fetchall()
        for row in ledger_rows:
            ids = json.loads(row[0])
            if not isinstance(ids, list) or not 2 <= len(ids) <= 4:
                raise ValueError('Ledger contains a malformed candidate path')
            ordinals = []
            for ident in ids:
                prefix, ordinal = ident.rsplit(':', 1)
                if prefix != source_sha or not ordinal.isdecimal() or str(int(ordinal)) != ordinal or int(ordinal) < 1:
                    raise ValueError('Ledger candidate contains a foreign or malformed transaction ID')
                ordinals.append(int(ordinal))
            ledger_paths.add(tuple(ordinals))
        coverage_queries = {
            'source_external_edges': (source, '''SELECT count(*) FROM transactions
                WHERE timestamp>=? AND timestamp<? AND
                (source_bank<>destination_bank OR source_account<>destination_account)''', [start, end]),
            'saved_seed_paths': (saved, 'SELECT count(*) FROM frontier WHERE json_array_length(path)=1', []),
            'saved_frontier_paths': (saved, 'SELECT count(*) FROM frontier', []),
            'pending_frontier_paths': (saved, 'SELECT count(*) FROM frontier WHERE done=0', []),
            'completed_paths_with_cursors': (saved, 'SELECT count(*) FROM frontier WHERE done=1 AND cursor IS NOT NULL', []),
            'retrieval_events': (saved, 'SELECT count(*) FROM events', []),
        }
        coverage = {key: bounded_query(db, sql, params, timeout_seconds)[0][0]
                    for key, (db, sql, params) in coverage_queries.items()}
        coverage['declared_seeded_edges'] = json.loads(metadata['seeded_edges'])
        coverage['declared_seeds_complete'] = json.loads(metadata['seeds_complete'])
        coverage['declared_seed_cursor'] = json.loads(metadata['seed_cursor'])
        coverage['counts_agree'] = (coverage['source_external_edges'] == coverage['saved_seed_paths'] ==
                                   coverage['declared_seeded_edges'])
        coverage['completion_agrees'] = (coverage['declared_seeds_complete'] is True and
            coverage['declared_seed_cursor'] is None and coverage['pending_frontier_paths'] == 0 and
            coverage['completed_paths_with_cursors'] == 0)
        report['coverage'] = coverage
        report['ledger_cycles'] = len(ledger_paths)
        report['ledger_duplicate_paths'] = len(ledger_rows)-len(ledger_paths)
        report['oracle_cycles'] = len(oracle)
        report['complete'] = not report['errors']
        if report['complete']:
            report['missing_from_ledger'] = sorted(oracle-ledger_paths)
            report['extra_in_ledger'] = sorted(ledger_paths-oracle)
            report['exact_path_sets_match'] = ledger_paths == oracle
            report['passed'] = (report['config_matches'] and report['exact_path_sets_match'] and
                report['ledger_duplicate_paths'] == 0 and coverage['counts_agree'] and coverage['completion_agrees'])
        else:
            report['exact_path_sets_match'] = None
    except (KeyError, ValueError, TypeError, sqlite3.Error) as error:
        report['errors'].append(str(error))
        report['complete'], report['passed'] = False, False
    finally:
        source.close()
        saved.close()
    report['seconds'] = round(time.monotonic()-started, 6)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', default='2022/09/01 00:00')
    parser.add_argument('--end', default='2022/09/19 00:00')
    parser.add_argument('--timeout-seconds', type=float, default=30)
    args = parser.parse_args()
    report = audit(args.database, args.ledger, args.start, args.end, args.timeout_seconds)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
