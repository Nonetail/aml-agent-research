import copy
import json
import unittest

from cycle_detection import (FUNCTION, MAX_MATCHES, MAX_OUTPUT_TOKENS,
                             accept_response, request_for, validate_matches)


class CompactCycleTests(unittest.TestCase):
    def setUp(self):
        self.answer = {'matches': [{'transaction_ids': ['T1', 'T2'], 'confidence_percent': 73}]}

    def verify(self, ids):
        return {'valid': ids == ['T1', 'T2'], 'unavailable_ids': []}

    def check(self, answer=None, verify=None):
        return validate_matches(self.answer if answer is None else answer,
                                ['T1', 'T2', 'T3'], verify or self.verify)

    def response(self):
        return {'finish_reason': 'tool_calls', 'message': {'tool_calls': [
            {'function': {'name': FUNCTION, 'arguments': json.dumps(self.answer)}}]}}

    def test_confidence_remains_separate_from_verified_facts(self):
        original = copy.deepcopy(self.answer)
        checked = accept_response(self.response(), ['T1', 'T2'], self.verify)
        self.assertEqual(checked['matches'][0]['confidence_percent'], 73)
        self.assertTrue(checked['matches'][0]['verification']['valid'])
        self.assertEqual(checked['coverage'], 'not_established')
        self.assertEqual(self.answer, original)

    def test_confidence_is_required_integer_between_zero_and_hundred(self):
        for value in (-1, 101, True, 0.95, '95'):
            self.answer['matches'][0]['confidence_percent'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check()
        for value in (0, 100):
            self.answer['matches'][0]['confidence_percent'] = value
            self.check()
        del self.answer['matches'][0]['confidence_percent']
        with self.assertRaises(ValueError):
            self.check()

    def test_explanations_and_other_extra_fields_are_rejected(self):
        for location in ('top', 'match'):
            answer = copy.deepcopy(self.answer)
            target = answer if location == 'top' else answer['matches'][0]
            target['reason'] = 'An explanation is not part of this contract.'
            with self.subTest(location=location), self.assertRaises(ValueError):
                self.check(answer)

    def test_unknown_ids_rejected_before_lookup(self):
        self.answer['matches'][0]['transaction_ids'] = ['T1', 'invented']
        with self.assertRaisesRegex(ValueError, 'Unsupplied'):
            self.check(verify=lambda ids: self.fail('Unknown IDs reached source lookup'))

    def test_high_confidence_cannot_override_wrong_path_order(self):
        self.answer['matches'][0].update(transaction_ids=['T2', 'T1'], confidence_percent=100)
        with self.assertRaisesRegex(ValueError, 'Invalid cycle'):
            self.check()

    def test_missing_source_and_nonboolean_verification_are_rejected(self):
        for result in ({'valid': True, 'unavailable_ids': ['T2']}, {'valid': 1}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                self.check(verify=lambda ids: result)

    def test_duplicate_edges_and_duplicate_matches_are_rejected(self):
        self.answer['matches'][0]['transaction_ids'] = ['T1', 'T1']
        with self.assertRaises(ValueError):
            self.check()
        self.answer['matches'][0]['transaction_ids'] = ['T1', 'T2']
        self.answer['matches'] *= 2
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.check()

    def test_empty_output_does_not_claim_search_completion(self):
        self.assertEqual(self.check({'matches': []}),
                         {'matches': [], 'coverage': 'not_established', 'candidate_limit_reached': False})

    def test_candidate_limit_is_enforced_and_visible(self):
        matches = [{'transaction_ids': [f'T{i*2}', f'T{i*2+1}'], 'confidence_percent': 95}
                   for i in range(MAX_MATCHES)]
        ids = [i for m in matches for i in m['transaction_ids']]
        verifier = lambda ids: {'valid': True}
        checked = validate_matches({'matches': matches}, ids, verifier)
        self.assertTrue(checked['candidate_limit_reached'])
        with self.assertRaises(ValueError):
            validate_matches({'matches': matches + [matches[0]]}, ids, verifier)

    def test_prose_truncation_and_wrong_or_multiple_calls_are_rejected(self):
        truncated = self.response(); truncated['finish_reason'] = 'length'
        prose = self.response(); prose['message']['content'] = 'Let me explain.'
        wrong = self.response(); wrong['message']['tool_calls'][0]['function']['name'] = 'other'
        multiple = self.response(); multiple['message']['tool_calls'] *= 2
        for response in (truncated, prose, wrong, multiple):
            with self.subTest(response=response), self.assertRaises(ValueError):
                accept_response(response, ['T1', 'T2'], self.verify)

    def test_request_selects_compact_function_with_bounded_generation(self):
        request = request_for('unchanged evidence', 'selected-model')
        self.assertEqual(request['messages'][1]['content'], 'unchanged evidence')
        self.assertEqual(request['model'], 'selected-model')
        self.assertEqual(request['tool_choice']['function']['name'], FUNCTION)
        self.assertEqual(request['max_tokens'], MAX_OUTPUT_TOKENS)
        self.assertFalse(request['chat_template_kwargs']['enable_thinking'])
        self.assertFalse(request['parallel_tool_calls'])


if __name__ == '__main__':
    unittest.main()
