"""Frozen 100-case development pilot; evaluator targets never enter Case state."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import fcntl
import hashlib
import json
from pathlib import Path
import random
import threading
import time

from chunk_case import Case, DEFAULTS, SCOPE, alias, discover, init
from model import Model, MODEL, ENDPOINT
from replay_audit import audit, AuditFailure
from run_case import save
from tools import HERE, Tools

OUT = HERE / 'generated/pilot-100-v1'
TOKEN_BUDGET = 60_000_000

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare():
    OUT.mkdir(parents=True, exist_ok=False)
    tools = Tools(receipts=OUT/'preparation-receipts.sqlite')
    rng = random.Random(20261023)
    pools, counts = {}, {}
    for row in tools.db.execute('SELECT row_id,timestamp FROM transactions WHERE timestamp>=? AND timestamp<? AND (source_bank!=destination_bank OR source_account!=destination_account) ORDER BY row_id', SCOPE):
        day = row['timestamp'][:10]
        pool = pools.setdefault(day, [])
        counts[day] = counts.get(day, 0) + 1
        if len(pool) < 300: pool.append(row['row_id'])
        else:
            index = rng.randrange(counts[day])
            if index < 300: pool[index] = row['row_id']
    cases = []
    for day, pool in sorted(pools.items()):
        ranked = []
        for row_id in pool:
            row = tools.db.execute('SELECT * FROM transactions WHERE row_id=?', (row_id,)).fetchone()
            activity = 0
            for side in ('source', 'destination'):
                for direction in ('source', 'destination'):
                    activity += tools.db.execute(f'SELECT count(*) FROM transactions WHERE {direction}_bank=? AND {direction}_account=? AND timestamp>=? AND timestamp<?', (row[side+'_bank'], row[side+'_account'], *SCOPE)).fetchone()[0]
            ranked.append((activity, row_id))
        ranked.sort()
        for band, name in enumerate(('low', 'medium', 'high')):
            stratum = ranked[band*100:(band+1)*100]
            number = 4 if len(cases) < 68 else 3
            for activity, row_id in rng.sample(stratum, number):
                cases.append({'seed_id':row_id, 'cohort':'label_free', 'day':day, 'activity_band':name, 'endpoint_incidence_count':activity})
    assert len(cases) == 80
    groups = []
    for line in (HERE.parents[1]/'data/HI-Small_Patterns.txt').read_text().splitlines():
        if line.startswith('BEGIN'): groups.append({'name':line,'rows':[]})
        elif line.startswith('2022/'): groups[-1]['rows'].append(next(csv.reader([line])))
    old = HERE/'generated/thresholds-v2/reference-sweep/cases.json'
    used = {c['pattern_index'] for c in json.loads(old.read_text())} if old.exists() else set()
    golden = json.loads((HERE/'threshold-golden-evaluator.json').read_text())
    used.update(c['pattern_index'] for c in golden['navigation_cases'] if 'pattern_index' in c)
    targets = {}
    for family in ('CYCLE','RANDOM','FAN-IN','FAN-OUT'):
        selected = 0
        for index, group in enumerate(groups):
            if index in used or f' - {family}:' not in group['name'] or not 3 <= len(group['rows']) <= 20 or not all(SCOPE[0] <= r[0] < SCOPE[1] for r in group['rows']): continue
            ids = []
            for r in group['rows']:
                hits = tools.db.execute('SELECT row_id FROM transactions WHERE source_bank=? AND source_account=? AND timestamp=? AND destination_bank=? AND destination_account=? AND received_amount=? AND received_currency=? AND paid_amount=? AND paid_currency=? AND payment_format=?', (r[1].lstrip('0') or '0',r[2],r[0],r[3].lstrip('0') or '0',r[4],*r[5:10])).fetchall()
                if len(hits) != 1: break
                ids.append(hits[0][0])
            if len(ids) != len(group['rows']): continue
            seed = min(zip(group['rows'], ids), key=lambda pair:(pair[0][0],pair[1]))[1]
            if seed in {c['seed_id'] for c in cases}: continue
            cases.append({'seed_id':seed,'cohort':'challenge','family':family,'pattern_index':index})
            targets[str(seed)] = ['T'+str(i) for i in ids]
            selected += 1
            if selected == 5: break
        assert selected == 5, family
    source_sha = tools.sha
    tools.close()
    # Smoke gate covers all four challenge families and six spread-out label-free seeds.
    smoke = [cases[i] for i in (0,15,30,45,60,75,80,85,90,95)]
    cases = smoke + [c for c in cases if c not in smoke]
    for index, spec in enumerate(cases, 1): spec['id'] = f'case-{index:03d}'
    assert len(cases) == len({c['seed_id'] for c in cases}) == 100
    save(OUT/'cases.json', cases)
    save(OUT/'evaluator-targets.json', targets)
    frozen = OUT/'frozen-source'; frozen.mkdir()
    for path in HERE.glob('*.py'): (frozen/path.name).write_bytes(path.read_bytes())
    save(OUT/'manifest.json', {'model':MODEL,'endpoint':ENDPOINT,'limits':DEFAULTS,'token_budget':TOKEN_BUDGET,'workers':2,
        'source_sha256':source_sha,
        'source_hashes':{p.name:digest(p) for p in HERE.glob('*.py')},'cases_sha256':digest(OUT/'cases.json'), 'targets_sha256':digest(OUT/'evaluator-targets.json'),
        'selection':'Seed 20261023 reservoir of 300 external transactions per reporting day; rank by summed endpoint incoming/outgoing incidence, split into thirds, sample 4 in first17 strata and3 in last4. Activity bands are within sampled day candidates, not population quantiles. Twenty challenges: first5 eligible unused publisher groups per family; 3..20 edges; exact unambiguous source matches. Previous reference-sweep groups excluded.',
        'gate':'After10: stop on any replay failure in a clean closed case, or fewer than8 clean cases. Failed/open calls are uncertifiable execution failures, not structural passes. No automatic retries or prompt tuning.',
        'metrics':'All100 attempted cases in reliability denominator. Challenge additional-edge retrieval recall excludes seed; failed cases retained. Label-free descriptive outcomes only. Separate exploration/review completion, structural audit, pending work, token usage, wall time, overlap. No laundering precision/recall claim.',
        'budget':'160 total calls including navigation/checkpoints/review; no review extensions. Global60M: reserve serialized request bytes plus max output tokens plus2048 before each HTTP request; reconcile reported usage, retain reservation for unknown usage. Budget interruption can leave uncertifiable open segment. No automatic retries.'})
    print(json.dumps({'prepared':len(cases),'directory':str(OUT)}), flush=True)

class Budget:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {'charged_tokens':0,'reported_tokens':0,'requests':0,'unknown_usage':0}
        if (OUT/'budget.json').exists(): self.state = json.loads((OUT/'budget.json').read_text())
    def complete(self, provider, messages, tools, tool_choice, max_tokens):
        reserve = len(json.dumps({'messages':messages,'tools':tools,'tool_choice':tool_choice}).encode()) + max_tokens + 2048
        with self.lock:
            if self.state['charged_tokens'] + reserve > TOKEN_BUDGET: raise RuntimeError('Pilot global token budget exhausted')
            self.state['charged_tokens'] += reserve; self.state['requests'] += 1; self.state['unknown_usage'] += 1
            save(OUT/'budget.json', self.state)
        result = provider.complete(messages, tools, tool_choice, max_tokens)
        usage = (result.get('usage') or {}).get('total_tokens')
        if usage is not None:
            with self.lock:
                self.state['charged_tokens'] += usage-reserve; self.state['reported_tokens'] += usage; self.state['unknown_usage'] -= 1
                save(OUT/'budget.json', self.state)
        return result

class BudgetModel:
    def __init__(self, budget): self.provider = Model(); self.budget = budget
    def complete(self, messages, tools=None, tool_choice='auto', max_tokens=2048):
        return self.budget.complete(self.provider, messages, tools, tool_choice, max_tokens)

def run_one(spec, budget):
    directory = OUT/spec['id']
    if (directory/'result.json').exists(): return json.loads((directory/'result.json').read_text())
    # Existing incomplete directories require manual inspection, never implicit reruns.
    init(directory)
    state = json.loads((directory/'state.json').read_text())
    tools = Tools(receipts=directory/'receipts.sqlite')
    row = tools.get_transactions([tools.sha+':'+str(spec['seed_id'])])['rows'][0]; tools.close()
    state.update(seed=alias(row), evidence={}, queries={}, anchors=[alias(row)])
    discover(state, [row]); save(directory/'state.json', state)
    start = time.monotonic(); failure = None
    case = Case(directory, model=BudgetModel(budget))
    try:
        while case.state['status'] == 'active': case.segment()
        case.review()  # Explicit partial review at bounded exploration pause.
    except Exception as exc:
        failure = {'type':type(exc).__name__, 'message':str(exc)[:300]}
    finally: case.close()
    state = json.loads((directory/'state.json').read_text())
    clean = failure is None and state.get('active_view') is None and all(c['status']=='received' or c.get('outcome') in ('rejected','transport_error') for c in state['calls'])
    replay = {'status':'uncertifiable_execution_failure'}
    if clean:
        try: replay = {'status':'passed','details':audit(directory)}
        except AuditFailure as exc: replay = {'status':'failed','message':str(exc)[:500]}
        except Exception as exc: replay = {'status':'audit_error','message':str(exc)[:500]}
    queue = state.get('review_queue') or {}
    result = {**spec,'failure':failure,'replay':replay,'seconds':time.monotonic()-start,'status':state['status'],
        'review_status':state.get('review_status','not_started'),'rows':len(state['evidence']),'pages':len(state['actions']),
        'calls':len(state['calls']),'chunks':len(state['chunks']),'pending_scopes':sum(q['status']=='pending' for q in state['queries'].values()),
        'review_packets':len(queue.get('packets',[])),'review_packets_completed':len(queue.get('completed',[])),
        'view_changes':len(state.get('view_events',[])), 'tokens':sum((c.get('usage') or {}).get('total_tokens',0) for c in state['calls'])}
    save(directory/'result.json', result)
    print(json.dumps({k:result[k] for k in ('id','cohort','status','review_status','calls','tokens','failure')}), flush=True)
    return result

def report():
    cases = json.loads((OUT/'cases.json').read_text()); targets = json.loads((OUT/'evaluator-targets.json').read_text())
    results = []; unique = set(); total_rows = 0
    for spec in cases:
        directory = OUT/spec['id']
        if not (directory/'result.json').exists(): continue
        result = json.loads((directory/'result.json').read_text()); state=json.loads((directory/'state.json').read_text())
        evidence = set(state['evidence']); unique.update(evidence); total_rows += len(evidence)
        if spec['cohort']=='challenge':
            expected = set(targets[str(spec['seed_id'])]) - {state['seed']}
            result['additional_reference_edges'] = len(expected)
            result['retrieved_reference_edges'] = len(expected & evidence)
            result['additional_edge_recall'] = len(expected & evidence)/len(expected)
        results.append(result)
    summary = {'planned':100,'finished_attempts':len(results),'execution_failures':sum(r['failure'] is not None for r in results),
        'replay_passed':sum(r['replay']['status']=='passed' for r in results),'replay_failed':sum(r['replay']['status']=='failed' for r in results),
        'exploration_complete':sum(r['status']=='frontier_exhausted' for r in results),'review_complete':sum(r['review_status']=='complete' for r in results),
        'total_evidence_rows_across_cases':total_rows,'unique_evidence_rows':len(unique),'budget':json.loads((OUT/'budget.json').read_text()) if (OUT/'budget.json').exists() else {},'cases':results}
    save(OUT/'results.json',summary)
    return summary

def run_locked():
    manifest=json.loads((OUT/'manifest.json').read_text())
    assert all(digest(HERE/name)==sha for name,sha in manifest['source_hashes'].items()), 'Source changed after freeze'
    assert digest(OUT/'cases.json')==manifest['cases_sha256'] and digest(OUT/'evaluator-targets.json')==manifest['targets_sha256']
    cases=json.loads((OUT/'cases.json').read_text()); budget=Budget()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=list(pool.map(lambda spec:run_one(spec,budget),cases[:10]))
        gate = sum(r['replay']['status']=='passed' for r in first)>=8 and not any(r['replay']['status']=='failed' for r in first)
        save(OUT/'smoke-gate.json',{'passed':gate,'finished':10}); report()
        if not gate:
            print('Smoke gate failed; baseline preserved, remaining90 not started.',flush=True); return
        for result in pool.map(lambda spec:run_one(spec,budget),cases[10:]): report()
    print(json.dumps({k:v for k,v in report().items() if k!='cases'}),flush=True)

def run():
    with (OUT/'pilot.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_locked()

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['prepare','run','report']); args=parser.parse_args()
    if args.action=='prepare': prepare()
    elif args.action=='run': run()
    else: print(json.dumps({k:v for k,v in report().items() if k!='cases'},indent=2))
