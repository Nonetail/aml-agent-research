"""Read-only source replay of integrated model navigation and review receipts.

Does not import the global runner, traversal implementation, or runtime path builder.
A structural pass does not imply complete exploration or correct model judgments.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from replay_audit import AuditFailure, require, compact, candidates, packets, typed_answer

HERE=Path(__file__).resolve().parent


def audit(directory,database=HERE/'generated/transactions.sqlite'):
    ledger=Path(directory)
    if ledger.is_dir():ledger=ledger/'ledger.sqlite'
    db=sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    source=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True);source.row_factory=sqlite3.Row
    try:
        meta={r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM meta')}
        sha=source.execute("SELECT value FROM metadata WHERE key='source_sha256'").fetchone()[0]
        require(meta['source_sha256']==sha,'source','Identity mismatch')
        start,end=meta['start'],meta['end'];require(start<end,'scope','Invalid interval')
        known={};owners={};scopes={};scope_keys={};revisions={};view=[];page_ids=[];used_calls=set();review_events={}
        calls={r['id']:dict(r) for r in db.execute('SELECT * FROM agent_calls ORDER BY id')}
        def row(ident):
            value=source.execute('SELECT * FROM transactions WHERE row_id=?',(ident,)).fetchone()
            require(value is not None,'source','Unknown transaction')
            value=dict(value);require(start<=value['timestamp']<end,'source','Out of scope')
            value['transaction_id']=sha+':'+str(value.pop('row_id'));return value
        def discover(rows,component):
            new=False
            for r in rows:
                alias='T'+r['transaction_id'].rsplit(':',1)[1]
                if alias not in known:known[alias]=r;owners[alias]=component;new=True
                require(owners[alias]==component,'component','Connected rows split across components')
            if new:revisions[component]=revisions.get(component,0)+1
            endpoints=sorted({(r[s+'_bank'],r[s+'_account']) for r in rows for s in ('source','destination')})
            for bank,account in endpoints:
                for direction in ('source','destination'):
                    key=(bank,account,direction)
                    if key not in scope_keys:
                        ident=len(scopes)+1;scope_keys[key]=ident
                        scopes[ident]={'id':ident,'bank':bank,'account':account,'direction':direction,'component_id':component,'after_time':None,'after_id':None,'status':'pending','pages':0}
        def payload(call):
            request=json.loads(call['request']);data=json.loads(request['messages'][-1]['content'])
            require(data['source_sha256']==sha and data['scope']==[start,end],'call','Source/scope differs')
            return request,data
        def assessment(call,context,index):
            request,data=payload(call);packet=context['packets'][index]
            require(data['rows']==[compact(context['evidence'][i]) for i in packet['view']],'review','Prompt rows differ')
            require(data['revision']==context['revision'],'review','Revision differs')
            expected=[f for f in context['findings'] if f['id'] in {p['id'] for p in packet['paths']}]
            require(data['verified_paths']==expected,'review','Prompt paths differ')
            answer=typed_answer(request,json.loads(call['response']))
            decisions=answer['decisions'];ids={p['id'] for p in packet['paths']}
            require(len(decisions)==len(ids) and {d['id'] for d in decisions}==ids,'review','Assessment IDs differ')
            return answer,data
        for event in db.execute('SELECT * FROM agent_events ORDER BY id'):
            body=json.loads(event['body']);kind=event['kind'];cid=event['call_id']
            if cid is not None:
                require(cid in calls and cid not in used_calls,'event','Unknown or duplicated call')
                require(calls[cid]['status']=='applied','event','Unapplied call has an event');used_calls.add(cid)
            if kind=='seed':
                require(cid is None and body['before']==view,'seed','Invalid event transition')
                require(not any(s['status']=='pending' for s in scopes.values()),'seed','Previous component has pending work')
                alias='T'+str(body['row_id']);require(alias not in known,'seed','Repeated seed')
                discover([row(body['row_id'])],body['component_id']);view=[alias]
                require(body['after']==view,'seed','Seed view differs')
            elif kind=='rollover':
                require(cid is None and body['before']==view and body['after'] in (view[-8:],[]),'rollover','Invalid transition')
                view=body['after']
            elif kind=='navigate':
                require(cid is not None and body['before']==view,'navigate','Before view differs')
                request,data=payload(calls[cid]);answer=typed_answer(request,json.loads(calls[cid]['response']))
                require(data['rows']==[compact(known[i]) for i in view],'navigate','Prompt rows differ')
                frontier=[s for s in scopes.values() if s['status']=='pending'][:16]
                require(data['frontier']==frontier,'navigate','Advertised frontier differs')
                evict,restore=answer['evict_ids'],answer['restore_ids'];selected=answer['scope_ids']
                require(answer['action'] in ('expand','revise','review'),'navigate','Unknown action')
                require(len(evict)<=50 and len(restore)<=25 and len(selected)<=4,'navigate','Action exceeds allowance')
                require((answer['action']=='expand' and bool(selected)) or (answer['action']!='expand' and not selected),'navigate','Scope/action mismatch')
                require(answer['action']!='review' or not (evict or restore),'navigate','Review changes view')
                require(set(data.get('restorable_ids',[]))<=set(known)-set(view),'navigate','Invalid advertised restorations')
                require(len(evict)==len(set(evict)) and set(evict)<=set(view),'navigate','Invalid evictions')
                require(len(restore)==len(set(restore)) and set(restore)<=set(known)-set(view),'navigate','Invalid restorations')
                view=[i for i in view if i not in evict]+restore
                require(len(view)<=150,'navigate','Oversized view')
                require(len(selected)==len(set(selected)) and set(selected)<={s['id'] for s in frontier},'navigate','Invalid scopes')
                require(len(body['page_ids'])==len(body['page_limits'])==(len(selected) if answer['action']=='expand' else 0),'navigate','Page count differs')
                for scope_id,pid,limit in zip(selected,body['page_ids'],body['page_limits']):
                    require(pid not in page_ids and 1<=limit<=meta['page_rows'] and limit<=150-len(view),'page','Invalid capacity')
                    p=db.execute('SELECT * FROM pages WHERE id=?',(pid,)).fetchone();s=scopes[scope_id]
                    require(p is not None and p['scope_id']==scope_id and (p['before_time'],p['before_id'])==(s['after_time'],s['after_id']),'page','Broken cursor')
                    side=s['direction'];sql=f'SELECT row_id FROM transactions WHERE {side}_bank=? AND {side}_account=? AND timestamp>=? AND timestamp<?'
                    args=[s['bank'],s['account'],start,end]
                    if s['after_time'] is not None:sql+=' AND (timestamp,row_id)>(?,?)';args.extend([s['after_time'],s['after_id']])
                    found=[r[0] for r in source.execute(sql+' ORDER BY timestamp,row_id LIMIT ?',args+[limit+1])]
                    complete=len(found)<=limit;found=found[:limit];rows=[row(i) for i in found]
                    digest=hashlib.sha256(json.dumps(found,separators=(',',':')).encode()).hexdigest()
                    require(p['digest']==digest and p['returned_count']==len(found) and p['complete']==complete,'page','Source page differs')
                    after=(rows[-1]['timestamp'],found[-1]) if found else (s['after_time'],s['after_id'])
                    require((p['after_time'],p['after_id'])==after,'page','End cursor differs')
                    s.update(after_time=after[0],after_id=after[1],status='complete' if complete else 'pending',pages=s['pages']+1)
                    discover(rows,s['component_id']);view=list(dict.fromkeys(view+['T'+str(i) for i in found]));page_ids.append(pid)
                require(body['after']==view and len(view)<=150,'navigate','After view differs')
            elif kind=='review':
                job=db.execute('SELECT * FROM review_jobs WHERE id=?',(body['job_id'],)).fetchone()
                saved=db.execute('SELECT * FROM agent_reviews WHERE job_id=?',(body['job_id'],)).fetchone()
                require(job is not None and saved is not None,'review','Missing job/context')
                context=json.loads(saved['context']);index=body['packet_index']
                require(context['component_id']==job['component_id'] and context['revision']==job['revision']==revisions[job['component_id']],'review','Stale context')
                require(all(i in known and known[i]==r and owners[i]==job['component_id'] for i,r in context['evidence'].items()),'review','Unknown evidence')
                paths,eligible=candidates(context['evidence'])
                require([f['candidate'] for f in context['findings']]==paths,'review','Path inventory differs')
                for finding in context['findings']:
                    path=finding['candidate'];rows=[context['evidence'][i] for i in path['ids']];check=finding['check']
                    minutes=int((datetime.strptime(rows[-1]['timestamp'],'%Y/%m/%d %H:%M')-datetime.strptime(rows[0]['timestamp'],'%Y/%m/%d %H:%M')).total_seconds()/60)
                    require(finding['id']==path['id'] and check['valid'] and check['errors']==[] and check['transaction_ids']==[r['transaction_id'] for r in rows] and check['elapsed_minutes']==minutes,'review','Verification differs')
                coverage=context['coverage']
                require(coverage['eligible_start_edges']==eligible and coverage['selected_paths']==len(paths) and coverage['deduplicated_subpaths']==eligible-len(paths) and coverage['omitted_start_edges']==0,'review','Coverage differs')
                require(context['packets']==packets(context['evidence'],paths,150),'review','Packets differ')
                expected_index=len(review_events.get(job['id'],[]));require(index==expected_index,'review','Repeated or out-of-order packet')
                answer,data=assessment(calls[cid],context,index);require(data['job_id']==job['id'],'review','Job differs')
                review_events.setdefault(job['id'],[]).append({'packet_index':index,'call_id':cid,'assessment':answer})
            else:raise AuditFailure('Unknown event kind: '+kind)
        require(set(page_ids)=={r[0] for r in db.execute('SELECT id FROM pages')},'pages','Unbound page')
        require({r['id']:dict(r) for r in db.execute('SELECT * FROM scopes')}==scopes,'scopes','Saved scopes differ')
        require({('T'+str(r[0])):r[1] for r in db.execute('SELECT * FROM seen')}==owners,'evidence','Seen set differs')
        require(meta['rows']==len(known) and meta['pages']==len(page_ids),'counts','Ledger counts differ')
        for component in db.execute('SELECT * FROM components'):
            require(component['revision']==revisions.get(component['id']),'component','Revision differs')
        if 'agent' in meta:require(meta['agent']['view']==view,'view','Saved view differs')
        for cid,call in calls.items():
            require((call['status']=='applied')==(cid in used_calls),'calls','Applied/event mismatch')
            require(call['status'] in ('applied','received','rejected','transport_error','admitted'),'calls','Unknown status')
            require(call['reserved_tokens']>=0 and call['charged_tokens']>=0,'calls','Invalid token accounting')
            request,data=payload(call)
            for values in data['rows']:
                require(values==compact(row(int(values[0][1:]))),'calls','Non-source prompt row')
            if call['status'] in ('applied','received','rejected'):require(call['response'] is not None,'calls','Missing recorded response')
        for saved in db.execute('SELECT * FROM agent_reviews'):
            context=json.loads(saved['context']);completed=json.loads(saved['completed']);job=db.execute('SELECT * FROM review_jobs WHERE id=?',(saved['job_id'],)).fetchone()
            require(completed==review_events.get(saved['job_id'],[]),'review','Completion journal differs')
            ids={r[0] for r in db.execute('SELECT row_id FROM review_rows WHERE job_id=?',(saved['job_id'],))}
            require(ids=={int(i[1:]) for i in context['evidence']} and 1<=len(ids)<=150,'review','Job evidence differs')
            expected_job=hashlib.sha256(json.dumps([sha,start,end,job['component_id'],job['revision'],sorted(ids)]).encode()).hexdigest()
            require(job['id']==expected_job,'review','Job identity differs')
            require(job['status']!='complete' or len(completed)==len(context['packets']),'review','False completion')
            if job['status']=='complete':
                receipt=json.loads(job['receipt']);require(receipt['kind']=='global_agent','review','Missing completion receipt')
                if 'job_id' in receipt:require(receipt['job_id']==job['id'],'review','Receipt job mismatch')
                if 'context_sha256' in receipt:require(receipt['context_sha256']==hashlib.sha256(saved['context'].encode()).hexdigest(),'review','Receipt context mismatch')
        require(not db.execute("SELECT 1 FROM review_jobs j LEFT JOIN agent_reviews a ON a.job_id=j.id WHERE j.status='complete' AND a.job_id IS NULL LIMIT 1").fetchone(),'review','Unbound completed job')
        if meta['status']=='complete':
            from coverage_verify import audit as coverage_audit
            require(coverage_audit(ledger,database)['status']=='passed','coverage','Whole-source coverage failed')
        return {'status':'passed','source_sha256':sha,'seen_rows':len(known),'pages':len(page_ids),'model_calls':len(calls),'applied_calls':len(used_calls),'review_packets':sum(map(len,review_events.values())),
            'exploration_complete':meta['status']=='complete','limitations':['Structural source replay only; does not certify model judgments or exhaustive path detection.','Source identity trusts database metadata; CSV bytes are not rehashed.','Failed and rejected calls are checked for absence of committed effects; rejection reasoning and model summaries are not certified.']}
    finally:db.close();source.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--database',type=Path,default=HERE/'generated/transactions.sqlite');args=parser.parse_args()
    try:print(json.dumps(audit(args.directory,args.database),indent=2))
    except (AuditFailure,KeyError,ValueError) as exc:print(json.dumps({'status':'failed','error':str(exc)}));raise SystemExit(1)
