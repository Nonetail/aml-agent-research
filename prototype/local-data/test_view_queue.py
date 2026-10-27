import json
import unittest
import test_chunks
from chunk_case import Case
from verified_paths import build_paths
from test_threshold_eval import row

class ViewQueueTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_chunks.ChunkTests();self.fixture.setUp()
        self.run=self.fixture.run;self.database=self.fixture.database
    def tearDown(self):self.fixture.tearDown()
    def open(self):return Case(self.run,test_chunks.ScriptedNavigator(),self.database)

    def populated(self):
        case=self.open()
        rows=[case.tools._row(r) for r in case.tools.db.execute('SELECT * FROM transactions WHERE row_id>=200000 ORDER BY row_id')]
        from chunk_case import discover
        discover(case.state,rows);case.persist()
        return case

    def test_evict_restore_preserves_evidence_and_query_cursors(self):
        case=self.populated();ids=list(case.state['evidence']);view=ids[:12]
        evidence=dict(case.state['evidence']);queries=json.dumps(case.state['queries'],sort_keys=True)
        changed=case.revise_view(view,view[2:8],[ids[15]],'Follow another direction')
        self.assertNotIn(view[2],changed);self.assertIn(ids[15],changed)
        changed=case.revise_view(changed,[ids[15]],[view[2]],'Bring back a boundary')
        self.assertIn(view[2],changed)
        self.assertEqual(case.state['evidence'],evidence)
        self.assertEqual(json.dumps(case.state['queries'],sort_keys=True),queries)
        case.close();case=self.open();self.assertEqual(case.state['active_view'],changed);case.close()

    def test_invalid_eviction_is_atomic(self):
        case=self.populated();view=list(case.state['evidence'])[:12];before=json.dumps(case.state,sort_keys=True)
        for evict,restore in [([case.state['seed']],[]),(['T999'],[]),([view[2]],['T999']),([view[2]],[view[3]]),([],[])]:
            with self.assertRaises(ValueError):case.revise_view(view,evict,restore,'Invalid fixture')
            self.assertEqual(json.dumps(case.state,sort_keys=True),before)
        case.close()

    def test_queue_resumes_after_committed_batch_without_repeating(self):
        case=self.populated();case.state['status']='deferred_by_query_page_budget'
        case.state['limits']['max_model_calls']=1
        result=case.review()
        self.assertEqual(result['completed_packets'],1)
        self.assertGreater(result['pending_packets'],0)
        self.assertGreater(len(case.state['review_queue']['findings']),24)
        first=case.state['review_queue']['completed'][0];case.close()
        case=self.open();case.review(additional_model_calls=30)
        self.assertEqual(case.state['review_queue']['completed'][0],first)
        self.assertEqual(len(case.state['calls']),len(case.state['review_queue']['packets']))
        decisions=case.state['review']['final']['decisions']
        self.assertEqual(len(decisions),len({d['id'] for d in decisions}))
        self.assertEqual(len(decisions),len(case.state['review']['findings']))
        count=len(case.state['calls']);case.review();self.assertEqual(len(case.state['calls']),count)
        case.close()

    def test_changed_evidence_archives_prior_queue(self):
        case=self.populated();case.state['status']='deferred_by_query_page_budget'
        case.state['limits']['max_model_calls']=1;case.review()
        old=json.loads(json.dumps(case.state['review_queue']))
        raw=case.tools.db.execute('SELECT * FROM transactions WHERE row_id=100005').fetchone()
        from chunk_case import discover
        discover(case.state,[case.tools._row(raw)])
        case.review(additional_model_calls=1)
        self.assertNotEqual(case.state['review_queue']['evidence_fingerprint'],old['evidence_fingerprint'])
        archived=self.run/f'review-queue-{old["evidence_fingerprint"]}.json'
        self.assertEqual(json.loads(archived.read_text()),old)
        self.assertEqual(len(case.state['review_queue']['completed']),1)
        case.close()

    def test_no_default_path_cap_and_contained_path_dedup(self):
        evidence={f'T{i}':row(i,str(i).zfill(3),str(i),str(i+1)) for i in range(60)}
        paths,coverage=build_paths(evidence)
        self.assertGreater(len(paths),24);self.assertEqual(coverage['omitted_start_edges'],0)
        self.assertEqual(coverage['deduplicated_subpaths'],4)
        self.assertEqual(len({p['id'] for p in paths}),len(paths))
        again,_=build_paths(dict(reversed(list(evidence.items()))))
        self.assertEqual(paths,again)

    def test_contained_closed_cycle_is_not_discarded(self):
        evidence={'T1':row(1,'01','A','B'),'T2':row(2,'02','B','C'),
                  'T3':row(3,'03','C','B'),'T4':row(4,'04','B','D')}
        paths,_=build_paths(evidence)
        self.assertTrue(any(p['ids']==['T2','T3'] and p['cycle'] for p in paths))
        self.assertTrue(any(p['ids']==['T1','T2','T3','T4'] for p in paths))

    def test_checkpoint_contains_delta_after_view_revisions(self):
        class RevisingNavigator(test_chunks.ScriptedNavigator):
            def complete(self,messages,tools,choice,max_tokens):
                result=super().complete(messages,tools,choice,max_tokens)
                if tools[0]['function']['name']=='manage_view':
                    payload=json.loads(messages[-1]['content'])
                    args={'action':'continue','evict_ids':[r[0] for r in payload['rows'] if r[0]!=payload['seed']][:6],
                          'restore_ids':[],'reason':'Follow a new branch'}
                    result['message']['tool_calls'][0]['function']['arguments']=json.dumps(args)
                return result
        case=Case(self.run,RevisingNavigator(),self.database)
        case.segment()
        self.assertTrue(case.state['view_events'])
        for event in case.state['view_events']:
            self.assertLess(len(event['after']),12)
            self.assertTrue(set(event['evicted_ids'])<=set(case.state['evidence']))
        request=next(self.run.glob('*checkpoint-request.json'))
        payload=json.loads(json.loads(request.read_text())['messages'][-1]['content'])
        self.assertGreater(payload['chunk_delta']['new_evidence_count'],0)
        self.assertTrue(payload['chunk_delta']['view_changes'])
        self.assertGreater(case.state['chunks'][0]['checkpoint']['runtime_delta']['view_revisions'],0)
        case.close()

if __name__=='__main__':unittest.main()
