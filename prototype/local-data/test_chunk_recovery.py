import json
import unittest
from unittest.mock import patch
import test_chunks
from chunk_case import Case
from replay_audit import audit

class Interrupted(BaseException): pass

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_chunks.ChunkTests();self.fixture.setUp()
        self.root=self.fixture.run;self.db=self.fixture.database
    def tearDown(self):self.fixture.tearDown()
    def finish(self,case):
        while case.state['status']=='active':case.segment()
        case.review();case.close()
        return audit(self.root,self.db)

    def test_invalid_duplicate_view_then_correction_is_auditable(self):
        class InvalidOnce(test_chunks.ScriptedNavigator):
            invalid=False
            def complete(self,messages,tools,*args):
                result=super().complete(messages,tools,*args)
                if tools[0]['function']['name']=='manage_view' and not self.invalid:
                    self.invalid=True
                    payload=json.loads(messages[-1]['content']);ident=next(r[0] for r in payload['rows'] if r[0]!=payload['seed'])
                    result['message']['tool_calls'][0]['function']['arguments']=json.dumps({'action':'continue','evict_ids':[ident,ident],'restore_ids':[],'reason':'fixture'})
                return result
        case=Case(self.root,InvalidOnce(),self.db)
        result=self.finish(case)
        self.assertEqual(result['failed_calls_replayed'],1)

    def test_provider_retry_exhaustion_then_fresh_process_resumes_same_chunk(self):
        class Fails(test_chunks.ScriptedNavigator):
            def complete(self,messages,tools,*args):
                if tools[0]['function']['name']=='manage_view':raise TimeoutError('fixture')
                return super().complete(messages,tools,*args)
        case=Case(self.root,Fails(),self.db)
        with patch('chunk_case.time.sleep'),self.assertRaisesRegex(RuntimeError,'retry exhausted'):case.segment()
        start=(self.root/'chunk-1-start.json').read_bytes();pages=len(case.state['actions'])
        case.close()
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        result=self.finish(case)
        self.assertEqual((self.root/'chunk-1-start.json').read_bytes(),start)
        self.assertGreater(result['pages_replayed'],pages)
        self.assertEqual(result['failed_calls_replayed'],2)

    def test_interruption_after_page_commit_resumes_batch_without_duplicate_page(self):
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        original=case.commit_action
        def interrupted(action,result):
            original(action,result)
            raise Interrupted()
        case.commit_action=interrupted
        with self.assertRaises(Interrupted):case.segment()
        first=case.state['actions'][0];case.close()
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        result=self.finish(case)
        state=json.loads((self.root/'state.json').read_text())
        self.assertEqual(sum(a['id']==first['id'] for a in state['actions']),1)
        self.assertEqual(result['status'],'passed')

    def test_received_unapplied_response_reused_after_interruption(self):
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        original=case.call
        def interrupted(*args,**kwargs):
            original(*args,**kwargs)
            raise Interrupted()
        case.call=interrupted
        with self.assertRaises(Interrupted):case.segment()
        response=(self.root/'01-investigator-response.json').read_bytes();case.close()
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        self.finish(case)
        self.assertEqual((self.root/'01-investigator-response.json').read_bytes(),response)
        state=json.loads((self.root/'state.json').read_text())
        self.assertEqual(state['calls'][0]['outcome'],'applied')

    def test_repeated_invalid_view_preserves_journal_for_later_resume(self):
        class Invalid(test_chunks.ScriptedNavigator):
            def complete(self,messages,tools,*args):
                result=super().complete(messages,tools,*args)
                if tools[0]['function']['name']=='manage_view':
                    result['message']['tool_calls'][0]['function']['arguments']=json.dumps({'action':'continue','evict_ids':[],'restore_ids':[],'reason':'invalid'})
                return result
        case=Case(self.root,Invalid(),self.db)
        with self.assertRaisesRegex(ValueError,'correction exhausted'):case.segment()
        self.assertFalse(case.state.get('view_events'));case.close()
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        self.assertEqual(self.finish(case)['failed_calls_replayed'],2)

    def test_checkpoint_response_at_last_call_reused(self):
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        case.state['limits']['max_model_calls']=2;case.persist()
        original=case.call
        def interrupt_checkpoint(role,*args,**kwargs):
            result=original(role,*args,**kwargs)
            if role=='checkpoint':raise Interrupted()
            return result
        case.call=interrupt_checkpoint
        with self.assertRaises(Interrupted):case.segment()
        self.assertEqual(len(case.state['calls']),2);case.close()
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        case.segment();case.close()
        self.assertEqual(audit(self.root,self.db)['status'],'passed')

    def test_interrupted_corrective_response_reused(self):
        class InvalidOnce(test_chunks.ScriptedNavigator):
            count=0
            def complete(self,messages,tools,*args):
                result=super().complete(messages,tools,*args)
                if tools[0]['function']['name']=='manage_view':
                    self.count+=1
                    if self.count==1:
                        result['message']['tool_calls'][0]['function']['arguments']=json.dumps({'action':'continue','evict_ids':[],'restore_ids':[],'reason':'invalid'})
                return result
        case=Case(self.root,InvalidOnce(),self.db);original=case.call
        def interrupt_correction(role,payload,*args,**kwargs):
            result=original(role,payload,*args,**kwargs)
            if 'correction' in payload:raise Interrupted()
            return result
        case.call=interrupt_correction
        with self.assertRaises(Interrupted):case.segment()
        case.close();case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        self.assertEqual(self.finish(case)['failed_calls_replayed'],1)

    def test_response_saved_before_received_marker_recovers(self):
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        case.state['limits']['max_model_calls']=2;case.persist()
        original=case.call
        def interrupt_checkpoint(role,*args,**kwargs):
            result=original(role,*args,**kwargs)
            if role=='checkpoint':
                case.state['calls'][-1]['status']='admitted';case.persist()
                raise Interrupted()
            return result
        case.call=interrupt_checkpoint
        with self.assertRaises(Interrupted):case.segment()
        case.close();case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        case.segment();case.close()
        self.assertEqual(audit(self.root,self.db)['status'],'passed')

if __name__=='__main__':unittest.main()
