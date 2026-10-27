import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from global_scan import Scan
from coverage_verify import audit

class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'source.sqlite';self.ledger=self.root/'ledger.sqlite'
        db=sqlite3.connect(self.source)
        db.executescript('''CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
            INSERT INTO metadata VALUES('source_sha256','fixture');
            CREATE TABLE transactions(row_id INTEGER PRIMARY KEY,timestamp TEXT,source_bank TEXT,source_account TEXT,destination_bank TEXT,destination_account TEXT);
            CREATE INDEX outgoing ON transactions(source_bank,source_account,timestamp,row_id);
            CREATE INDEX incoming ON transactions(destination_bank,destination_account,timestamp,row_id);''')
        # A cycle, a disconnected edge, a self-edge, and identical account text in another bank.
        rows=[(1,'01','1','A','1','B'),(2,'01','1','B','1','C'),(3,'02','1','C','1','A'),
              (4,'03','1','X','1','Y'),(5,'04','1','Z','1','Z'),(6,'05','2','A','2','B')]
        db.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?)',[(i,'2022/09/01 00:'+t,*rest)for i,t,*rest in rows]);db.commit();db.close()
    def tearDown(self):self.temp.cleanup()
    def open(self,**kwargs):return Scan(self.ledger,self.source,page_rows=1,**kwargs)

    def test_entire_source_components_and_zero_review_claim(self):
        scan=self.open(seed=4);result=scan.run();scan.close()
        self.assertEqual(result['rows'],6)
        self.assertEqual(result['returned_rows'],12)
        self.assertEqual(result['components'],{'complete':4})
        self.assertEqual(result['awaiting_review_rows'],6)
        self.assertFalse(result['graph_review_complete'])
        self.assertEqual(audit(self.ledger,self.source)['status'],'passed')

    def test_reopen_preserves_cursors_and_does_not_repeat_committed_pages(self):
        scan=self.open();scan.run(max_pages=3)
        before=[tuple(r)for r in scan.db.execute('SELECT * FROM pages ORDER BY id')];scan.close()
        scan=self.open();result=scan.run()
        after=[tuple(r)for r in scan.db.execute('SELECT * FROM pages ORDER BY id')]
        self.assertEqual(after[:len(before)],before);self.assertEqual(result['returned_rows'],12)
        scan.close();self.assertEqual(audit(self.ledger,self.source)['status'],'passed')

    def test_failed_transaction_rolls_back_discovery_and_cursor(self):
        scan=self.open();scan.step();before=scan.status();original=scan.discover
        def fail(rows,component):
            original(rows,component);raise RuntimeError('injected interruption')
        scan.discover=fail
        with self.assertRaises(RuntimeError):scan.step()
        self.assertEqual(scan.status(),before);scan.close()
        scan=self.open();scan.run();scan.close()
        self.assertEqual(audit(self.ledger,self.source)['status'],'passed')

    def test_scope_is_pinned_and_exact(self):
        scan=self.open(start='2022/09/01 00:03',end='2022/09/01 00:05');result=scan.run();scan.close()
        self.assertEqual(result['rows'],2)
        self.assertEqual(audit(self.ledger,self.source)['status'],'passed')
        with self.assertRaisesRegex(ValueError,'Scope differs'):self.open(start='2022/09/01 00:00')

    def test_pending_scope_selection_and_completed_scope_rejection(self):
        scan=self.open();scan.step();scope=scan.frontier()[-1]['id'];scan.step(scope)
        complete=scan.db.execute("SELECT id FROM scopes WHERE status='complete' LIMIT 1").fetchone()[0]
        with self.assertRaisesRegex(ValueError,'advertised'):scan.step(complete)
        scan.run();scan.close();self.assertEqual(audit(self.ledger,self.source)['status'],'passed')

    def test_review_is_versioned_and_requires_audited_complete_packet(self):
        scan=self.open();scan.step();job=scan.claim_review()
        self.assertEqual(scan.claim_review()['id'],job['id'])
        case=self.root/'case';case.mkdir()
        state={'source_sha256':'fixture','scope':[scan.start,scan.end],'status':'deferred_by_query_page_budget','calls':[],
               'evidence':{'T'+str(i):{}for i in job['row_ids']},'review_queue':{'completed':[]}}
        (case/'state.json').write_text(json.dumps(state))
        scan.prepare_review(job['id'],case)
        state['calls']=[{'role':'reviewer'}];(case/'state.json').write_text(json.dumps(state))
        with patch('replay_audit.audit',return_value={'status':'passed'}):
            with self.assertRaisesRegex(ValueError,'all requested rows'):scan.complete_review(job['id'],case)
            state['review_queue']['completed']=[{'view':['T'+str(i) for i in job['row_ids']]}]
            (case/'state.json').write_text(json.dumps(state));scan.complete_review(job['id'],case)
        self.assertEqual(scan.status()['reviewed_rows_in_current_context'],len(job['row_ids']))
        scan.run()
        self.assertEqual(scan.status()['reviewed_rows_in_current_context'],0)
        with self.assertRaisesRegex(ValueError,'stale'):scan.complete_review(job['id'],case)
        fresh=scan.claim_review();self.assertNotEqual(fresh['id'],job['id'])
        with self.assertRaisesRegex(ValueError,'before any reviewer'):scan.prepare_review(fresh['id'],case)
        with self.assertRaisesRegex(ValueError,'bound'):scan.complete_review(fresh['id'],case)
        scan.close()

    def test_real_replayable_review_receipt_completes_bound_job(self):
        import test_chunks
        from chunk_case import Case,SCOPE
        fixture=test_chunks.ChunkTests();fixture.setUp()
        scan=None
        try:
            scan=Scan(self.root/'review-ledger.sqlite',fixture.database,start=SCOPE[0],end=SCOPE[1])
            scan.run();job=scan.claim_review(limit=1)
            case=Case(fixture.run,test_chunks.ScriptedNavigator(),fixture.database)
            while case.state['status']=='active':case.segment()
            case.close()
            scan.prepare_review(job['id'],fixture.run)
            case=Case(fixture.run,test_chunks.ScriptedNavigator(),fixture.database)
            case.review();case.close()
            scan.complete_review(job['id'],fixture.run)
            self.assertEqual(scan.status()['reviewed_rows_in_current_context'],1)
            self.assertFalse(scan.status()['graph_review_complete'])
        finally:
            if scan:scan.close()
            fixture.tearDown()

if __name__=='__main__':unittest.main()
