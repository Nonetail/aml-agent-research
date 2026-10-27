from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cycle_audit import audit


START, END = '2022/09/01 00:00', '2022/09/19 00:00'


class IndependentCycleAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name)/'source.sqlite'
        self.ledger = Path(self.temp.name)/'ledger.sqlite'
        db = sqlite3.connect(self.source)
        db.executescript('''CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
            INSERT INTO metadata VALUES('source_sha256','test-source');
            CREATE TABLE transactions(row_id INTEGER PRIMARY KEY,timestamp TEXT,
                source_bank TEXT,source_account TEXT,destination_bank TEXT,destination_account TEXT);
            CREATE INDEX outgoing ON transactions(source_bank,source_account,timestamp,row_id);''')
        edges = [(1,0,'1','A','1','B'), (2,1,'1','B','1','A'), (3,2,'1','B','1','C'),
                 (4,3,'1','C','1','A'), (5,3,'1','C','1','D'), (6,4,'1','D','1','A'),
                 (7,1,'2','B','1','A'), (8,0,'1','B','1','A'), (9,3,'1','C','1','B'),
                 (10,4,'1','B','1','A'), (11,1,'1','A','1','A'), (12,2,'1','A','1','A'),
                 (13,-1,'1','A','1','B'), (14,18*24*60,'1','B','1','A')]
        for ident, minute, *nodes in edges:
            when = (datetime.strptime(START,'%Y/%m/%d %H:%M')+timedelta(minutes=minute)).strftime('%Y/%m/%d %H:%M')
            db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?)',(ident,when,*nodes))
        db.commit()
        db.close()
        self.expected = [(1,2),(1,10),(3,9),(1,3,4),(1,3,5,6)]
        db = sqlite3.connect(self.ledger)
        db.executescript('''CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE candidates(path TEXT);CREATE TABLE frontier(path TEXT,done INTEGER,cursor TEXT);
            CREATE TABLE events(kind TEXT);''')
        config = {'source_sha256':'test-source','start':START,'end':END,'max_edges':4,'max_duration_minutes':None}
        db.executemany('INSERT INTO meta VALUES(?,?)',[(key,json.dumps(value)) for key,value in
            {'config':config,'seeded_edges':10,'seeds_complete':True,'seed_cursor':None}.items()])
        db.executemany('INSERT INTO candidates VALUES(?)',[(json.dumps(self.ids(path)),) for path in self.expected])
        db.executemany('INSERT INTO frontier VALUES(?,1,NULL)',[(json.dumps(self.ids([i])),) for i in range(1,11)])
        db.execute("INSERT INTO events VALUES('fixture')")
        db.commit()
        db.close()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def ids(path):
        return [f'test-source:{i}' for i in path]

    def test_exact_sql_oracle_checks_all_lengths_and_rejects_graph_lookalikes(self):
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (self.source,self.ledger)]
        result = audit(self.source,self.ledger)
        self.assertTrue(result['passed'],result)
        self.assertEqual(result['oracle_cycles'],5)
        self.assertEqual({key:value['cycles'] for key,value in result['oracle_by_length'].items()}, {'2':3,'3':1,'4':1})
        self.assertEqual(result['coverage']['source_external_edges'],10)
        self.assertEqual(result['missing_from_ledger'],[])
        self.assertEqual(result['extra_in_ledger'],[])
        self.assertEqual([hashlib.sha256(path.read_bytes()).hexdigest() for path in (self.source,self.ledger)],before)

    def test_missing_cycle_and_invalid_extra_fail_exact_comparison(self):
        with sqlite3.connect(self.ledger) as db:
            db.execute('DELETE FROM candidates WHERE path=?',(json.dumps(self.ids((1,3,4))),))
            db.execute('INSERT INTO candidates VALUES(?)',(json.dumps(self.ids((1,3,9,10))),))
        result = audit(self.source,self.ledger)
        self.assertTrue(result['complete'])
        self.assertFalse(result['passed'])
        self.assertEqual(result['missing_from_ledger'],[(1,3,4)])
        self.assertEqual(result['extra_in_ledger'],[(1,3,9,10)])

    def test_incorrect_coverage_counts_and_pending_work_fail(self):
        with sqlite3.connect(self.ledger) as db:
            db.execute("UPDATE meta SET value='9' WHERE key='seeded_edges'")
            db.execute('UPDATE frontier SET done=0 WHERE rowid=1')
        result = audit(self.source,self.ledger)
        self.assertFalse(result['passed'])
        self.assertFalse(result['coverage']['counts_agree'])
        self.assertFalse(result['coverage']['completion_agrees'])

    def test_oracle_interruption_cannot_be_reported_as_complete_or_pass(self):
        with patch('cycle_audit.bounded_query',side_effect=sqlite3.OperationalError('interrupted')):
            result = audit(self.source,self.ledger)
        self.assertFalse(result['complete'])
        self.assertFalse(result['passed'])
        self.assertTrue(result['errors'])

    def test_rule_scope_mismatch_fails_even_when_path_sets_match(self):
        with sqlite3.connect(self.ledger) as db:
            config = json.loads(db.execute("SELECT value FROM meta WHERE key='config'").fetchone()[0])
            config['max_duration_minutes'] = 1440
            db.execute("UPDATE meta SET value=? WHERE key='config'",(json.dumps(config),))
        result = audit(self.source,self.ledger)
        self.assertFalse(result['passed'])
        self.assertTrue(result['exact_path_sets_match'])
        self.assertFalse(result['config_matches'])


if __name__ == '__main__':
    unittest.main()
