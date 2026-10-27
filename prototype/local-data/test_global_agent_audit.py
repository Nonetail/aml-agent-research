import json
import sqlite3
import tempfile
from pathlib import Path
import unittest
from global_scan import Scan
from global_agent_audit import audit,AuditFailure
from replay_audit import compact


class GlobalAgentAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'source.sqlite';self.ledger=self.root/'ledger.sqlite'
        db=sqlite3.connect(self.source)
        db.executescript('''CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);INSERT INTO metadata VALUES('source_sha256','fixture');
        CREATE TABLE transactions(row_id INTEGER PRIMARY KEY,timestamp TEXT,source_bank TEXT,source_account TEXT,destination_bank TEXT,destination_account TEXT,paid_amount REAL,paid_currency TEXT,received_amount REAL,received_currency TEXT,payment_format TEXT);''')
        db.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?)',[(1,'2022/09/01 00:01','1','A','1','B',10,'USD',10,'USD','Wire'),(2,'2022/09/01 00:02','1','A','1','C',20,'USD',20,'USD','Wire')]);db.commit();db.close()
        scan=Scan(self.ledger,self.source,page_rows=1)
        scan.db.executescript('''CREATE TABLE agent_calls(id INTEGER PRIMARY KEY,role TEXT,request TEXT,response TEXT,status TEXT,error TEXT,reserved_tokens INT,charged_tokens INT);
        CREATE TABLE agent_events(id INTEGER PRIMARY KEY,call_id INTEGER UNIQUE,kind TEXT,body TEXT);
        CREATE TABLE agent_reviews(job_id TEXT PRIMARY KEY,context TEXT,completed TEXT);''')
        with scan.db:
            scan.next_component();scan.db.execute('INSERT INTO agent_events(call_id,kind,body) VALUES(NULL,?,?)',('seed',json.dumps({'row_id':1,'component_id':1,'before':[],'after':['T1']})))
        self.scan=scan

    def tearDown(self):self.scan.close();self.temp.cleanup()

    def navigate(self):
        scan=self.scan;row=dict(scan.db.execute('SELECT * FROM source.transactions WHERE row_id=1').fetchone());row['transaction_id']='fixture:'+str(row.pop('row_id'))
        payload={'source_sha256':'fixture','scope':[scan.start,scan.end],'rows':[compact(row)],'frontier':scan.frontier()}
        definition={'name':'navigate','parameters':{'type':'object','properties':{k:{} for k in ('action','scope_ids','evict_ids','restore_ids','summary')}}}
        req={'messages':[{'role':'user','content':json.dumps(payload)}],'tools':[{'type':'function','function':definition}]}
        answer={'action':'expand','scope_ids':[2],'evict_ids':[],'restore_ids':[],'summary':''}
        response={'message':{'tool_calls':[{'function':{'name':'navigate','arguments':json.dumps(answer)}}]},'finish_reason':'tool_calls'}
        with scan.db:
            scan._step(2)
            scan.db.execute('INSERT INTO agent_calls VALUES(1,?,?,?,?,?,?,?)',('navigator',json.dumps(req),json.dumps(response),'applied',None,100,10))
            scan.db.execute('INSERT INTO agent_events VALUES(2,1,?,?)',('navigate',json.dumps({'before':['T1'],'after':['T1'],'page_ids':[1],'page_limits':[1]})))

    def review_seed(self):
        scan=self.scan;job=scan.claim_review();row=dict(scan.db.execute('SELECT * FROM source.transactions WHERE row_id=1').fetchone());row['transaction_id']='fixture:'+str(row.pop('row_id'))
        context={'evidence':{'T1':row},'findings':[],'coverage':{'eligible_start_edges':0,'selected_paths':0,'deduplicated_subpaths':0,'omitted_start_edges':0},'packets':[{'view':['T1'],'paths':[]}],'revision':1,'component_id':1}
        payload={'source_sha256':'fixture','scope':[scan.start,scan.end],'rows':[compact(row)],'verified_paths':[],'job_id':job['id'],'revision':1}
        req={'messages':[{'role':'user','content':json.dumps(payload)}],'tools':[{'function':{'name':'assess_verified_paths','parameters':{'type':'object','properties':{'decisions':{'type':'array','items':{}}}}}}]}
        answer={'decisions':[]};response={'message':{'tool_calls':[{'function':{'name':'assess_verified_paths','arguments':json.dumps(answer)}}]}}
        with scan.db:
            scan.db.execute('INSERT INTO agent_calls VALUES(1,?,?,?,?,?,?,?)',('reviewer',json.dumps(req),json.dumps(response),'applied',None,100,10))
            scan.db.execute('INSERT INTO agent_events VALUES(2,1,?,?)',('review',json.dumps({'job_id':job['id'],'packet_index':0})))
            completed=[{'packet_index':0,'call_id':1,'assessment':answer}]
            scan.db.execute('INSERT INTO agent_reviews VALUES(?,?,?)',(job['id'],json.dumps(context),json.dumps(completed)))
            scan.db.execute("UPDATE review_jobs SET status='complete',receipt=?",(json.dumps({'kind':'global_agent'}),))

    def test_review_receipt_and_forged_completion(self):
        self.review_seed();self.assertEqual(audit(self.root,self.source)['review_packets'],1)
        with self.scan.db:self.scan.db.execute("UPDATE agent_reviews SET completed='[]'")
        with self.assertRaisesRegex(AuditFailure,'Completion journal differs'):audit(self.root,self.source)

    def test_complete_packets_can_be_audited_before_publication(self):
        self.review_seed()
        with self.scan.db:self.scan.db.execute("UPDATE review_jobs SET status='pending',receipt=NULL")
        self.assertEqual(audit(self.root,self.source)['review_packets'],1)

    def test_review_wrong_revision(self):
        self.review_seed()
        with self.scan.db:self.scan.db.execute('UPDATE review_jobs SET revision=2')
        with self.assertRaisesRegex(AuditFailure,'Stale context'):audit(self.root,self.source)

    def test_partial_seed_passes_without_claiming_completion(self):
        result=audit(self.root,self.source);self.assertEqual(result['status'],'passed');self.assertFalse(result['exploration_complete'])

    def test_page_replay_and_corrupt_digest(self):
        self.navigate();self.assertEqual(audit(self.root,self.source)['pages'],1)
        with self.scan.db:self.scan.db.execute("UPDATE pages SET digest='wrong'")
        with self.assertRaisesRegex(AuditFailure,'Source page differs'):audit(self.root,self.source)

    def test_false_applied_call_rejected(self):
        self.navigate()
        with self.scan.db:self.scan.db.execute("UPDATE agent_calls SET status='transport_error'")
        with self.assertRaisesRegex(AuditFailure,'Unapplied call'):audit(self.root,self.source)

    def test_prompt_source_corruption_rejected(self):
        self.navigate();request=json.loads(self.scan.db.execute('SELECT request FROM agent_calls').fetchone()[0]);payload=json.loads(request['messages'][0]['content']);payload['rows'][0][6]=999;request['messages'][0]['content']=json.dumps(payload)
        with self.scan.db:self.scan.db.execute('UPDATE agent_calls SET request=?',(json.dumps(request),))
        with self.assertRaisesRegex(AuditFailure,'Prompt rows differ'):audit(self.root,self.source)

if __name__=='__main__':unittest.main()
