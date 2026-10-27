import json
import unittest
from global_agent import Agent
from global_agent_audit import audit
from model import ProviderError
import test_global_agent_audit as fixtures

class Scripted:
    def complete(self,**request):
        payload=json.loads(request['messages'][-1]['content']);name=request['tools'][0]['function']['name']
        if name=='navigate':
            answer={'action':'expand','scope_ids':[r['id'] for r in payload['frontier'][:min(4,payload['remaining_pages'] or 4)]],'evict_ids':[],'restore_ids':[],'summary':'Continue pending scopes.'}
        else:answer={'decisions':[{'id':p['id'],'status':'unresolved','reason':'Synthetic fixture lacks economic context.'} for p in payload['verified_paths']],'limitations':['Not exhaustive.']}
        return {'message':{'tool_calls':[{'function':{'name':name,'arguments':json.dumps(answer)}}]},'finish_reason':'tool_calls','usage':{'total_tokens':10}}

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.GlobalAgentAuditTests();self.fixture.setUp();self.fixture.scan.close()
        self.source=self.fixture.source;self.root=self.fixture.root;self.agent=None
    def tearDown(self):
        if self.agent:self.agent.close()
        self.fixture.temp.cleanup()
    def create(self,**kwargs):
        self.agent=Agent(self.root/'run',self.source,model=kwargs.pop('model',Scripted()),min_interval=0,**kwargs);return self.agent
    def test_disconnected_graph_and_review(self):
        import sqlite3
        with sqlite3.connect(self.source) as db:db.execute("INSERT INTO transactions VALUES(3,'2022/09/01 00:03','1','X','1','Y',20,'USD',20,'USD','Wire')")
        a=self.create(limits={'max_pages':20,'max_calls':40});result=a.run()
        self.assertEqual(result['agent']['status'],'complete',result)
        self.assertEqual(a.db.execute('SELECT count(*) FROM components').fetchone()[0],2)
        self.assertEqual(a.db.execute("SELECT count(*) FROM review_jobs WHERE status='complete'").fetchone()[0],2)
        self.assertEqual(audit(a.directory,self.source)['status'],'passed')
    def test_full_run_exhausts_source_despite_small_total_limits(self):
        a=self.create(limits={'max_pages':1,'max_calls':1,'max_tokens':1});a.enable_full_run()
        result=a.run();self.assertEqual(result['agent']['status'],'complete',result)
        self.assertGreater(result['usage']['calls'],1)
        self.assertEqual(audit(a.directory,self.source)['status'],'passed')
        a.close();self.agent=None;a=self.create();self.assertTrue(a.limits['full_run'])
    def test_bounded_resume_preserves_pages(self):
        a=self.create(limits={'max_pages':2});self.assertEqual(a.run()['agent']['status'],'paused_budget')
        pages=[tuple(r) for r in a.db.execute('SELECT * FROM pages')];a.close();self.agent=None
        a=self.create();a.extend(pages=20);result=a.run();self.assertEqual(result['agent']['status'],'complete',result)
        self.assertEqual([tuple(r) for r in a.db.execute('SELECT * FROM pages LIMIT 2')],pages)
        self.assertEqual(audit(a.directory,self.source)['status'],'passed')
    def test_provider_pause_no_navigation_effect(self):
        class Failing:
            def complete(self,**kwargs):raise ProviderError(429,120)
        a=self.create(model=Failing());result=a.run()
        self.assertEqual(result['agent']['status'],'waiting_for_provider');self.assertEqual(a.scan.get('pages'),0)
        self.assertEqual(a.run()['usage']['calls'],1)
        self.assertEqual(audit(a.directory,self.source)['status'],'passed')
    def test_cached_invalid_response_is_rejected(self):
        a=self.create();a.seed();a.navigate()
        with a.db:
            a.db.execute("UPDATE agent_calls SET status='received',response=? WHERE id=1",(json.dumps({'message':{'tool_calls':[]}}),))
        request=json.loads(a.db.execute('SELECT request FROM agent_calls WHERE id=1').fetchone()[0])
        with self.assertRaises(ValueError):a.call('investigator',json.loads(request['messages'][-1]['content']),request['tools'][0]['function'],1600)
        self.assertEqual(a.db.execute('SELECT status FROM agent_calls WHERE id=1').fetchone()[0],'rejected')
    def test_provider_schema_retains_local_duplicate_validation(self):
        from model import provider_schema
        from run_case import validate
        schema={'type':'array','items':{'type':'integer'},'uniqueItems':True}
        self.assertNotIn('uniqueItems',provider_schema(schema))
        self.assertTrue(schema['uniqueItems'])
        with self.assertRaises(ValueError):validate(schema,[1,1])
    def test_provider_retry_after_is_sanitized(self):
        from unittest.mock import patch
        from urllib.error import HTTPError
        from model import Model
        model=Model.__new__(Model);model.key='fixture'
        with patch('model.request.build_opener') as opener:
            opener.return_value.open.side_effect=HTTPError('https://example.test',429,'private body',{'Retry-After':'120'},None)
            with self.assertRaises(ProviderError) as caught:model.complete([])
        self.assertEqual(caught.exception.retry_after,120)
        self.assertEqual(str(caught.exception),'NVIDIA HTTP 429')
    def test_review_publication_at_call_limit(self):
        a=self.create(limits={'max_calls':1});a.seed();a.state['phase']='review';a.persist();a.start_review()
        result=a.run();self.assertEqual(result['usage']['calls'],1)
        self.assertEqual(a.db.execute("SELECT count(*) FROM review_jobs WHERE status='complete'").fetchone()[0],1,result)

if __name__=='__main__':unittest.main()
