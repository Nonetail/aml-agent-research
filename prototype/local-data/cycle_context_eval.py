"""Frozen, fresh-context cycle experiments with exact token admission and scoring."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timedelta
import fcntl
import hashlib
import io
import json
from pathlib import Path
import random
import sqlite3
import sys
import threading
import time

from cycle_prompts import REVIEWER_SYSTEM, review_definition
from cycle_context_scoring import oracle_cycles, score_answer
from cycle_view_scenarios import partition_views, overlap_views
from cycle_benchmark import short_account_clusters
from model import Model, MODEL, ENDPOINT, provider_schema
from run_case import save

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[1]/'experiments/2026-10-24-cycle-context'
ROOT = HERE/'generated/cycle-context-v1'
sys.path.insert(0, str(RESEARCH))
SCOPE = ['2022/09/01 00:00', '2022/09/19 00:00']
GROUPS = {'dev-2':24, 'dev-3':74, 'dev-4':68,
          'holdout-2':143, 'holdout-3':167, 'holdout-4':155}
SOURCE_FILES = ['cycle_context_eval.py', 'cycle_context_scoring.py', 'cycle_view_scenarios.py',
                'cycle_prompts.py', 'cycle_benchmark.py', 'model.py', 'run_case.py']
FORMAT = '''The following CSV is an exact transaction snapshot, not a graph image.
T<number> means the original row ordinal under the single supplied source_sha256.
The columns preserve exact bank/account identifiers and both sides' amounts/currencies.
Search the whole supplied snapshot for all simple strictly chronological 2..4-edge
return cycles. Propose exact ordered supports yourself; no candidates or seeds are
provided. No external tools or scopes are available: evidence_requests must be [].
Assess the structural finding separately from suspicion; missing context is a limitation.
The snapshot may contain zero, one, or several cycles. Use only its supplied rows.
'''
COLUMNS = ['id','time','from_bank','from_account','to_bank','to_account',
           'paid','paid_currency','received','received_currency','format']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def row(raw):
    result = dict(raw)
    result['transaction_id'] = 'T'+str(result.pop('row_id'))
    return result


def ordered(rows):
    # Stable shuffled order shared by nested packets; no labels or account topology.
    return sorted(rows, key=lambda r: hashlib.sha256(r['transaction_id'].encode()).hexdigest())


def request_for(rows, sha):
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(COLUMNS)
    for r in rows:
        writer.writerow([r['transaction_id'],r['timestamp'],r['source_bank'],r['source_account'],
            r['destination_bank'],r['destination_account'],r['paid_amount'],r['paid_currency'],
            r['received_amount'],r['received_currency'],r['payment_format']])
    metadata = {'source_sha256':sha, 'start':SCOPE[0], 'end':SCOPE[1],
                'max_edges':4, 'max_duration_minutes':None, 'available_scope_ids':[]}
    definition = review_definition([r['transaction_id'] for r in rows], [])
    return {'model':MODEL, 'messages':[{'role':'system','content':REVIEWER_SYSTEM+'\n'+FORMAT},
            {'role':'user','content':json.dumps(metadata,separators=(',',':'))+'\n'+stream.getvalue()}],
        'tools':provider_schema([{'type':'function','function':definition}]),
        'tool_choice':{'type':'function','function':{'name':definition['name']}},
        'parallel_tool_calls':False, 'max_tokens':4096, 'temperature':0, 'stream':False,
        'chat_template_kwargs':{'enable_thinking':False}}


def extract_answer(response):
    if response.get('finish_reason') == 'length':
        raise ValueError('Truncated response')
    calls = response['message'].get('tool_calls', [])
    if len(calls) != 1 or calls[0]['function']['name'] != 'assess_cycle_evidence':
        raise ValueError('Expected exactly one assess_cycle_evidence function call')
    return json.loads(calls[0]['function']['arguments'])


def fetch(db, ordinals):
    result = {}
    values = list(dict.fromkeys(ordinals))
    for offset in range(0, len(values), 400):
        batch = values[offset:offset+400]
        query = 'SELECT * FROM transactions WHERE row_id IN ('+','.join('?' for _ in batch)+')'
        result.update((r['row_id'], row(r)) for r in db.execute(query,batch))
    return [result[i] for i in values if i in result]


def labels_for(db, rows):
    result = {}
    ids = [int(r['transaction_id'][1:]) for r in rows]
    for offset in range(0,len(ids),400):
        batch = ids[offset:offset+400]
        query = 'SELECT row_id,is_laundering FROM labels WHERE row_id IN ('+','.join('?' for _ in batch)+')'
        result.update(('T'+str(r[0]),r[1]) for r in db.execute(query,batch))
    if len(result) != len(rows):
        raise ValueError('Incomplete evaluator labels')
    return result


def prepare():
    if ROOT.exists():
        raise ValueError('Frozen experiment already exists')
    ROOT.mkdir(parents=True)
    (ROOT/'runtime').mkdir()
    (ROOT/'evaluator').mkdir()
    (ROOT/'calls').mkdir()
    from context_tokens import ContextTokens, TOKENIZER_REVISION
    counter = ContextTokens()
    db = readonly(HERE/'generated/transactions.sqlite')
    labels = readonly(HERE/'generated/evaluator.sqlite')
    sha = db.execute("SELECT value FROM metadata WHERE key='source_sha256'").fetchone()[0]
    catalogue = json.loads((HERE/'generated/cycle-family-v2/evaluator/catalogue.json').read_text())['groups']
    groups = {g['group_id']:g for g in catalogue}
    clusters = short_account_clusters(catalogue)
    if len({clusters[i] for i in GROUPS.values()}) != len(GROUPS):
        raise ValueError('Reference cases share an episode account cluster')
    maximum = db.execute('SELECT max(row_id) FROM transactions').fetchone()[0]
    background = fetch(db, random.Random(202610241).sample(range(1,maximum+1),16000))
    background = [r for r in background if SCOPE[0] <= r['timestamp'] < SCOPE[1]]
    cases = {}
    for name, group_id in GROUPS.items():
        group = groups[group_id]
        if not group.get('eligible_short'):
            raise ValueError('Ineligible reference')
        core = fetch(db, group['temporal_row_ids'])
        start = (datetime.strptime(core[0]['timestamp'],'%Y/%m/%d %H:%M')-timedelta(hours=24)).strftime('%Y/%m/%d %H:%M')
        end = (datetime.strptime(core[-1]['timestamp'],'%Y/%m/%d %H:%M')+timedelta(hours=24)).strftime('%Y/%m/%d %H:%M')
        context = {}
        for bank,account in group['accounts']:
            for side in ('source','destination'):
                query = f'''SELECT * FROM transactions WHERE {side}_bank=? AND {side}_account=?
                    AND timestamp>=? AND timestamp<=? ORDER BY timestamp,row_id LIMIT 2000'''
                for raw in db.execute(query,(bank,account,start,end)):
                    if SCOPE[0] <= raw['timestamp'] < SCOPE[1]:
                        context[raw['row_id']] = row(raw)
        core_ids = {r['transaction_id'] for r in core}
        context_rows = ordered([r for r in context.values() if r['transaction_id'] not in core_ids])
        other_clusters = {clusters[other] for other in GROUPS.values() if other != group_id}
        excluded = {tuple(account) for other,g in groups.items() if clusters.get(other) in other_clusters
                    for account in g['accounts']}
        allowed_background = [r for r in context_rows+background if all(
            (r[side+'_bank'],r[side+'_account']) not in excluded for side in ('source','destination'))]
        pool = list({r['transaction_id']:r for r in core+allowed_background}.values())[:6000]
        cases[name] = {'rows':pool, 'targets':[[r['transaction_id'] for r in core]],
            'group_id':group_id, 'kind':'seeded_positive', 'core_rows':len(core),
            'incident_rows_available':len(context_rows), 'context_selection':'up to2000 per account/direction within24h padding'}
    # An ordinary labelled-zero cycle tests structure without conflating its label.
    baseline = readonly(HERE/'generated/cycle-family-v2/baseline/ledger.sqlite')
    zero_core = None
    for item in baseline.execute('SELECT path FROM candidates ORDER BY id'):
        core = fetch(db,[int(i.rsplit(':',1)[1]) for i in json.loads(item[0])])
        if not any(labels_for(labels,core).values()):
            zero_core = core
            break
    baseline.close()
    if not zero_core:
        raise ValueError('No zero-labelled cycle control')
    cases['control-cycle'] = {'rows':list({r['transaction_id']:r for r in zero_core+background}.values())[:6000],
        'targets':[], 'kind':'zero_label_cycle', 'control_support':[r['transaction_id'] for r in zero_core]}
    # A globally increasing source/destination ordering rules out every directed cycle.
    acyclic = [r for r in background if (r['source_bank'],r['source_account']) < (r['destination_bank'],r['destination_account'])][:6000]
    if len(acyclic)<1500:
        raise ValueError('Insufficient acyclic control rows')
    cases['control-acyclic'] = {'rows':acyclic,'targets':[],'kind':'constructed_acyclic'}
    natural = [row(r) for r in db.execute('''SELECT * FROM transactions WHERE row_id>=2000000
        AND timestamp>=? AND timestamp<? ORDER BY row_id LIMIT 6000''',SCOPE)]
    cases['control-natural'] = {'rows':natural,'targets':[],'kind':'label_blind_ordinal_window'}
    jobs = []

    def add(name, condition, selected, repeats=1, **extra):
        for repetition in range(repeats):
            ident = f'{name}--{condition}--r{repetition+1}'
            jobs.append({'id':ident,'case':name,'condition':condition,'repetition':repetition+1,
                         'row_ids':[r['transaction_id'] for r in selected],**extra})

    dev_names = [name for name in cases if not name.startswith('holdout')]
    grouping = {}
    for name in dev_names:
        pool = cases[name]['rows']
        base = ordered(pool[:1500])
        add(name,'single-1500',base,2)
        if name.startswith('dev-'):
            for size in (300,750):
                add(name,f'single-{size}',ordered(pool[:size]),2)
            for count in (2,3,4):
                partition = partition_views(base,count,strategy='graph')
                grouping[f'{name}-graph-{count}'] = partition
                lookup = {r['transaction_id']:r for r in base}
                for part,ids in enumerate(partition['views']):
                    add(name,f'graph-{count}',[lookup[i] for i in ids],group_part=part,group_count=count)
                    jobs[-1]['id'] += f'-p{part}'
            partition = partition_views(base,3,strategy='chronological')
            grouping[f'{name}-chronological-3'] = partition
            lookup = {r['transaction_id']:r for r in base}
            for part,ids in enumerate(partition['views']):
                add(name,'chronological-3',[lookup[i] for i in ids],group_part=part,group_count=3)
                jobs[-1]['id'] += f'-p{part}'
            for token_target in (150000,190000):
                low,high = 1,len(pool)
                while low<high:
                    middle = (low+high+1)//2
                    count = counter.count_request(request_for(ordered(pool[:middle]),sha))
                    if count <= token_target:
                        low = middle
                    else:
                        high = middle-1
                add(name,f'input-{token_target}',ordered(pool[:low]))
    for name,case in cases.items():
        save(ROOT/'runtime'/f'{name}.json',case['rows'])
        evaluator = {k:v for k,v in case.items() if k!='rows'}
        evaluator['labels'] = labels_for(labels,case['rows'])
        evaluator['base_oracle'] = oracle_cycles(ordered(case['rows'][:1500]))
        save(ROOT/'evaluator'/f'{name}.json',evaluator)
    overlap_audit = []
    for left in cases:
        for right in cases:
            if left >= right:
                continue
            def accounts(selected):
                return {(r[s+'_bank'],r[s+'_account']) for r in selected for s in ('source','destination')}
            a,b = cases[left]['rows'][:1500],cases[right]['rows'][:1500]
            overlap_audit.append({'left':left,'right':right,
                'shared_rows':len({r['transaction_id'] for r in a}&{r['transaction_id'] for r in b}),
                'shared_accounts':len(accounts(a)&accounts(b))})
    save(ROOT/'evaluator/case-overlap.json',{'reference_clusters':{name:clusters[gid] for name,gid in GROUPS.items()},
                                         'base_packet_overlap':overlap_audit})
    save(ROOT/'grouping.json',grouping)
    save(ROOT/'jobs.json',jobs)
    sources = {name:digest(HERE/name) for name in SOURCE_FILES}
    sources['context_tokens.py'] = digest(RESEARCH/'context_tokens.py')
    sources['PROTOCOL.md'] = digest(RESEARCH/'PROTOCOL.md')
    sources.update({str(p.relative_to(RESEARCH)):digest(p) for p in (RESEARCH/'tokenizer').iterdir() if p.is_file()})
    inputs = {str(p.relative_to(ROOT)):digest(p) for directory in ('runtime','evaluator') for p in (ROOT/directory).glob('*.json')}
    inputs.update({name:digest(ROOT/name) for name in ('jobs.json','grouping.json')})
    save(ROOT/'manifest.json',{'source_sha256':sha,'model':MODEL,'endpoint':ENDPOINT,'sources':sources,
        'inputs':inputs,'tokenizer_revision':TOKENIZER_REVISION,'group_ids':GROUPS,
        'max_calls':120,'max_tokens':10000000,'context_cap':200000,'output_reserve':4096,'safety_tokens':4096,
        'initial_jobs':len(jobs),'selection':'Label-informed constructed development stresscases; not population precision/recall.',
        'repetitions':'Identical independent fresh requests, temperature0; not independent source cases.',
        'holdout':'Untouched episodes selected before outcomes; same source population, not external validation.'})
    frozen = ROOT/'frozen-source'
    frozen.mkdir()
    for name in SOURCE_FILES:
        (frozen/name).write_bytes((HERE/name).read_bytes())
    (frozen/'context_tokens.py').write_bytes((RESEARCH/'context_tokens.py').read_bytes())
    (frozen/'PROTOCOL.md').write_bytes((RESEARCH/'PROTOCOL.md').read_bytes())
    (frozen/'tokenizer').mkdir()
    for path in (RESEARCH/'tokenizer').iterdir():
        if path.is_file():
            (frozen/'tokenizer'/path.name).write_bytes(path.read_bytes())
    db.close(); labels.close()
    print(json.dumps({'initial_jobs':len(jobs),'cases':list(cases),'manifest':str(ROOT/'manifest.json')}))


def verify_manifest():
    manifest = json.loads((ROOT/'manifest.json').read_text())
    for name,sha in manifest['sources'].items():
        parent = RESEARCH if name in ('context_tokens.py','PROTOCOL.md') or name.startswith('tokenizer/') else HERE
        if digest(parent/name) != sha:
            raise ValueError('Frozen implementation changed: '+name)
    for name,sha in manifest['inputs'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Frozen input changed: '+name)
    return manifest


class Runner:
    def __init__(self):
        from context_tokens import ContextTokens
        self.manifest = verify_manifest()
        self.counter = ContextTokens()
        self.model = Model()
        self.lock = threading.Lock()
        self.records = json.loads((ROOT/'attempts.json').read_text()) if (ROOT/'attempts.json').exists() else []

    def execute(self,job):
        directory = ROOT/'calls'/job['id']
        if directory.exists():
            return {'id':job['id'],'status':'existing_attempt_preserved'}
        pool = json.loads((ROOT/'runtime'/f"{job['case']}.json").read_text())
        lookup = {r['transaction_id']:r for r in pool}
        rows = [lookup[i] for i in job['row_ids']]
        request = request_for(rows,self.manifest['source_sha256'])
        with self.lock:
            admission = self.counter.admission(request,context_cap=self.manifest['context_cap'],
                                               safety_tokens=self.manifest['safety_tokens'])
            if not admission['admitted']:
                directory.mkdir()
                result = {'id':job['id'],'case':job['case'],'condition':job['condition'],
                    'status':'ineligible','reason':'Local context admission failed','rows':len(rows),**admission}
                save(directory/'job.json',job);save(directory/'request.json',request);save(directory/'result.json',result)
                return result
            def charged_tokens(record):
                total = (record.get('usage') or {}).get('total_tokens')
                return total if type(total) is int and total >= 0 else record['reserved_total']
            charged = sum(charged_tokens(r) for r in self.records)
            if len(self.records)>=self.manifest['max_calls'] or charged+admission['reserved_total']>self.manifest['max_tokens']:
                raise ValueError('Cumulative experiment budget exhausted')
            directory.mkdir()
            save(directory/'request.json',request)
            save(directory/'job.json',job)
            record = {'id':job['id'],'status':'admitted','usage':None,**admission}
            self.records.append(record)
            save(ROOT/'attempts.json',self.records)
        result = {'id':job['id'],'case':job['case'],'condition':job['condition'],
                  'rows':len(rows),'local_prompt_tokens':admission['local_prompt_tokens']}
        started = time.monotonic()
        try:
            response = self.model.complete(request['messages'],request['tools'],request['tool_choice'],request['max_tokens'])
            save(directory/'response.json',response)
            result.update(status='received',usage=response.get('usage'),seconds=response.get('seconds'))
            try:
                answer = extract_answer(response)
                evaluator = json.loads((ROOT/'evaluator'/f"{job['case']}.json").read_text())
                result['score'] = score_answer(rows,answer,evaluator['targets'],evaluator['labels'])
                save(directory/'answer.json',answer)
            except (ValueError,KeyError,TypeError) as error:
                result.update(status='invalid_response',error=str(error))
        except Exception as error:
            result.update(status='provider_error',error=type(error).__name__,seconds=time.monotonic()-started)
            if getattr(error,'status',None):
                result['http_status'] = error.status
            result['usage'] = None
        with self.lock:
            record.update({key:result[key] for key in ('status','usage','seconds','http_status','error') if key in result})
            save(directory/'result.json',result)
            save(ROOT/'attempts.json',self.records)
        print(json.dumps(result if 'score' not in result else {k:v for k,v in result.items() if k!='score'}),flush=True)
        return result


def read_result(job):
    path = ROOT/'calls'/job['id']/'result.json'
    return json.loads(path.read_text()) if path.exists() else None


def followup_jobs():
    """Freeze follow-up choices once from development results, never holdout answers."""
    if (ROOT/'followup-jobs.json').exists():
        return json.loads((ROOT/'followup-jobs.json').read_text())
    jobs = json.loads((ROOT/'jobs.json').read_text())
    scores = {}
    for count in (2,3,4):
        recovered,structural,invalid,tokens = 0,0,0,0
        for name in ('dev-2','dev-3','dev-4'):
            records = [read_result(j) for j in jobs if j['case']==name and j['condition']==f'graph-{count}']
            found = {tuple(p) for r in records if r for p in r.get('score',{}).get('accepted_cycles',[])}
            evaluator = json.loads((ROOT/'evaluator'/f'{name}.json').read_text())
            targets = evaluator['targets']
            recovered += sum(tuple(p) in found for p in targets)
            oracle = {tuple(p) for p in evaluator['base_oracle']}
            structural += len(found&oracle)/len(oracle) if oracle else 1
            invalid += sum(not r or r.get('status')!='received' or not r.get('score',{}).get('response_valid') for r in records)
            for record in records:
                if record:
                    reported=(record.get('usage') or {}).get('total_tokens')
                    tokens += reported if type(reported) is int and reported>=0 else record.get('local_prompt_tokens',200000)+8192
        scores[count] = {'recovered':recovered,'structural_recall_sum':structural,'invalid_or_unavailable':invalid,'tokens':tokens}
    best = min(scores,key=lambda n:(-scores[n]['recovered'],-scores[n]['structural_recall_sum'],
                                   scores[n]['invalid_or_unavailable'],scores[n]['tokens'],n))
    following=[]; scenarios={}
    for name in ('dev-2','dev-3','dev-4'):
        pool=json.loads((ROOT/'runtime'/f'{name}.json').read_text())
        base=ordered(pool[:1500]); lookup={r['transaction_id']:r for r in pool}
        initial=read_result(next(j for j in jobs if j['case']==name and j['condition']=='single-1500' and j['repetition']==1))
        accepted={tuple(p) for p in (initial or {}).get('score',{}).get('accepted_cycles',[])}
        answer_path=ROOT/'calls'/initial['id']/'answer.json' if initial else None
        saved_answer=json.loads(answer_path.read_text()) if accepted and answer_path and answer_path.exists() else {}
        observations=saved_answer.get('observations',[]) if isinstance(saved_answer,dict) else []
        candidates=[o['transaction_ids'] for o in observations if isinstance(o,dict) and
                    isinstance(o.get('transaction_ids'),list) and
                    all(isinstance(i,str) for i in o['transaction_ids']) and tuple(o['transaction_ids']) in accepted] if isinstance(observations,list) else []
        if candidates:
            retained=candidates[0]; anchor=retained[0]; origin='first_model_detected_verified_cycle'
        else:
            degree=Counter((r['source_bank'],r['source_account']) for r in base)
            anchor=min(base,key=lambda r:(-degree[(r['source_bank'],r['source_account'])],r['transaction_id']))['transaction_id']
            retained=[anchor]; origin='label_blind_source_degree_fallback'
        for fraction in (0,.25,.5,.75):
            scenario=overlap_views(pool,anchor,1500,fraction,first_view_ids=[r['transaction_id'] for r in base])
            key=f'{name}--overlap-{int(fraction*100)}'
            scenarios[key]={**scenario,'anchor_origin':origin,'source_response_id':initial['id'] if initial else None}
            following.append({'id':key+'--r1','case':name,'condition':f'overlap-{int(fraction*100)}',
                              'repetition':1,'row_ids':scenario['views'][1]})
        key=f'{name}--overlap-boundary'
        if candidates:
            scenario=overlap_views(pool,anchor,1500,0,retained_ids=retained,first_view_ids=[r['transaction_id'] for r in base])
            scenarios[key]={**scenario,'anchor_origin':origin}
            following.append({'id':key+'--r1','case':name,'condition':'overlap-boundary','repetition':1,'row_ids':scenario['views'][1]})
        else:
            scenarios[key]={'status':'unavailable','reason':'No valid model-discovered path in initial response','anchor_origin':origin}
    for name in ('holdout-2','holdout-3','holdout-4'):
        base=ordered(json.loads((ROOT/'runtime'/f'{name}.json').read_text())[:1500])
        partition=partition_views(base,best,strategy='graph')
        scenarios[name+'-grouping']=partition
        for repetition in (1,2):
            following.append({'id':f'{name}--single-1500--r{repetition}','case':name,'condition':'single-1500',
                              'repetition':repetition,'row_ids':[r['transaction_id'] for r in base]})
            for part,ids in enumerate(partition['views']):
                following.append({'id':f'{name}--graph-{best}--r{repetition}-p{part}','case':name,
                    'condition':f'graph-{best}','repetition':repetition,'group_part':part,'group_count':best,'row_ids':ids})
    save(ROOT/'followup-selection.json',{'graph_scores':scores,'selected_group_count':best,
          'selection':'Max development complete-episode recovery, then structural recall, then fewer invalid/unavailable calls, then fewer reported tokens, then fewer groups.'})
    save(ROOT/'followup-scenarios.json',scenarios)
    save(ROOT/'followup-jobs.json',following)
    save(ROOT/'followup-hashes.json',{name:digest(ROOT/name) for name in ('followup-selection.json','followup-scenarios.json','followup-jobs.json')})
    return following


def run(stage,workers=2):
    with (ROOT/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        runner=Runner()
        jobs=json.loads((ROOT/'jobs.json').read_text())
        if stage=='probe':
            jobs=[next(j for j in jobs if j['case']=='dev-2' and j['condition']=='single-300' and j['repetition']==1)]
        elif stage=='followup':
            if any(read_result(j) is None for j in jobs):
                raise ValueError('Finish all initial attempts before selecting follow-ups')
            jobs=followup_jobs()
            for name,sha in json.loads((ROOT/'followup-hashes.json').read_text()).items():
                if digest(ROOT/name)!=sha:
                    raise ValueError('Frozen follow-up changed')
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures=[executor.submit(runner.execute,j) for j in jobs]
            for future in as_completed(futures):
                future.result()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','probe','initial','followup'])
    parser.add_argument('--workers',type=int,choices=[1,2],default=2)
    args=parser.parse_args()
    if args.command=='prepare':
        prepare()
    else:
        run(args.command,args.workers)
