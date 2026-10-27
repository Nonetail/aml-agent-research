import json
import unittest
from copy import deepcopy
from chunk_case import Case
from replay_audit import audit, AuditFailure, rejection_proven
import test_chunks


class RecoveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_chunks.ChunkTests();self.fixture.setUp()
        self.root=self.fixture.run;self.db=self.fixture.database
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        while case.state['status']=='active':case.segment()
        case.close()

    def tearDown(self):self.fixture.tearDown()

    def insert_failure(self,operation='expand_batch',outcome='transport_error',mutate=None):
        state=json.loads((self.root/'state.json').read_text())
        for pos,call in enumerate(state['calls']):
            request=json.loads((self.root/f'{pos+1:02d}-{call["role"]}-request.json').read_text())
            if request['tools'][0]['function']['name']==operation:break
        payload=json.loads(request['messages'][-1]['content'])
        response=json.loads((self.root/f'{pos+1:02d}-{call["role"]}-response.json').read_text())
        for old in range(len(state['calls']),pos,-1):
            role=state['calls'][old-1]['role']
            for suffix in ('request','response'):
                (self.root/f'{old:02d}-{role}-{suffix}.json').rename(self.root/f'{old+1:02d}-{role}-{suffix}.json')
        record=deepcopy(state['calls'][pos]);record.update(status='failed',outcome=outcome)
        # These fixtures insert into the first chunk before any view revision.
        pages=0
        for i,previous in enumerate(state['calls'][:pos],1):
            prior=json.loads((self.root/f'{i:02d}-{previous["role"]}-response.json').read_text())
            pages+=len(json.loads(prior['message']['tool_calls'][0]['function']['arguments'])['queries'])
        record['unchanged']={'view':[r[0] for r in payload['rows']],'actions':pages,'view_events':0,'chunks':0}
        state['calls'].insert(pos,record)
        prefix=self.root/f'{pos+1:02d}-{record["role"]}'
        prefix.with_name(prefix.name+'-request.json').write_text(json.dumps(request))
        if outcome=='rejected':
            mutate(response)
            prefix.with_name(prefix.name+'-response.json').write_text(json.dumps(response))
        (self.root/'state.json').write_text(json.dumps(state))
        return state,pos

    def test_transport_failure_then_success_replays(self):
        self.insert_failure()
        self.assertEqual(audit(self.root,self.db)['failed_calls_replayed'],1)

    def test_invalid_eviction_then_success_replays(self):
        def invalidate(response):
            function=response['message']['tool_calls'][0]['function']
            function['arguments']=json.dumps({'action':'continue','evict_ids':['T999999999'],'restore_ids':[],'reason':'Invalid ID'})
        self.insert_failure('manage_view','rejected',invalidate)
        self.assertEqual(audit(self.root,self.db)['failed_calls_replayed'],1)

    def test_invalid_json_then_success_replays(self):
        self.insert_failure(outcome='rejected',mutate=lambda r:r['message']['tool_calls'][0]['function'].update(arguments='{'))
        self.assertEqual(audit(self.root,self.db)['failed_calls_replayed'],1)

    def test_truncated_response_then_success_replays(self):
        self.insert_failure(outcome='rejected',mutate=lambda r:r.update(finish_reason='length'))
        self.assertEqual(audit(self.root,self.db)['failed_calls_replayed'],1)

    def test_transport_failure_with_response_cannot_be_certified(self):
        state,pos=self.insert_failure();role=state['calls'][pos]['role']
        (self.root/f'{pos+1:02d}-{role}-response.json').write_text('{}')
        with self.assertRaisesRegex(AuditFailure,'Transport failure has a response'):audit(self.root,self.db)

    def test_duplicate_review_decisions_proven_independently(self):
        case=Case(self.root,test_chunks.ScriptedNavigator(),self.db)
        case.review();case.close()
        state=json.loads((self.root/'state.json').read_text())
        for index,call in enumerate(state['calls'],1):
            if call['role']!='reviewer':continue
            request=json.loads((self.root/f'{index:02d}-reviewer-request.json').read_text())
            response=json.loads((self.root/f'{index:02d}-reviewer-response.json').read_text())
            function=response['message']['tool_calls'][0]['function']
            answer=json.loads(function['arguments'])
            if len(answer['decisions'])<2:continue
            self.assertFalse(rejection_proven(request,response,[],{},state['seed'],150))
            answer['decisions'][1]=deepcopy(answer['decisions'][0])
            function['arguments']=json.dumps(answer)
            self.assertTrue(rejection_proven(request,response,[],{},state['seed'],150))
            break
        else:self.fail('Fixture needs a review packet with multiple paths')

    def test_duplicate_expansion_then_success_replays(self):
        def invalidate(response):
            function=response['message']['tool_calls'][0]['function']
            answer=json.loads(function['arguments'])
            answer['queries'][1]=deepcopy(answer['queries'][0])
            function['arguments']=json.dumps(answer)
        self.insert_failure(outcome='rejected',mutate=invalidate)
        self.assertEqual(audit(self.root,self.db)['failed_calls_replayed'],1)

    def test_valid_response_cannot_be_hidden_as_rejected(self):
        self.insert_failure('manage_view','rejected',lambda r:None)
        with self.assertRaisesRegex(AuditFailure,'Rejected response is valid'):audit(self.root,self.db)

    def test_recovery_snapshot_corruption_fails(self):
        state,pos=self.insert_failure();state['calls'][pos]['unchanged']['actions']=1
        (self.root/'state.json').write_text(json.dumps(state))
        with self.assertRaisesRegex(AuditFailure,'Recovery snapshot differs'):audit(self.root,self.db)


if __name__=='__main__':unittest.main()
