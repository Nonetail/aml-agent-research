import json
import unittest
from replay_audit import audit, AuditFailure
from chunk_case import Case
import test_chunks

class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_chunks.ChunkTests();self.fixture.setUp()
        self.root=self.fixture.run;self.db=self.fixture.database
        class RevisingNavigator(test_chunks.ScriptedNavigator):
            edits=0
            saved=None
            def complete(self,messages,tools,choice,max_tokens):
                result=super().complete(messages,tools,choice,max_tokens)
                if tools[0]['function']['name']=='manage_view' and self.edits<2:
                    payload=json.loads(messages[-1]['content'])
                    evict=[r[0] for r in payload['rows'] if r[0]!=payload['seed']][:6]
                    args={'action':'continue','evict_ids':evict,'restore_ids':[self.saved] if self.saved else [],'reason':'Fixture restoration'}
                    self.saved=evict[0];self.edits+=1
                    result['message']['tool_calls'][0]['function']['arguments']=json.dumps(args)
                return result
        self.model=RevisingNavigator();case=Case(self.root,self.model,self.db)
        while case.state['status']=='active':case.segment()
        case.state['limits']['max_model_calls']=len(case.state['calls'])+1
        case.review();case.close()
    def tearDown(self):self.fixture.tearDown()

    def state(self):return json.loads((self.root/'state.json').read_text())
    def save(self,state):(self.root/'state.json').write_text(json.dumps(state))

    def test_valid_eviction_restoration_and_partial_queue(self):
        report=audit(self.root,self.db)
        self.assertEqual(report['status'],'passed')
        self.assertEqual(report['view_changes_replayed'],2)
        self.assertGreater(report['pending_review_packets'],0)
        self.assertTrue(self.state()['view_events'][1]['restored_ids'])

    def test_completed_resumed_queue_replays(self):
        case=Case(self.root,self.model,self.db);case.review(additional_model_calls=40);case.close()
        self.assertEqual(audit(self.root,self.db)['pending_review_packets'],0)

    def test_changed_source_row_fails_at_evidence_id(self):
        state=self.state();state['evidence'][state['seed']]['paid_amount']='999';self.save(state)
        with self.assertRaisesRegex(AuditFailure,'evidence/T.*Source row differs'):audit(self.root,self.db)

    def test_missing_packet_fails_independent_queue_reconstruction(self):
        state=self.state();state['review_queue']['packets'].pop();self.save(state)
        with self.assertRaisesRegex(AuditFailure,'queue: Missing/extra/altered review packet'):audit(self.root,self.db)

    def test_corrupt_restore_transition_fails_at_model_call(self):
        state=self.state();state['view_events'][1]['restored_ids']=[];self.save(state)
        with self.assertRaisesRegex(AuditFailure,'call/.*Recorded eviction/restoration differs'):audit(self.root,self.db)

    def test_unaccounted_review_response_is_not_certified(self):
        state=self.state();state['review_queue']['completed']=[];self.save(state)
        with self.assertRaisesRegex(AuditFailure,'Committed assessments do not match'):audit(self.root,self.db)

if __name__=='__main__':unittest.main()
