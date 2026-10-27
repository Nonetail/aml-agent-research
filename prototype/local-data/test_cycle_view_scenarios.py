"""Scenario checks use external known supports solely for assertions."""
from copy import deepcopy
import json
import random
import unittest

from cycle_view_scenarios import overlap_metrics, overlap_views, partition_views


def row(number, source, destination, minute=None, source_bank='1', destination_bank='1'):
    return {'transaction_id': f'fixture:{number}',
            'timestamp': f'2022/09/02 00:{number if minute is None else minute:02d}',
            'source_bank': source_bank, 'source_account': source,
            'destination_bank': destination_bank, 'destination_account': destination,
            'is_laundering': number % 2, 'evaluator_only': 'must not escape'}


def contained(support, views):
    return any(set(support) <= set(view) for view in views)


class CycleViewScenarioTests(unittest.TestCase):
    def setUp(self):
        self.pool = [row(i, f'A{i}', f'A{i+1}') for i in range(1, 21)]

    def test_graph_grouping_retains_connected_account_bundles(self):
        rows = [row(1, 'A', 'B'), row(2, 'D', 'E'), row(3, 'B', 'C'),
                row(4, 'E', 'F'), row(5, 'C', 'A'), row(6, 'F', 'D')]
        supports = [['fixture:1', 'fixture:3', 'fixture:5'],
                    ['fixture:2', 'fixture:4', 'fixture:6']]
        graph = partition_views(rows, 2, 'graph', 'fixture:1')
        chronological = partition_views(rows, 2, 'chronological')
        self.assertEqual(graph['view_rows'], [3, 3])
        self.assertEqual(graph['cut_edges'], 0)
        self.assertGreater(chronological['cut_edges'], 0)
        self.assertTrue(all(contained(s, graph['views']) for s in supports))
        self.assertFalse(any(contained(s, chronological['views']) for s in supports))

    def test_graph_grouping_does_not_claim_to_preserve_cross_group_cycle(self):
        rows = [row(1, 'A', 'B'), row(2, 'B', 'C'), row(3, 'C', 'D'), row(4, 'D', 'A')]
        support = [r['transaction_id'] for r in rows]
        result = partition_views(rows, 2, anchor_id='fixture:1')
        self.assertFalse(contained(support, result['views']))
        self.assertTrue(contained(support, [sum(result['views'], [])]))
        self.assertGreater(result['cut_edges'], 0)

    def test_every_partition_covers_pool_once_and_is_order_independent(self):
        shuffled = random.Random(43).sample(self.pool, len(self.pool))
        for count in (2, 3, 4):
            for strategy in ('graph', 'chronological'):
                result = partition_views(self.pool, count, strategy, 'fixture:1')
                self.assertEqual(result, partition_views(shuffled, count, strategy, 'fixture:1'))
                self.assertCountEqual(sum(result['views'], []), [r['transaction_id'] for r in self.pool])
                self.assertEqual(len(result['views']), count)

    def test_accounts_include_bank_and_bundles_are_never_split(self):
        rows = [row(1, 'A', 'X'), row(2, 'A', 'Y'), row(3, 'A', 'Z', source_bank='2')]
        graph = partition_views(rows, 2, 'graph')
        self.assertEqual(sorted(graph['view_rows']), [1, 2])
        self.assertEqual(graph['split_source_accounts'], 0)
        self.assertTrue(contained(['fixture:1', 'fixture:2'], graph['views']))

    def test_small_pool_reports_empty_partitions_without_losing_rows(self):
        result = partition_views(self.pool[:1], 4)
        self.assertEqual(result['view_rows'], [1, 0, 0, 0])
        self.assertEqual(partition_views([], 2)['views'], [[], []])

    def test_zero_overlap_keeps_anchor_and_reports_actual_cost(self):
        result = overlap_views(self.pool, 'fixture:1', 8, 0)
        self.assertEqual(result['metrics']['shared_rows'], 1)
        self.assertEqual(result['metrics']['overlap_fraction'], 1/8)
        self.assertEqual(result['metrics']['new_rows'], 7)
        self.assertEqual(result['metrics']['union_rows'], 15)
        self.assertTrue(all('fixture:1' in v for v in result['views']))

    def test_requested_overlap_grid_and_actual_union(self):
        for fraction in (0.25, 0.5, 0.75, 1):
            result = overlap_views(self.pool, 'fixture:1', 8, fraction)
            self.assertEqual([len(v) for v in result['views']], [8, 8])
            self.assertEqual(result['metrics']['overlap_fraction'], fraction)
            self.assertEqual(result['metrics']['union_rows'], 16-int(8*fraction))
            self.assertEqual(result['metrics']['new_rows'], 8-int(8*fraction))

    def test_candidate_boundary_is_separate_from_nominal_row_overlap(self):
        support = ['fixture:1', 'fixture:2', 'fixture:3']
        result = overlap_views(self.pool, 'fixture:1', 8, 0, retained_ids=support)
        self.assertEqual(result['metrics']['shared_rows'], 3)
        self.assertEqual(result['minimum_boundary_rows'], 3)
        self.assertTrue(all(set(support) <= set(v) for v in result['views']))
        anchor_only = overlap_views(self.pool, 'fixture:1', 8, 0)
        self.assertFalse(set(support) <= set(anchor_only['views'][1]))

    def test_fixed_baseline_is_preserved_even_if_shuffled(self):
        first = [f'fixture:{i}' for i in (8, 6, 3, 5, 2, 7, 1, 4)]
        result = overlap_views(self.pool, 'fixture:3', 8, 0.5,
                               retained_ids=['fixture:2'], first_view_ids=first)
        self.assertEqual(result['views'][0], first)
        self.assertEqual(result['metrics']['shared_rows'], 4)
        self.assertTrue({'fixture:3', 'fixture:2'} <= set(result['views'][1]))

    def test_small_pool_forces_more_overlap_without_shrinking_views(self):
        result = overlap_views(self.pool[:10], 'fixture:1', 8, 0)
        self.assertEqual(result['pool_forced_minimum_shared_rows'], 6)
        self.assertEqual(result['metrics']['shared_rows'], 6)
        self.assertEqual(result['metrics']['union_rows'], 10)
        self.assertEqual([len(v) for v in result['views']], [8, 8])

    def test_label_changes_do_not_change_decisions_or_mutate_input(self):
        original = deepcopy(self.pool)
        changed = deepcopy(self.pool)
        for r in changed:
            r['is_laundering'] = 1-r['is_laundering']
            r['evaluator_only'] = ['arbitrary', 'gold', 'support']
        for function, args in ((partition_views, (3,)), (overlap_views, ('fixture:1', 8, 0.25))):
            result = function(self.pool, *args)
            self.assertEqual(result, function(changed, *args))
            self.assertNotIn('evaluator_only', json.dumps(result))
            self.assertNotIn('is_laundering', json.dumps(result))
        self.assertEqual(original, self.pool)

    def test_bad_inputs_fail_instead_of_silently_losing_evidence(self):
        calls = [lambda: partition_views(self.pool*2, 2),
                 lambda: partition_views(self.pool, 5),
                 lambda: partition_views(self.pool, 2, 'oracle'),
                 lambda: overlap_views(self.pool, 'missing', 8, 0),
                 lambda: overlap_views(self.pool, 'fixture:1', 8, -0.1),
                 lambda: overlap_views(self.pool, 'fixture:1', 21, 0),
                 lambda: overlap_views(self.pool, 'fixture:1', 1, 0, ['fixture:2']),
                 lambda: overlap_views(self.pool, 'fixture:1', 8, 0, first_view_ids=['fixture:1']*8),
                 lambda: overlap_views(self.pool, 'fixture:1', 8, 0,
                                       first_view_ids=[f'fixture:{i}' for i in range(2, 10)])]
        for call in calls:
            with self.assertRaises(ValueError):
                call()

    def test_metrics_deduplicate_ids_and_distinguish_jaccard(self):
        metrics = overlap_metrics([['a', 'b', 'b'], ['b', 'c']])
        self.assertEqual(metrics['shared_rows'], 1)
        self.assertEqual(metrics['overlap_fraction'], 0.5)
        self.assertEqual(metrics['jaccard'], 1/3)
        self.assertEqual(overlap_metrics([[], []])['union_rows'], 0)


if __name__ == '__main__':
    unittest.main()
