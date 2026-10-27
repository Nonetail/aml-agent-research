"""Accounting tests: unfinished calls, grouping visibility, and sequence novelty."""
import json
from pathlib import Path
import tempfile
import unittest

from cycle_context_report import Report, cost, markdown
from cycle_context_scoring import score_answer


def row(ident, source, target, minute):
    return {'transaction_id':ident,'source_bank':'1','source_account':source,
            'destination_bank':'1','destination_account':target,'timestamp':f'2022/09/01 00:{minute:02}'}


def answer(path):
    return {'observations':[{'transaction_ids':path,'pattern_present':True,'status':'insufficient_evidence',
                            'reason':'Purpose is unavailable.','limitations':[]}],
            'evidence_requests':[],'limitations':[]}


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        for name in ('runtime','evaluator','calls'):
            (self.root/name).mkdir()
        self.rows=[row('T1','a','b',1),row('T2','b','a',2),row('T3','c','d',3),row('T4','d','c',4)]
        self.write('manifest.json',{'output_reserve':4096})
        self.write('runtime/dev-2.json',self.rows)
        self.write('evaluator/dev-2.json',{'targets':[['T1','T2']],
            'labels':{'T1':1,'T2':1,'T3':0,'T4':0}})

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        path=self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data))

    def job(self, ident, condition, ids, **extra):
        return {'id':ident,'case':'dev-2','condition':condition,'row_ids':ids,'repetition':1,**extra}

    def received(self, job, found):
        rows=[r for r in self.rows if r['transaction_id'] in job['row_ids']]
        self.write(f"calls/{job['id']}/result.json",{'id':job['id'],'status':'received',
            'score':score_answer(rows,answer(found),[['T1','T2']],{'T1':1,'T2':1,'T3':0,'T4':0}),
            'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120},'local_prompt_tokens':101})

    def test_missing_slots_keep_gate_incomplete_but_terminal_errors_finish_execution(self):
        job=self.job('base','single-1500',['T1','T2'])
        self.write('jobs.json',[job]);self.write('followup-jobs.json',[])
        self.received(job,['T1','T2'])
        report=Report(self.root).build()
        gate=next(g for g in report['gates'] if g['cohort']=='dev' and g['condition']=='single-1500')
        self.assertEqual(gate['status'],'incomplete')
        self.assertEqual(gate['recovered_reference_slots'],1)
        self.write('calls/base/result.json',{'status':'provider_error','usage':None})
        report=Report(self.root).build()
        self.assertEqual(report['status'],'completed_with_provider_errors')
        self.assertTrue(report['execution_finished'])
        self.assertTrue(report['quality_inconclusive_provider_errors'])
        self.assertEqual(report['operational']['completed_responses'],0)
        self.assertEqual(report['operational']['provider_errors'],1)

    def test_grouping_reports_split_support_against_original_denominator(self):
        jobs=[self.job('p0','graph-2',['T1','T3'],group_part=0,group_count=2),
              self.job('p1','graph-2',['T2','T4'],group_part=1,group_count=2)]
        self.write('jobs.json',jobs)
        report=Report(self.root).build()
        group=report['grouping'][0]
        self.assertEqual(group['original_oracle_cycles'],2)
        self.assertEqual(group['visible_oracle_cycles'],0)
        self.assertEqual(group['reference_retention'],0)
        self.assertEqual(group['unique_union_rows'],4)
        self.assertEqual(group['duplicate_rows'],0)
        self.assertTrue(group['union_equals_base'])
        self.assertIsNone(group['structural_recall_visible'])
        self.assertFalse(group['all_responses_completed'])

    def test_movement_deduplicates_recovery_and_charges_first_once_globally(self):
        first=self.job('first','single-1500',['T1','T2'])
        next1=self.job('next1','overlap-50',['T1','T2','T3'])
        next2=self.job('next2','overlap-0',['T3','T4'])
        self.write('jobs.json',[first]);self.write('followup-jobs.json',[next1,next2])
        self.received(first,['T1','T2']);self.received(next1,['T1','T2']);self.received(next2,['T3','T4'])
        report=Report(self.root).build()
        repeated,new=report['movements']
        self.assertEqual(repeated['accepted_cycle_union'],1)
        self.assertEqual(repeated['newly_recovered_cycles'],0)
        self.assertEqual(repeated['duplicate_rows'],2)
        self.assertEqual(new['accepted_cycle_union'],2)
        self.assertEqual(new['newly_recovered_cycles'],1)
        self.assertEqual(new['newly_recovered_references'],0)
        self.assertEqual(report['operational']['provider_total_tokens'],360)
        self.assertEqual(sum(m['cost']['provider_total_tokens'] for m in report['movements']),480)
        self.assertIn('No dollar cost',markdown(report))

    def test_usage_and_reservations_are_separate(self):
        measured=cost([{'status':'received','usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120},
                        'local_prompt_tokens':101,'reserved_total':9000},
                       {'status':'provider_error','usage':None,'local_prompt_tokens':200,'reserved_total':9200},
                       {'status':'ineligible','local_prompt_tokens':300000,'reserved_total':310000}])
        self.assertEqual(measured['attempted_calls'],2)
        self.assertEqual(measured['provider_total_tokens'],120)
        self.assertEqual(measured['unknown_usage_reserved_tokens'],9200)
        self.assertEqual(measured['provider_minus_local_range'],[-1,-1])
        self.assertEqual(measured['local_prompt_tokens_peak'],200)

    def test_declined_confirmation_is_not_an_unfinished_holdout_gate(self):
        self.rows += [row(f'T{i}',f'a{i}',f'b{i}',i) for i in range(5,33)]
        self.write('runtime/dev-2.json',self.rows)
        self.write('jobs.json',[])
        job=self.job('small','single-32',[r['transaction_id'] for r in self.rows])
        self.write('supplemental-jobs.json',[job])
        self.write('diagnostic-confirmation-status.json',{'status':'not_selected','reason':'Development gate failed'})
        report=Report(self.root).build()
        self.assertEqual(report['diagnostic_confirmation']['status'],'not_selected')
        self.assertFalse(any(g['cohort']=='holdout' for g in report['diagnostic_gates']))
        self.assertIn('**not selected**',markdown(report))
        self.assertEqual(report['display_timezone'],'Australia/Sydney')

    def test_confirmation_jobs_enter_attempt_and_posthoc_accounting(self):
        self.write('runtime/holdout-2.json',self.rows)
        self.write('evaluator/holdout-2.json',{'targets':[['T1','T2']],'labels':{}})
        job={**self.job('confirmation','single-32',['T1','T2']),'case':'holdout-2'}
        self.write('jobs.json',[])
        self.write('diagnostic-confirmation-jobs.json',[job])
        self.received(job,['T1','T2'])
        report=Report(self.root).build()
        self.assertEqual(report['planned_calls'],1)
        self.assertEqual(report['supplemental_calls'],1)
        self.assertEqual(report['operational']['attempted_calls'],1)
        self.assertTrue(report['case_results'][0]['posthoc_diagnostic'])

    def test_raw_valid_support_survives_diagnostic_whole_response_rejection(self):
        job=self.job('mixed','single-1500',['T1','T2'])
        self.write('jobs.json',[job])
        supplied=answer(['T1','T2'])
        supplied['evidence_requests']=[{'scope_id':99,'reason':'Unsupported scope'}]
        score=score_answer(self.rows[:2],supplied,[['T1','T2']])
        self.assertFalse(score['response_valid'])
        self.write('calls/mixed/result.json',{'status':'received','score':score})
        report=Report(self.root).build()
        result=report['case_results'][0]
        self.assertEqual(result['target_recovered'],0)
        self.assertEqual(result['raw_valid_cycles'],[['T1','T2']])
        self.assertEqual(result['raw_reference_recovered'],1)
        self.assertEqual(report['raw_claim_diagnostic']['raw_valid_rejected_by_contract'],1)

    def test_whole_path_availability_requires_model_origin_and_exact_valid_path(self):
        first=self.job('first','single-1500',['T1','T2'])
        next_job=self.job('next','overlap-25',['T1','T2','T3'])
        self.write('jobs.json',[first]);self.write('followup-jobs.json',[next_job])
        self.received(first,['T1','T2'])
        key='dev-2--overlap-25'
        for origin,retained,expected in [
            ('label_blind_source_degree_fallback',['T1'],False),
            ('first_model_detected_verified_cycle',['T1'],False),
            ('first_model_detected_verified_cycle',['T1','T2'],True),
            ('first_model_detected_verified_cycle',['T2','T1'],False)]:
            self.write('followup-scenarios.json',{key:{'anchor_origin':origin,'retained_ids':retained}})
            self.assertEqual(Report(self.root).build()['movements'][0]['whole_path_intervention_available'],expected)


if __name__=='__main__':
    unittest.main()
