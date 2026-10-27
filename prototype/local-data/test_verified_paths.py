import unittest
from verified_paths import build_paths, review_packets
from test_threshold_eval import row

class VerifiedPathsTests(unittest.TestCase):
    def test_strict_time_bank_identity_self_edges_and_ties(self):
        rows=[row(1,'01','A','B'),row(2,'01','B','C'),row(3,'02','B','B'),
              row(4,'02','B','C','2'),row(11,'03','B','D'),row(9,'03','B','C'),row(15,'04','C','A')]
        paths,coverage=build_paths({'T'+str(i['transaction_id'].split(':')[-1]):i for i in rows})
        first=next(p for p in paths if p['ids'][0]=='T1')
        self.assertEqual(first['ids'],['T1','T9','T15'])
        self.assertTrue(first['cycle'])

    def test_no_continuation_and_truncation_are_explicit(self):
        evidence={'T1':row(1,'01','A','B'),'T2':row(2,'02','C','D')}
        self.assertEqual(build_paths(evidence)[0],[])
        evidence={f'T{i}':row(i,str(i).zfill(3),str(i),str(i+1)) for i in range(40)}
        paths,coverage=build_paths(evidence,max_paths=2)
        self.assertEqual(coverage['omitted_start_edges'],33)
        self.assertEqual(coverage['deduplicated_subpaths'],4)
        self.assertTrue(all(len(p['ids'])<=6 for p in paths))

    def test_paths_cross_input_order_boundaries_and_keep_complete_support(self):
        evidence={f'T{i}':row(i,str(i).zfill(3),str(i),str(i+1)) for i in reversed(range(40))}
        paths,_=build_paths(evidence)
        packets=review_packets(evidence,paths,6)
        self.assertEqual({i for p in packets for i in p['view']},set(evidence))
        self.assertEqual([x['id'] for p in packets for x in p['paths']],[x['id'] for x in paths])
        for p in packets:
            self.assertLessEqual(len(p['view']),6)
            for path in p['paths']:self.assertLessEqual(set(path['ids']),set(p['view']))

if __name__=='__main__': unittest.main()
