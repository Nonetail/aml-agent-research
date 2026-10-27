"""Tests the evaluator preparation contract, without source data or model access."""
import csv
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cycle_benchmark import build, choose_bundles, cycle_properties, nearest_count, resolve_catalogue, short_account_clusters


SCHEMA = '''CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE accounts(bank TEXT,account TEXT,raw_bank TEXT,bank_name TEXT,entity_id TEXT,entity_name TEXT,PRIMARY KEY(bank,account));
CREATE TABLE transactions(row_id INTEGER PRIMARY KEY,timestamp TEXT NOT NULL,source_bank TEXT,source_account TEXT,
 destination_bank TEXT,destination_account TEXT,received_amount TEXT,received_currency TEXT,paid_amount TEXT,paid_currency TEXT,
 payment_format TEXT,raw_source_bank TEXT,raw_destination_bank TEXT);
CREATE INDEX outgoing ON transactions(source_bank,source_account,timestamp,row_id);
CREATE INDEX incoming ON transactions(destination_bank,destination_account,timestamp,row_id);'''


def edge(row_id, source, destination, timestamp):
    return {'row_id': row_id, 'timestamp': timestamp, 'source_bank': source[0], 'source_account': source[1],
            'destination_bank': destination[0], 'destination_account': destination[1]}


def fixture(root):
    source_path, labels_path, patterns_path = root / 'source.sqlite', root / 'labels.sqlite', root / 'patterns.txt'
    source, labels = sqlite3.connect(source_path), sqlite3.connect(labels_path)
    source.executescript(SCHEMA)
    source.execute("INSERT INTO metadata VALUES('source_sha256','fixture')")
    labels.execute('CREATE TABLE labels(row_id INTEGER PRIMARY KEY,is_laundering INTEGER NOT NULL)')
    endpoints = [('a', 'b'), ('b', 'a'), ('c', 'd'), ('d', 'e'), ('e', 'c')]
    records = []
    for row_id in range(1, 101):
        a, b = endpoints[row_id - 1] if row_id <= 5 else (f'x{row_id}', f'y{row_id}')
        raw = [f'2022/09/01 {row_id // 60:02}:{row_id % 60:02}', '001', a, '001', b,
               '10.00', 'US Dollar', '10.00', 'US Dollar', 'ACH', str(int(row_id <= 20))]
        records.append(raw)
        source.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (row_id, raw[0], '1', a, '1', b, *raw[5:10], raw[1], raw[3]))
        labels.execute('INSERT INTO labels VALUES(?,?)', (row_id, int(row_id <= 20)))
        for account in (a, b):
            source.execute('INSERT OR IGNORE INTO accounts VALUES(?,?,?,?,?,?)', ('1', account, '001', 'Bank', account, account))
    source.commit(); labels.commit(); source.close(); labels.close()
    with patterns_path.open('w', newline='') as f:
        writer = csv.writer(f)
        f.write('BEGIN LAUNDERING ATTEMPT - CYCLE\n')
        writer.writerows(records[:2])
        f.write('END LAUNDERING ATTEMPT\nBEGIN LAUNDERING ATTEMPT - CYCLE\n')
        writer.writerows(records[2:5])
    return source_path, labels_path, patterns_path


class CycleBenchmarkTests(unittest.TestCase):
    def test_exact_rounding_and_small_population_infeasible(self):
        self.assertEqual(nearest_count(300000, 5177, 5078345), 306)
        self.assertEqual(nearest_count(300000, 287, 5078345), 17)
        self.assertEqual(nearest_count(300000, 79, 5078345), 5)
        self.assertEqual(nearest_count(1, 1, 2), 1)
        bundle = {'seed_rows': {1, 2}, 'complete': {1, 2}}
        with self.assertRaisesRegex(ValueError, 'complete eligible short cycle'):
            choose_bundles([bundle], {1, 2}, {1, 2}, {1, 2}, {'cycle': 1, 'short': 1, 'positive': 2}, 1)

    def test_bank_account_identity_and_strict_chronology(self):
        rows = [edge(1, ('1', 'a'), ('2', 'a'), '2022/09/01 00:02'),
                edge(2, ('2', 'a'), ('3', 'a'), '2022/09/01 00:03'),
                edge(3, ('3', 'a'), ('1', 'a'), '2022/09/01 00:01')]
        result = cycle_properties(rows)
        self.assertTrue(result['eligible_short'])
        self.assertEqual(result['temporal_row_ids'], [3, 1, 2])
        rows[0]['timestamp'] = rows[1]['timestamp']
        self.assertFalse(cycle_properties(rows)['strict_temporal'])
        rows[0]['destination_bank'] = '99'
        self.assertFalse(cycle_properties(rows)['closed'])

    def test_context_positives_are_kept_and_infeasible_quota_is_rejected(self):
        bundle = {'seed_rows': {1, 2}, 'complete': {1, 2, 10, 11}}
        chosen, rows = choose_bundles([bundle], {1, 2}, {1, 2}, {1, 2, 10},
                                     {'cycle': 2, 'short': 2, 'positive': 3}, 1)
        self.assertEqual(rows, {1, 2, 10, 11})
        self.assertEqual(chosen, [bundle])
        with self.assertRaisesRegex(ValueError, 'complete eligible short cycle'):
            choose_bundles([bundle], {1, 2}, {1, 2}, {1, 2, 10},
                           {'cycle': 2, 'short': 2, 'positive': 2}, 1)

    def test_independent_selection_uses_full_transitive_account_clusters(self):
        groups = [{'group_id': 1, 'eligible_short': True, 'accounts': [('1', 'a'), ('1', 'b')]},
                  {'group_id': 2, 'eligible_short': True, 'accounts': [('1', 'b'), ('1', 'c')]},
                  {'group_id': 3, 'eligible_short': True, 'accounts': [('1', 'c'), ('1', 'd')]},
                  {'group_id': 4, 'eligible_short': True, 'accounts': [('2', 'a'), ('2', 'b')]}]
        self.assertEqual(short_account_clusters(groups), {1: 1, 2: 1, 3: 1, 4: 4})
        row_groups = [{1, 2}, {3, 4, 5}, {6, 7}]
        bundles = [{'seed_rows': rows, 'complete': rows} for rows in row_groups]
        population = set(range(1, 8))
        _, rows = choose_bundles(bundles, population, population, population,
                                 {'cycle': 5, 'short': 5, 'positive': 5}, 1,
                                 [(row_groups[0], 1), (row_groups[1], 1), (row_groups[2], 4)])
        self.assertEqual(rows, {3, 4, 5, 6, 7})

    def test_repeated_account_and_backwards_legs(self):
        rows = [edge(1, ('1', 'a'), ('1', 'b'), '2022/09/01 00:01'),
                edge(2, ('1', 'b'), ('1', 'a'), '2022/09/01 00:03'),
                edge(3, ('1', 'a'), ('1', 'b'), '2022/09/01 00:02'),
                edge(4, ('1', 'b'), ('1', 'a'), '2022/09/01 00:04')]
        result = cycle_properties(rows)
        self.assertTrue(result['closed'])
        self.assertFalse(result['simple'])
        self.assertFalse(result['strict_temporal'])

    def test_source_ambiguity_fails_without_deduplicating_parallel_edges(self):
        with tempfile.TemporaryDirectory() as name:
            source_path, _, patterns = fixture(Path(name))
            db = sqlite3.connect(source_path)
            row = list(db.execute('SELECT * FROM transactions WHERE row_id=1').fetchone())
            row[0] = 101
            db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', row)
            db.commit()
            with self.assertRaisesRegex(ValueError, 'exact source match count 2'):
                resolve_catalogue(db, patterns, set(range(1, 21)))
            db.close()

    def test_build_preserves_edges_nodes_ratios_and_answer_boundary(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source, labels, patterns = fixture(root)
            before_source = source.read_bytes()
            before_labels = labels.read_bytes()
            result = build(source, labels, patterns, root / 'first', size=60, seed=7)
            second = build(source, labels, patterns, root / 'second', size=60, seed=7)
            self.assertEqual(result['integer_targets'], {'positive': 12, 'cycle': 3, 'short': 3})
            self.assertEqual(result['partial_publisher_groups'], [])
            self.assertEqual(result['artifacts'], second['artifacts'])
            self.assertEqual(source.read_bytes(), before_source)
            self.assertEqual(labels.read_bytes(), before_labels)
            runtime = sqlite3.connect(root / 'first/runtime/transactions.sqlite')
            actual_tables = {r[0] for r in runtime.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            self.assertEqual(actual_tables, {'transactions', 'accounts', 'metadata'})
            columns = {r[1] for t in actual_tables for r in runtime.execute(f'PRAGMA table_info({t})')}
            self.assertFalse(columns & {'is_laundering', 'family', 'eligible_short', 'selection_role'})
            self.assertEqual(runtime.execute('SELECT COUNT(*) FROM transactions').fetchone()[0], 60)
            ids = {r[0] for r in runtime.execute('SELECT row_id FROM transactions')}
            self.assertTrue({3, 4, 5} <= ids)
            self.assertFalse({1, 2} & ids)
            endpoints = {tuple(r) for r in runtime.execute('SELECT source_bank,source_account FROM transactions UNION SELECT destination_bank,destination_account FROM transactions')}
            self.assertEqual(endpoints, set(runtime.execute('SELECT bank,account FROM accounts')))
            runtime.execute('ATTACH DATABASE ? AS original', (str(source),))
            self.assertEqual(runtime.execute('SELECT COUNT(*) FROM (SELECT * FROM transactions EXCEPT SELECT * FROM original.transactions)').fetchone()[0], 0)
            runtime.close()
            with self.assertRaises(FileExistsError):
                build(source, labels, patterns, root / 'first', size=60, seed=7)


if __name__ == '__main__':
    unittest.main()
