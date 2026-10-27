"""Experimental batch retrieval with mandatory, byte-budgeted review checkpoints.

Uses a conservative UTF-8 byte allowance as a token upper-bound proxy, not a
model-specific tokenizer. No production-scale path-generation claim is made.
"""
import argparse
import json
from pathlib import Path
from global_agent import Agent,SYSTEM,compact
from global_scan import Scan
from tools import HERE
from verified_paths import build_paths

COLUMNS=['id','timestamp','source_bank','source_account','destination_bank','destination_account','paid_amount','paid_currency','received_amount','received_currency','payment_format']


def review_definition(paths):
    return {'name':'review_evidence','description':'Assess verified paths using economic observations, not connectivity alone.',
        'parameters':{'type':'object','properties':{
            'decisions':{'type':'array',**({'minItems':len(paths),'maxItems':len(paths)} if paths else {}),'items':{'type':'object','properties':{
                'id':{'type':'string','enum':[p['id'] for p in paths] or ['NONE']},
                'status':{'type':'string','enum':['investigate','insufficient_evidence','not_supported']},
                'reason':{'type':'string','maxLength':300}},'required':['id','status','reason'],'additionalProperties':False}},
            'limitations':{'type':'array','maxItems':3,'items':{'type':'string','maxLength':200}}},
            'required':['decisions','limitations'],'additionalProperties':False}}


class BatchAgent(Agent):
    def __init__(self,directory,database=HERE/'generated/transactions.sqlite',model=None,seed=None,row_ceiling=150,
                 context_budget=24000,burst_rows=1500,burst_pages=100,max_calls=40,min_interval=2):
        directory=Path(directory)
        if not (directory/'ledger.sqlite').exists():
            scan=Scan(directory/'ledger.sqlite',database,page_rows=250,seed=seed);scan.close()
        super().__init__(directory,database,model=model,min_interval=min_interval,
                         limits={'max_calls':max_calls,'max_tokens':500000,'request_bytes':context_budget})
        self.db.executescript('''CREATE TABLE IF NOT EXISTS batch_jobs(id INTEGER PRIMARY KEY,choice TEXT,packets TEXT,status TEXT);
            CREATE TABLE IF NOT EXISTS batch_receipts(job_id INTEGER,packet INTEGER,call_id INTEGER UNIQUE,answer TEXT,PRIMARY KEY(job_id,packet));
            CREATE TABLE IF NOT EXISTS batch_reviewed_rows(row_id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS batch_reviewed_paths(id TEXT PRIMARY KEY);''')
        if self.scan.get('batch') is None:
            if row_ceiling<6 or context_budget<6000 or burst_rows<1 or burst_pages<1:raise ValueError('Invalid batch settings')
            with self.db:
                self.scan.put('batch',{'phase':'choose','job':None,'completed':0})
                self.scan.put('batch_config',{'row_ceiling':row_ceiling,'context_budget':context_budget,'burst_rows':burst_rows,'burst_pages':burst_pages})
        self.batch=self.scan.get('batch');self.config=self.scan.get('batch_config')
        self.db.execute('CREATE TABLE IF NOT EXISTS batch_recovery(id INTEGER PRIMARY KEY,phase TEXT,call_id INTEGER,error TEXT,delay REAL)');self.db.commit()

    def recovery_hint(self):
        cached=self.db.execute("SELECT request FROM agent_calls WHERE status='received' ORDER BY id LIMIT 1").fetchone()
        if cached:return json.loads(json.loads(cached[0])['messages'][-1]['content']).get('recovery_hint')
        return self.state['error_hint']

    def request_size(self,payload,definition):
        request={'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(payload)}],
                 'tools':[{'type':'function','function':definition}],
                 'tool_choice':{'type':'function','function':{'name':definition['name']}},'max_tokens':2400}
        return len(json.dumps(request).encode())+2400+2048

    def review_payload(self,ids,paths):
        p=self.payload(ids)
        p.update(columns=COLUMNS,verified_paths=paths,recovery_hint=self.recovery_hint(),instruction='Return compact JSON without whitespace padding. If verified_paths is empty return decisions=[]. Otherwise assess each path ID exactly once. Look for economically relevant patterns: rapid onward movement, amount/currency compatibility, convergence, and cycles. Connectivity alone is insufficient. Cite supplied row IDs in reasons; distinguish observations from hypotheses. Account identity is source/destination bank plus account. No-path rows have been presented but are not thereby benign. Ground-truth labels are withheld.')
        return p

    def choose(self):
        if not self.scan.frontier():
            with self.db:self.scan.next_component()
        frontier=self.scan.frontier()
        if not frontier:
            self.state['status']='complete';return
        definition={'name':'choose_directions','description':'Choose a retrieval strategy; code will paginate and deduplicate.',
            'parameters':{'type':'object','properties':{'scope_ids':{'type':'array','maxItems':4,'uniqueItems':True,'items':{'type':'integer','enum':[s['id']for s in frontier]}},
                'reason':{'type':'string','maxLength':240}},'required':['scope_ids','reason'],'additionalProperties':False}}
        previous=self.db.execute('SELECT answer FROM batch_receipts ORDER BY job_id DESC,packet DESC LIMIT 1').fetchone()
        payload={'source_sha256':self.scan.get('source_sha256'),'scope':[self.scan.start,self.scan.end],
            'frontier':frontier,'discovered_rows':self.scan.get('rows'),'previous_review':json.loads(previous[0]) if previous else None,
            'recovery_hint':self.recovery_hint(),
            'instruction':'Systematic with scope_ids=[] follows all pending scopes, including newly discovered branches. Selected requires1..4 advertised scopes and exhausts only those. Code pauses at a checkpoint for mandatory review. No raw-row pagination decisions are needed.'}
        call,choice=self.call('batch-navigator',payload,definition,None if self.config.get('continuous') else 600)
        choice['mode']='selected' if choice['scope_ids'] else 'systematic'
        with self.db:
            job=self.db.execute("INSERT INTO batch_jobs(choice,status) VALUES(?,'retrieving')",(json.dumps(choice),)).lastrowid
            self.db.execute("UPDATE agent_calls SET status='applied' WHERE id=?",(call,))
            self.batch.update(phase='retrieve',job=job);self.scan.put('batch',self.batch)

    def retrieve(self):
        choice=json.loads(self.db.execute('SELECT choice FROM batch_jobs WHERE id=?',(self.batch['job'],)).fetchone()[0])
        start=self.scan.get('rows')
        # Pages, discovery, cursors and phase transition commit together.
        with self.db:
            for _ in range(self.config['burst_pages']):
                frontier=self.scan.frontier()
                scopes=[s for s in frontier if choice['mode']=='systematic' or s['id']in choice['scope_ids']]
                if not scopes:break
                self.scan._step(scopes[0]['id'])
                if self.scan.get('rows')-start>=self.config['burst_rows']:break
            self.batch['phase']='prepare';self.scan.put('batch',self.batch)

    def prepare(self):
        # All collected evidence participates; this deliberately bounded prototype
        # does not claim this in-memory candidate builder scales to five million rows.
        ids=['T'+str(r[0])for r in self.db.execute('SELECT row_id FROM seen ORDER BY row_id')]
        evidence=dict(zip(ids,self.rows(ids)));paths,coverage=build_paths(evidence)
        reviewed={r[0]for r in self.db.execute('SELECT id FROM batch_reviewed_paths')}
        paths=[p for p in paths if p['id'] not in reviewed]
        units=[]
        for path in paths:
            check=self.tools.verify_path([evidence[i]['transaction_id']for i in path['ids']],strict=True,cycle=path['cycle'])
            if not check['valid']:raise ValueError('Candidate failed source verification')
            units.append((path['ids'],[path]))
        covered={i for rows,_ in units for i in rows}
        old={r[0]for r in self.db.execute('SELECT row_id FROM batch_reviewed_rows')}
        units.extend(([i],[])for i in ids if i not in covered and int(i[1:])not in old)
        packets=[];view=[];candidates=[]
        for rows,additional in units:
            merged=list(dict.fromkeys(view+rows));proposed=candidates+additional
            if len(merged)>self.config['row_ceiling'] or len(proposed)>6 or self.request_size(self.review_payload(merged,proposed),review_definition(proposed))>self.config['context_budget']:
                if view:packets.append({'ids':view,'paths':candidates})
                merged=list(rows);proposed=additional
            if len(merged)>self.config['row_ceiling'] or self.request_size(self.review_payload(merged,proposed),review_definition(proposed))>self.config['context_budget']:
                raise ValueError('One complete evidence unit cannot fit the context budget; no truncation applied')
            view,candidates=merged,proposed
        if view:packets.append({'ids':view,'paths':candidates})
        with self.db:
            self.db.execute("UPDATE batch_jobs SET packets=?,status='reviewing' WHERE id=?",(json.dumps(packets),self.batch['job']))
            self.batch['phase']='review';self.scan.put('batch',self.batch)

    def review_batch(self):
        job=self.batch['job'];packets=json.loads(self.db.execute('SELECT packets FROM batch_jobs WHERE id=?',(job,)).fetchone()[0])
        done=self.db.execute('SELECT count(*) FROM batch_receipts WHERE job_id=?',(job,)).fetchone()[0]
        if done==len(packets):
            with self.db:
                self.db.execute("UPDATE batch_jobs SET status='complete' WHERE id=?",(job,))
                self.batch.update(phase='choose',job=None,completed=self.batch['completed']+1);self.scan.put('batch',self.batch)
            return
        packet=packets[done];paths=packet['paths']
        call,answer=self.call('batch-reviewer',self.review_payload(packet['ids'],paths),review_definition(paths),None if self.config.get('continuous') else 2400)
        if {d['id']for d in answer['decisions']}!={p['id']for p in paths}:
            self.reject(call,'Path decision IDs differ');raise ValueError('Path decision IDs differ')
        with self.db:
            self.db.execute('INSERT INTO batch_receipts VALUES(?,?,?,?)',(job,done,call,json.dumps(answer)))
            self.db.executemany('INSERT OR IGNORE INTO batch_reviewed_rows VALUES(?)',[(int(i[1:]),)for i in packet['ids']])
            self.db.executemany('INSERT OR IGNORE INTO batch_reviewed_paths VALUES(?)',[(p['id'],)for p in paths])
            self.db.execute("UPDATE agent_calls SET status='applied' WHERE id=?",(call,))

    def enable_continuous(self):
        self.enable_full_run()
        with self.db:
            self.config['continuous']=True
            self.scan.put('batch_config',self.config)

    def split_pending_review(self):
        if self.batch['phase']!='review':return False
        job=self.batch['job']
        packets=json.loads(self.db.execute('SELECT packets FROM batch_jobs WHERE id=?',(job,)).fetchone()[0])
        index=self.db.execute('SELECT count(*) FROM batch_receipts WHERE job_id=?',(job,)).fetchone()[0]
        packet=packets[index]
        paths=packet['paths'];covered={i for path in paths for i in path['ids']}
        units=[{'ids':path['ids'],'paths':[path]}for path in paths]
        units.extend({'ids':[i],'paths':[]}for i in packet['ids'] if i not in covered)
        if len(units)<2:return False
        middle=len(units)//2
        replacements=[{'ids':list(dict.fromkeys(i for u in group for i in u['ids'])),
                       'paths':[p for u in group for p in u['paths']]}for group in (units[:middle],units[middle:])]
        packets[index:index+1]=replacements
        with self.db:self.db.execute('UPDATE batch_jobs SET packets=? WHERE id=?',(json.dumps(packets),job))
        return True

    def wait_retry(self,delay):
        import time
        time.sleep(delay)

    def run_batches(self,count=1):
        import time
        continuous=self.config.get('continuous',False)
        if self.state['cooldown_until']>time.time():
            if not continuous:return self.batch_report()
            self.wait_retry(self.state['cooldown_until']-time.time())
        if count is not None and (type(count)is not int or count<1):raise ValueError('Checkpoint count must be positive or None')
        target=None if count is None else self.batch['completed']+count
        self.state['status']='active';failures=0
        while (target is None or self.batch['completed']<target) and self.state['status']=='active':
            previous_call=self.db.execute('SELECT coalesce(max(id),0) FROM agent_calls').fetchone()[0]
            try:
                {'choose':self.choose,'retrieve':self.retrieve,'prepare':self.prepare,'review':self.review_batch}[self.batch['phase']]()
                self.state['error_hint']=None;failures=0
                with self.db:self.persist()
            except Exception as exc:
                self.state=self.scan.get('agent');self.batch=self.scan.get('batch')
                latest=self.db.execute('SELECT id,status FROM agent_calls ORDER BY id DESC LIMIT 1').fetchone()
                rejected=latest and latest['id']>previous_call and latest['status']=='rejected'
                status=getattr(exc,'status',None)
                transient=self.state['status']=='waiting_for_provider' and (status is None or status in (408,429) or status>=500)
                if continuous and (rejected or transient):
                    failures+=1
                    if rejected and failures>=2:self.split_pending_review()
                    delay=max(min(300,2**min(failures,8)),self.state['cooldown_until']-time.time(),getattr(exc,'retry_after',None) or 0)
                    self.state.update(status='retrying',error_hint=str(exc)[:300],cooldown_until=time.time()+delay)
                    with self.db:
                        self.db.execute('INSERT INTO batch_recovery(phase,call_id,error,delay) VALUES(?,?,?,?)',(self.batch['phase'],latest['id'],str(exc)[:300],delay))
                        self.persist()
                    print(json.dumps({'event':'automatic_retry','phase':self.batch['phase'],'error':str(exc)[:300],'delay_seconds':round(delay,1)}),flush=True)
                    self.wait_retry(delay)
                    self.state.update(status='active',cooldown_until=0)
                    with self.db:self.persist()
                    continue
                if self.state['status']!='waiting_for_provider':self.state['status']='paused_error'
                self.state['error_hint']=str(exc)[:300]
                break
        if self.state['status']=='active':self.state['status']='paused_checkpoint'
        with self.db:self.persist()
        result=self.batch_report();(self.directory/'batch-result.json').write_text(json.dumps(result,indent=2)+'\n');return result

    def batch_report(self):
        return {'status':self.state['status'],'error':self.state['error_hint'],'batch':self.batch,'config':self.config,
            'rows':self.scan.get('rows'),'pages':self.scan.get('pages'),'usage':self.usage(),'full_run':bool(self.limits.get('full_run')),
            'rows_presented_for_review':self.db.execute('SELECT count(*) FROM batch_reviewed_rows').fetchone()[0],
            'paths_assessed':self.db.execute('SELECT count(*) FROM batch_reviewed_paths').fetchone()[0],
            'calls_by_role':[dict(r)for r in self.db.execute('SELECT role,count(*) AS calls FROM agent_calls GROUP BY role')]}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--database',type=Path,default=HERE/'generated/transactions.sqlite');p.add_argument('--seed',type=int,default=100003);p.add_argument('--rows',type=int,default=150);p.add_argument('--burst-pages',type=int,default=100);p.add_argument('--batches',type=int,default=1);p.add_argument('--continuous',action='store_true',help='Full traversal with automatic transient/invalid-response recovery and provider-default output length');p.add_argument('--full',action='store_true',help='Continue to source exhaustion without total checkpoint/call/token caps; preserve context limits and failure pauses');a=p.parse_args()
    agent=BatchAgent(a.directory,a.database,seed=a.seed,row_ceiling=a.rows,burst_pages=a.burst_pages)
    try:
        if a.full:agent.enable_full_run()
        if a.continuous:agent.enable_continuous()
        print(json.dumps(agent.run_batches(None if a.full or a.continuous else a.batches),indent=2))
    finally:agent.close()
