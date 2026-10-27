import json
import sqlite3
import tempfile
from pathlib import Path
import unittest
from batch_agent import BatchAgent
from model import ProviderError

class Scripted:
    def complete(self,**request):
        name=request['tools'][0]['function']['name'];payload=json.loads(request['messages'][-1]['content'])
        if name=='choose_directions':answer={'scope_ids':[],'reason':'Enumerate known frontier.'}
        else:answer={'decisions':[{'id':p['id'],'status':'insufficient_evidence','reason':'Fixture, no economic conclusion.'}for p in payload['verified_paths']],'limitations':['Not a detection evaluation.']}
        return {'message':{'tool_calls':[{'function':{'name':name,'arguments':json.dumps(answer)}}]},'finish_reason':'tool_calls','usage':{'total_tokens':20}}

class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=self.root/'source.sqlite';self.agent=None
        with sqlite3.connect(self.source) as c:
            c.executescript("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);INSERT INTO metadata VALUES('source_sha256','fixture');CREATE TABLE transactions(row_id INTEGER PRIMARY KEY,timestamp TEXT,source_bank TEXT,source_account TEXT,destination_bank TEXT,destination_account TEXT,paid_amount REAL,paid_currency TEXT,received_amount REAL,received_currency TEXT,payment_format TEXT);")
            c.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?)',[(1,'2022/09/01 00:01','1','A','1','B',100,'USD',100,'USD','Wire'),(2,'2022/09/01 00:02','1','B','1','C',99,'USD',99,'USD','Wire'),(3,'2022/09/01 00:03','1','C','1','A',98,'USD',98,'USD','Wire'),(4,'2022/09/01 00:04','1','X','1','Y',100,'USD',100,'USD','Wire')])
    def tearDown(self):
        if self.agent:self.agent.close()
        self.tmp.cleanup()
    def make(self,**kw):
        self.agent=BatchAgent(self.root/'run',self.source,model=kw.pop('model',Scripted()),min_interval=0,**kw);return self.agent
    def test_cross_checkpoint_path_resume_and_disconnected_seed(self):
        a=self.make(burst_pages=1);r=a.run_batches(1);self.assertEqual(r['status'],'paused_checkpoint',r)
        first=[tuple(r)for r in a.db.execute('SELECT * FROM pages')];a.close();self.agent=None
        a=self.make();r=a.run_batches(20);self.assertEqual(r['status'],'complete',r)
        self.assertEqual([tuple(r)for r in a.db.execute('SELECT * FROM pages LIMIT 1')],first)
        self.assertEqual(r['rows_presented_for_review'],4)
        from batch_audit import audit
        self.assertEqual(audit(a.directory,self.source)['status'],'passed')
        packets=[p for row in a.db.execute('SELECT packets FROM batch_jobs')for p in json.loads(row[0])]
        self.assertTrue(any(len(p['ids'])==3 and any(x['cycle']for x in p['paths'])for p in packets))
        self.assertEqual(a.db.execute('SELECT count(*) FROM components').fetchone()[0],2)
        for row in a.db.execute('SELECT request FROM agent_calls'):
            req=json.loads(row[0]);self.assertLessEqual(len(json.dumps(req).encode())+2400+2048,a.config['context_budget'])
    def test_full_run_exhausts_disconnected_source_with_review(self):
        from batch_audit import audit
        a=self.make(max_calls=1,burst_pages=1);a.enable_full_run()
        result=a.run_batches(None)
        self.assertEqual(result['status'],'complete',result)
        self.assertGreater(result['usage']['calls'],1)
        self.assertEqual(result['rows_presented_for_review'],4)
        self.assertEqual(audit(a.directory,self.source)['status'],'passed')
        a.close();self.agent=None;a=self.make();self.assertTrue(a.limits['full_run'])
    def test_review_failure_blocks_further_navigation(self):
        class FailReview(Scripted):
            def complete(self,**request):
                if request['tools'][0]['function']['name']=='review_evidence':raise ProviderError(500)
                return super().complete(**request)
        a=self.make(model=FailReview());r=a.run_batches(5)
        self.assertEqual(r['status'],'waiting_for_provider');self.assertEqual(a.db.execute("SELECT count(*) FROM agent_calls WHERE role='batch-navigator'").fetchone()[0],1)
        self.assertEqual(a.batch['phase'],'review')
    def test_retrieval_transaction_rolls_back(self):
        a=self.make();a.choose();original=a.scan._step
        def broken(*args):original(*args);raise RuntimeError('simulated crash')
        a.scan._step=broken;r=a.run_batches();self.assertEqual(r['status'],'paused_error')
        self.assertEqual(a.scan.get('pages'),0);self.assertEqual(a.batch['phase'],'retrieve')
        a.scan._step=original;r=a.run_batches();self.assertEqual(r['status'],'paused_checkpoint',r)
    def test_received_review_response_reused_after_interruption(self):
        a=self.make();a.choose();a.retrieve();a.prepare();original=a.call
        def interrupted(*args):
            original(*args)
            raise RuntimeError('Interrupted after durable response')
        a.call=interrupted;r=a.run_batches();self.assertEqual(r['status'],'paused_error')
        calls=a.usage()['calls'];a.call=original;r=a.run_batches()
        self.assertEqual(r['status'],'paused_checkpoint',r);self.assertEqual(a.usage()['calls'],calls)
    def test_continuous_recovers_timeout_and_truncation_without_losing_rows(self):
        class Flaky(Scripted):
            attempts=0
            def complete(self,**request):
                self.attempts+=1
                if self.attempts==1:raise TimeoutError('read timed out')
                if self.attempts==3:return {'message':{'content':'incomplete'},'finish_reason':'length','usage':{'total_tokens':10}}
                assert request['max_tokens'] is None
                return super().complete(**request)
        a=self.make(model=Flaky());a.enable_continuous();a.wait_retry=lambda delay:None
        result=a.run_batches(None)
        self.assertEqual(result['status'],'complete',result);self.assertEqual(result['rows_presented_for_review'],4)
        self.assertEqual(a.db.execute('SELECT count(*) FROM batch_recovery').fetchone()[0],2)
        from batch_audit import audit
        self.assertEqual(audit(a.directory,self.source)['status'],'passed')
    def test_split_keeps_whole_paths_and_completed_receipts(self):
        a=self.make();a.choose();a.retrieve();a.prepare()
        job=a.batch['job'];packets=json.loads(a.db.execute('SELECT packets FROM batch_jobs WHERE id=?',(job,)).fetchone()[0])
        path=next(p for packet in packets for p in packet['paths'])
        # Two overlapping complete paths remain intact in separate packets.
        second={**path,'id':'test-second','ids':list(path['ids'])}
        with a.db:a.db.execute('UPDATE batch_jobs SET packets=? WHERE id=?',(json.dumps([{'ids':path['ids'],'paths':[path,second]}]),job))
        self.assertTrue(a.split_pending_review())
        parts=json.loads(a.db.execute('SELECT packets FROM batch_jobs WHERE id=?',(job,)).fetchone()[0])
        self.assertEqual(len(parts),2)
        self.assertTrue(all(p['ids']==path['ids'] and len(p['paths'])==1 for p in parts))
        self.assertEqual(a.db.execute('SELECT count(*) FROM batch_receipts').fetchone()[0],0)
    def test_continuous_does_not_retry_invalid_credentials(self):
        class Denied:
            def complete(self,**request):raise ProviderError(401)
        a=self.make(model=Denied());a.enable_continuous();a.wait_retry=lambda delay:self.fail('Must not retry credentials')
        result=a.run_batches(None);self.assertEqual(result['usage']['calls'],1)
        self.assertEqual(a.db.execute('SELECT count(*) FROM batch_recovery').fetchone()[0],0)
    def test_empty_path_schema_does_not_force_zero_length_array(self):
        from batch_agent import review_definition
        schema=review_definition([])['parameters']['properties']['decisions']
        self.assertNotIn('minItems',schema);self.assertNotIn('maxItems',schema)
    def test_audit_rejects_corrupted_prompt(self):
        from batch_audit import audit
        a=self.make();a.run_batches();self.assertEqual(audit(a.directory,self.source)['status'],'passed')
        r=a.db.execute("SELECT id,request FROM agent_calls WHERE role='batch-reviewer' LIMIT 1").fetchone()
        request=json.loads(r['request']);payload=json.loads(request['messages'][-1]['content']);payload['rows'][0][6]=99999
        request['messages'][-1]['content']=json.dumps(payload)
        with a.db:a.db.execute('UPDATE agent_calls SET request=? WHERE id=?',(json.dumps(request),r['id']))
        with self.assertRaisesRegex(ValueError,'Prompt rows'):audit(a.directory,self.source)
    def test_ceiling_comparison_same_evidence_and_token_bound(self):
        results=[]
        for ceiling in (150,500,1500):
            a=BatchAgent(self.root/str(ceiling),self.source,model=Scripted(),row_ceiling=ceiling,min_interval=0)
            try:
                r=a.run_batches(10);self.assertEqual(r['status'],'complete',r);results.append((r['rows'],r['paths_assessed']))
            finally:a.close()
        self.assertEqual(len(set(results)),1)

if __name__=='__main__':unittest.main()
