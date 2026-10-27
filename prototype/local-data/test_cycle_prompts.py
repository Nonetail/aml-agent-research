import copy
import json
import unittest

from cycle_prompts import (navigation_definition,review_definition,
                           validate_navigation,validate_review)
from global_agent import parse
from model import provider_schema
from run_case import validate


class CyclePromptTests(unittest.TestCase):
    def setUp(self):
        self.ids=['source:1','source:2','source:3']
        self.answer={'observations':[{'transaction_ids':list(self.ids),'pattern_present':True,
            'status':'insufficient_evidence','reason':'A temporal return is present; its economic purpose is unknown.',
            'limitations':['No customer-purpose records.']}],
            'evidence_requests':[{'scope_id':7,'reason':'Check later continuations from the intermediate account.'}],
            'limitations':[]}

    def verify(self,ids):
        return {'valid':ids==self.ids,'transaction_ids':ids,'unavailable_ids':[],'elapsed_minutes':2}

    def check(self,answer=None,verify=None):
        return validate_review(answer or self.answer,self.ids,[7,9],verify or self.verify)

    def test_new_cycle_without_preassigned_candidate_id_is_accepted_and_verified(self):
        original=copy.deepcopy(self.answer)
        result=self.check()
        self.assertEqual(result['observations'][0]['verification']['transaction_ids'],self.ids)
        self.assertEqual(result['observations'][0]['status'],'insufficient_evidence')
        self.assertEqual(self.answer,original)

    def test_fabricated_id_is_rejected_before_source_lookup(self):
        self.answer['observations'][0]['transaction_ids'][-1]='source:999'
        with self.assertRaisesRegex(ValueError,'Unsupplied'):
            self.check(verify=lambda ids:self.fail('Unknown IDs must not reach verifier'))

    def test_pattern_claim_must_match_deterministic_facts(self):
        for asserted in (True,False):
            self.answer['observations'][0]['pattern_present']=asserted
            with self.subTest(asserted=asserted),self.assertRaisesRegex(ValueError,'Pattern claim'):
                self.check(verify=lambda ids:{'valid':not asserted,'unavailable_ids':[]})

    def test_invalid_cycle_is_not_a_laundering_or_clean_account_verdict(self):
        item=self.answer['observations'][0]
        item.update(pattern_present=False,status='not_supported',reason='The proposed edges do not close.')
        result=self.check(verify=lambda ids:{'valid':False,'errors':['not closed'],'unavailable_ids':[]})
        self.assertFalse(result['observations'][0]['verification']['valid'])
        item['status']='investigate'
        with self.assertRaisesRegex(ValueError,'verified cycle'):self.check()

    def test_missing_source_evidence_is_not_accepted_as_a_negative_pattern(self):
        self.answer['observations'][0]['pattern_present']=False
        with self.assertRaisesRegex(ValueError,'Source evidence unavailable'):
            self.check(verify=lambda ids:{'valid':False,'unavailable_ids':[ids[-1]]})

    def test_only_advertised_work_can_be_requested(self):
        self.answer['evidence_requests'][0]['scope_id']=99
        with self.assertRaisesRegex(ValueError,'Unadvertised'):self.check()
        self.answer['evidence_requests']=[{'scope_id':7,'reason':'Check closure.'}]*2
        with self.assertRaisesRegex(ValueError,'Repeated'):self.check()

    def test_duplicate_support_and_edges_are_rejected(self):
        self.answer['observations']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.check()
        self.answer['observations']=self.answer['observations'][:1]
        self.answer['observations'][0]['transaction_ids']=['source:1','source:1']
        with self.assertRaisesRegex(ValueError,'Repeated array'):self.check()

    def test_no_candidate_can_request_further_evidence(self):
        self.answer['observations']=[]
        self.assertEqual(len(self.check()['evidence_requests']),1)
        empty={'observations':[],'evidence_requests':[],'limitations':['No complete support in this view.']}
        self.assertEqual(validate_review(empty,[],[],self.verify),empty)

    def test_review_can_assess_more_than_six_complete_candidates(self):
        ids=[f'source:{i}' for i in range(14)]
        item=self.answer['observations'][0]
        answer={'observations':[{**item,'transaction_ids':ids[i:i+2]} for i in range(0,14,2)],
                'evidence_requests':[],'limitations':[]}
        result=validate_review(answer,ids,[],lambda support:{'valid':True,'transaction_ids':support,'unavailable_ids':[]})
        self.assertEqual(len(result['observations']),7)

    def test_navigation_systematic_or_known_scopes_with_no_cursor_control(self):
        for ids in ([],[7],[7,9]):
            answer={'scope_ids':ids,'reason':'Resolve return paths.'}
            self.assertEqual(validate_navigation(answer,[7,9]),answer)
        for answer in ({'scope_ids':[99],'reason':'Unknown.'},
                       {'scope_ids':[7,7],'reason':'Repeated.'},
                       {'scope_ids':[],'reason':'Systematic.','cursor':12}):
            with self.subTest(answer=answer),self.assertRaises(ValueError):validate_navigation(answer,[7,9])
        validate_navigation({'scope_ids':[],'reason':'No pending work.'},[])

    def test_native_tool_call_contract_and_truncation(self):
        definition=review_definition(self.ids,[7,9])
        response={'message':{'tool_calls':[{'function':{'name':definition['name'],
            'arguments':json.dumps(self.answer)}}]},'finish_reason':'tool_calls'}
        self.assertEqual(parse(response,definition),self.answer)
        response['finish_reason']='length'
        with self.assertRaisesRegex(ValueError,'Truncated'):parse(response,definition)
        response['finish_reason']='tool_calls'
        response['message']['tool_calls']*=2
        with self.assertRaisesRegex(ValueError,'one requested'):parse(response,definition)

    def test_schema_stays_compact_and_local_validation_retains_uniqueness(self):
        small=review_definition(self.ids,[7])
        large=review_definition([f"{'a'*64}:{i}" for i in range(1000)],list(range(1000)))
        self.assertLess(abs(len(json.dumps(large))-len(json.dumps(small))),10)
        self.assertNotIn('uniqueItems',json.dumps(provider_schema(large)))
        self.answer['observations'][0]['transaction_ids']=['source:1','source:1']
        with self.assertRaisesRegex(ValueError,'Repeated array'):
            validate(small['parameters'],self.answer)


if __name__=='__main__':unittest.main()
