import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from model import Model
from run_case import Run, validate

class ModelTests(unittest.TestCase):
    def test_explicit_reasoning_model_is_sent_and_used_as_fallback(self):
        payload={'choices':[{'message':{'role':'assistant','content':'done'},'finish_reason':'stop'}]}
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): return json.dumps(payload).encode()
        class Opener:
            def open(self,req,timeout):
                body=json.loads(req.data)
                assert body['model']=='nvidia/nemotron-3-ultra-550b-a55b'
                assert body['chat_template_kwargs']=={'enable_thinking':True}
                assert timeout==240
                return Response()
        model=Model.__new__(Model); model.key='test-only'
        with patch('model.request.build_opener',return_value=Opener()):
            result=model.complete([{'role':'user','content':'test'}],
                model_name='nvidia/nemotron-3-ultra-550b-a55b',enable_thinking=True,timeout=240)
        self.assertEqual(result['model'],'nvidia/nemotron-3-ultra-550b-a55b')

    def test_adapter_preserves_native_tool_calls_and_usage(self):
        call={'id':'c1','type':'function','function':{'name':'get_accounts','arguments':'{"accounts":[]}'}}
        payload={'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[call]},'finish_reason':'tool_calls'}],
                 'usage':{'total_tokens':25},'model':'test'}
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): return json.dumps(payload).encode()
        class Opener:
            def open(self,req,timeout):
                body=json.loads(req.data)
                assert body['chat_template_kwargs']=={'enable_thinking':False}
                assert body['parallel_tool_calls'] is False
                assert body['tool_choice']['function']['name']=='get_accounts'
                return Response()
        model=Model.__new__(Model); model.key='test-only'
        with patch('model.request.build_opener',return_value=Opener()):
            result=model.complete([{'role':'user','content':'test'}],[{'type':'function','function':{'name':'get_accounts'}}],
                                  {'type':'function','function':{'name':'get_accounts'}})
        self.assertEqual(result['message']['tool_calls'],[call])
        self.assertEqual(result['usage']['total_tokens'],25)
        self.assertNotIn('test-only',json.dumps(result))

    def test_tool_argument_bounds(self):
        with self.assertRaises(ValueError): validate({'type':'integer','maximum':30},31)
        with self.assertRaises(ValueError): validate({'type':'integer'},True)
        with self.assertRaises(ValueError): validate({'type':'object','properties':{},'additionalProperties':False},{'sql':'SELECT'})

    def test_unknown_evidence_cannot_pass_verification(self):
        run=Run.__new__(Run); run.evidence={}
        result=run.check({'kind':'path','implicated_ids':['invented'],'path_ids':['invented','other']})
        self.assertFalse(result['valid'])

    def test_context_budget_prevents_provider_call(self):
        run=Run.__new__(Run); run.calls=[]
        from types import SimpleNamespace
        run.tools=SimpleNamespace(sha='test')
        import time
        run.started=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'byte budget'):
            run.call('test',[{'role':'user','content':'a'*120000}])

    def test_exhausted_tool_budget_does_not_execute(self):
        run=Run.__new__(Run); run.tool_calls=12
        self.assertIn('error',run.execute('fetch_transactions',{}))

    def test_alias_roundtrip_preserves_exact_source_identity(self):
        from types import SimpleNamespace
        run=Run.__new__(Run); run.tools=SimpleNamespace(sha='sourcehash')
        self.assertEqual(run.canonical({'ids':['T123','T124']}),{'ids':['sourcehash:123','sourcehash:124']})

    def test_failed_provider_call_is_recorded_with_unknown_usage(self):
        from types import SimpleNamespace
        import time
        from tools import HERE
        class FailedModel:
            def complete(self,*args): raise TimeoutError('fixture timeout')
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            run=Run.__new__(Run); run.tools=SimpleNamespace(sha='test'); run.calls=[]
            run.started=time.monotonic(); run.directory=Path(temp); run.model=FailedModel()
            with self.assertRaises(TimeoutError): run.call('test',[{'role':'user','content':'test'}])
            saved=json.loads((Path(temp)/'usage.json').read_text())
            self.assertEqual(saved[0]['status'],'response_unavailable')
            self.assertIsNone(saved[0]['usage'])

if __name__=='__main__': unittest.main()
