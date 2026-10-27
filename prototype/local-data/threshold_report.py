"""Generate threshold evaluation reports from saved results, including failed attempts."""
from collections import defaultdict
import html
import json
from pathlib import Path
import statistics

from threshold_eval import ROOT, VIEWS, verify_manifest
from run_case import save


def mean(values):
    values=[x for x in values if x is not None]
    return sum(values)/len(values) if values else None


def fmt(value):
    if value is None: return '—'
    if isinstance(value,float): return f'{value:.3f}'
    return str(value)


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+
                     ['| '+' | '.join(fmt(x) for x in row)+' |' for row in rows])


def main():
    manifest=verify_manifest();cases=json.loads((ROOT/'cases-evaluator.json').read_text())
    specs={c['id']:c for c in cases};offline=json.loads((ROOT/'offline-results.json').read_text())
    provider=json.loads((ROOT/'provider-budget.json').read_text()) if (ROOT/'provider-budget.json').exists() else []
    usage={k:sum((r.get('usage') or {}).get(k,0) for r in provider) for k in ['prompt_tokens','completion_tokens','total_tokens']}
    context=[]
    context_sizes=sorted(VIEWS+([40,75] if (ROOT/'lower-context-manifest.json').exists() else []))
    for size in context_sizes:
        records=[]
        for spec in cases:
            for repetition in range(2):
                directory=ROOT/f"context-{spec['id']}-{size}-{repetition}"
                if (directory/'result.json').exists(): r=json.loads((directory/'result.json').read_text())
                elif (directory/'failure.json').exists(): r={**json.loads((directory/'failure.json').read_text()),'repetition':repetition}
                else: r={'status':'pending','repetition':repetition}
                records.append(r)
        finished=[r for r in records if r['status']!='pending']
        completed=[r for r in records if r['status']=='completed']
        exact=sum(r.get('exact',False) for r in records);invalid=sum(not r['valid_edges'] for r in completed)
        failures=sum(r['status']=='failed' for r in records)
        verdict='INCONCLUSIVE' if len(finished)<8 else ('PASS' if exact>=7 and invalid==0 and failures<=1 else 'FAIL')
        context.append({'size':size,'finished':len(finished),'exact':exact,'invalid_edge_answers':invalid,'failures':failures,'verdict':verdict,
                        'chronological_exact':sum(r.get('exact',False) for r in records if r['repetition']==0),
                        'shuffled_exact':sum(r.get('exact',False) for r in records if r['repetition']==1),
                        'mean_prompt_tokens':mean([(r.get('usage') or {}).get('prompt_tokens') for r in completed]),
                        'mean_seconds':mean([r.get('seconds') for r in completed])})
    groups=defaultdict(list)
    for r in offline[:48]: groups[r['branches'],r['page']].append(r)
    grid=[]
    for (branches,page),rs in groups.items():
        grid.append({'branches':branches,'page':page,'additional_recall':mean([r['reference_additional_recall'] for r in rs]),
                     'mean_returned':mean([r['returned_rows'] for r in rs]),'mean_pages':mean([r['query_pages'] for r in rs]),
                     'mean_repeat_fraction':mean([r['repeat_fraction'] for r in rs]),'per_case_unique':[r['unique_rows'] for r in rs]})
    best=max(r['additional_recall'] for r in grid)
    candidate=min([r for r in grid if r['additional_recall']>=best-.05],key=lambda r:(r['mean_returned'],r['mean_pages']))
    views=[]
    for size in VIEWS:
        rs=[r for r in offline[48:] if r['view_limit']==size]
        views.append({'size':size,'additional_recall':mean([r['reference_additional_recall'] for r in rs]),
                      'mean_returned':mean([r['returned_rows'] for r in rs]),'mean_pages':mean([r['query_pages'] for r in rs])})
    best_view=max(r['additional_recall'] for r in views)
    eligible=[r['size'] for r in views if r['additional_recall']>=best_view-.05 and next(c for c in context if c['size']==r['size'])['verdict']=='PASS']
    navigation=[]
    for policy in ['broad','cautious','adaptive']:
        for spec in cases:
            for repetition in range(2):
                directory=ROOT/f"live-{policy}-{spec['id']}-{repetition}"
                result=json.loads((directory/'result.json').read_text()) if (directory/'result.json').exists() else None
                state=json.loads((directory/'state.json').read_text()) if (directory/'state.json').exists() else None
                failure=json.loads((directory/'failure.json').read_text()) if (directory/'failure.json').exists() else None
                targets=set(spec['target_ids'])-({'T'+str(spec['seed_id'])})
                found=set(state['evidence']) if state else set()
                navigation.append({'policy':policy,'case':spec['id'],'repetition':repetition,
                    'status':'completed' if result else 'failed' if failure else 'pending',
                    'additional_recall':len(found&targets)/len(targets) if targets and state else None,
                    'unique_rows':len(found) if state else None,'query_pages':len(state['actions']) if state else None,
                    'model_calls':len(state['calls']) if state else None,
                    'total_tokens':sum((c.get('usage') or {}).get('total_tokens',0) for c in state['calls']) if state else None,
                    'valid_paths':result['valid_paths'] if result else None,'proposed_paths':result['proposed_paths'] if result else None,
                    'requested_sizes':result['requested_sizes'] if result else None,
                    'handoffs':result['handoffs'] if result else None,'max_view':result['max_view'] if result else None,
                    'error':failure['detail'] if failure else None})
    nav_summary=[]
    for policy in ['broad','cautious','adaptive']:
        rs=[r for r in navigation if r['policy']==policy]
        nav_summary.append({'policy':policy,'completed':sum(r['status']=='completed' for r in rs),
            'failed':sum(r['status']=='failed' for r in rs),'pending':sum(r['status']=='pending' for r in rs),
            'mean_additional_recall_including_partial':mean([r['additional_recall'] for r in rs]),
            'mean_rows':mean([r['unique_rows'] for r in rs]),'mean_calls':mean([r['model_calls'] for r in rs]),
            'total_tokens':sum(r['total_tokens'] or 0 for r in rs),'valid_paths':sum(r['valid_paths'] or 0 for r in rs),
            'proposed_paths':sum(r['proposed_paths'] or 0 for r in rs)})
    lower_sweep_path=ROOT/'lower-view-sweep/results.json'
    lower_sweep=[]
    if lower_sweep_path.exists():
        groups_lower=defaultdict(list)
        for r in json.loads(lower_sweep_path.read_text()):groups_lower[r['view_limit'],r['page']].append(r)
        for (view,page),rs in groups_lower.items():
            lower_sweep.append({'view':view,'page':page,'recall':mean([r['reference_additional_recall'] for r in rs]),
                                'mean_returned':mean([r['returned_rows'] for r in rs]),'mean_pages':mean([r['query_pages'] for r in rs])})
    sweep_path=ROOT/'reference-sweep/results.json'
    sweep_summary=[];sweep_candidate=None
    if sweep_path.exists():
        sweep_groups=defaultdict(list)
        for r in json.loads(sweep_path.read_text()):sweep_groups[r['branches'],r['page'],r['view_limit']].append(r)
        for (branches,page,view),rs in sweep_groups.items():
            sweep_summary.append({'branches':branches,'page':page,'view':view,
                'recall':mean([r['reference_additional_recall'] for r in rs]),
                'mean_returned':mean([r['returned_rows'] for r in rs]),'mean_pages':mean([r['query_pages'] for r in rs]),
                'families':{family:mean([r['reference_additional_recall'] for r in rs if r['family']==family]) for family in ['CYCLE','RANDOM','FAN-IN','FAN-OUT']}})
        base=[r for r in sweep_summary if r['view']==300];best_sweep=max(r['recall'] for r in base)
        sweep_candidate=min([r for r in base if r['recall']>=best_sweep-.05],key=lambda r:(r['mean_returned'],r['mean_pages']))
    complete=all(c['finished']==8 for c in context) and all(r['status']!='pending' for r in navigation)
    normal=min([r for r in sweep_summary if r['view']==300 and abs(r['recall']-best_sweep)<1e-12],key=lambda r:(r['mean_returned'],r['mean_pages'])) if sweep_summary else None
    recommendations={'expansion_low_cost':sweep_candidate,'expansion_higher_coverage':normal,
                     'validated_context_row_limit':None if not eligible else min(eligible),
                     'context_note':'No passing quality screen; do not present a row limit as a reliable smart zone.' if not eligible else 'Small constructed development screen only, not a production guarantee.',
                     'runtime_defaults_changed':False}
    summary={'recommendations':recommendations,'study_complete':complete,'context':context,'offline_grid':grid,'offline_views':views,'expansion_candidate':candidate,
             'screened_view_candidate':min(eligible) if eligible else None,'navigation':navigation,'navigation_summary':nav_summary,
             'lower_view_sweep':lower_sweep,'reference_sweep':sweep_summary,'reference_sweep_candidate':sweep_candidate,
             'provider_requests':len(provider),'provider_usage':usage,'unknown_usage_requests':sum(r.get('usage') is None for r in provider),
             'source_sha256':manifest['source_sha256']}
    save(ROOT/'summary.json',summary)
    lines=['# Threshold study: measured development results','',
           'Status: '+('all planned conditions have a completed result or an explicit failure.' if complete else 'IN PROGRESS; no final threshold recommendation yet.'),'',
           'This study tests retrieval and exact graph reading on four deliberately selected IBM HI-Small cases. It does not estimate production detection quality. Failed conditions remain in denominators. The frozen protocol is in `THRESHOLD-PROTOCOL.md`.','',
           '## What one case means','',
           'The three-edge-cycle case starts with one known reference edge, but the model sees only its ordinary transaction fields. Finding its other two reference edges gives additional-reference recall 1.0. The seven-edge-cycle case has six further edges to find. Labels and reference membership are used only for case preparation and post-run scoring. The ordinary control has a label-zero seed, not a certified benign neighborhood; the hub is selected by degree without labels.','',
           table(['Case','Meaning'],[[c['id'],c['description']] for c in cases]),'',
           '## Context screening','',
           'Each size has eight constructed probes: four cases in chronological and shuffled order. PASS requires at least 7/8 exact greedy traces and zero invalid-edge answers; at most one failed/invalid-format request. A pass on eight probes is not a guarantee.','',
           table(['Rows','Finished / 8','Exact / 8','Chronological / 4','Shuffled / 4','Invalid edges','Failed calls','Screen','Mean input tokens','Mean seconds'],
                 [[r[k] for k in ['size','finished','exact','chronological_exact','shuffled_exact','invalid_edge_answers','failures','verdict','mean_prompt_tokens','mean_seconds']] for r in context]),'',
           '## Expansion grid (no model calls)','',
           'Same 300-row view, 599 returned rows including repeats, 24 page queries and 12 decisions. Additional recall is the unweighted mean over the two reference cycles; the supplied seed is excluded. Other columns average all four cases.','',
           table(['Branches','Rows/page','Additional recall','Mean returned rows','Mean pages','Mean repeat fraction'],[[r[k] for k in ['branches','page','additional_recall','mean_returned','mean_pages','mean_repeat_fraction']] for r in grid]),'',
           'The predeclared recall-within-five-points, then lowest-returned-rows rule selects '+str(candidate['branches'])+' branch(es) × '+str(candidate['page'])+' rows for a **development candidate**, not a universal optimum.','',
           'Large-page results depend on the current scheduler: requests are capped in listed order, so an early large page can leave only one row for a later branch. This is a comparison within the fixed row/page/decision budgets, not evidence that 500-row pages are universally inferior.','',
           '## Working-view sensitivity of fixed broad navigation','',
           table(['View limit','Additional recall','Mean returned rows','Mean pages'],[[r[k] for k in ['size','additional_recall','mean_returned','mean_pages']] for r in views]),'',
           'Smallest view meeting both the context screen and retrieval rule: '+(str(min(eligible)) if eligible else 'none established')+'. This comparison holds the broad policy fixed; it does not establish an adaptive-policy optimum.','',
           '## Live navigation comparison','',
           'Two repetitions per policy and case. All policies share maximum retrieval/decision allowances and a real-model reviewer. Fixed policies require no investigator model calls. Coverage includes partial evidence from failed runs; factual path counts below include completed reviews only. A failure is not silently retried.','',
           table(['Policy','Completed / 8','Failed','Pending','Mean additional recall (partial included)','Mean rows','Mean model calls','Total reported tokens','Valid/proposed paths'],
                 [[r['policy'],r['completed'],r['failed'],r['pending'],r['mean_additional_recall_including_partial'],r['mean_rows'],r['mean_calls'],r['total_tokens'],f"{r['valid_paths']}/{r['proposed_paths']}"] for r in nav_summary]),'',
           table(['Policy','Case','Repeat','Status','Additional recall','Rows','Calls','Tokens','Valid paths','Proposed paths'],
                 [[r[k] for k in ['policy','case','repetition','status','additional_recall','unique_rows','model_calls','total_tokens','valid_paths','proposed_paths']] for r in navigation]),'',
           '## Actual provider usage','',
           table(['Requests','Input tokens','Output tokens','Total tokens','Unknown-usage requests'],[[len(provider),usage['prompt_tokens'],usage['completion_tokens'],usage['total_tokens'],summary['unknown_usage_requests']]]),'',
           'Account dollar pricing is unavailable. Reported tokens include failed calls when the provider returned usage; unknown consumption is not treated as zero. Two concurrent jobs and network variability make elapsed times observational, not controlled latency benchmarks.','',
           '## What these results cannot establish','',
           'Only two deliberately selected reference networks contribute known-pattern recall. The context test contains controlled distractors and a specific three-edge tracing instruction; passing it does not prove reliable open-ended investigation, aggregation, suspicion judgments, or 1,500-row review. The navigation experiment uses deterministic seed-plus-six-row carryover, not the earlier model-summary/Meterless choreography. Repeated same-prompt runs on the same cases are not independent population samples. Valid connectivity does not establish laundering or conserved funds. Unfinished branches remain unknown.','']
    if normal:
        insertion=lines.index('## What one case means')
        findings=['## Practical settings supported by this study','',
                  table(['Setting','Development recommendation','Evidence'],[
                      ['Rows per branch',normal['page'],'Larger fixed pages did not improve the best reference recovery under the tested budgets'],
                      ['Cautious expansion',str(sweep_candidate['branches'])+' branch × '+str(sweep_candidate['page'])+' rows',f"Lowest-cost candidate within the declared five-point tolerance: {100*sweep_candidate['recall']:.1f}% additional reference recall"],
                      ['Broader expansion',str(normal['branches'])+' branches × '+str(normal['page'])+' rows',f"Highest observed macro additional recall: {100*normal['recall']:.1f}%; lower returned-row cost among tied settings"],
                      ['Reliable working-view threshold','None established' if not eligible else str(min(eligible)),recommendations['context_note']],
                      ['Autonomous review','Not established','Most proposed paths failed deterministic checks; keep factual verification mandatory']]),'',
                  'These are retrieval presets, not evidence of reliable laundering detection. Runtime defaults were not silently changed. No row setting is promoted as a model-quality default. Fixed budgets (599 returned rows, 24 pages, 12 decisions) were experimental controls, not optimized thresholds.','']
        lines[insertion:insertion]=findings
    failures=[r for r in navigation if r['error']]
    if failures:
        lines+=['## Recorded navigation failures','',table(['Policy','Case','Repeat','Error'],[[r['policy'],r['case'],r['repetition'],r['error']] for r in failures]),'']
    if sweep_summary:
        lines+=['## Broader offline sensitivity check','',
                'After the first two reference networks gave identical recovery across settings, a separate deterministic sweep selected the first four fully in-scope publisher groups of 3–12 edges from each of CYCLE, RANDOM, FAN-IN and FAN-OUT. These 16 enriched development cases add shape diversity; they are not an independent holdout and do not change the live scoring gates. All values below are additional reference recall, excluding the seed.','',
                table(['Branches','Page','View','Macro recall','Cycle','Random chain','Fan-in','Fan-out','Mean returned','Mean pages'],
                      [[r['branches'],r['page'],r['view'],r['recall'],*[r['families'][f] for f in ['CYCLE','RANDOM','FAN-IN','FAN-OUT']],r['mean_returned'],r['mean_pages']] for r in sweep_summary]),'',
                'The same within-five-points then lowest-returned-rows rule selects '+str(sweep_candidate['branches'])+' × '+str(sweep_candidate['page'])+'. The full per-case results and selection manifest are under reference-sweep/. This tolerance explicitly permits some loss of recovery in exchange for lower retrieval cost; inspect family-level losses before choosing a default.','']
    if lower_sweep:
        lines+=['## Downward context bracket','',
                'After every original size produced invalid-edge answers, the same task and screening gate were applied at 40 and 75 rows (16 additional calls within the same cumulative budget). These are follow-up development probes on the same cases, not independent confirmation. The context table above includes them. The offline table below holds four branches fixed on the broader 16-reference set.','',
                table(['View','Page size','Additional recall','Mean returned rows','Mean pages'],[[r[k] for k in ['view','page','recall','mean_returned','mean_pages']] for r in lower_sweep]),'']
    context_failures=[]
    for path in sorted(ROOT.glob('context-*/failure.json')):
        failure=json.loads(path.read_text());context_failures.append([path.parent.name,failure['detail']])
    if context_failures:
        lines+=['## Context transport/format failures','',
                'HTTP 429 and HTTP 500 are service failures, not evidence that a row count exceeded model comprehension. They remain in the end-to-end screen. The smaller-size accuracy comparison is inconclusive where rate limits prevented responses; separately, every tested size produced an invalid-edge counterexample, so none satisfies the zero-invalid-edge requirement.','',
                table(['Condition','Failure'],context_failures),'']
    phases=defaultdict(list)
    for record in provider:phases[record.get('study','unclassified')].append(record)
    lines+=['## Usage by study phase','',table(['Phase','Requests','Reported tokens','Unknown usage'],
        [[name,len(rs),sum((r.get('usage') or {}).get('total_tokens',0) for r in rs),sum(r.get('usage') is None for r in rs)] for name,rs in phases.items()]),'']
    md='\n'.join(lines);(ROOT/'report.md').write_text(md)
    # Standalone review surface. Render markdown tables directly from the generated text.
    blocks=[];chunk=[]
    def flush():
        if not chunk:return
        if chunk[0].startswith('|'):
            cells=[[c.strip() for c in row.strip('|').split('|')] for row in chunk]
            head='<tr>'+''.join('<th>'+html.escape(c)+'</th>' for c in cells[0])+'</tr>'
            body=''.join('<tr>'+''.join('<td'+(' class="prose"' if len(c)>50 else '')+'>'+html.escape(c)+'</td>' for c in row)+'</tr>' for row in cells[2:])
            blocks.append('<div class="table"><table><thead>'+head+'</thead><tbody>'+body+'</tbody></table></div>')
        else:
            for line in chunk:
                if line.startswith('# '): blocks.append('<h1>'+html.escape(line[2:])+'</h1>')
                elif line.startswith('## '):blocks.append('<h2>'+html.escape(line[3:])+'</h2>')
                else:blocks.append('<p>'+html.escape(line)+'</p>')
        chunk.clear()
    for line in md.splitlines():
        if not line: flush()
        else:chunk.append(line)
    flush()
    (ROOT/'report.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AML threshold study</title><style>body{font:16px/1.55 system-ui;margin:32px auto;padding:0 20px;max-width:1200px;color:#20262b;background:#f6f7f9}h1,h2{line-height:1.2}.table{overflow-x:auto;margin:24px 0}table{border-collapse:collapse;min-width:700px;background:white}td,th{padding:9px 12px;border:1px solid #cdd4da;text-align:left;white-space:nowrap}th{background:#e3ebf2}.prose{white-space:normal;min-width:28ch;max-width:65ch}p{max-width:100ch;overflow-wrap:anywhere}</style>'+''.join(blocks))
    if complete:
        (ROOT.parent.parent/'THRESHOLD-RESULTS.md').write_text(md)
        save(ROOT.parent.parent/'threshold-results.json',summary)
    print(json.dumps({'complete':complete,'context':context,'provider_requests':len(provider),'summary':str(ROOT/'summary.json')}))

if __name__=='__main__':main()
