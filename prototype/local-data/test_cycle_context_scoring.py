import unittest

from cycle_context_scoring import oracle_cycles, score_answer


def row(i, source, destination, minute, source_bank='1', destination_bank='1'):
    return {'transaction_id': f'T{i}', 'source_bank': source_bank, 'source_account': source,
            'destination_bank': destination_bank, 'destination_account': destination,
            'timestamp': f'2022/09/01 00:{minute:02d}'}


def answer(paths=(), present=True, status='insufficient_evidence'):
    return {'observations': [{'transaction_ids': list(path), 'pattern_present': present,
                             'status': status, 'reason': 'Evidence assessment.', 'limitations': []}
                            for path in paths], 'evidence_requests': [], 'limitations': []}


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.rows = [row(1, 'A', 'B', 1), row(2, 'B', 'C', 2),
                     row(3, 'C', 'D', 3), row(4, 'D', 'A', 4)]
        self.path = ('T1', 'T2', 'T3', 'T4')

    def test_four_edges_and_shuffled_input(self):
        self.assertEqual(oracle_cycles(self.rows[::-1]), [self.path])
        self.assertTrue(score_answer(self.rows, answer([self.path]))['structural_exact'])

    def test_ties_bank_identity_self_edge_and_internal_repeat(self):
        self.assertEqual(oracle_cycles([row(1, 'A', 'B', 1), row(2, 'B', 'A', 1)]), [])
        self.assertEqual(oracle_cycles([row(1, 'A', 'B', 1), row(2, 'B', 'A', 2, '2')]), [])
        self.assertEqual(oracle_cycles([row(1, 'A', 'A', 1)]), [])
        rows = [row(1, 'A', 'B', 1), row(2, 'B', 'A', 2), row(3, 'A', 'B', 3), row(4, 'B', 'A', 4)]
        self.assertTrue(all(len(path) == 2 for path in oracle_cycles(rows)))

    def test_parallel_edges_are_distinct(self):
        rows = [row(1, 'A', 'B', 1), row(2, 'A', 'B', 1), row(3, 'B', 'A', 2)]
        self.assertEqual(oracle_cycles(rows), [('T1', 'T3'), ('T2', 'T3')])
        with self.assertRaises(ValueError):
            oracle_cycles(rows + [rows[0]])

    def test_omission_false_claim_and_unknown_id(self):
        self.assertEqual(score_answer(self.rows, answer(), [self.path])['target_recall'], 0)
        score = score_answer(self.rows, answer([self.path], False, 'not_supported'))
        self.assertFalse(score['response_valid'])
        self.assertEqual(score['claim_mismatches'], 1)
        score = score_answer(self.rows, answer([('T1', 'T999')]))
        self.assertEqual(score['unknown_ids'], ['T999'])
        self.assertEqual(score['structural_recovered'], 0)

    def test_valid_false_observation_is_not_recovery(self):
        score = score_answer(self.rows, answer([('T1', 'T2')], False, 'not_supported'))
        self.assertTrue(score['response_valid'])
        self.assertEqual(score['valid_false_observations'], 1)
        self.assertEqual(score['structural_recovered'], 0)

    def test_duplicate_response_strictly_fails_but_preserves_diagnostics(self):
        score = score_answer(self.rows, answer([self.path, self.path]))
        self.assertEqual(score['duplicate_supports'], 1)
        self.assertFalse(score['response_valid'])
        self.assertEqual(score['structural_recovered'], 0)
        self.assertEqual(score['raw_valid_cycles'], [list(self.path)])

    def test_structural_zero_label_cycle_is_not_false_positive(self):
        score = score_answer(self.rows, answer([self.path]), [self.path], {f'T{i}': 0 for i in range(1, 5)})
        self.assertTrue(score['structural_exact'])
        self.assertEqual(score['accepted_cycle_label_composition'], {'zero_positive': 1})
        self.assertEqual(score['investigate_zero_label_row_ids'], [])

    def test_positive_flags_are_separate_from_pattern_recovery(self):
        labels = {f'T{i}': int(i != 4) for i in range(1, 5)}
        score = score_answer(self.rows, answer([self.path], status='investigate'), [self.path], labels)
        self.assertEqual(score['target_recall'], 1)
        self.assertEqual(score['accepted_cycle_label_composition'], {'mixed': 1})
        self.assertEqual(score['investigate_positive_row_ids'], ['T1', 'T2', 'T3'])
        self.assertEqual(score['investigate_zero_label_row_ids'], ['T4'])

    def test_split_target_is_retained_in_denominator(self):
        score = score_answer(self.rows[:3], answer(), [self.path])
        self.assertEqual(score['target_count'], 1)
        self.assertEqual(score['target_visibility_ceiling'], 0)
        self.assertEqual(score['target_recall'], 0)
        self.assertTrue(score['structural_exact'])

    def test_missing_malformed_empty_and_unadvertised_scope(self):
        for bad in (None, {}, {'observations': 'bad'}, answer() | {'unexpected': 1}):
            self.assertFalse(score_answer(self.rows, bad)['response_valid'])
        self.assertTrue(score_answer([], answer())['structural_exact'])
        bad = answer([self.path])
        bad['evidence_requests'] = [{'scope_id': 1, 'reason': 'More rows.'}]
        self.assertFalse(score_answer(self.rows, bad)['response_valid'])


if __name__ == '__main__':
    unittest.main()
