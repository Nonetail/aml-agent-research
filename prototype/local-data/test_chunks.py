import json
import sqlite3
import unittest
from pathlib import Path
import test_tools
from chunk_case import Case, init, DEFAULTS

class ScriptedNavigator:
    def complete(self,messages,tools,tool_choice,max_tokens):
        payload=json.loads(messages[-1]['content']); name=tools[0]['function']['name']
        if name=='expand_batch':
            count=min(4,payload['budgets']['remaining_view_rows'],payload['budgets']['remaining_query_pages'])
            args={'queries':[{'query_id':q['id'],'limit':payload['budgets']['max_rows_per_query']} for q in payload['frontier'][:count]],'question':'Broaden and finish pages'}
        elif name=='manage_view': args={'action':'handoff','evict_ids':[],'restore_ids':[],'reason':'Fixture context boundary'}
        elif name=='checkpoint':
            args={'summary':'Still investigating; do not infer benign status.','boundary_ids':[r[0] for r in payload['rows'][-2:]],
                  'resume_query_ids':[q['id'] for q in payload['frontier'][:4]],'questions':['Finish these exact paginated scopes']}
        elif name=='assess_verified_paths': args={'decisions':[{'id':p['id'],'status':'unresolved','reason':'Fixture'} for p in payload['verified_paths']], 'limitations':['Not a detector']}
        else: args={'decisions':[],'limitations':['Not a detector']}
        return {'message':{'role':'assistant','tool_calls':[{'id':'fixture','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},
                'finish_reason':'tool_calls','usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15},'seconds':0}

class ChunkTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_tools.NavigationTests(); self.fixture.setUp()
        self.database=self.fixture.root/'db/transactions.sqlite'
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE transactions SET row_id=row_id+100003,timestamp=REPLACE(timestamp,'2022/09/02','2022/09/04')")
            for i in range(60):
                a,b=('B','C') if i%2 else ('C','B')
                db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (200000+i,f'2022/09/04 01:{i:02d}','1',a,'1',b,'1.00','USD','1.00','USD','ACH','1','1'))
        self.run=self.fixture.root/'run'
        init(self.run,{**DEFAULTS,'view_rows':12,'max_query_pages':20},self.database)

    def tearDown(self): self.fixture.tearDown()

    def open(self): return Case(self.run,ScriptedNavigator(),self.database)

    def test_fresh_instance_resumes_pages_and_preserves_boundary_evidence(self):
        first=self.open()
        a=first.segment(); first.close()
        second=self.open()
        b=second.segment()
        while second.state['status']=='active': second.segment()
        second.review(); report=second.audit(); second.close()
        self.assertEqual(a['reason'],'row_allowance')
        self.assertEqual(b['status'],'active')
        self.assertGreater(report['chunks'],3)
        self.assertTrue(report['review_complete'])
        self.assertEqual(report['retrieved_unique_rows'],report['reviewer_presented_unique_rows'])
        for h in report['handoffs']:
            self.assertTrue(h['prior_evidence_preserved'])
            self.assertTrue(h['pending_cursors_preserved'])
            self.assertTrue(h['anchors_in_new_context'])
            self.assertTrue(h['resumed_requested_query'])
        self.assertTrue(all(n<=12 for n in report['working_view_counts']))

    def test_receipt_recovery_does_not_repeat_a_committed_page(self):
        first=self.open(); key=first.pending()[0]
        args=dict(first.state['queries'][key]['scope'],limit=2)
        action={'id':'interruption-fixture','query_id':key,'arguments':args,'chunk':1}
        first.state['pending_action']=action; first.persist()
        result=first.tools.dispatch('fetch_transactions',args,action_id=action['id'])
        first.close()
        resumed=self.open()
        self.assertIsNone(resumed.state['pending_action'])
        self.assertEqual(len(resumed.state['actions']),1)
        self.assertEqual(resumed.state['actions'][0]['receipt_id'],result['receipt_id'])
        self.assertEqual(resumed.tools.log.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],1)
        resumed.close()

    def test_action_id_cannot_replay_another_scope(self):
        case=self.open(); key=case.pending()[0]; args=dict(case.state['queries'][key]['scope'],limit=2)
        case.tools.dispatch('fetch_transactions',args,action_id='fixed')
        with self.assertRaisesRegex(ValueError,'another request'):
            case.tools.dispatch('fetch_transactions',dict(args,limit=3),action_id='fixed')
        case.close()

    def test_identical_model_calls_execute_one_batch(self):
        class DuplicateNavigator(ScriptedNavigator):
            def complete(self,*args,**kwargs):
                result=super().complete(*args,**kwargs)
                result['message']['tool_calls']*=2
                return result
        case=Case(self.run,DuplicateNavigator(),self.database)
        definition={'name':'expand_batch','description':'Fixture','parameters':{'type':'object','properties':{
            'queries':{'type':'array','items':{'type':'object','properties':{'query_id':{'type':'string'},'limit':{'type':'integer'}},'required':['query_id','limit']},'maxItems':4},'question':{'type':'string'}},
            'required':['queries','question'],'additionalProperties':False}}
        selected=case.call('investigator',case.payload([case.state['seed']]),definition)
        case.expand(selected['queries'],12)
        self.assertEqual(len(case.state['actions']),len(selected['queries']))
        self.assertEqual(case.state['calls'][0]['identical_calls_coalesced'],1)
        case.close()

    def test_model_sizes_are_preserved_or_capped_before_fetch(self):
        case=self.open(); case.state['limits']['page_rows']=500
        keys=case.pending()[:3]
        case.expand([{'query_id':keys[0],'limit':1},{'query_id':keys[1],'limit':500},
                     {'query_id':keys[2],'limit':25}],10)
        actions=case.state['actions']
        self.assertEqual([a['arguments']['limit'] for a in actions],[1,8,1])
        self.assertEqual([a['requested_limit'] for a in actions],[1,500,25])
        self.assertLessEqual(sum(len(a['returned_ids']) for a in actions),10)
        self.assertEqual(case.payload([case.state['seed']])['recent_pages'][1]['effective_limit'],8)
        case.close()

    def test_invalid_batch_has_no_partial_side_effects(self):
        case=self.open(); keys=case.pending()[:2]
        for requests in ([{'query_id':keys[0],'limit':0}],
                         [{'query_id':keys[0],'limit':501}],
                         [{'query_id':keys[0],'limit':True}],
                         [{'query_id':keys[0],'limit':1}]*2,
                         [{'query_id':keys[0],'limit':1},{'query_id':'unknown','limit':2}]):
            with self.assertRaises(ValueError): case.expand(requests,10)
        case.state['limits']['max_query_pages']=1
        with self.assertRaises(RuntimeError):
            case.expand([{'query_id':k,'limit':1} for k in keys],10)
        self.assertEqual(case.state['actions'],[])
        case.close()

    def test_query_budget_hands_off_to_review(self):
        case=self.open(); case.state['limits']['max_query_pages']=1
        result=case.segment()
        self.assertEqual(result['status'],'deferred_by_query_page_budget')
        self.assertEqual(len(case.state['actions']),1)
        case.review()
        self.assertIsNotNone(case.state['review'])
        case.close()

    def test_larger_views_and_small_reviewer_reserve_enough_calls(self):
        run=self.fixture.root/'large-run'
        init(run,{'view_rows':1500,'review_view_rows':10,'max_request_bytes':500000},self.database)
        case=Case(run,ScriptedNavigator(),self.database)
        while case.state['status']=='active': case.segment()
        case.review()
        self.assertEqual(set(case.state['review']['presented_ids']),set(case.state['evidence']))
        self.assertGreater(case.state['limits']['max_model_calls'],18)
        for path in run.glob('review-*.json'):
            self.assertLessEqual(len(json.loads(path.read_text())['view']),10)
        case.close()

    def test_full_1500_row_views_keep_the_hard_boundary(self):
        with sqlite3.connect(self.database) as db:
            for i in range(3500):
                db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (300000+i,'2022/09/04 02:00','1','B','1','C','1.00','USD','1.00','USD','ACH','1','1'))
        run=self.fixture.root/'full-view-run'
        init(run,{'view_rows':1500,'review_view_rows':1500,'page_rows':500,'max_request_bytes':500000},self.database)
        case=Case(run,ScriptedNavigator(),self.database)
        while case.state['status']=='active': case.segment()
        case.review()
        report=case.audit()
        self.assertIn(1500,report['working_view_counts'])
        self.assertTrue(all(n<=1500 for n in report['working_view_counts']))
        self.assertTrue(all(a['arguments']['limit']<=500 for a in case.state['actions']))
        self.assertEqual(report['retrieved_unique_rows'],report['reviewer_presented_unique_rows'])
        case.close()

    def test_default_pages_and_verified_review(self):
        run=self.fixture.root/'defaults'
        init(run,database=self.database)
        case=Case(run,ScriptedNavigator(),self.database)
        while case.state['status']=='active': case.segment()
        case.review()
        self.assertEqual(case.state['limits']['view_rows'],150)
        self.assertEqual(case.state['limits']['review_view_rows'],150)
        self.assertTrue(all(a['requested_limit']==25 and a['arguments']['limit']<=25 for a in case.state['actions']))
        self.assertTrue(case.state['review']['findings'])
        self.assertTrue(all(f['check']['valid'] for f in case.state['review']['findings']))
        for request in run.glob('*reviewer-request.json'):
            payload=json.loads(json.loads(request.read_text())['messages'][-1]['content'])
            self.assertLessEqual(len(payload['rows']),150)
            for path in payload['verified_paths']:
                self.assertTrue(path['check']['valid'])
                self.assertLessEqual(set(path['candidate']['ids']),{r[0] for r in payload['rows']})
        case.close()

    def test_failed_verification_never_reaches_reviewer(self):
        case=self.open()
        while case.state['status']=='active': case.segment()
        original=case.tools.dispatch
        def reject(name,args,**kwargs):
            if name=='verify_path': return {'valid':False,'errors':['Fixture source mismatch']}
            return original(name,args,**kwargs)
        case.tools.dispatch=reject
        case.review()
        self.assertTrue(case.state['review']['findings'])
        self.assertTrue(all(d['status']=='unsupported' for d in case.state['review']['final']['decisions']))
        for request in self.run.glob('*reviewer-request.json'):
            self.assertEqual(json.loads(json.loads(request.read_text())['messages'][-1]['content'])['verified_paths'],[])
        case.close()

    def test_missing_path_assessment_cannot_complete_review(self):
        class IncompleteReviewer(ScriptedNavigator):
            def complete(self,messages,tools,tool_choice,max_tokens):
                result=super().complete(messages,tools,tool_choice,max_tokens)
                if tools[0]['function']['name']=='assess_verified_paths':
                    self.assert_named=tool_choice
                    result['message']['tool_calls'][0]['function']['arguments']=json.dumps({'decisions':[],'limitations':[]})
                return result
        model=IncompleteReviewer();case=Case(self.run,model,self.database)
        while case.state['status']=='active': case.segment()
        with self.assertRaises(ValueError):case.review()
        self.assertIsNone(case.state['review'])
        self.assertEqual(model.assert_named['function']['name'],'assess_verified_paths')
        case.close()

    def test_chunk_allows_more_than_three_expansions(self):
        class NarrowNavigator(ScriptedNavigator):
            def complete(self,messages,tools,tool_choice,max_tokens):
                result=super().complete(messages,tools,tool_choice,max_tokens)
                if tools[0]['function']['name']=='expand_batch':
                    fn=result['message']['tool_calls'][0]['function']
                    args=json.loads(fn['arguments']);args['queries']=args['queries'][:1]
                    fn['arguments']=json.dumps(args)
                return result
        run=self.fixture.root/'narrow'
        init(run,database=self.database)
        case=Case(run,NarrowNavigator(),self.database)
        result=case.segment()
        self.assertGreater(len(case.state['chunks'][0]['batches']),3)
        self.assertEqual(result['status'],'frontier_exhausted')
        self.assertLess(len(case.state['chunks'][0]['final_view']),150)
        self.assertEqual(case.pending(),[])
        case.close()

    def test_budget_pause_and_resume_preserve_exact_progress(self):
        case=self.open();case.state['limits']['max_query_pages']=4
        result=case.segment();self.assertEqual(result['status'],'deferred_by_query_page_budget')
        evidence=dict(case.state['evidence']);cursors={k:v['cursor'] for k,v in case.state['queries'].items()}
        case.resume(additional_query_pages=30)
        self.assertEqual(case.state['evidence'],evidence)
        self.assertEqual({k:v['cursor'] for k,v in case.state['queries'].items()},cursors)
        while case.state['status']=='active':case.segment()
        self.assertGreater(len(case.state['chunks']),3)
        self.assertTrue(set(evidence)<=set(case.state['evidence']))
        self.assertTrue(case.audit()['cursor_chains_valid'])
        case.close()

    def test_model_budget_saves_handoff_and_requires_extension(self):
        case=self.open();case.state['limits']['max_model_calls']=2
        result=case.segment()
        self.assertEqual(result['status'],'deferred_by_model_call_budget')
        self.assertEqual(len(case.state['calls']),2)
        self.assertEqual(case.state['calls'][-1]['role'],'checkpoint')
        with self.assertRaises(ValueError):case.resume(additional_query_pages=10)
        case.resume(additional_model_calls=10)
        self.assertEqual(case.state['status'],'active')
        case.segment();case.close()

    def test_full_frontier_can_finish_after_many_contexts(self):
        with sqlite3.connect(self.database) as db:
            for i in range(1000):
                a,b=('B','C') if i%2 else ('C','B')
                db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (400000+i,'2022/09/04 02:00','1',a,'1',b,'1.00','USD','1.00','USD','ACH','1','1'))
        run=self.fixture.root/'full-frontier'
        init(run,{'max_query_pages':200,'max_model_calls':200},self.database)
        case=Case(run,ScriptedNavigator(),self.database)
        while case.state['status']=='active':case.segment()
        self.assertEqual(case.state['status'],'frontier_exhausted')
        self.assertGreater(len(case.state['chunks']),3)
        self.assertGreater(max(len(c['batches']) for c in case.state['chunks']),3)
        for chunk in case.state['chunks'][:-1]:
            self.assertEqual(chunk['reason'],'row_allowance')
            self.assertEqual(len(chunk['final_view']),150)
        self.assertTrue(case.audit()['investigation_complete'])
        case.close()

    def test_review_budget_is_deferred_before_any_review_call(self):
        case=self.open();case.state['limits']['max_query_pages']=1
        case.segment();case.state['limits']['max_model_calls']=len(case.state['calls'])
        before=len(case.state['calls']);result=case.review()
        self.assertEqual(result['review_status'],'deferred_by_model_call_budget')
        self.assertEqual(len(case.state['calls']),before)
        self.assertIsNone(case.state['review'])
        case.close()

    def test_completed_frontier_can_resume_only_its_deferred_review(self):
        case=self.open();case.state['limits']['max_query_pages']=120
        while case.state['status']=='active':case.segment()
        self.assertEqual(case.state['status'],'frontier_exhausted')
        case.state['limits']['max_model_calls']=len(case.state['calls'])
        case.review()
        result=case.resume(additional_model_calls=30)
        self.assertEqual(result['status'],'frontier_exhausted')
        case.review()
        self.assertTrue(case.state['review']['investigation_complete'])
        case.close()

    def test_two_writers_cannot_advance_one_case(self):
        first=self.open()
        with self.assertRaisesRegex(RuntimeError,'Another process'):
            self.open()
        first.close()

if __name__=='__main__': unittest.main()
