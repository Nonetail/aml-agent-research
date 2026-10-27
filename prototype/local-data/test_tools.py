import csv
import json
from pathlib import Path
import tempfile
import unittest
from import_data import HEADER, build
from tools import Tools

class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temp.name)
        with (self.root/'HI-Small_accounts.csv').open('w') as f:
            f.write('Bank Name,Bank ID,Account Number,Entity ID,Entity Name\nBank,01,A,E1,Alpha\nBank,1,B,E2,Beta\nBank,1,C,E3,Gamma\nOther,2,A,E4,Other Alpha\n')
        rows = [
            ['2022/09/02 00:02','01','B','1','C','0.20','USD','0.20','USD','ACH','1'],
            ['2022/09/02 00:01','1','A','01','B','0.10','USD','0.10','USD','ACH','0'],
            ['2022/09/02 00:01','1','A','01','B','0.10','USD','0.10','USD','ACH','0'],
            ['2022/09/02 00:03','1','C','1','A','9.99','EUR','10.00','USD','ACH','1'],
            ['2022/09/02 00:04','1','A','1','A','0.10','USD','0.10','USD','ACH','0'],
            ['2022/09/11 00:00','1','A','1','B','100','USD','100','USD','ACH','1'],
            ['2022/09/02 00:01','2','A','1','B','100','USD','100','USD','ACH','0'],
        ]
        with (self.root/'HI-Small_Trans.csv').open('w') as f:
            w=csv.writer(f); w.writerow(HEADER); w.writerows(rows)
        build(self.root,self.root/'db')
        self.tools=Tools(self.root/'db/transactions.sqlite',self.root/'db/receipts.sqlite')
        self.query=dict(bank='001',account='A',start='2022/09/01 00:00',end='2022/09/11 00:00',direction='outgoing')

    def tearDown(self):
        self.tools.close(); self.temp.cleanup()

    def ident(self, n):
        return f'{self.tools.sha}:{n}'

    def test_pages_preserve_equal_time_duplicates_and_account_identity(self):
        a=self.tools.dispatch('fetch_transactions',dict(self.query,limit=1))
        b=self.tools.dispatch('fetch_transactions',dict(self.query,limit=1,cursor=a['next_cursor']))
        c=self.tools.dispatch('fetch_transactions',dict(self.query,limit=1,cursor=b['next_cursor']))
        self.assertEqual([p['rows'][0]['transaction_id'] for p in [a,b,c]], [self.ident(n) for n in [2,3,5]])
        self.assertTrue(c['complete'])
        wrong=self.tools.dispatch('fetch_transactions',dict(self.query,account='B',cursor=a['next_cursor']))
        self.assertIn('error',wrong)
        self.assertNotIn('laundering',json.dumps(a).lower())

    def test_exact_amounts_currency_sides_and_partial_scope(self):
        s=self.tools.dispatch('summarize_activity',self.query)
        self.assertEqual(s['totals_by_currency'],{'USD':'0.30'})
        self.assertEqual(s['external_counterparties'],1)
        incoming=self.tools.dispatch('summarize_activity',dict(self.query,direction='incoming'))
        self.assertEqual(incoming['totals_by_currency'],{'EUR':'9.99','USD':'0.10'})
        self.assertIn('error',self.tools.dispatch('fetch_transactions',dict(self.query,end='2022/09/12 00:00')))
        self.assertEqual(self.tools.dispatch('get_transactions',{'transaction_ids':[self.ident(6)]})['unavailable_ids'],[self.ident(6)])

    def test_path_checks_and_persisted_receipts(self):
        good=self.tools.dispatch('verify_path',{'transaction_ids':[self.ident(n) for n in [2,1,4]],'cycle':True})
        self.assertTrue(good['valid']); self.assertEqual(good['elapsed_minutes'],2)
        bad=self.tools.dispatch('verify_path',{'transaction_ids':[self.ident(n) for n in [2,3]],'cycle':True})
        self.assertFalse(bad['valid'])
        self.tools.close()
        self.tools=Tools(self.root/'db/transactions.sqlite',self.root/'db/receipts.sqlite')
        saved=self.tools.log.execute('SELECT result FROM receipts WHERE id=?',(good['receipt_id'],)).fetchone()
        self.assertEqual(json.loads(saved[0]),good)

    def test_batched_navigation_and_entity_identity(self):
        result=self.tools.dispatch('expand_frontier',{'queries':[dict(self.query,limit=2),dict(self.query,direction='incoming',limit=2)]})
        self.assertEqual(len(result['branches']),2)
        self.assertEqual(len(result['branches'][0]['rows']),2)
        accounts=self.tools.dispatch('get_accounts',{'accounts':[{'bank':'01','account':'A'},{'bank':'2','account':'A'}]})
        self.assertEqual([r['entity_id'] for r in accounts['accounts']],['E1','E4'])
        self.assertIn('error', self.tools.dispatch('expand_frontier',{'queries':[dict(self.query,limit=500)]*2}))

    def test_same_minute_does_not_invent_strict_chronology(self):
        # A->B then B->C can form a non-decreasing path when timestamps tie.
        self.tools.db.close()
        import sqlite3
        with sqlite3.connect(self.root/'db/transactions.sqlite') as db:
            db.execute("UPDATE transactions SET timestamp='2022/09/02 00:01' WHERE row_id=1")
        self.tools.log.close()
        self.tools=Tools(self.root/'db/transactions.sqlite',self.root/'db/receipts.sqlite')
        args={'transaction_ids':[self.ident(2),self.ident(1)]}
        self.assertFalse(self.tools.dispatch('verify_path',args)['valid'])
        self.assertTrue(self.tools.dispatch('verify_path',dict(args,strict=False))['valid'])

if __name__=='__main__':
    unittest.main()
