import unittest
from threshold_eval import trace, check_trace


def row(n,time,source,dest,source_bank='1',dest_bank='1'):
    return {'transaction_id':f'source:{n}','timestamp':time,'source_bank':source_bank,'source_account':source,
            'destination_bank':dest_bank,'destination_account':dest}


class ThresholdTests(unittest.TestCase):
    def test_trace_uses_bank_identity_strict_time_and_numeric_tie_break(self):
        rows=[row(1,'01','A','B'),row(2,'01','B','C'),row(3,'02','B','B'),
              row(4,'02','B','C','2'),row(11,'03','B','D'),row(9,'03','B','C'),row(15,'04','C','E')]
        self.assertEqual(trace(rows,'T1'),['T1','T9','T15'])
        self.assertTrue(check_trace(rows,'T1',['T1','T9','T15'])['exact'])

    def test_missing_continuation_requires_short_answer(self):
        rows=[row(1,'01','A','B'),row(2,'02','C','D')]
        self.assertTrue(check_trace(rows,'T1',['T1'])['exact'])
        result=check_trace(rows,'T1',['T1','T2'])
        self.assertFalse(result['exact']);self.assertFalse(result['valid_edges'])

    def test_valid_alternative_path_is_not_exact_greedy_answer(self):
        rows=[row(1,'01','A','B'),row(2,'02','B','C'),row(3,'03','B','D')]
        result=check_trace(rows,'T1',['T1','T3'])
        self.assertFalse(result['exact']);self.assertTrue(result['valid_edges'])

    def test_unknown_and_repeated_ids_are_invalid(self):
        rows=[row(1,'01','A','B')]
        self.assertFalse(check_trace(rows,'T1',['T1','T999'])['valid_edges'])
        self.assertFalse(check_trace(rows,'T1',['T1','T1'])['valid_edges'])

if __name__=='__main__': unittest.main()
