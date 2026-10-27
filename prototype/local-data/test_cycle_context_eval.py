"""Offline runner/provenance checks; tokenizer and provider are always mocked."""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import cycle_context_eval as evaluation
import model as provider


def fixture_rows():
    return [dict(transaction_id=f'T{i}', timestamp=f'2022/09/02 00:0{i}',
                 source_bank='001', source_account=source,
                 destination_bank='001', destination_account=destination,
                 paid_amount='12.0300', paid_currency='US Dollar',
                 received_amount='10.02', received_currency='Euro',
                 payment_format='Wire, transfer', is_laundering=1,
                 evaluator_answer='HIDDEN_REFERENCE_SUPPORT')
            for i, source, destination in [(1, 'A', 'B'), (2, 'B', 'A')]]


def response(usage=None):
    answer = {'observations': [], 'evidence_requests': [], 'limitations': []}
    return {'message': {'tool_calls': [{'function': {'name': 'assess_cycle_evidence',
                        'arguments': json.dumps(answer)}}]},
            'finish_reason': 'tool_calls', 'usage': usage, 'seconds': 0.01}


class CycleContextRequestTests(unittest.TestCase):
    def test_csv_preserves_exact_fields_and_excludes_evaluator_answers(self):
        rows = fixture_rows()
        request = evaluation.request_for(rows, 'source-hash')
        metadata, table = request['messages'][1]['content'].split('\n', 1)
        self.assertEqual(json.loads(metadata)['source_sha256'], 'source-hash')
        decoded = list(csv.DictReader(io.StringIO(table)))
        self.assertEqual(decoded[0], dict(zip(evaluation.COLUMNS,
            ['T1', '2022/09/02 00:01', '001', 'A', '001', 'B', '12.0300',
             'US Dollar', '10.02', 'Euro', 'Wire, transfer'])))
        rendered = json.dumps(request)
        for secret in ('is_laundering', 'HIDDEN_REFERENCE_SUPPORT', 'group_id', 'targets', 'base_oracle'):
            self.assertNotIn(secret, rendered)
        changed = deepcopy(rows)
        for row in changed:
            row['is_laundering'] = 0
            row['evaluator_answer'] = 'DIFFERENT_GOLD'
        self.assertEqual(request, evaluation.request_for(changed, 'source-hash'))
        self.assertEqual(request['tool_choice']['function']['name'], 'assess_cycle_evidence')
        self.assertFalse(request['parallel_tool_calls'])

    def test_saved_request_matches_provider_body_without_network(self):
        request = evaluation.request_for(fixture_rows(), 'source-hash')
        client = provider.Model.__new__(provider.Model)
        client.key = 'offline-placeholder'
        raw = {'choices': [{'message': {'role': 'assistant', 'content': 'offline'},
                            'finish_reason': 'stop'}], 'usage': None}
        transport = MagicMock()
        transport.open.return_value.__enter__.return_value.read.return_value = json.dumps(raw).encode()
        with patch.object(provider.request, 'build_opener', return_value=transport):
            client.complete(request['messages'], request['tools'], request['tool_choice'], request['max_tokens'])
        self.assertEqual(json.loads(transport.open.call_args.args[0].data), request)

    def test_extract_rejects_truncation_multiple_calls_and_wrong_function(self):
        invalid = response()
        invalid['finish_reason'] = 'length'
        multiple = response()
        multiple['message']['tool_calls'] *= 2
        wrong = response()
        wrong['message']['tool_calls'][0]['function']['name'] = 'other'
        for item in (invalid, multiple, wrong):
            with self.assertRaises(ValueError):
                evaluation.extract_answer(item)


class CycleContextRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('runtime', 'evaluator', 'calls'):
            (self.root/name).mkdir()
        evaluation.save(self.root/'runtime/dev-2.json', fixture_rows())
        evaluation.save(self.root/'evaluator/dev-2.json',
                        {'targets': [['T1', 'T2']], 'labels': {'T1': 1, 'T2': 1}})
        self.manifest = {'source_sha256': 'source-hash', 'max_calls': 3,
                         'max_tokens': 1500, 'context_cap': 200000, 'safety_tokens': 4096}
        self.counter = MagicMock()
        self.counter.admission.return_value = dict(local_prompt_tokens=100,
            output_reserve=300, safety_tokens=100, reserved_total=500,
            context_cap=200000, admitted=True)
        self.model = MagicMock()
        self.model.complete.return_value = response({'total_tokens': 200})
        patches = [patch.object(evaluation, 'ROOT', self.root),
                   patch.object(evaluation, 'verify_manifest', return_value=self.manifest),
                   patch.object(evaluation, 'Model', return_value=self.model),
                   patch.dict('sys.modules', {'context_tokens': SimpleNamespace(ContextTokens=lambda: self.counter)}),
                   patch('builtins.print')]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.runner = evaluation.Runner()

    @staticmethod
    def job(ident='job-1'):
        return {'id': ident, 'case': 'dev-2', 'condition': 'single-1500',
                'repetition': 1, 'row_ids': ['T1', 'T2']}

    def test_replay_preserves_attempt_and_exact_request(self):
        result = self.runner.execute(self.job())
        before = (self.root/'attempts.json').read_bytes()
        replay = self.runner.execute(self.job())
        self.assertEqual(result['status'], 'received')
        self.assertEqual(replay['status'], 'existing_attempt_preserved')
        self.assertEqual((self.root/'attempts.json').read_bytes(), before)
        self.model.complete.assert_called_once()
        self.assertEqual(json.loads((self.root/'calls/job-1/request.json').read_text()),
                         evaluation.request_for(fixture_rows(), 'source-hash'))
        resumed = evaluation.Runner()
        self.assertEqual(len(resumed.records), 1)
        resumed.execute(self.job())
        self.model.complete.assert_called_once()

    def test_provider_errors_are_recorded_once_with_unknown_usage_reserved(self):
        self.model.complete.side_effect = provider.ProviderError(429)
        result = self.runner.execute(self.job())
        self.assertEqual(result['status'], 'provider_error')
        self.assertEqual(result['http_status'], 429)
        self.assertIsNone(result['usage'])
        self.assertEqual(self.runner.records[0]['reserved_total'], 500)
        self.assertTrue((self.root/'calls/job-1/result.json').exists())
        self.manifest['max_tokens'] = 999
        with self.assertRaises(ValueError):
            self.runner.execute(self.job('job-2'))
        self.model.complete.assert_called_once()

    def test_returned_invalid_response_retains_reported_usage(self):
        invalid = response({'total_tokens': 201})
        invalid['finish_reason'] = 'length'
        self.model.complete.return_value = invalid
        result = self.runner.execute(self.job())
        self.assertEqual(result['status'], 'invalid_response')
        self.assertEqual(self.runner.records[0]['usage']['total_tokens'], 201)
        self.assertTrue((self.root/'calls/job-1/response.json').exists())
        self.assertNotIn('score', result)

    def test_inflight_and_missing_usage_debit_full_reservation(self):
        for usage in (None, {}, {'prompt_tokens': 100}):
            self.runner.records = [{'id': 'inflight', 'reserved_total': 1001, 'usage': usage}]
            with self.assertRaises(ValueError):
                self.runner.execute(self.job())
        self.model.complete.assert_not_called()

    def test_null_usage_total_debits_reservation_instead_of_crashing(self):
        self.runner.records = [{'id': 'unknown', 'reserved_total': 1001,
                                'usage': {'total_tokens': None}}]
        with self.assertRaises(ValueError):
            self.runner.execute(self.job())
        self.model.complete.assert_not_called()

    def test_call_ceiling_counts_provider_failures_and_reservations(self):
        self.manifest['max_calls'] = 1
        self.runner.records = [{'id': 'prior', 'reserved_total': 500, 'usage': None}]
        with self.assertRaises(ValueError):
            self.runner.execute(self.job())
        self.model.complete.assert_not_called()

    def test_local_admission_uses_frozen_cap_and_safety_margin(self):
        self.manifest.update(context_cap=12345, safety_tokens=789)
        self.runner.execute(self.job())
        self.assertEqual(self.counter.admission.call_args.kwargs,
                         {'context_cap': 12345, 'safety_tokens': 789})

    def test_ineligible_context_is_saved_without_provider_call(self):
        self.counter.admission.return_value['admitted'] = False
        try:
            self.runner.execute(self.job())
        except ValueError:
            pass
        self.model.complete.assert_not_called()
        path = self.root/'calls/job-1/result.json'
        self.assertTrue(path.exists(), 'An ineligible condition needs a persistent result')
        result = json.loads(path.read_text())
        self.assertNotEqual(result['status'], 'received')
        self.assertEqual(result['local_prompt_tokens'], 100)


class CycleContextManifestTests(unittest.TestCase):
    def test_manifest_detects_source_and_packet_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, packet = root/'implementation.py', root/'packet.json'
            source.write_text('frozen implementation')
            packet.write_text('frozen rows')
            manifest = {'sources': {'implementation.py': evaluation.digest(source)},
                        'inputs': {'packet.json': evaluation.digest(packet)}}
            evaluation.save(root/'manifest.json', manifest)
            with patch.object(evaluation, 'ROOT', root), patch.object(evaluation, 'HERE', root):
                self.assertEqual(evaluation.verify_manifest(), manifest)
                packet.write_text('changed rows')
                with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
                    evaluation.verify_manifest()
                packet.write_text('frozen rows')
                source.write_text('changed algorithm')
                with self.assertRaisesRegex(ValueError, 'Frozen implementation changed'):
                    evaluation.verify_manifest()


class CycleContextFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ('runtime', 'evaluator', 'calls'):
            (self.root/directory).mkdir()
        self.patch = patch.object(evaluation, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.supports = [['T1', 'T2'], ['T3', 'T4']]
        rows = fixture_rows()
        rows += [dict(rows[0], transaction_id='T3', source_account='C', destination_account='D'),
                 dict(rows[1], transaction_id='T4', source_account='D', destination_account='C')]
        rows += [dict(rows[0], transaction_id=f'T{i}', source_account=f'X{i}',
                      destination_account=f'Y{i}') for i in range(5, 1601)]
        jobs = []
        for name in ('dev-2', 'dev-3', 'dev-4', 'holdout-2', 'holdout-3', 'holdout-4'):
            evaluation.save(self.root/'runtime'/f'{name}.json', rows)
            evaluation.save(self.root/'evaluator'/f'{name}.json',
                            {'targets': self.supports[:1], 'base_oracle': self.supports})
            if name.startswith('holdout'):
                continue
            initial = {'id': name+'--baseline', 'case': name, 'condition': 'single-1500',
                       'repetition': 1, 'row_ids': [r['transaction_id'] for r in rows[:1500]]}
            jobs.append(initial)
            directory = self.root/'calls'/initial['id']
            directory.mkdir()
            accepted = self.supports if name == 'dev-2' else []
            evaluation.save(directory/'result.json', dict(initial, status='received',
                            score={'accepted_cycles': accepted, 'response_valid': True}))
            # Response order differs from the scorer's sorted accepted support order.
            evaluation.save(directory/'answer.json', {'observations': [
                {'transaction_ids': path, 'pattern_present': True,
                 'status': 'insufficient_evidence', 'reason': 'Unknown purpose', 'limitations': []}
                for path in reversed(accepted)], 'evidence_requests': [], 'limitations': []})
            for count in (2, 3, 4):
                for part in range(count):
                    job = dict(initial, id=f'{name}--graph-{count}--r1-p{part}',
                               condition=f'graph-{count}', group_part=part, group_count=count)
                    jobs.append(job)
                    directory = self.root/'calls'/job['id']
                    directory.mkdir()
                    found = (self.supports if count == 3 else self.supports[:1]) if part == 0 else []
                    evaluation.save(directory/'result.json', dict(job, status='received',
                                    usage={'total_tokens': 100}, score={
                                        'accepted_cycles': found, 'response_valid': True,
                                        'structural_recovered': len(found), 'claim_mismatches': 0,
                                        'unknown_ids': [], 'duplicate_supports': 0}))
        evaluation.save(self.root/'jobs.json', jobs)

    def test_boundary_unavailable_without_initial_model_path(self):
        jobs = evaluation.followup_jobs()
        boundary = [j for j in jobs if j['condition'] == 'overlap-boundary']
        self.assertEqual([j['case'] for j in boundary], ['dev-2'])
        scenarios = json.loads((self.root/'followup-scenarios.json').read_text())
        self.assertEqual(scenarios['dev-2--overlap-boundary']['anchor_id'], 'T3')
        self.assertEqual(scenarios['dev-2--overlap-boundary']['retained_ids'], ['T3', 'T4'])

    def test_invalid_saved_answer_cannot_break_followup_selection(self):
        path = self.root/'calls/dev-3--baseline/answer.json'
        evaluation.save(path, [])
        jobs = evaluation.followup_jobs()
        self.assertFalse(any(j['case'] == 'dev-3' and j['condition'] == 'overlap-boundary' for j in jobs))

    def test_unknown_reported_usage_does_not_crash_policy_ranking(self):
        path = self.root/'calls/dev-2--graph-3--r1-p0/result.json'
        result = json.loads(path.read_text())
        result.update(usage={'total_tokens': None}, local_prompt_tokens=100)
        evaluation.save(path, result)
        evaluation.followup_jobs()
        selection = json.loads((self.root/'followup-selection.json').read_text())
        self.assertEqual(selection['selected_group_count'], 3)

    def test_policy_ranking_uses_structural_recall_before_cost(self):
        jobs = evaluation.followup_jobs()
        selection = json.loads((self.root/'followup-selection.json').read_text())
        self.assertEqual(selection['selected_group_count'], 3)
        self.assertEqual(len({j['id'] for j in jobs}), len(jobs))
        for name in ('holdout-2', 'holdout-3', 'holdout-4'):
            for repetition in (1, 2):
                parts = [j for j in jobs if j['case'] == name and
                         j['condition'] == 'graph-3' and j['repetition'] == repetition]
                self.assertEqual(sorted(j['group_part'] for j in parts), [0, 1, 2])
                self.assertEqual(len(set(i for j in parts for i in j['row_ids'])), 1500)
                self.assertEqual(sum(len(j['row_ids']) for j in parts), 1500)
        before = (self.root/'followup-jobs.json').read_bytes()
        self.assertEqual(jobs, evaluation.followup_jobs())
        self.assertEqual(before, (self.root/'followup-jobs.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
