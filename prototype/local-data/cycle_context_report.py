"""Generate an auditable partial/final report from saved cycle-context artifacts.

No credentials, hosted calls, tokenizer initialization or run-ledger mutation.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from cycle_context_scoring import oracle_cycles

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE/'generated/cycle-context-v1'
DEFAULT_MARKDOWN = HERE.parents[1]/'experiments/2026-10-24-cycle-context/RESULTS.md'
COMPLETED = {'received', 'invalid_response'}


def load(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def paths(value):
    return {tuple(p) for p in value or []}


def fraction(numerator, denominator):
    return numerator/denominator if denominator else None


def case_name(name):
    if name.startswith('dev-') or name.startswith('holdout-'):
        prefix, edges = name.split('-', 1)
        return ('Development' if prefix == 'dev' else 'Held-out')+f' {edges}-edge'
    return {'control-cycle':'Zero-label cycle control',
            'control-acyclic':'Constructed acyclic control',
            'control-natural':'Natural-window control'}.get(name, name)


def accounts(rows):
    return {(r[side+'_bank'], r[side+'_account']) for r in rows for side in ('source','destination')}


def cost(records):
    attempted = [r for r in records if r['status'] not in ('not_attempted','ineligible','unavailable')]
    usages = [r['usage'] for r in attempted if isinstance(r.get('usage'), dict)]
    local = [r['local_prompt_tokens'] for r in attempted if r.get('local_prompt_tokens') is not None]
    delta = [r['usage']['prompt_tokens']-r['local_prompt_tokens'] for r in attempted
             if (r.get('usage') or {}).get('prompt_tokens') is not None and r.get('local_prompt_tokens') is not None]
    seconds = [r['seconds'] for r in attempted if isinstance(r.get('seconds'), (int,float))]
    total = sum(u.get('total_tokens',u.get('prompt_tokens',0)+u.get('completion_tokens',0)) for u in usages)
    unknown = [r for r in attempted if not isinstance(r.get('usage'),dict)]
    return {'attempted_calls':len(attempted), 'completed_responses':sum(r['status'] in COMPLETED for r in attempted),
            'provider_errors':sum(r['status']=='provider_error' for r in attempted),
            'inflight_or_interrupted':sum(r['status']=='admitted' for r in attempted),
            'calls_with_usage':len(usages), 'calls_without_usage':len(unknown),
            'provider_prompt_tokens':sum(u.get('prompt_tokens',0) for u in usages),
            'provider_completion_tokens':sum(u.get('completion_tokens',0) for u in usages),
            'provider_total_tokens':total,
            'unknown_usage_reserved_tokens':sum(r.get('reserved_total',0) for r in unknown),
            'usage_plus_unknown_reservations':total+sum(r.get('reserved_total',0) for r in unknown),
            'local_prompt_tokens_total':sum(local), 'local_prompt_tokens_peak':max(local,default=None),
            'provider_prompt_tokens_peak':max((u.get('prompt_tokens',0) for u in usages),default=None),
            'provider_minus_local_range':[min(delta),max(delta)] if delta else None,
            'call_seconds_sum':sum(seconds), 'call_seconds_mean':sum(seconds)/len(seconds) if seconds else None,
            'status_counts':dict(Counter(r['status'] for r in records))}


class Report:
    def __init__(self, root):
        self.root = Path(root)
        self.manifest = load(self.root/'manifest.json', {})
        self.confirmation_jobs = load(self.root/'diagnostic-confirmation-jobs.json', [])
        self.confirmation_status = load(self.root/'diagnostic-confirmation-status.json', {})
        self.supplemental_jobs = load(self.root/'supplemental-jobs.json', [])+self.confirmation_jobs
        self.supplemental_ids = {j['id'] for j in self.supplemental_jobs}
        self.jobs = load(self.root/'jobs.json', [])+load(self.root/'followup-jobs.json', [])+self.supplemental_jobs
        self.attempts = {r['id']:r for r in load(self.root/'attempts.json', [])}
        self.evaluators = {p.stem:load(p) for p in (self.root/'evaluator').glob('*.json')}
        self.rows = {p.stem:load(p) for p in (self.root/'runtime').glob('*.json')}
        self.lookup = {name:{r['transaction_id']:r for r in rows} for name,rows in self.rows.items()}
        self.oracle_cache = {}
        self.records = {j['id']:self.record(j) for j in self.jobs}

    def record(self, job):
        attempt = self.attempts.get(job['id'], {})
        result = load(self.root/'calls'/job['id']/'result.json', {})
        record = {**attempt, **result, 'id':job['id'], 'case':job['case'],
                  'condition':job['condition'], 'repetition':job.get('repetition',1),
                  'rows':len(job['row_ids'])}
        record.setdefault('status', 'ineligible' if job.get('ineligible') else 'not_attempted')
        return record

    def oracle(self, case, ids):
        key = case, frozenset(ids)
        if key not in self.oracle_cache:
            self.oracle_cache[key] = set(oracle_cycles([self.lookup[case][i] for i in ids]))
        return self.oracle_cache[key]

    def accepted(self, record):
        score = record.get('score', {})
        return paths(score.get('accepted_cycles')) if score.get('response_valid') else set()

    def targets(self, case):
        return paths(self.evaluators.get(case,{}).get('targets'))

    def base(self, case):
        return {r['transaction_id'] for r in self.rows[case][:1500]}

    def summary(self, job):
        r = self.records[job['id']]
        score = r.get('score', {})
        found = self.accepted(r)
        raw_valid = paths(score.get('raw_valid_cycles'))
        oracle = self.oracle(job['case'], job['row_ids'])
        targets = self.targets(job['case'])
        labels = self.evaluators.get(job['case'],{}).get('labels',{})
        composition = Counter()
        for path in found:
            values = [labels.get(i) for i in path]
            composition['unknown' if any(v not in (0,1) for v in values) else
                        'zero_positive' if not any(values) else 'all_positive' if all(values) else 'mixed'] += 1
        failure = ('provider_error' if r['status']=='provider_error' else
                   'output_truncation' if 'Truncated' in r.get('error','') else
                   'invalid_factual_claim' if score.get('invalid_true_claims') or score.get('unknown_ids') or score.get('claim_mismatches') else
                   'invalid_contract' if r['status'] in COMPLETED and not score.get('response_valid') else
                   'valid_incomplete_discovery' if score.get('response_valid') and found != oracle else
                   'valid_exact' if score.get('response_valid') else r['status'])
        return {**{k:v for k,v in r.items() if k!='score'}, 'response_valid':score.get('response_valid'),
                'quality_outcome':failure,
                'score_available':bool(score),
                'raw_valid_cycles':[list(path) for path in sorted(raw_valid)],
                'raw_valid_cycle_count':len(raw_valid),
                'raw_reference_recovered':len(targets & raw_valid),
                'raw_valid_rejected_by_contract':len(raw_valid-found),
                'oracle_cycles':len(oracle), 'structural_recovered':len(found),
                'structural_exact':score.get('structural_exact',False),
                'target_count':len(targets), 'target_visible':len(targets & oracle),
                'target_recovered':len(targets & found),
                'posthoc_diagnostic':job['id'] in self.supplemental_ids,
                'control_support_recovered':(tuple(self.evaluators.get(job['case'],{}).get('control_support',[])) in found) if r['status'] in COMPLETED else None,
                'acyclic_control_pass':(score.get('response_valid') is True and not oracle and not found and
                    not score.get('invalid_true_claims') and not score.get('unknown_ids')) if job['case']=='control-acyclic' and r['status'] in COMPLETED else None,
                'invalid_true_claims':score.get('invalid_true_claims',0),
                'unknown_id_claims':len(score.get('unknown_ids',[])),
                'duplicate_supports':score.get('duplicate_supports',0),
                'claim_mismatches':score.get('claim_mismatches',0),
                'errors':score.get('errors',[]), 'cycle_label_composition':dict(composition),
                'supplied_positive_rows':sum(labels.get(i)==1 for i in job['row_ids']),
                'supplied_unknown_label_rows':sum(labels.get(i) not in (0,1) for i in job['row_ids']),
                'investigate_positive_rows':len(score.get('investigate_positive_row_ids',[])),
                'investigate_zero_label_rows':len(score.get('investigate_zero_label_row_ids',[]))}

    def gate(self, prefix, condition, summaries):
        wanted = {(f'{prefix}-{edges}', repetition) for edges in (2,3,4) for repetition in (1,2)}
        slots = [r for r in summaries if r['condition']==condition and (r['case'],r['repetition']) in wanted]
        completed = sum(r['status'] in COMPLETED for r in slots)
        recovered = sum(r['target_recovered']>=1 for r in slots)
        invalid = sum(r['invalid_true_claims'] for r in slots)
        unknown = sum(r['unknown_id_claims'] for r in slots)
        return {'cohort':prefix,'condition':condition,'expected_response_slots':6,
                'planned_slots':len(slots),'completed_response_slots':completed,
                'operationally_unavailable_slots':sum(r['status']=='provider_error' for r in slots),
                'recovered_reference_slots':recovered,'invalid_true_claims':invalid,'unknown_id_claims':unknown,
                'status':'incomplete' if completed<6 else 'pass' if recovered>=5 and not invalid and not unknown else 'fail'}

    def grouping(self):
        groups = defaultdict(list)
        for job in self.jobs:
            if 'group_part' in job:
                groups[job['case'],job['condition'],job.get('repetition',1)].append(job)
        result=[]
        for (case,condition,repetition), jobs in sorted(groups.items()):
            base_ids = self.base(case)
            whole = self.oracle(case,base_ids)
            targets = self.targets(case)
            visible=set(); found=set(); union=set()
            for job in jobs:
                visible |= self.oracle(case,job['row_ids'])
                found |= self.accepted(self.records[job['id']])
                union.update(job['row_ids'])
            records=[self.records[j['id']] for j in jobs]
            baseline_job=next((j for j in self.jobs if j['case']==case and
                j['condition']=='single-1500' and j.get('repetition',1)==repetition),None)
            baseline=self.records[baseline_job['id']] if baseline_job else {}
            baseline_found=self.accepted(baseline)
            displayed=sum(len(j['row_ids']) for j in jobs)
            expected=jobs[0].get('group_count',len(jobs))
            result.append({'case':case,'condition':condition,'repetition':repetition,
                'planned_calls':len(jobs),'expected_calls':expected,
                'all_responses_completed':len(jobs)==expected and all(r['status'] in COMPLETED for r in records),
                'view_rows':[len(j['row_ids']) for j in sorted(jobs,key=lambda j:j['group_part'])],
                'view_accounts':[len(accounts([self.lookup[case][i] for i in j['row_ids']])) for j in jobs],
                'unique_union_rows':len(union),'displayed_rows':displayed,'duplicate_rows':displayed-len(union),
                'union_equals_base':union==base_ids,'original_oracle_cycles':len(whole),
                'visible_oracle_cycles':len(visible & whole),'structural_retention':fraction(len(visible & whole),len(whole)),
                'recovered_cycles':len(found & whole),'structural_recall_original':fraction(len(found & whole),len(whole)),
                'structural_recall_visible':fraction(len(found & whole),len(visible & whole)),
                'reference_count':len(targets),'visible_references':len(targets & visible),
                'reference_retention':fraction(len(targets & visible),len(targets)),
                'recovered_references':len(targets & found),
                'baseline_status':baseline.get('status','not_attempted'),
                'baseline_recovered_references':len(targets & baseline_found),
                'baseline_recovered_cycles':len(whole & baseline_found),
                'paired_reference_change':len(targets & found)-len(targets & baseline_found),
                'paired_cycle_change':len(whole & found)-len(whole & baseline_found),
                'baseline_cost':cost([baseline]) if baseline else None,
                'reference_recall_original':fraction(len(targets & found),len(targets)),
                'reference_recall_visible':fraction(len(targets & found),len(targets & visible)),
                'invalid_true_claims':sum(r.get('score',{}).get('invalid_true_claims',0) for r in records),
                'unknown_id_claims':sum(len(r.get('score',{}).get('unknown_ids',[])) for r in records),
                'cost':cost(records)})
        return result

    def grouped_gate(self, grouping, selection):
        condition='graph-'+str(selection.get('selected_group_count','pending'))
        slots=[g for g in grouping if g['case'].startswith('holdout-') and g['condition']==condition]
        complete=sum(g['all_responses_completed'] for g in slots)
        recovered=sum(g['recovered_references']>=1 for g in slots)
        invalid=sum(g['invalid_true_claims'] for g in slots)
        unknown=sum(g['unknown_id_claims'] for g in slots)
        return {'cohort':'holdout grouped','condition':condition,'expected_response_slots':6,
            'planned_slots':len(slots),'completed_response_slots':complete,
            'operationally_unavailable_slots':sum(g['cost']['provider_errors']>0 for g in slots),
            'recovered_reference_slots':recovered,'invalid_true_claims':invalid,'unknown_id_claims':unknown,
            'status':'incomplete' if complete<6 else 'pass' if recovered>=5 and not invalid and not unknown else 'fail'}

    def movements(self):
        scenarios=load(self.root/'followup-scenarios.json',{})
        movements=[]
        for job in self.jobs:
            if not job['condition'].startswith('overlap-'):
                continue
            case=job['case']; scenario=scenarios.get(case+'--'+job['condition'],{})
            first_job=next((j for j in self.jobs if j['case']==case and j['condition']=='single-1500' and j.get('repetition',1)==1),None)
            if first_job is None:
                continue
            first=self.records[first_job['id']]; second=self.records[job['id']]
            left=set(first_job['row_ids']); right=set(job['row_ids']); union=left|right
            initial=self.accepted(first); following=self.accepted(second); found=initial|following
            first_oracle=self.oracle(case,left); second_oracle=self.oracle(case,right)
            visible=first_oracle|second_oracle; whole=self.oracle(case,union); targets=self.targets(case)
            origin=scenario.get('anchor_origin','unknown')
            retained=tuple(scenario.get('retained_ids',[]))
            whole_path_available=(origin=='first_model_detected_verified_cycle' and
                                  len(retained)>=2 and retained in initial)
            displayed=len(left)+len(right)
            movements.append({'case':case,'condition':job['condition'],'first_response_id':first_job['id'],
                'second_response_id':job['id'],'first_status':first['status'],'second_status':second['status'],
                'anchor_origin':origin,'whole_path_intervention_available':whole_path_available,
                'retained_path_edges':len(scenario.get('retained_ids',[])),
                'movement_metadata':{k:v for k,v in scenario.items() if k not in ('views','retained_ids','anchor_id')},
                'first_rows':len(left),'second_rows':len(right),'displayed_rows':displayed,
                'unique_union_rows':len(union),'duplicate_rows':displayed-len(union),
                'duplicate_fraction_of_displayed':fraction(displayed-len(union),displayed),
                'achieved_overlap_fraction':fraction(len(left&right),len(right)),
                'new_rows':len(right-left),'union_accounts':len(accounts([self.lookup[case][i] for i in union])),
                'first_oracle_cycles':len(first_oracle),'second_oracle_cycles':len(second_oracle),
                'individually_visible_cycle_union':len(visible),'whole_union_oracle_cycles':len(whole),
                'cycles_only_visible_after_combining_rows':len(whole-visible),
                'first_recovered_cycles':len(initial),'second_recovered_cycles':len(following),
                'accepted_cycle_union':len(found),'newly_recovered_cycles':len(following-initial),
                'newly_recovered_cycles_using_new_rows':sum(bool(set(p)&(right-left)) for p in following-initial),
                'reference_count':len(targets),'second_visible_references':len(targets&second_oracle),
                'sequence_visible_references':len(targets&visible),'first_recovered_references':len(targets&initial),
                'second_recovered_references':len(targets&following),'sequence_recovered_references':len(targets&found),
                'newly_recovered_references':len((following-initial)&targets),
                'cost':cost([first,second])})
        unavailable=[{'scenario':name,**value} for name,value in scenarios.items()
                     if isinstance(value,dict) and (value.get('unavailable') or value.get('status')=='unavailable')]
        return movements,unavailable

    def build(self):
        summaries=[self.summary(j) for j in self.jobs]
        grouping=self.grouping()
        movements,unavailable=self.movements()
        overlap=[]
        names=sorted(self.rows)
        for index,left in enumerate(names):
            for right in names[index+1:]:
                l=self.base(left);r=self.base(right)
                overlap.append({'left':left,'right':right,'shared_base_rows':len(l&r),
                    'shared_base_accounts':len(accounts([self.lookup[left][i] for i in l]) & accounts([self.lookup[right][i] for i in r]))})
        conditions=[]
        for condition in sorted({r['condition'] for r in summaries}):
            records=[r for r in summaries if r['condition']==condition]
            conditions.append({'condition':condition,'planned_calls':len(records),'cost':cost(records),
                'strict_valid_responses':sum(r['response_valid'] is True for r in records),
                'quality_failures':sum(r['status'] in COMPLETED and r['response_valid'] is not True for r in records),
                'quality_outcomes':dict(Counter(r['quality_outcome'] for r in records)),
                'accepted_cycle_label_composition':dict(sum((Counter(r['cycle_label_composition']) for r in records),Counter()))})
        selection=load(self.root/'followup-selection.json',{})
        incomplete=[r['id'] for r in summaries if r['status'] not in COMPLETED|{'provider_error','ineligible','unavailable'}]
        operational=cost(list(self.records.values()))
        execution_finished=bool(self.manifest) and not incomplete and (self.root/'followup-jobs.json').exists()
        phase=('not_prepared' if not self.manifest else 'incomplete' if not execution_finished else
               'completed_with_provider_errors' if operational['provider_errors'] else
               'completed_with_ineligible_conditions' if operational['status_counts'].get('ineligible') else 'completed')
        diagnostic_conditions={j['condition'] for j in self.supplemental_jobs if len(j['row_ids'])==32}
        diagnostic_gates=[{**self.gate(prefix,condition,summaries),'posthoc_diagnostic':True}
                          for condition in sorted(diagnostic_conditions)
                          for prefix in (('dev','holdout') if self.confirmation_jobs else ('dev',))]
        confirmation=self.confirmation_status or {'status':'selected' if self.confirmation_jobs else 'pending_selection'}
        background=[r for r in summaries if r['condition']!='core-only']
        raw_diagnostic={'scored_responses':sum(r['score_available'] for r in summaries),
            'unscored_responses':sum(r['status'] in COMPLETED and not r['score_available'] for r in summaries),
            'raw_valid_cycles':sum(r['raw_valid_cycle_count'] for r in summaries),
            'raw_reference_recoveries':sum(r['raw_reference_recovered'] for r in summaries),
            'raw_valid_rejected_by_contract':sum(r['raw_valid_rejected_by_contract'] for r in summaries),
            'background_scored_responses':sum(r['score_available'] for r in background),
            'background_raw_valid_cycles':sum(r['raw_valid_cycle_count'] for r in background),
            'background_raw_reference_recoveries':sum(r['raw_reference_recovered'] for r in background)}
        return {'generated_at':datetime.now(ZoneInfo('Australia/Sydney')).isoformat(),
            'display_timezone':'Australia/Sydney','experiment_root':str(self.root.resolve()),
            'status':phase,'manifest':self.manifest,'planned_calls':len(self.jobs),
            'execution_finished':execution_finished,
            'quality_inconclusive_provider_errors':bool(operational['provider_errors']),
            'initial_matrix_saved':(self.root/'jobs.json').exists(),'followup_matrix_saved':(self.root/'followup-jobs.json').exists(),
            'supplemental_calls':len(self.supplemental_jobs), 'diagnostic_gates':diagnostic_gates,
            'diagnostic_confirmation':confirmation,
            'operational':operational, 'conditions':conditions,
            'raw_claim_diagnostic':raw_diagnostic,
            'case_results':summaries,'gates':[self.gate('dev',f'single-{n}',summaries) for n in (300,750,1500)]+[self.gate('holdout','single-1500',summaries),self.grouped_gate(grouping,selection)],
            'grouping':grouping,'selection':selection,'movements':movements,
            'output_capacity':load(self.root/'output-capacity.json',{}),
            'unavailable_interventions':unavailable,'case_overlap':overlap,
            'unrecorded_result_ids':incomplete,
            'limitations':['Constructed reference-enriched stress cases; not population precision/recall.',
                'Repeats share exact evidence and are not independent source cases.',
                'Provider failures are operationally inconclusive for model quality.',
                'Known token usage excludes unknown provider usage; reservations are separate.',
                'No dollar cost: actual account tariff is unavailable.',
                'Topology, hidden-label recovery, economic concern and laundering verdict are distinct.']}


def num(value):
    return '—' if value is None else f'{value:,}' if isinstance(value,int) else f'{value:.1f}'


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+
                     ['| '+' | '.join(str(v).replace('|','\\|').replace('\n',' ') for v in row)+' |' for row in rows])


def quality(r):
    if r['status'] not in COMPLETED:
        return r['status']
    return r['quality_outcome'].replace('_',' ')


def measure_output_capacity(report):
    """Measure tiny-content oracle outputs with the pinned public tokenizer only."""
    sys.path.insert(0,str(DEFAULT_MARKDOWN.parent))
    from context_tokens import ContextTokens, TOKENIZER_REVISION
    counter=ContextTokens()
    measured=[]
    for case in sorted(report.rows):
        oracle=report.oracle(case,report.base(case))
        answer={'observations':[{'transaction_ids':list(path),'pattern_present':True,
            'status':'investigate','reason':'x','limitations':[]} for path in sorted(oracle)],
            'evidence_requests':[],'limitations':[]}
        rendered=counter.tokenizer.apply_chat_template([
            {'role':'user','content':'x'},
            {'role':'assistant','content':'','tool_calls':[{'type':'function','function':{
                'name':'assess_cycle_evidence','arguments':answer}}]}],
            tokenize=False,add_generation_prompt=False,enable_thinking=False)
        output=rendered.rsplit('<|im_start|>assistant\n',1)[1]
        if output.startswith('<think></think>'):
            output=output[len('<think></think>'):]
        xml_tokens=counter.text(output)
        compact_json=json.dumps(answer,separators=(',',':'))
        reserve=report.manifest.get('output_reserve',4096)
        measured.append({'case':case,'oracle_cycles':len(oracle),'output_reserve':reserve,
            'minimal_content_arguments_json_tokens':counter.text(compact_json),
            'minimal_content_generated_tool_xml_tokens':xml_tokens,
            'exceeds_output_reserve':xml_tokens>reserve,
            'illustrative_output_sha256':__import__('hashlib').sha256(output.encode()).hexdigest()})
    result={'tokenizer_revision':TOKENIZER_REVISION,
        'method':'All base oracle supports, schema-shaped observations, one-character reason x, empty limitations, investigate status. Count public-template generated tool XML including end marker, excluding prefilled thinking prefix; also count compact API argument JSON.',
        'limitation':'Illustrative tiny-content output, not a mathematical token lower bound or valid economic rationale. Normal useful reasons/limitations require more output; transport serialization can differ. No inference performed.',
        'cases':measured}
    (report.root/'output-capacity.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def markdown(report):
    o=report['operational']
    raw=report['raw_claim_diagnostic']
    lines=['# Live cycle context experiment results','',f"Snapshot: {report['generated_at']} (Australia/Sydney). State: **{report['status']}**.",'',
        f"{report['planned_calls']} saved planned calls ({report['supplemental_calls']} post-hoc diagnostics); {o['attempted_calls']} attempted, {o['completed_responses']} responses returned, "
        f"{o['provider_errors']} provider errors, {o['inflight_or_interrupted']} in flight or interrupted. "
        'Provider errors are operationally inconclusive; returned schema failures and truncations are quality failures. '
        'Execution is finished when all saved planned attempts have terminal outcomes; provider errors can still leave quality gates inconclusive. '
        'An unfinished or absent follow-up matrix remains incomplete.','',
        f"Before whole-response acceptance, {raw['scored_responses']} scored responses contain "
        f"**{raw['raw_valid_cycles']} raw valid cycle claims and {raw['raw_reference_recoveries']} raw reference recoveries**; "
        f"{raw['raw_valid_rejected_by_contract']} valid claims were excluded by the whole-response contract. "
        f"Excluding core-only sanity checks, {raw['background_scored_responses']} scored responses contain "
        f"{raw['background_raw_valid_cycles']} raw valid cycles and {raw['background_raw_reference_recoveries']} raw reference recoveries. "
        f"These counts exclude {raw['unscored_responses']} returned responses that could not be scored, and count each repeat separately.",'',
        '## Screening gates','',
        table(['Cohort / view','Returned / 6','Reference recoveries / 6','Invalid true / unknown IDs','Decision'],
            [[g['cohort']+' / '+g['condition'],g['completed_response_slots'],g['recovered_reference_slots'],
              f"{g['invalid_true_claims']} / {g['unknown_id_claims']}",g['status']] for g in report['gates']]),'',
        'Pass requires at least five of six reference recoveries, all six returned response slots, and zero invalid-edge or unsupported-ID claims. '
        'Passing is provisional evidence on these constructed cases.','',
        '## Positive cases: individual repetitions','',
        table(['Case','View','Repeat','Rows','Outcome','Reference','Cycles recovered / oracle','Invalid true / unknown','Provider total'],
            [[case_name(r['case']),r['condition'],r['repetition'],r['rows'],quality(r),
              f"{r['target_recovered']}/{r['target_count']}",f"{r['structural_recovered']}/{r['oracle_cycles']}",
              f"{r['invalid_true_claims']}/{r['unknown_id_claims']}",num((r.get('usage') or {}).get('total_tokens'))]
             for r in report['case_results'] if not r['case'].startswith('control') and
             not r['posthoc_diagnostic'] and (r['condition'].startswith('single-') or r['condition'].startswith('input-'))]),'',
        '## Controls and accepted-cycle labels','',
        table(['Case','Repeat','Outcome','Positive rows','Cycles recovered / oracle','Zero / all-positive / mixed / unknown','Control check','Investigate positive / zero rows'],
            [[case_name(r['case']),r['repetition'],quality(r),r['supplied_positive_rows'],
              f"{r['structural_recovered']}/{r['oracle_cycles']}",
              ' / '.join(str(r['cycle_label_composition'].get(k,0)) for k in ('zero_positive','all_positive','mixed','unknown')),
              str(r['acyclic_control_pass']) if r['case']=='control-acyclic' else str(r['control_support_recovered']) if r['case']=='control-cycle' else 'natural sample',
              f"{r['investigate_positive_rows']} / {r['investigate_zero_label_rows']}"]
             for r in report['case_results'] if r['case'].startswith('control')]),'',
        'Valid zero-label cycles are structural successes. A zero oracle denominator has undefined recall; valid empty output can still be exact. '
        'Hidden labels do not establish whether an economic concern was justified.','',
        '## Grouping: union recovery and retention','',
        table(['Case','Policy / repeat','View rows','Reference recovered / visible / original','Cycles recovered / visible / original',
               'Union rows / duplicates','Returned / planned','Δ reference / cycles vs baseline','Total tokens / peak input'],
            [[case_name(g['case']),f"{g['condition']} / {g['repetition']}",'/'.join(map(str,g['view_rows'])),
              f"{g['recovered_references']}/{g['visible_references']}/{g['reference_count']}",
              f"{g['recovered_cycles']}/{g['visible_oracle_cycles']}/{g['original_oracle_cycles']}",
              f"{g['unique_union_rows']} / {g['duplicate_rows']}",f"{g['cost']['completed_responses']}/{g['planned_calls']}",
              f"{g['paired_reference_change']:+d} / {g['paired_cycle_change']:+d}" if g['all_responses_completed'] and g['baseline_status'] in COMPLETED else 'inconclusive',
              f"{num(g['cost']['provider_total_tokens'])} / {num(g['cost']['provider_prompt_tokens_peak'])}"] for g in report['grouping']]),'',
        'Visible counts are deduplicated supports wholly contained in at least one view. Original counts use the whole common 1,500-row packet. '
        'Loss of support across a cut is a grouping retention loss. Smaller peak context can require more total calls and tokens.','']
    selection=report['selection']
    lines += ['Saved development selection: '+(f"**{selection.get('selected_group_count')} graph views**. {selection.get('selection','')}" if selection else 'pending.')]
    if selection and not any(g['recovered_references'] for g in report['grouping'] if g['case'].startswith('dev-')):
        lines += ['No development grouping recovered a reference: selection is diagnostic, with **no demonstrated grouping advantage**.']
    if report['supplemental_calls']:
        lines += ['','## Post-hoc lower-boundary diagnostics','',
            'These conditions were added after observing the frozen experiment. They are reported separately and do not retroactively change its gates. '
            'Core-only packets test minimal format and prompt understanding, not discovery amid ordinary background.','',
            table(['Case','Condition','Repeat','Rows','Outcome','Reference','Cycles recovered / oracle','Provider total'],
                [[case_name(r['case']),r['condition'],r['repetition'],r['rows'],quality(r),
                  f"{r['target_recovered']}/{r['target_count']}",f"{r['structural_recovered']}/{r['oracle_cycles']}",
                  num((r.get('usage') or {}).get('total_tokens'))]
                 for r in report['case_results'] if r['posthoc_diagnostic']]),'',
            table(['Post-hoc screen','Returned / 6','Recovered / 6','Invalid / unknown IDs','Decision'],
                [[g['cohort']+' / '+g['condition'],g['completed_response_slots'],g['recovered_reference_slots'],
                  f"{g['invalid_true_claims']} / {g['unknown_id_claims']}",g['status']] for g in report['diagnostic_gates']]),'']
        confirmation=report['diagnostic_confirmation']
        lines += [f"Held-out 32-row confirmation: **{confirmation['status'].replace('_',' ')}**. {confirmation.get('reason','')}",'']
    lines += ['', '## Next-view movement and overlap','',
        table(['Case','Next view','Anchor','New / union / duplicated rows','Cycles second visible / sequence visible / whole union',
               'Recovered union / new','Reference union / new','Returned / 2','Sequence tokens'],
            [[case_name(m['case']),m['condition'],
              'model path' if m['anchor_origin']=='first_model_detected_verified_cycle' else 'degree fallback' if 'fallback' in m['anchor_origin'] else m['anchor_origin'],
              f"{m['new_rows']} / {m['unique_union_rows']} / {m['duplicate_rows']}",
              f"{m['second_oracle_cycles']} / {m['individually_visible_cycle_union']} / {m['whole_union_oracle_cycles']}",
              f"{m['accepted_cycle_union']} / {m['newly_recovered_cycles']}",
              f"{m['sequence_recovered_references']} / {m['newly_recovered_references']}",
              f"{m['cost']['completed_responses']}/2",num(m['cost']['provider_total_tokens'])]
             for m in report['movements']]),'',
        'Sequence cost includes the reused first response for each paired comparison; the overall total charges that call only once. '
        '“New” recovery excludes every support already recovered in the first response. Whole-union oracle cycles can cross snapshots and be absent from both individual views. '
        'Actual duplicated rows are shown even when nominal overlap is zero. Whole-path retention is available only after a model-discovered valid path.','',
        '## Accepted-cycle label composition','',
        table(['Condition','Zero-positive','All-positive','Mixed','Unknown'],
            [[c['condition']]+[c['accepted_cycle_label_composition'].get(k,0) for k in ('zero_positive','all_positive','mixed','unknown')]
             for c in report['conditions']]),'',
        'Counts are per returned response, so repeats and shared evidence can count the same cycle again. '
        'Grouping and movement recovery tables separately deduplicate exact supports.','',
        '## Execution and token cost','',
        table(['Condition','Planned / attempted / returned','Provider errors / quality failures','Input / output / total','Peak provider / local input','Provider − local'],
            [[c['condition'],f"{c['planned_calls']} / {c['cost']['attempted_calls']} / {c['cost']['completed_responses']}",
              f"{c['cost']['provider_errors']} / {c['quality_failures']}",
              ' / '.join(num(c['cost'][k]) for k in ('provider_prompt_tokens','provider_completion_tokens','provider_total_tokens')),
              f"{num(c['cost']['provider_prompt_tokens_peak'])} / {num(c['cost']['local_prompt_tokens_peak'])}",
              str(c['cost']['provider_minus_local_range']) if c['cost']['provider_minus_local_range'] else '—'] for c in report['conditions']]),'',
        f"Known provider usage: **{num(o['provider_total_tokens'])} tokens** across {o['calls_with_usage']} calls. "
        f"Unknown usage: {o['calls_without_usage']} calls, with {num(o['unknown_usage_reserved_tokens'])} reserved token units retained separately. "
        f"Sum of call latency: {num(o['call_seconds_sum'])} seconds; this is not parallel wall time. "
        'No dollar cost is asserted because the account tariff is unknown.','', '## Limits and outstanding work','']
    capacity=report['output_capacity']
    if capacity:
        lines += ['','### Output-capacity confound','',
            table(['Base case','Oracle cycles','Tiny-content tool XML tokens','API argument JSON tokens','Output reserve','Exceeds reserve'],
                [[case_name(c['case']),c['oracle_cycles'],num(c['minimal_content_generated_tool_xml_tokens']),
                  num(c['minimal_content_arguments_json_tokens']),c['output_reserve'],c['exceeds_output_reserve']]
                 for c in capacity['cases']]),'',
            'These measured oracle answers use one-character reasons and empty limitations, so they are an illustrative tiny-content schema cost, '
            'not useful economic assessments or a proved mathematical lower bound. '
            'When even this output exceeds the fixed reserve, exhaustive structural recall is confounded by output capacity. '
            'Known-reference recovery remains measurable; poor exhaustive recall cannot be attributed solely to input-context size. '
            'The report distinguishes output truncation, valid incomplete discovery, invalid factual claims and invalid contracts.','']
    statuses=Counter(r['status'] for r in report['case_results'])
    lines += [f"Saved outcomes: `{dict(statuses)}`. Unavailable interventions: {len(report['unavailable_interventions'])}."]
    if report['unavailable_interventions']:
        lines += ['',table(['Unavailable scenario','Reason'],
            [[case_name(v['scenario'].split('--')[0])+' / '+v['scenario'].split('--')[-1],v.get('reason','Unavailable')]
             for v in report['unavailable_interventions']]),'']
    if report['case_overlap']:
        pairs=report['case_overlap']
        lines += [f"Base packets share rows in {sum(p['shared_base_rows']>0 for p in pairs)}/{len(pairs)} case pairs "
                  f"(maximum {max(p['shared_base_rows'] for p in pairs)} rows and {max(p['shared_base_accounts'] for p in pairs)} accounts). "
                  'Distinct reference episodes do not make the shared backgrounds independent; the JSON records every pair.']
    lines += ['']+['- '+v for v in report['limitations']]+['',
        'Full metrics, view-level records, saved policy selection, movement provenance and incomplete identities are in '
        '[results.json](../../prototype/local-data/generated/cycle-context-v1/results.json).','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    parser.add_argument('--markdown',type=Path,default=DEFAULT_MARKDOWN)
    parser.add_argument('--measure-output-capacity',action='store_true',help='Requires the pinned tokenizer Python environment; performs local counting only.')
    args=parser.parse_args()
    builder=Report(args.root)
    if args.measure_output_capacity:
        measure_output_capacity(builder)
    report=builder.build()
    if args.root.exists():
        (args.root/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    args.markdown.parent.mkdir(parents=True,exist_ok=True)
    args.markdown.write_text(markdown(report))
    print(json.dumps({'status':report['status'],'planned_calls':report['planned_calls'],
                      'attempted_calls':report['operational']['attempted_calls'],'markdown':str(args.markdown)}))


if __name__=='__main__':
    main()
