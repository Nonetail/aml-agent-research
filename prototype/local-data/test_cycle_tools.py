from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cycle_tools import CycleTools


START = '2022/09/02 00:00'
END = '2022/09/03 00:00'


class CycleToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'transactions.sqlite'
        self.db = sqlite3.connect(self.path)
        self.db.executescript('''
            CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO metadata VALUES('source_sha256','fixture');
            CREATE TABLE transactions(row_id INTEGER PRIMARY KEY, timestamp TEXT,
                source_bank TEXT, source_account TEXT, destination_bank TEXT, destination_account TEXT,
                received_amount TEXT, received_currency TEXT, paid_amount TEXT, paid_currency TEXT,
                payment_format TEXT, raw_source_bank TEXT, raw_destination_bank TEXT,
                is_laundering INTEGER);
            CREATE INDEX outgoing ON transactions(source_bank,source_account,timestamp,row_id);
        ''')
        # The extra label column deliberately tests the evidence column allowlist.
        edges = [
            (1, 0, '1', 'A', '1', 'B'),
            (2, 1, '1', 'B', '1', 'D'),
            (3, 2, '1', 'B', '1', 'C'),
            (4, 3, '1', 'C', '1', 'A'),
            (5, 4, '1', 'B', '1', 'A'),
            (6, 5, '1', 'B', '1', 'E'),
            (7, 6, '1', 'E', '1', 'A'),
            (8, 7, '1', 'A', '1', 'A'),
            (9, 1, '2', 'B', '1', 'A'),
            (10, 0, '1', 'B', '1', 'A'),
            (11, 3, '1', 'C', '1', 'B'),
            (12, 4, '1', 'B', '1', 'B'),
            (13, 2, '1', 'D', '1', 'F'),
            (14, 3, '1', 'F', '1', 'A'),
            (15, 3, '1', 'F', '1', 'G'),
            (16, 0, '2', 'A', '1', 'B'),
            (17, 2, '1', 'B', '1', 'C'),
            (18, -1, '1', 'A', '1', 'B'),
            (19, 1440, '1', 'B', '1', 'A'),
            (20, 1441, '1', 'A', '1', 'B'),
        ]
        rows = []
        for ident, minute, source_bank, source, destination_bank, destination in edges:
            time = (datetime.strptime(START, '%Y/%m/%d %H:%M')+timedelta(minutes=minute)).strftime('%Y/%m/%d %H:%M')
            received_currency = 'EUR' if ident == 4 else 'USD'
            rows.append((ident, time, source_bank, source, destination_bank, destination,
                         '99.99', received_currency, '100.00', 'USD', 'ACH', source_bank, destination_bank,
                         0 if ident == 5 else 1))
        self.db.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
        self.db.commit()
        self.db.close()
        self.tools = CycleTools(self.path, START, END)

    def tearDown(self):
        self.tools.close()
        self.temp.cleanup()

    @staticmethod
    def ids(*numbers):
        return [f'fixture:{number}' for number in numbers]

    def test_seed_pagination_covers_every_external_scoped_edge_once(self):
        cursor, seen = None, []
        while True:
            page = self.tools.seed_page(limit=2, cursor=cursor)
            seen.extend(row['transaction_id'] for row in page['rows'])
            self.assertEqual(page['complete'], page['next_cursor'] is None)
            if page['complete']:
                break
            cursor = page['next_cursor']
        expected = self.ids(*[n for n in range(1, 18) if n not in (8, 12)])
        self.assertEqual(seen, expected)

    def test_competing_branches_and_cycles_survive_every_page(self):
        cursor, returned, continuations, cycles = None, [], [], []
        while True:
            result = self.tools.expand_frontier([self.ids(1)], row_budget=1, cursors=[cursor])
            branch = result['branches'][0]
            returned.extend(row['transaction_id'] for row in branch['rows'])
            continuations.extend(branch['continuations'])
            cycles.extend(branch['cycles'])
            if branch['complete']:
                self.assertIsNone(branch['next_cursor'])
                break
            self.assertIsNotNone(branch['next_cursor'])
            cursor = branch['next_cursor']
        self.assertEqual(returned, self.ids(2, 3, 17, 5, 6))
        self.assertEqual(continuations, [self.ids(1, 2), self.ids(1, 3), self.ids(1, 17), self.ids(1, 6)])
        self.assertEqual(cycles, [self.ids(1, 5)])

    def test_four_edge_cycle_excludes_nonclosing_fourth_edge(self):
        branch = self.tools.expand_frontier([self.ids(1, 2, 13)])['branches'][0]
        self.assertEqual(branch['cycles'], [self.ids(1, 2, 13, 14)])
        self.assertEqual(branch['continuations'], [])
        self.assertTrue(branch['complete'])
        self.assertTrue(self.tools.verify_cycle(branch['cycles'][0])['valid'])

    def test_navigation_excludes_repeated_internal_nodes(self):
        branch = self.tools.expand_frontier([self.ids(1, 3)])['branches'][0]
        self.assertEqual(branch['cycles'], [self.ids(1, 3, 4)])
        self.assertEqual(branch['continuations'], [])
        result = self.tools.verify_cycle(self.ids(1, 3, 11, 5))
        self.assertFalse(result['valid'])
        self.assertIn('Repeated internal bank/account node', result['errors'])

    def test_bank_identity_ties_nonclosure_and_self_edges_are_invalid(self):
        for ids in (self.ids(1, 9), self.ids(16, 5), self.ids(1, 10), self.ids(1, 3), self.ids(1, 5, 8)):
            with self.subTest(ids=ids):
                self.assertFalse(self.tools.verify_cycle(ids)['valid'])

    def test_currency_changes_and_label_zero_controls_do_not_change_topology(self):
        cross_currency = self.tools.verify_cycle(self.ids(1, 3, 4))
        self.assertTrue(cross_currency['valid'])
        self.assertEqual(cross_currency['currencies'], ['EUR', 'USD'])
        self.assertEqual(cross_currency['elapsed_minutes'], 3)
        self.assertTrue(self.tools.verify_cycle(self.ids(1, 5))['valid'])
        self.assertIn('does not establish the same funds', cross_currency['limitation'])
        self.assertNotIn('is_laundering', json.dumps(cross_currency))

    def test_duplicate_edge_is_rejected_and_canonical_ids_are_required(self):
        self.assertIn('Repeated transaction edge', self.tools.verify_cycle(self.ids(1, 1))['errors'])
        for ids in (['fixture:01', 'fixture:5'], ['other:1', 'fixture:5'], ['fixture:0', 'fixture:5']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.tools.verify_cycle(ids)

    def test_evidence_order_missing_ids_and_cutoff_are_explicit(self):
        result = self.tools.get_transactions(self.ids(4, 1, 4, 18, 19, 999))
        self.assertEqual([row['transaction_id'] for row in result['rows']], self.ids(4, 1, 4))
        self.assertEqual(result['unavailable_ids'], self.ids(18, 19, 999))
        invalid = self.tools.verify_cycle(self.ids(1, 19))
        self.assertFalse(invalid['valid'])
        self.assertEqual(invalid['unavailable_ids'], self.ids(19))

    def test_duration_is_optional_and_inclusive_at_boundary(self):
        self.assertTrue(self.tools.verify_cycle(self.ids(1, 6, 7))['valid'])
        bounded = CycleTools(self.path, START, END, max_duration_minutes=3)
        try:
            self.assertTrue(bounded.verify_cycle(self.ids(1, 3, 4))['valid'])
            self.assertFalse(bounded.verify_cycle(self.ids(1, 6, 7))['valid'])
            branch = bounded.expand_frontier([self.ids(1, 3)])['branches'][0]
            self.assertEqual(branch['cycles'], [self.ids(1, 3, 4)])
            self.assertTrue(branch['complete'])
        finally:
            bounded.close()

    def test_resume_cursors_work_after_reopening(self):
        seed = self.tools.seed_page(limit=1)
        first = self.tools.expand_frontier([self.ids(1)], row_budget=2)['branches'][0]
        identity = self.tools.identity
        self.tools.close()
        self.tools = CycleTools(self.path, START, END)
        self.assertEqual(self.tools.identity, identity)
        next_seed = self.tools.seed_page(limit=1, cursor=seed['next_cursor'])
        self.assertEqual(next_seed['rows'][0]['transaction_id'], 'fixture:2')
        resumed = self.tools.expand_frontier([self.ids(1)], row_budget=20, cursors=[first['next_cursor']])['branches'][0]
        self.assertEqual([row['transaction_id'] for row in resumed['rows']], self.ids(17, 5, 6))
        self.assertTrue(resumed['complete'])

    def test_cursors_reject_other_queries_scopes_policies_and_copied_sources(self):
        seed_cursor = self.tools.seed_page(limit=1)['next_cursor']
        continuation_cursor = self.tools.expand_frontier([self.ids(1)], row_budget=1)['branches'][0]['next_cursor']
        with self.assertRaises(ValueError):
            self.tools.seed_page(cursor=continuation_cursor)
        with self.assertRaises(ValueError):
            self.tools.expand_frontier([self.ids(16)], cursors=[continuation_cursor])
        other_scope = CycleTools(self.path, START, '2022/09/02 01:00')
        other_policy = CycleTools(self.path, START, END, max_edges=3)
        copied = Path(self.temp.name)/'copy.sqlite'
        copied.write_bytes(self.path.read_bytes())
        other_source = CycleTools(copied, START, END)
        for other in (other_scope, other_policy, other_source):
            try:
                with self.assertRaises(ValueError):
                    other.seed_page(cursor=seed_cursor)
            finally:
                other.close()

    def test_completed_and_empty_branches_are_explicit_under_batch_budget(self):
        result = self.tools.expand_frontier([self.ids(1), self.ids(15)], row_budget=3)
        self.assertLessEqual(result['rows_returned'], 3)
        self.assertFalse(result['complete'])
        self.assertFalse(result['branches'][0]['complete'])
        self.assertTrue(result['branches'][1]['complete'])
        self.assertIsNone(result['branches'][1]['next_cursor'])
        self.assertEqual(result['branches'][1]['rows'], [])

    def test_ineligible_rows_do_not_produce_a_spurious_incomplete_cursor(self):
        bounded = CycleTools(self.path, START, END, max_duration_minutes=1)
        try:
            branch = bounded.expand_frontier([self.ids(1)], row_budget=1)['branches'][0]
            self.assertEqual([row['transaction_id'] for row in branch['rows']], self.ids(2))
            self.assertTrue(branch['complete'])
            self.assertIsNone(branch['next_cursor'])
            empty = bounded.expand_frontier([self.ids(1, 2)], row_budget=1)['branches'][0]
            self.assertEqual(empty['rows'], [])
            self.assertTrue(empty['complete'])
        finally:
            bounded.close()

    def test_closed_invalid_or_too_long_partial_paths_are_rejected(self):
        for ids in (self.ids(1, 5), self.ids(1, 3, 4), self.ids(1, 2, 13, 14), self.ids(1, 9)):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.tools.expand_frontier([ids])

    def test_source_is_read_only_and_unchanged(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.tools.seed_page()
        self.tools.expand_frontier([self.ids(1)])
        self.tools.get_transactions(self.ids(1, 3, 4))
        self.tools.verify_cycle(self.ids(1, 3, 4))
        with self.assertRaises(sqlite3.OperationalError):
            self.tools.db.execute('DELETE FROM transactions')
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()
