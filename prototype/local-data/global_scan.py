"""Persistent whole-source traversal prototype. No model or evaluator labels are used."""
import argparse
from datetime import datetime, timedelta
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3
import time

HERE=Path(__file__).resolve().parent

def digest(ids):
    return hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()

class Scan:
    def __init__(self,ledger,database=HERE/'generated/transactions.sqlite',start=None,end=None,page_rows=25,seed=None):
        self.path=Path(ledger);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=self.path.with_suffix('.lock').open('a')
        try:
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self._initialize(database,start,end,page_rows,seed)
        except Exception:
            if hasattr(self,'db'):self.db.close()
            self.lock.close()
            raise

    def _initialize(self,database,start,end,page_rows,seed):
        self.database=Path(database).resolve()
        self.db=sqlite3.connect(self.path,uri=True);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('ATTACH DATABASE ? AS source',(self.database.as_uri()+'?mode=ro',))
        sha=self.db.execute("SELECT value FROM source.metadata WHERE key='source_sha256'").fetchone()[0]
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS components(id INTEGER PRIMARY KEY,seed INTEGER NOT NULL,status TEXT NOT NULL,revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS seen(row_id INTEGER PRIMARY KEY,component_id INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS seen_component ON seen(component_id,row_id);
            CREATE TABLE IF NOT EXISTS scopes(id INTEGER PRIMARY KEY,bank TEXT NOT NULL,account TEXT NOT NULL,direction TEXT NOT NULL,
                component_id INTEGER NOT NULL,after_time TEXT,after_id INTEGER,status TEXT NOT NULL,pages INTEGER NOT NULL DEFAULT 0,
                UNIQUE(bank,account,direction));
            CREATE INDEX IF NOT EXISTS scope_pending ON scopes(status,id);
            CREATE TABLE IF NOT EXISTS pages(id INTEGER PRIMARY KEY,scope_id INTEGER NOT NULL,before_time TEXT,before_id INTEGER,
                after_time TEXT,after_id INTEGER,returned_count INTEGER NOT NULL,digest TEXT NOT NULL,complete INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS pages_scope ON pages(scope_id,id);
            CREATE TABLE IF NOT EXISTS review_jobs(id TEXT PRIMARY KEY,component_id INTEGER NOT NULL,revision INTEGER NOT NULL,
                status TEXT NOT NULL,receipt TEXT);
            CREATE TABLE IF NOT EXISTS review_bindings(job_id TEXT PRIMARY KEY,case_directory TEXT,evidence_fingerprint TEXT,call_count INTEGER,call_prefix TEXT);
            CREATE TABLE IF NOT EXISTS review_rows(job_id TEXT NOT NULL,row_id INTEGER NOT NULL,PRIMARY KEY(job_id,row_id));
            CREATE INDEX IF NOT EXISTS review_rows_row ON review_rows(row_id,job_id);
        ''')
        if self.get('source_sha256') is None:
            minimum,maximum=self.db.execute('SELECT min(timestamp),max(timestamp) FROM source.transactions').fetchone()
            start=start or minimum
            end=end or (datetime.strptime(maximum,'%Y/%m/%d %H:%M')+timedelta(minutes=1)).strftime('%Y/%m/%d %H:%M')
            if not start<end or not 1<=page_rows<=500:raise ValueError('Invalid scope or page size')
            with self.db:
                for key,value in {'source_sha256':sha,'start':start,'end':end,'page_rows':page_rows,'status':'active',
                    'seed_watermark':0,'initial_seed':seed,'pages':0,'rows':0,'returned_rows':0}.items():self.put(key,value)
        elif self.get('source_sha256')!=sha:
            raise ValueError('Source identity differs from saved scan')
        elif (start is not None and start!=self.get('start')) or (end is not None and end!=self.get('end')):
            raise ValueError('Scope differs from saved scan')
        self.start,self.end=self.get('start'),self.get('end')
        self.page_rows=self.get('page_rows')

    def get(self,key):
        row=self.db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None
    def put(self,key,value):self.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',(key,json.dumps(value)))

    def discover(self,rows,component):
        before=self.db.total_changes
        self.db.executemany('INSERT OR IGNORE INTO seen VALUES(?,?)',[(r['row_id'],component)for r in rows])
        new=self.db.total_changes-before
        if new:
            self.db.execute('UPDATE components SET revision=revision+1 WHERE id=?',(component,))
            self.put('rows',self.get('rows')+new)
        endpoints={(r[side+'_bank'],r[side+'_account'])for r in rows for side in ('source','destination')}
        self.db.executemany("INSERT OR IGNORE INTO scopes(bank,account,direction,component_id,status) VALUES(?,?,?,?,'pending')",
            [(bank,account,direction,component)for bank,account in sorted(endpoints) for direction in ('source','destination')])

    def next_component(self):
        active=self.db.execute("SELECT id FROM components WHERE status='active'").fetchone()
        if active:self.db.execute("UPDATE components SET status='complete' WHERE id=?",(active[0],))
        initial=self.get('initial_seed')
        if initial is not None:
            seed=self.db.execute('SELECT * FROM source.transactions WHERE row_id=? AND timestamp>=? AND timestamp<?',(initial,self.start,self.end)).fetchone()
            if seed is None:raise ValueError('Initial seed is outside the source scope')
            self.put('initial_seed',None)
        else:
            seed=self.db.execute('''SELECT t.* FROM source.transactions t LEFT JOIN seen s ON s.row_id=t.row_id
                WHERE t.row_id>? AND t.timestamp>=? AND t.timestamp<? AND s.row_id IS NULL ORDER BY t.row_id LIMIT 1''',
                (self.get('seed_watermark'),self.start,self.end)).fetchone()
            if seed is not None:self.put('seed_watermark',seed['row_id'])
        if seed is None:
            self.put('status','complete');return False
        component=self.db.execute("INSERT INTO components(seed,status,revision) VALUES(?,'active',0)",(seed['row_id'],)).lastrowid
        self.discover([seed],component)
        return True

    def frontier(self,limit=16):
        if not 1<=limit<=100:raise ValueError('Frontier limit must be 1..100')
        return [dict(r) for r in self.db.execute("SELECT * FROM scopes WHERE status='pending' ORDER BY id LIMIT ?",(limit,))]

    def _step(self,scope_id=None,limit=None):
        limit=self.page_rows if limit is None else limit
        if not 1<=limit<=self.page_rows:raise ValueError("Page limit exceeds configured allowance")
        if self.get('status')=='complete':return False
        if scope_id is not None:
            if scope_id not in {r['id']for r in self.frontier()}:raise ValueError('Choose an advertised pending scope')
            scope=self.db.execute('SELECT * FROM scopes WHERE id=?',(scope_id,)).fetchone()
        else:scope=self.db.execute("SELECT * FROM scopes WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
        if scope is None:
            if not self.next_component():return False
            scope=self.db.execute("SELECT * FROM scopes WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
        side=scope['direction']
        sql=f'SELECT * FROM source.transactions WHERE {side}_bank=? AND {side}_account=? AND timestamp>=? AND timestamp<?'
        args=[scope['bank'],scope['account'],self.start,self.end]
        if scope['after_time'] is not None:
            sql+=' AND (timestamp,row_id)>(?,?)';args.extend([scope['after_time'],scope['after_id']])
        rows=self.db.execute(sql+' ORDER BY timestamp,row_id LIMIT ?',args+[limit+1]).fetchall()
        complete=len(rows)<=limit;rows=rows[:limit]
        self.last_rows=rows
        self.discover(rows,scope['component_id'])
        after_time,after_id=(rows[-1]['timestamp'],rows[-1]['row_id']) if rows else (scope['after_time'],scope['after_id'])
        self.db.execute('UPDATE scopes SET after_time=?,after_id=?,status=?,pages=pages+1 WHERE id=?',
            (after_time,after_id,'complete' if complete else 'pending',scope['id']))
        self.db.execute('INSERT INTO pages(scope_id,before_time,before_id,after_time,after_id,returned_count,digest,complete) VALUES(?,?,?,?,?,?,?,?)',
            (scope['id'],scope['after_time'],scope['after_id'],after_time,after_id,len(rows),digest([r['row_id']for r in rows]),int(complete)))
        self.put('pages',self.get('pages')+1);self.put('returned_rows',self.get('returned_rows')+len(rows))
        return True

    def step(self,scope_id=None):
        with self.db:return self._step(scope_id)

    def run(self,max_pages=None,commit_pages=100):
        if max_pages is not None and max_pages<1:raise ValueError('Page budget must be positive')
        if not 1<=commit_pages<=10000:raise ValueError('Commit batch must be 1..10000 pages')
        used=0;last=time.monotonic()
        while self.get('status')!='complete' and (max_pages is None or used<max_pages):
            allowance=commit_pages if max_pages is None else min(commit_pages,max_pages-used)
            with self.db:
                for _ in range(allowance):
                    if not self._step():break
                    used+=1
            if time.monotonic()-last>=10:
                print(json.dumps(self.status()),flush=True);last=time.monotonic()
        return self.status()

    def status(self):
        result={k:self.get(k)for k in ('source_sha256','start','end','status','pages','rows','returned_rows')}
        result['components']={r[0]:r[1]for r in self.db.execute('SELECT status,count(*) FROM components GROUP BY status')}
        result['scopes']={r[0]:r[1]for r in self.db.execute('SELECT status,count(*) FROM scopes GROUP BY status')}
        result['current_review_jobs']={r[0]:r[1]for r in self.db.execute('SELECT j.status,count(*) FROM review_jobs j JOIN components c ON c.id=j.component_id AND c.revision=j.revision GROUP BY j.status')}
        result['reviewed_rows_in_current_context']=self.db.execute("SELECT count(DISTINCT r.row_id) FROM review_rows r JOIN review_jobs j ON j.id=r.job_id JOIN components c ON c.id=j.component_id AND c.revision=j.revision WHERE j.status='complete'").fetchone()[0]
        result['awaiting_review_rows']=result['rows']-result['reviewed_rows_in_current_context']
        result['graph_review_complete']=False
        return result

    def claim_review(self,limit=150):
        if not 1<=limit<=150:raise ValueError('Review working view must be 1..150 rows')
        with self.db:
            pending=self.db.execute("SELECT j.* FROM review_jobs j JOIN components c ON c.id=j.component_id AND c.revision=j.revision WHERE j.status='pending' ORDER BY j.rowid LIMIT 1").fetchone()
            if pending:
                result=dict(pending);result['row_ids']=[r[0]for r in self.db.execute('SELECT row_id FROM review_rows WHERE job_id=? ORDER BY row_id',(pending['id'],))];return result
            rows=self.db.execute('''SELECT s.row_id,s.component_id,c.revision FROM seen s JOIN components c ON c.id=s.component_id
                WHERE NOT EXISTS(SELECT 1 FROM review_rows r JOIN review_jobs j ON j.id=r.job_id
                    WHERE r.row_id=s.row_id AND j.revision=c.revision AND j.status IN ('pending','complete'))
                ORDER BY s.component_id,s.row_id LIMIT ?''',(limit,)).fetchall()
            if not rows:return None
            component=rows[0]['component_id'];revision=rows[0]['revision'];ids=[r['row_id']for r in rows if r['component_id']==component]
            ident=hashlib.sha256(json.dumps([self.get('source_sha256'),self.start,self.end,component,revision,ids]).encode()).hexdigest()
            self.db.execute("INSERT INTO review_jobs VALUES(?,?,?,'pending',NULL)",(ident,component,revision))
            self.db.executemany('INSERT INTO review_rows VALUES(?,?)',[(ident,i)for i in ids])
            return {'id':ident,'component_id':component,'revision':revision,'status':'pending','row_ids':ids}

    def prepare_review(self,job_id,case_directory):
        job=self.db.execute('SELECT j.*,c.revision AS current_revision FROM review_jobs j JOIN components c ON c.id=j.component_id WHERE j.id=?',(job_id,)).fetchone()
        if job is None or job['revision']!=job['current_revision'] or job['status']!='pending':
            raise ValueError('Unknown, stale or completed review job')
        directory=str(Path(case_directory).resolve())
        state=json.loads((Path(directory)/'state.json').read_text())
        if state['source_sha256']!=self.get('source_sha256') or state.get('scope')!=[self.start,self.end]:
            raise ValueError('Review source or time scope differs')
        if state['status']=='active' or any(c['role']=='reviewer' for c in state['calls']):
            raise ValueError('Bind a stopped case before any reviewer call')
        ids={r[0]for r in self.db.execute('SELECT row_id FROM review_rows WHERE job_id=?',(job_id,))}
        if not {'T'+str(i)for i in ids}<=set(state['evidence']):raise ValueError('Review case lacks requested evidence')
        fingerprint=hashlib.sha256(json.dumps(state['evidence'],sort_keys=True).encode()).hexdigest()
        prefix=hashlib.sha256(json.dumps(state['calls'],sort_keys=True).encode()).hexdigest()
        with self.db:self.db.execute('INSERT INTO review_bindings VALUES(?,?,?,?,?)',(job_id,directory,fingerprint,len(state['calls']),prefix))
        return {'job_id':job_id,'revision':job['revision'],'case_directory':directory,'evidence_fingerprint':fingerprint}

    def complete_review(self,job_id,case_directory):
        # Only a saved, independently replayable reviewer trace can supply completion.
        job=self.db.execute('SELECT j.*,c.revision AS current_revision FROM review_jobs j JOIN components c ON c.id=j.component_id WHERE j.id=?',(job_id,)).fetchone()
        if job is None or job['revision']!=job['current_revision']:raise ValueError('Unknown or stale review job')
        binding=self.db.execute('SELECT * FROM review_bindings WHERE job_id=?',(job_id,)).fetchone()
        if binding is None or binding['case_directory']!=str(Path(case_directory).resolve()):
            raise ValueError('Review must be bound to this job before reviewer execution')
        from replay_audit import audit
        audit(case_directory,self.database)
        state=json.loads((Path(case_directory)/'state.json').read_text())
        if state['source_sha256']!=self.get('source_sha256') or state.get('scope')!=[self.start,self.end]:raise ValueError('Review source or time scope differs')
        fingerprint=hashlib.sha256(json.dumps(state['evidence'],sort_keys=True).encode()).hexdigest()
        prefix=hashlib.sha256(json.dumps(state['calls'][:binding['call_count']],sort_keys=True).encode()).hexdigest()
        if fingerprint!=binding['evidence_fingerprint'] or prefix!=binding['call_prefix']:
            raise ValueError('Bound review evidence or prior call history changed')
        if not any(c['role']=='reviewer' for c in state['calls'][binding['call_count']:]):
            raise ValueError('No reviewer call after job binding')
        reviewed={int(i[1:])for p in (state.get('review_queue') or {}).get('completed',[])for i in p['view']}
        ids={r[0]for r in self.db.execute('SELECT row_id FROM review_rows WHERE job_id=?',(job_id,))}
        if not ids<=reviewed:raise ValueError('Reviewer has not assessed all requested rows')
        receipt={'directory':str(Path(case_directory).resolve()),'state_sha256':hashlib.sha256((Path(case_directory)/'state.json').read_bytes()).hexdigest(),
            'meaning':'These rows appeared in completed review packets; relationships or entire graph are not exhaustively reviewed.'}
        with self.db:self.db.execute("UPDATE review_jobs SET status='complete',receipt=? WHERE id=?",(json.dumps(receipt),job_id))

    def close(self):
        self.db.close();fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['run','status','claim-review']);parser.add_argument('ledger',type=Path)
    parser.add_argument('--database',type=Path,default=HERE/'generated/transactions.sqlite')
    parser.add_argument('--start');parser.add_argument('--end');parser.add_argument('--seed',type=int)
    parser.add_argument('--page-rows',type=int,default=25);parser.add_argument('--max-pages',type=int)
    args=parser.parse_args()
    scan=Scan(args.ledger,args.database,args.start,args.end,args.page_rows,args.seed)
    try:
        result=scan.run(args.max_pages) if args.action=='run' else scan.status() if args.action=='status' else scan.claim_review()
        print(json.dumps(result),flush=True)
    finally:scan.close()
