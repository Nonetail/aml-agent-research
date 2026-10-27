import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pilot

class Provider:
    def __init__(self, usage=None, fail=False): self.usage=usage; self.fail=fail; self.calls=0
    def complete(self, *args):
        self.calls += 1
        if self.fail: raise RuntimeError('provider failure')
        return {'usage':self.usage}

class BudgetTests(unittest.TestCase):
    def test_reconcile_and_reload(self):
        with tempfile.TemporaryDirectory() as path, patch.object(pilot,'OUT',Path(path)):
            budget=pilot.Budget(); provider=Provider({'total_tokens':100})
            budget.complete(provider,[],[],'auto',10)
            self.assertEqual(pilot.Budget().state, {'charged_tokens':100,'reported_tokens':100,'requests':1,'unknown_usage':0})
    def test_unknown_usage_and_provider_failure_keep_reservation(self):
        with tempfile.TemporaryDirectory() as path, patch.object(pilot,'OUT',Path(path)):
            budget=pilot.Budget()
            budget.complete(Provider(),[],[],'auto',10)
            first=budget.state['charged_tokens']
            with self.assertRaises(RuntimeError): budget.complete(Provider(fail=True),[],[],'auto',10)
            self.assertEqual(budget.state['charged_tokens'],first*2)
            self.assertEqual(budget.state['unknown_usage'],2)
    def test_refusal_does_not_contact_provider(self):
        with tempfile.TemporaryDirectory() as path, patch.object(pilot,'OUT',Path(path)), patch.object(pilot,'TOKEN_BUDGET',1):
            budget=pilot.Budget(); provider=Provider()
            with self.assertRaisesRegex(RuntimeError,'budget exhausted'): budget.complete(provider,[],[],'auto',10)
            self.assertEqual(provider.calls,0)
            self.assertEqual(budget.state['requests'],0)

if __name__=='__main__': unittest.main()
