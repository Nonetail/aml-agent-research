import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from run_case import Run
from tools import Tools, HERE

class ScriptedModel:
    def __init__(self, reverse=False): self.n=0; self.reverse=reverse
    def complete(self,messages,tools=None,tool_choice='auto',max_tokens=4096):
        self.n+=1
        if self.n in (1,2):
            args={'bank':'1','account':'B','start':'2022/09/04 00:00','end':'2022/09/05 00:00','direction':'incoming' if self.n==1 else 'outgoing','limit':2}
            msg={'role':'assistant','tool_calls':[{'id':str(self.n),'type':'function','function':{'name':'fetch_transactions','arguments':json.dumps(args)}}]}
        elif self.n==3: msg={'role':'assistant','content':'INVESTIGATOR_PERSUASION_MARKER'}
        elif self.n==4:
            assert 'INVESTIGATOR_PERSUASION_MARKER' not in json.dumps(messages)
            msg={'role':'assistant','content':'Ready to submit.'}
        elif self.n==5:
            ids=['test:100003','test:100004']
            candidate={'id':'c1','kind':'path','implicated_ids':ids,'path_ids':list(reversed(ids)) if self.reverse else ids,'cycle':False,'rationale':'Temporal path','alternatives':['Normal activity']}
            args={'candidates':[candidate],'limitations':['Synthetic fixture'],'assessment':'Exploratory'}
            msg={'role':'assistant','tool_calls':[{'id':'submit','type':'function','function':{'name':'submit_candidates','arguments':json.dumps(args)}}]}
        else:
            msg={'role':'assistant','content':json.dumps({'decisions':[{'id':'c1','disposition':'provisional','reason':'Observation only'}],'limitations':['Not a laundering verdict']})}
        return {'message':msg,'usage':{'prompt_tokens':20,'completion_tokens':1,'total_tokens':21},'finish_reason':'tool_calls' if msg.get('tool_calls') else 'stop','model':'fixture','seconds':0}

class CaseTests(unittest.TestCase):
    def exercise(self,reverse):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            root=Path(temp)
            db=sqlite3.connect(root/'data.sqlite')
            db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT); INSERT INTO metadata VALUES('source_sha256','test');
                CREATE TABLE transactions(row_id INTEGER PRIMARY KEY,timestamp TEXT,source_bank TEXT,source_account TEXT,destination_bank TEXT,destination_account TEXT,received_amount TEXT,received_currency TEXT,paid_amount TEXT,paid_currency TEXT,payment_format TEXT,raw_source_bank TEXT,raw_destination_bank TEXT);''')
            for i,minute,a,b in [(100003,'01','A','B'),(100004,'02','B','C')]:
                db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(i,'2022/09/04 00:'+minute,'1',a,'1',b,'10.00','USD','10.00','USD','ACH','1','1'))
            db.commit(); db.close()
            tool=Tools(root/'data.sqlite',root/'receipts.sqlite')
            result=Run(ScriptedModel(reverse),root/'run',tool).run()
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['model_calls'],6)
            self.assertEqual(result['presented_unique_rows'],2)
            checks=json.loads((root/'run/checks.json').read_text())
            self.assertEqual(checks[0]['check']['valid'],not reverse)
            self.assertEqual(result['decision']['decisions'][0]['disposition'],'unresolved' if reverse else 'provisional')
            self.assertTrue((root/'run/evidence.json').exists())
    def test_complete_tool_to_reviewer_flow(self): self.exercise(False)
    def test_invalid_path_cannot_be_approved(self): self.exercise(True)

if __name__=='__main__': unittest.main()
