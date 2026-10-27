"""Independent read-only source checks for the bounded batch prototype."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from replay_audit import typed_answer


def audit(directory,database):
    with sqlite3.connect((Path(directory)/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db,sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as source:
        db.row_factory=source.row_factory=sqlite3.Row
        db.execute('BEGIN');meta={r['key']:json.loads(r['value'])for r in db.execute('SELECT * FROM meta')}
        sha=source.execute("SELECT value FROM metadata WHERE key='source_sha256'").fetchone()[0]
        def require(value,message):
            if not value:raise ValueError(message)
        require(sha==meta['source_sha256'],'Source identity mismatch')
        def row(ident):
            r=source.execute('SELECT * FROM transactions WHERE row_id=?',(int(ident[1:]),)).fetchone()
            require(r is not None and meta['start']<=r['timestamp']<meta['end'],'Unknown/out-of-scope row')
            return r
        retrieved={r[0]for r in db.execute('SELECT seed FROM components')};cursors={}
        for p in db.execute('SELECT * FROM pages ORDER BY id'):
            s=db.execute('SELECT * FROM scopes WHERE id=?',(p['scope_id'],)).fetchone();side=s['direction'];require(side in ('source','destination'),'Invalid direction')
            before=(p['before_time'],p['before_id']);require(cursors.get(s['id'],(None,None))==before,'Cursor gap')
            sql=f'SELECT row_id,timestamp FROM transactions WHERE {side}_bank=? AND {side}_account=? AND timestamp>=? AND timestamp<?';args=[s['bank'],s['account'],meta['start'],meta['end']]
            if before[0] is not None:sql+=' AND (timestamp,row_id)>(?,?)';args.extend(before)
            rows=source.execute(sql+' ORDER BY timestamp,row_id LIMIT ?',args+[meta['page_rows']+1]).fetchall()
            complete=len(rows)<=meta['page_rows'];rows=rows[:meta['page_rows']];ids=[r['row_id']for r in rows]
            require(p['returned_count']==len(rows) and p['digest']==hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest() and p['complete']==complete,'Source page mismatch')
            after=(rows[-1]['timestamp'],rows[-1]['row_id']) if rows else before
            require(after==(p['after_time'],p['after_id']),'Cursor mismatch');cursors[s['id']]=after;retrieved.update(ids)
        require(retrieved=={r[0]for r in db.execute('SELECT row_id FROM seen')},'Discovered rows differ')
        reviewed_rows=set();reviewed_paths=set();packets_count=0
        jobs=list(db.execute('SELECT * FROM batch_jobs ORDER BY id'))
        for index,job in enumerate(jobs):
            if index<len(jobs)-1:require(job['status']=='complete','Expansion outran mandatory review')
            packets=json.loads(job['packets']) if job['packets'] else []
            receipts=list(db.execute('SELECT * FROM batch_receipts WHERE job_id=? ORDER BY packet',(job['id'],)))
            require([r['packet']for r in receipts]==list(range(len(receipts))),'Receipt ordering gap')
            if job['status']=='complete':require(len(receipts)==len(packets),'False checkpoint completion')
            for receipt in receipts:
                packet=packets[receipt['packet']];call=db.execute('SELECT * FROM agent_calls WHERE id=?',(receipt['call_id'],)).fetchone()
                require(call['status']=='applied' and call['role']=='batch-reviewer','Unapplied review')
                request=json.loads(call['request']);payload=json.loads(request['messages'][-1]['content'])
                require(len(json.dumps(request).encode())+2400+2048<=meta['batch_config']['context_budget'],'Context budget exceeded')
                require(len(packet['ids'])<=meta['batch_config']['row_ceiling'],'Row ceiling exceeded')
                require(payload['verified_paths']==packet['paths'],'Path payload mismatch')
                expected=[]
                for ident in packet['ids']:
                    r=row(ident);require(r['row_id']in retrieved,'Review of undiscovered row')
                    expected.append([ident]+[r[k]for k in ('timestamp','source_bank','source_account','destination_bank','destination_account','paid_amount','paid_currency','received_amount','received_currency','payment_format')])
                require(payload['rows']==expected,'Prompt rows differ from source')
                answer=typed_answer(request,json.loads(call['response']));require(answer==json.loads(receipt['answer']),'Assessment receipt mismatch')
                require({d['id']for d in answer['decisions']}=={p['id']for p in packet['paths']},'Decision IDs mismatch')
                for path in packet['paths']:
                    require(set(path['ids'])<=set(packet['ids']),'Path crosses packet without supporting evidence')
                    require(path['id']=='P'+hashlib.sha256(json.dumps(path['ids']).encode()).hexdigest()[:16],'Path identity mismatch')
                    rs=[row(i)for i in path['ids']];require(len(set(path['ids']))==len(rs),'Repeated edge')
                    for a,b in zip(rs,rs[1:]):require((a['destination_bank'],a['destination_account'])==(b['source_bank'],b['source_account']) and a['timestamp']<b['timestamp'],'Invalid temporal path')
                    require(path['cycle']==((rs[0]['source_bank'],rs[0]['source_account'])==(rs[-1]['destination_bank'],rs[-1]['destination_account'])),'Incorrect cycle flag')
                    reviewed_paths.add(path['id'])
                reviewed_rows.update(int(i[1:])for i in packet['ids']);packets_count+=1
        require(reviewed_rows=={r[0]for r in db.execute('SELECT row_id FROM batch_reviewed_rows')},'Reviewed-row claims differ')
        require(reviewed_paths=={r[0]for r in db.execute('SELECT id FROM batch_reviewed_paths')},'Reviewed-path claims differ')
        if jobs and jobs[-1]['status']=='complete':require(retrieved<=reviewed_rows,'Completed checkpoint left rows unpresented')
        return {'status':'passed','rows':len(retrieved),'reviewed_rows':len(reviewed_rows),'packets':packets_count,'paths':len(reviewed_paths),'limitations':['Structural evidence checks only; does not certify model interpretations or exhaustive candidate detection.','Source identity trusts database metadata.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--database',type=Path,default=Path('generated/transactions.sqlite'));a=p.parse_args();print(json.dumps(audit(a.directory,a.database),indent=2))
