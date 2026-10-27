import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from coverage_verify import audit, AuditFailure


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source, self.ledger = self.root / 'source.sqlite', self.root / 'ledger.sqlite'
        with sqlite3.connect(self.source) as db:
            db.executescript('''CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
                INSERT INTO metadata VALUES('source_sha256','fixture');
                CREATE TABLE transactions(row_id INTEGER PRIMARY KEY,timestamp TEXT,source_bank TEXT,
                    source_account TEXT,destination_bank TEXT,destination_account TEXT);''')
            db.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?)', [
                (1, '2022/09/04 01:00', '1', 'A', '1', 'B'),
                (2, '2022/09/04 02:00', '1', 'B', '1', 'C'),
                (3, '2022/09/04 03:00', '2', 'A', '2', 'A'),
                (4, '2022/09/05 00:00', '1', 'A', '2', 'A')])
        with sqlite3.connect(self.ledger) as db:
            db.executescript('''CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE components(id INTEGER PRIMARY KEY,seed INTEGER,status TEXT,revision INTEGER);
                CREATE TABLE seen(row_id INTEGER PRIMARY KEY,component_id INTEGER);
                CREATE TABLE scopes(id INTEGER PRIMARY KEY,bank TEXT,account TEXT,direction TEXT,
                    component_id INTEGER,after_time TEXT,after_id INTEGER,status TEXT,pages INTEGER);
                CREATE TABLE pages(id INTEGER PRIMARY KEY,scope_id INTEGER,before_time TEXT,before_id INTEGER,
                    after_time TEXT,after_id INTEGER,returned_count INTEGER,digest TEXT,complete INTEGER);
                INSERT INTO components VALUES(1,1,'complete',2),(2,3,'complete',1);
                INSERT INTO seen VALUES(1,1),(2,1),(3,2);''')
            db.executemany('INSERT INTO meta VALUES(?,?)', [(k, json.dumps(v)) for k, v in {
                'source_sha256': 'fixture', 'start': '2022/09/04 00:00',
                'end': '2022/09/05 00:00', 'status': 'complete'}.items()])
            sid = 0
            for bank, account, owner, outgoing, incoming in [
                ('1', 'A', 1, [1], []), ('1', 'B', 1, [2], [1]),
                ('1', 'C', 1, [], [2]), ('2', 'A', 2, [3], [3])]:
                for direction, rows in [('source', outgoing), ('destination', incoming)]:
                    sid += 1
                    after_id = rows[-1] if rows else None
                    after_time = f'2022/09/04 0{after_id}:00' if rows else None
                    db.execute('INSERT INTO scopes VALUES(?,?,?,?,?,?,?,?,?)',
                        (sid, bank, account, direction, owner, after_time, after_id, 'complete', 1))
                    db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?,?,?)',
                        (sid, sid, None, None, after_time, after_id, len(rows), 'not-replayed', 1))

    def tearDown(self):
        self.temp.cleanup()

    def mutate(self, sql):
        with sqlite3.connect(self.ledger) as db:
            db.executescript(sql)

    def test_complete_exact_scope_and_composite_account_identity(self):
        result = audit(self.ledger, self.source)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual((result['source_rows'], result['accounts'], result['components']), (3, 4, 2))

    def test_missing_source_row(self):
        self.mutate('DELETE FROM seen WHERE row_id=2')
        with self.assertRaisesRegex(AuditFailure, 'missing source'):
            audit(self.ledger, self.source)

    def test_out_of_scope_row(self):
        self.mutate('INSERT INTO seen VALUES(4,1)')
        with self.assertRaisesRegex(AuditFailure, 'out-of-scope'):
            audit(self.ledger, self.source)

    def test_split_connected_component(self):
        self.mutate("INSERT INTO components VALUES(3,2,'complete',1); UPDATE seen SET component_id=3 WHERE row_id=2")
        with self.assertRaisesRegex(AuditFailure, 'different components'):
            audit(self.ledger, self.source)

    def test_merge_disconnected_components(self):
        self.mutate('UPDATE seen SET component_id=1; DELETE FROM components WHERE id=2')
        with self.assertRaisesRegex(AuditFailure, 'Disconnected graphs'):
            audit(self.ledger, self.source)

    def test_missing_empty_direction_scope(self):
        self.mutate("DELETE FROM pages WHERE scope_id=2; DELETE FROM scopes WHERE id=2")
        with self.assertRaisesRegex(AuditFailure, 'Missing account/direction'):
            audit(self.ledger, self.source)

    def test_corrupt_page_count(self):
        self.mutate('UPDATE pages SET returned_count=2 WHERE id=1')
        with self.assertRaisesRegex(AuditFailure, 'every source row'):
            audit(self.ledger, self.source)

    def test_corrupt_cursor(self):
        self.mutate("UPDATE pages SET before_time='2022/09/04 00:00',before_id=0 WHERE id=1")
        with self.assertRaisesRegex(AuditFailure, 'cursor chain'):
            audit(self.ledger, self.source)

    def test_orphaned_page(self):
        self.mutate('UPDATE pages SET scope_id=99 WHERE id=1')
        with self.assertRaises(AuditFailure):
            audit(self.ledger, self.source)

    def test_paused_is_not_certified(self):
        self.mutate('''UPDATE meta SET value='"paused"' WHERE key='status'; DELETE FROM seen WHERE row_id=2''')
        result = audit(self.ledger, self.source)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['missing_rows'], 1)


if __name__ == '__main__':
    unittest.main()
