import json
import hashlib
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from cycle_workflow import CycleWorkflow
import test_cycle_tools

START, END = test_cycle_tools.START, test_cycle_tools.END


class CycleWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_cycle_tools.CycleToolsTests()
        self.fixture.setUp()
        self.ledger = Path(self.fixture.temp.name)/'cycle-ledger.sqlite'
        self.workflow = self.open()

    def open(self, **kwargs):
        return CycleWorkflow(self.fixture.path, self.ledger, START, END, **kwargs)

    def tearDown(self):
        self.workflow.close()
        self.fixture.tearDown()

    def exhaust(self, seed_rows=2, row_budget=1):
        for _ in range(500):
            result = self.workflow.advance(seed_rows=seed_rows, row_budget=row_budget)
            if result['discovery_complete']:
                return result
        self.fail('Fixture discovery did not finish')

    def paths(self):
        return {tuple(json.loads(row[0])) for row in self.workflow.db.execute('SELECT path FROM candidates')}

    def observation(self, numbers=(1, 3, 4)):
        return {'transaction_ids': self.fixture.ids(*numbers), 'pattern_present': True,
                'status': 'insufficient_evidence', 'reason': 'A return cycle exists; purpose is unknown.',
                'limitations': ['No customer purpose or balances supplied.']}

    def answer(self, observations):
        return {'observations': observations, 'evidence_requests': [], 'limitations': []}

    def test_complete_scoped_search_across_pages_keeps_alternatives(self):
        result = self.exhaust()
        self.assertEqual(result['seeded_external_edges'], 15)
        self.assertEqual(result['assessed_candidates'], 0)
        self.assertEqual(result['prototype_provider_calls'], 0)
        for numbers in ((1, 3, 4), (1, 17, 4), (1, 5), (1, 6, 7), (1, 2, 13, 14)):
            self.assertIn(tuple(self.fixture.ids(*numbers)), self.paths())
        before = result['retrieval_actions']
        self.assertEqual(self.workflow.advance()['retrieval_actions'], before)

    def test_resume_preserves_committed_actions_and_exact_search_result(self):
        self.workflow.advance(seed_rows=1, row_budget=1)
        self.workflow.advance(seed_rows=1, row_budget=1)
        before = list(self.workflow.db.execute('SELECT kind,body FROM events'))
        self.workflow.close()
        self.workflow = self.open()
        self.exhaust()
        after = list(self.workflow.db.execute('SELECT kind,body FROM events ORDER BY id'))
        self.assertEqual([tuple(r) for r in after[:len(before)]], [tuple(r) for r in before])
        result = self.paths()
        second = Path(self.fixture.temp.name)/'other.sqlite'
        fresh = CycleWorkflow(self.fixture.path, second, START, END)
        try:
            while not fresh.advance(seed_rows=20, row_budget=100)['discovery_complete']:
                pass
            paths = {tuple(json.loads(r[0])) for r in fresh.db.execute('SELECT path FROM candidates')}
            self.assertEqual(paths, result)
        finally:
            fresh.close()

    def test_failed_page_commit_rolls_back_cursor_and_partial_paths(self):
        self.workflow.advance(seed_rows=1, row_budget=1)
        before = self.workflow.status()
        original = self.workflow._enqueue

        def fail(path):
            original(path)
            raise RuntimeError('Injected failure before cursor commit')

        with patch.object(self.workflow, '_enqueue', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'Injected'):
                self.workflow.advance(row_budget=1)
        self.assertEqual(self.workflow.status(), before)
        self.exhaust()
        self.assertIn(tuple(self.fixture.ids(1, 3, 4)), self.paths())

    def test_writer_lock_and_changed_rule_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Another writer'):
            self.open()
        self.workflow.close()
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.open(max_edges=3)
        self.workflow = self.open()

    def test_source_and_ledger_aliases_rejected_without_mutation(self):
        before = hashlib.sha256(self.fixture.path.read_bytes()).hexdigest()
        root = Path(self.fixture.temp.name)
        symbolic, hard = root/'symbolic.sqlite', root/'hard.sqlite'
        symbolic.symlink_to(self.fixture.path)
        os.link(self.fixture.path, hard)
        for path in (self.fixture.path, symbolic, hard):
            with self.assertRaisesRegex(ValueError, 'different file'):
                CycleWorkflow(self.fixture.path, path, START, END)
        self.assertEqual(hashlib.sha256(self.fixture.path.read_bytes()).hexdigest(), before)

    def test_navigation_replay_is_immutable_and_does_not_advance_twice(self):
        packet = self.workflow.packet('navigator')
        answer = {'scope_ids': [], 'reason': 'Begin systematic exploration.'}
        result = self.workflow.accept_navigation(packet['packet_id'], answer, seed_rows=1)
        self.assertEqual(self.workflow.accept_navigation(packet['packet_id'], answer), result)
        self.assertEqual(self.workflow.status()['retrieval_actions'], 1)
        with self.assertRaisesRegex(ValueError, 'immutable'):
            self.workflow.accept_navigation(packet['packet_id'], {**answer, 'reason': 'Changed'})

    def test_exploratory_review_can_add_new_verified_cycle_without_labels(self):
        packet = self.workflow.packet('reviewer', extra_ids=self.fixture.ids(1, 3, 4))
        payload = json.loads(packet['request']['messages'][1]['content'])
        self.assertEqual(payload['verified_candidates'], [])
        self.assertTrue(all('is_laundering' not in row for row in payload['rows']))
        self.assertEqual(packet['token_admission'], 'not_evaluated')
        answer = self.answer([self.observation()])
        result = self.workflow.accept_review(packet['packet_id'], answer)
        self.assertTrue(result['observations'][0]['verification']['valid'])
        self.assertEqual(self.workflow.status()['assessed_candidates'], 1)
        self.assertEqual(self.workflow.accept_review(packet['packet_id'], answer), result)
        with self.assertRaisesRegex(ValueError, 'immutable'):
            self.workflow.accept_review(packet['packet_id'], self.answer([]))

    def test_unaddressed_candidates_remain_pending_and_next_packet_has_new_context(self):
        self.exhaust()
        first = self.workflow.packet('reviewer')
        self.workflow.accept_review(first['packet_id'], self.answer([]))
        self.assertEqual(self.workflow.status()['assessed_candidates'], 0)
        second = self.workflow.packet('reviewer')
        self.assertNotEqual(first['packet_id'], second['packet_id'])
        self.assertEqual(first['candidate_ids'], second['candidate_ids'])

    def test_false_cycle_claim_rejected_without_receipt_or_candidate(self):
        packet = self.workflow.packet('reviewer', extra_ids=self.fixture.ids(1, 3))
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.workflow.accept_review(packet['packet_id'], self.answer([self.observation((1, 3))]))
        self.assertEqual(self.workflow.status()['structural_candidates'], 0)
        self.assertEqual(self.workflow.db.execute('SELECT count(*) FROM assessments').fetchone()[0], 0)

    def test_empty_review_is_not_scheduled_and_followup_keeps_other_work(self):
        with self.assertRaisesRegex(ValueError, 'No candidate review'):
            self.workflow.packet('reviewer')
        self.workflow.advance(seed_rows=3)
        before = self.workflow.status()['pending_scopes']
        packet = self.workflow.packet('reviewer', extra_ids=self.fixture.ids(1, 3))
        requested = packet['scope_ids'][-1]
        answer = self.answer([])
        answer['evidence_requests'] = [{'scope_id': requested, 'reason': 'Check a later closing transfer.'}]
        self.workflow.accept_review(packet['packet_id'], answer)
        self.assertEqual(self.workflow.pending()[0]['id'], requested)
        self.assertEqual(self.workflow.status()['pending_scopes'], before)

    def test_candidate_waits_for_followup_then_reopens_with_new_evidence(self):
        self.workflow.advance(seed_rows=1)
        packet = self.workflow.packet('reviewer', extra_ids=self.fixture.ids(1, 3, 4))
        scope = packet['scope_ids'][0]
        answer = self.answer([self.observation()])
        answer['evidence_requests'] = [{'scope_id': scope, 'reason': 'Check competing later transfers.'}]
        checked = self.workflow.accept_review(packet['packet_id'], answer)
        self.assertEqual(checked['followup_dispositions'], [{'scope_id': scope, 'status': 'prioritized'}])
        self.assertEqual(self.workflow.status()['assessed_candidates'], 0)
        with self.assertRaisesRegex(ValueError, 'No candidate review'):
            self.workflow.packet('reviewer')
        self.workflow.advance(scope_ids=[scope], row_budget=1)
        with self.assertRaisesRegex(ValueError, 'No candidate review'):
            self.workflow.packet('reviewer')
        while not self.workflow.db.execute('SELECT done FROM frontier WHERE id=?', (scope,)).fetchone()[0]:
            self.workflow.advance(scope_ids=[scope], row_budget=1)
        followup = self.workflow.packet('reviewer')
        self.assertIn('fixture:2', followup['transaction_ids'])
        self.assertIn(scope, json.loads(followup['request']['messages'][1]['content'])['completed_followup_scopes'])
        self.workflow.accept_review(followup['packet_id'], self.answer([self.observation()]))
        row = self.workflow.db.execute('SELECT assessed FROM candidates WHERE path=?',
                                      (json.dumps(self.fixture.ids(1, 3, 4), separators=(',', ':')),)).fetchone()
        self.assertEqual(row[0], 1)

    def assert_delayed_followup_preserves_earlier_pages(self, earlier_pages):
        self.workflow.advance(seed_rows=1)
        packet = self.workflow.packet('reviewer', extra_ids=self.fixture.ids(1, 3, 4))
        scope = packet['scope_ids'][0]
        for _ in range(earlier_pages):
            self.workflow.advance(scope_ids=[scope], row_budget=1)
        self.workflow.close()
        self.workflow = self.open()
        answer = self.answer([self.observation()])
        answer['evidence_requests'] = [{'scope_id': scope, 'reason': 'Inspect competing continuations and returns.'}]
        accepted = self.workflow.accept_review(packet['packet_id'], answer)
        candidate = self.workflow.db.execute('SELECT id FROM candidates WHERE path=?',
            (json.dumps(self.fixture.ids(1, 3, 4), separators=(',', ':')),)).fetchone()[0]
        evidence = lambda: {row[0] for row in self.workflow.db.execute(
            'SELECT transaction_id FROM followup_evidence WHERE candidate_id=?', (candidate,))}
        expected = self.fixture.ids(2, 3, 17, 5, 6)
        self.assertEqual(evidence(), set(expected[:earlier_pages]))
        while not self.workflow.db.execute('SELECT done FROM frontier WHERE id=?', (scope,)).fetchone()[0]:
            self.workflow.advance(scope_ids=[scope], row_budget=1)
        self.assertEqual(evidence(), set(expected))
        followup = self.workflow.packet('reviewer')
        self.assertTrue(set(expected) <= set(followup['transaction_ids']))
        before = self.workflow.status()
        self.assertEqual(self.workflow.accept_review(packet['packet_id'], answer), accepted)
        self.assertEqual(self.workflow.status(), before)
        self.assertEqual(evidence(), set(expected))

    def test_delayed_followup_backfills_a_scope_completed_before_acceptance(self):
        self.assert_delayed_followup_preserves_earlier_pages(5)

    def test_delayed_followup_combines_previous_pages_with_future_pages(self):
        self.assert_delayed_followup_preserves_earlier_pages(1)


if __name__ == '__main__':
    unittest.main()
