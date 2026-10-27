"""Derive the pilot readout from immutable case artifacts; no model calls."""
import collections
import fcntl
import json
from pathlib import Path
from pilot import OUT, report
from run_case import save


def build():
    summary=report()
    for result in summary['cases']:
        state=json.loads((OUT/result['id']/'state.json').read_text())
        result['unknown_usage_calls']=sum(c.get('usage') is None for c in state['calls'])
        result['received_responses']=sum((OUT/result['id']/f'{i:02d}-{c["role"]}-response.json').exists() for i,c in enumerate(state['calls'],1))
        if result['cohort']=='challenge':
            targets=json.loads((OUT/'evaluator-targets.json').read_text())
            expected=set(targets[str(result['seed_id'])])-{state['seed']}
            reviewed={i for packet in (state.get('review_queue') or {}).get('completed',[]) for i in packet['view']}
            result['completed_review_reference_edges']=len(expected & reviewed)
            result['completed_review_reference_coverage']=len(expected & reviewed)/len(expected)
    def aggregate(rows):
        challenges=[r for r in rows if r['cohort']=='challenge']
        return {'attempts':len(rows),'cases_with_model_response':sum(r['received_responses']>0 for r in rows),
            'execution_failures':sum(r['failure'] is not None for r in rows), 'replay':dict(collections.Counter(r['replay']['status'] for r in rows)),
            'exploration_complete':sum(r['status']=='frontier_exhausted' for r in rows),'review_complete':sum(r['review_status']=='complete' for r in rows),
            'calls':sum(r['calls'] for r in rows),'reported_tokens':sum(r['tokens'] for r in rows),'unknown_usage_calls':sum(r['unknown_usage_calls'] for r in rows),
            'case_seconds':sum(r['seconds'] for r in rows),'pages':sum(r['pages'] for r in rows),'pending_scopes':sum(r['pending_scopes'] for r in rows),
            'review_packets_pending':sum(r['review_packets']-r['review_packets_completed'] for r in rows),
            'macro_additional_edge_recall':sum(r['additional_edge_recall'] for r in challenges)/len(challenges) if challenges else None,
            'macro_completed_review_reference_coverage':sum(r['completed_review_reference_coverage'] for r in challenges)/len(challenges) if challenges else None}
    summary['cohorts']={name:aggregate([r for r in summary['cases'] if r['cohort']==name]) for name in ('label_free','challenge')}
    summary['families']={name:aggregate([r for r in summary['cases'] if r.get('family')==name]) for name in ('CYCLE','RANDOM','FAN-IN','FAN-OUT')}
    specs=json.loads((OUT/'cases.json').read_text())
    summary['activity_ranges']={name:[min(r['endpoint_incidence_count'] for r in specs if r.get('activity_band')==name),max(r['endpoint_incidence_count'] for r in specs if r.get('activity_band')==name)] for name in ('low','medium','high')}
    save(OUT/'readout.json',summary)
    gate=json.loads((OUT/'smoke-gate.json').read_text()) if (OUT/'smoke-gate.json').exists() else None
    lines=['# 100-case pilot readout','',f"Finished attempts: **{summary['finished_attempts']}/100**. Smoke gate: **{gate['passed'] if gate else 'pending'}**.",'',
        f"Full replay certificates: {summary['replay_passed']}; structural replay failures: {summary['replay_failed']}; execution failures: {summary['execution_failures']}.",
        f"Exploration complete: {summary['exploration_complete']}; review complete: {summary['review_complete']}. Budget-stopped exploration remains incomplete even when its partial review finishes.",'',
        f"Reported tokens: {summary['budget'].get('reported_tokens',0):,}; conservatively charged tokens: {summary['budget'].get('charged_tokens',0):,}; calls with unresolved usage: {summary['budget'].get('unknown_usage',0)}. Currency cost unavailable.",'',
        '| Cohort | Attempts | Execution failures | Exploration complete | Review complete | Additional-edge recall |',
        '|---|---:|---:|---:|---:|---:|']
    for name,data in summary['cohorts'].items():
        recall=data['macro_additional_edge_recall']; value=f'{recall:.1%}' if recall is not None else 'N/A'
        lines.append(f"| {name} | {data['attempts']} | {data['execution_failures']} | {data['exploration_complete']} | {data['review_complete']} | {value} |")
    lines += ['', 'Challenge retrieval measures recovery of supplied reference edges, excluding the seed; it does not measure laundering detection accuracy. Failed cases remain in attempted-case metrics. Unstarted cases have no result and are not counted as tested.', '', '## Failures', '']
    lines += ['Interrupted traces are uncertifiable execution failures. Zero structural replay failures does not establish structural correctness when no full trace was certified. Review packets are created only after exploration pauses cleanly; zero packets does not mean no review work was needed.', '', f"Unstarted cases: {100-summary['finished_attempts']}.", '']
    for result in summary['cases']:
        if result['failure'] or result['replay']['status']!='passed':lines.append(f"- {result['id']}: {json.dumps(result['failure'] or result['replay'])}")
    lines += ['', '## Per-case outcomes', '', '| Case | Cohort | Rows | Pages | Calls | Exploration | Review | Replay |','|---|---|---:|---:|---:|---|---|---|']
    for r in summary['cases']:lines.append(f"| {r['id']} | {r['cohort']} | {r['rows']} | {r['pages']} | {r['calls']} | {r['status']} | {r['review_status']} | {r['replay']['status']} |")
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('cases','families')},indent=2))

if __name__=='__main__':
    with (OUT/'pilot.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        build()
