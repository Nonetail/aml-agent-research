"""Read-only, model-free replay from source rows, receipts and recorded model calls.

Does not import runtime navigation, view-management, path-generation or audit code.
Requires complete call artifacts; --base-run supplies inherited artifacts for copied cases.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sqlite3

HERE=Path(__file__).resolve().parent

class AuditFailure(ValueError): pass

def require(condition,step,message):
    if not condition: raise AuditFailure(f'{step}: {message}')

def alias(row):return 'T'+row['transaction_id'].rsplit(':',1)[1]

def compact(row):
    return [alias(row)]+[row[k] for k in ('timestamp','source_bank','source_account','destination_bank','destination_account','paid_amount','paid_currency','received_amount','received_currency','payment_format')]

def source(row):return row['source_bank'],row['source_account']
def dest(row):return row['destination_bank'],row['destination_account']

def candidates(evidence):
    ordered=sorted(evidence,key=lambda i:(evidence[i]['timestamp'],int(i[1:])))
    possible=[]
    for first in ordered:
        if source(evidence[first])==dest(evidence[first]):continue
        ids=[first]
        while len(ids)<6:
            last=evidence[ids[-1]]
            following=next((i for i in ordered if evidence[i]['timestamp']>last['timestamp'] and
                source(evidence[i])==dest(last) and source(evidence[i])!=dest(evidence[i])),None)
            if following is None:break
            ids.append(following)
            if dest(evidence[following])==source(evidence[first]):break
        if len(ids)>1:possible.append({'id':'P'+hashlib.sha256(json.dumps(ids).encode()).hexdigest()[:16],
            'ids':ids,'cycle':dest(evidence[ids[-1]])==source(evidence[first])})
    kept=[]
    for item in sorted(possible,key=lambda p:(-len(p['ids']),tuple(p['ids']))):
        ids=item['ids']
        contained=any(any(p['ids'][i:i+len(ids)]==ids for i in range(len(p['ids'])-len(ids)+1)) for p in kept)
        if item['cycle'] or not contained:kept.append(item)
    return kept,len(possible)

def packets(evidence,paths,limit):
    result=[];current={'view':[],'paths':[]};seen=set()
    for path in paths:
        union=list(dict.fromkeys(current['view']+path['ids']))
        if len(union)>limit or len(current['paths'])==6:
            result.append(current);seen.update(current['view']);current={'view':[],'paths':[]};union=list(path['ids'])
        current['view']=union;current['paths'].append(path)
    if current['view']:result.append(current);seen.update(current['view'])
    remaining=[i for i in evidence if i not in seen]
    result.extend({'view':remaining[i:i+limit],'paths':[]} for i in range(0,len(remaining),limit))
    return result


def schema_valid(schema,value):
    kind=schema.get('type')
    if kind=='object':
        if not isinstance(value,dict) or set(schema.get('required',[]))-value.keys():return False
        properties=schema.get('properties',{})
        if schema.get('additionalProperties') is False and value.keys()-properties.keys():return False
        if any(k not in properties or not schema_valid(properties[k],v) for k,v in value.items()):return False
    elif kind=='array':
        if not isinstance(value,list) or not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',10000):return False
        if any(not schema_valid(schema['items'],v) for v in value):return False
    elif kind=='string':
        if not isinstance(value,str) or len(value)>min(20000,schema.get('maxLength',20000)):return False
    elif kind=='integer':
        if type(value) is not int or not schema.get('minimum',-10**9)<=value<=schema.get('maximum',10**9):return False
    elif kind=='boolean' and type(value) is not bool:return False
    return 'enum' not in schema or value in schema['enum']

def typed_answer(req,response):
    if response.get('finish_reason')=='length':raise ValueError('Truncated response')
    calls=response['message'].get('tool_calls',[])
    distinct={(c['function']['name'],json.dumps(json.loads(c['function']['arguments']),sort_keys=True)) for c in calls}
    if len(distinct)!=1:raise ValueError('Not one distinct typed call')
    name,raw=next(iter(distinct));definition=req['tools'][0]['function'];answer=json.loads(raw)
    if name!=definition['name'] or not schema_valid(definition['parameters'],answer):raise ValueError('Invalid typed response')
    return answer

def rejection_proven(req,response,view,known,seed,limit):
    try:answer=typed_answer(req,response)
    except (KeyError,TypeError,ValueError):return True
    operation=req['tools'][0]['function']['name']
    if operation=='assess_verified_paths':
        payload=json.loads(req['messages'][-1]['content'])
        expected={p['id'] for p in payload['verified_paths']}
        decisions=answer['decisions']
        return len(decisions)!=len(expected) or {d['id'] for d in decisions}!=expected
    if operation=='expand_batch':
        payload=json.loads(req['messages'][-1]['content'])
        selected=answer['queries'];ids=[q['query_id'] for q in selected]
        return (len(ids)!=len(set(ids)) or not 1<=len(ids)<=4 or
                not set(ids)<={q['id'] for q in payload['frontier']} or
                len(ids)>payload['budgets']['remaining_view_rows'] or
                len(ids)>payload['budgets']['remaining_query_pages'])
    if operation!='manage_view':return False
    evict=answer['evict_ids'];restore=answer['restore_ids']
    if answer['action']=='handoff':return bool(evict or restore)
    return (answer['action']!='continue' or not evict or len(evict)>100 or len(restore)>25 or
            len(evict)!=len(set(evict)) or len(restore)!=len(set(restore)) or
            not set(evict)<=set(view) or seed in evict or not set(restore)<=set(known)-set(view) or
            len([i for i in view if i not in evict]+restore)>=limit)


def audit(directory,database=HERE/'generated/transactions.sqlite',base_run=None):
    directory=Path(directory);state=json.loads((directory/'state.json').read_text())
    require(state.get('pending_action') is None,'state','In-flight page commit needs recovery before audit')
    db=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    receipts=sqlite3.connect((directory/'receipts.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    try:
        sha=db.execute("SELECT value FROM metadata WHERE key='source_sha256'").fetchone()[0]
        require(sha==state['source_sha256'],'source','Source identity mismatch')
        evidence={}
        for ident,row in state['evidence'].items():
            require(ident.startswith('T') and ident[1:].isdigit(),'evidence/'+ident,'Invalid ID')
            raw=db.execute('SELECT * FROM transactions WHERE row_id=?',(int(ident[1:]),)).fetchone()
            require(raw is not None,'evidence/'+ident,'Source row does not exist')
            expected=dict(raw);expected['transaction_id']=sha+':'+str(expected.pop('row_id'))
            require(row==expected,'evidence/'+ident,'Source row differs')
            require('2022/09/01 00:00'<=row['timestamp']<'2022/09/11 00:00','evidence/'+ident,'Outside authorized scope')
            evidence[ident]=expected
        require(state['seed'] in evidence,'seed','Missing source seed')
        known={state['seed']:evidence[state['seed']]};queries={};after={};page_rows=[]
        def discover(rows):
            for row in rows:
                for side in ('source','destination'):
                    for direction in ('incoming','outgoing'):
                        scope=dict(bank=row[side+'_bank'],account=row[side+'_account'],start=state['scope'][0],end=state['scope'][1],direction=direction)
                        key='Q'+hashlib.sha256(json.dumps(scope,sort_keys=True).encode()).hexdigest()[:12]
                        queries.setdefault(key,{'scope':scope,'pages':0,'cursor':None,'status':'pending','support':alias(row)})
        discover(known.values())
        query_snapshots=[json.loads(json.dumps(queries))]
        require(len({a['id'] for a in state['actions']})==len(state['actions']),'actions','Repeated action ID')
        for n,action in enumerate(state['actions']):
            step=f'page/{n+1}';args=action['arguments'];key=action['query_id']
            require(key in queries,step,'Undiscovered query')
            require(queries[key]['status']=='pending',step,'Repeated completed query')
            require(action['id']==action['receipt_id'],step,'Action/receipt identity differs')
            require(args.get('cursor')==after.get(key),step,'Broken cursor chain')
            require({k:args[k] for k in queries[key]['scope']}==queries[key]['scope'],step,'Query scope changed')
            require(1<=args['limit']<=action.get('requested_limit',args['limit'])<=500,step,'Invalid page allowance')
            require('2022/09/01 00:00'<=args['start']<args['end']<='2022/09/11 00:00',step,'Unauthorized page')
            record=receipts.execute('SELECT tool,parameters,result FROM receipts WHERE id=?',(action['receipt_id'],)).fetchone()
            require(record is not None and record[0]=='fetch_transactions',step,'Missing fetch receipt')
            require(json.loads(record[1])==args,step,'Receipt arguments differ')
            result=json.loads(record[2]);scope=queries[key]['scope']
            identity=hashlib.sha256(json.dumps([sha,scope],sort_keys=True).encode()).hexdigest()
            side='source' if args['direction']=='outgoing' else 'destination'
            sql=f'SELECT * FROM transactions WHERE {side}_bank=? AND {side}_account=? AND timestamp>=? AND timestamp<?'
            params=[args['bank'],args['account'],args['start'],args['end']]
            if args.get('cursor'):
                cursor=json.loads(base64.urlsafe_b64decode(args['cursor']))
                require(cursor['scope']==identity,step,'Cursor source/scope binding differs')
                sql+=' AND (timestamp,row_id)>(?,?)';params.extend(cursor['after'])
            raw=db.execute(sql+' ORDER BY timestamp,row_id LIMIT ?',params+[args['limit']+1]).fetchall()
            more=len(raw)>args['limit'];raw=raw[:args['limit']];rows=[]
            for r in raw:
                row=dict(r);row['transaction_id']=sha+':'+str(row.pop('row_id'));rows.append(row)
            cursor=None
            if more:cursor=base64.urlsafe_b64encode(json.dumps({'scope':identity,'after':[raw[-1]['timestamp'],raw[-1]['row_id']]}).encode()).decode()
            require(result['rows']==rows,step,'Receipt page differs from independent source query')
            require(result['source_sha256']==sha and result['authorized_scope']==['2022/09/01 00:00','2022/09/11 00:00'],step,'Receipt provenance differs')
            require(result['next_cursor']==cursor==action['next_cursor'] and result['complete']==action['complete']==(not more),step,'Continuation or completion differs')
            require(action['returned_ids']==[alias(r) for r in rows],step,'Returned ID list differs')
            after[key]=cursor;queries[key].update(cursor=cursor,pages=queries[key]['pages']+1,status='pending' if more else 'complete')
            known.update({alias(r):r for r in rows});discover(rows);page_rows.append(rows)
            query_snapshots.append(json.loads(json.dumps(queries)))
        require(known==evidence,'evidence','Stored evidence does not equal seed plus fetched rows')
        require(queries==state['queries'],'frontier','Query inventory, cursors or status differs from replay')
        fetched={r[0] for r in receipts.execute("SELECT id FROM receipts WHERE tool='fetch_transactions'")}
        require(fetched=={a['receipt_id'] for a in state['actions']},'receipts','Unaccounted fetch receipt or deleted action')
        require(len(state['actions'])<=state['limits']['max_query_pages'],'budget','Page budget exceeded')
        require(len(state['calls'])<=state['limits']['max_model_calls'],'budget','Model-call budget exceeded')

        # Replay each recorded model request, response and state transition in call order.
        known={state['seed']:evidence[state['seed']]};presented=[];view=[state['seed']]
        page_index=0;event_index=0;chunk_index=0;review_results=[];navigation_calls=0
        chunk_start_view=list(view);chunk_start_ids=list(known);chunk_start_page=0;chunk_start_event=0;chunk_batches=[]
        def artifact(name):
            path=directory/name
            if not path.exists() and base_run:path=Path(base_run)/name
            require(path.exists(),'artifact/'+name,'Missing call artifact; full replay is unavailable')
            return json.loads(path.read_text())
        for index,call in enumerate(state['calls'],1):
            step=f'call/{index}/{call["role"]}'
            req=artifact(f'{index:02d}-{call["role"]}-request.json')
            payload=json.loads(req['messages'][-1]['content'])
            name=req['tools'][0]['function']['name']
            failed=call.get('outcome') in ('rejected','transport_error')
            if not failed:require(call['status']=='received',step,'Failed/in-flight call requires explicit recovery; cannot certify full replay')
            response_name=f'{index:02d}-{call["role"]}-response.json'
            if call.get('outcome')=='transport_error':
                require(not (directory/response_name).exists() and not (base_run and (Path(base_run)/response_name).exists()),step,'Transport failure has a response artifact')
                response=None
            else:response=artifact(response_name)
            if not failed:
                try:answer=typed_answer(req,response)
                except (KeyError,TypeError,ValueError) as error:raise AuditFailure(f'{step}: Invalid typed response: {error}') from error
            visible=payload.get('rows',[])
            limit=state['limits']['review_view_rows'] if name=='assess_verified_paths' else state['limits']['view_rows']
            require(len(visible)<=limit and len({r[0] for r in visible})==len(visible),step,'Working-view limit or uniqueness violated')
            for row in visible:
                require(row[0] in evidence and row==compact(evidence[row[0]]),step,'Visible row is not exact source evidence')
            if name=='assess_verified_paths':
                if failed:
                    require(call.get('unchanged')=={'view':[],'actions':page_index,'view_events':event_index,'chunks':chunk_index},step,'Recovery snapshot differs from replay')
                    queue=state.get('review_queue')
                    require(queue is not None and len(review_results)<len(queue['packets']),step,'Failed review has no pending packet')
                    packet=queue['packets'][len(review_results)];path_ids={p['id'] for p in packet['paths']}
                    require(visible==[compact(evidence[i]) for i in packet['view']] and payload['verified_paths']==[f for f in queue['findings'] if f['id'] in path_ids],step,'Failed reviewer saw different pending packet')
                    if response is not None:require(rejection_proven(req,response,view,known,state['seed'],limit),step,'Rejected response is valid')
                else:review_results.append({'payload':payload,'answer':answer})
                continue
            require(name in ('expand_batch','manage_view','checkpoint'),step,'Unsupported navigation operation')
            navigation_calls+=1
            snapshot=query_snapshots[page_index]
            require(payload['stored_rows']==len(known),step,'Stored-row count differs')
            require(payload['pending_scope_count']==sum(q['status']=='pending' for q in snapshot.values()),step,'Pending-scope count differs')
            for entry in payload['frontier']:
                key=entry['id'];require(key in snapshot and snapshot[key]['status']=='pending',step,'Invalid advertised frontier')
                expected_entry={'id':key,**{k:v for k,v in snapshot[key].items() if k!='cursor'},'has_more_pages':bool(snapshot[key]['cursor'])}
                require(entry==expected_entry,step,'Advertised scope differs from replay')
            require([compact(known[i]) for i in view]==visible,step,'Working view differs from replay')
            presented=list(dict.fromkeys(presented+view))
            if failed:
                require(call.get('unchanged')=={'view':view,'actions':page_index,'view_events':event_index,'chunks':chunk_index},step,'Recovery snapshot differs from replay')
                if response is not None:require(rejection_proven(req,response,view,known,state['seed'],limit),step,'Rejected response is valid')
                continue
            if name=='expand_batch':
                selected=answer['queries'];capacity=state['limits']['view_rows']-len(view)
                require(1<=len(selected)<=4 and len({q['query_id'] for q in selected})==len(selected),step,'Invalid branch batch')
                returned=[]
                for pos,q in enumerate(selected):
                    require(page_index<len(state['actions']),step,'Missing committed page action')
                    a=state['actions'][page_index]
                    require(q['query_id'] in {f['id'] for f in payload['frontier']},step,'Selection outside advertised frontier')
                    require(1<=q['limit']<=state['limits'].get('page_rows',500),step,'Requested page exceeds configured allowance')
                    require(a['chunk']==chunk_index+1 and a['query_id']==q['query_id'] and a.get('requested_limit',a['arguments']['limit'])==q['limit'],step,'Model selection/action mismatch')
                    effective=min(q['limit'],capacity-(len(selected)-pos-1));capacity-=effective
                    require(effective>0 and a['arguments']['limit']==effective,step,'Incorrect effective page capacity')
                    for row in page_rows[page_index]:known[alias(row)]=row;returned.append(alias(row))
                    page_index+=1
                view=list(dict.fromkeys(view+returned))
                chunk_batches.append({'query_ids':[q['query_id'] for q in selected],'requests':selected,'question':answer['question'],'returned_ids':list(dict.fromkeys(returned))})
            elif name=='manage_view':
                require(len(view)==state['limits']['view_rows'],step,'View management outside full view')
                if answer['action']=='handoff':
                    require(not answer['evict_ids'] and not answer['restore_ids'],step,'Handoff mutated view')
                else:
                    require(answer['action']=='continue',step,'Unknown view action')
                    evict=answer['evict_ids'];restore=answer['restore_ids']
                    require(evict and len(evict)<=100 and len(restore)<=25 and len(evict)==len(set(evict)) and len(restore)==len(set(restore)),step,'Invalid view ID lists')
                    require(set(evict)<=set(view) and state['seed'] not in evict,step,'Invalid eviction')
                    require(set(restore)<=set(known)-set(view),step,'Unknown or already-visible restoration')
                    revised=[i for i in view if i not in evict]+restore
                    require(len(revised)<state['limits']['view_rows'],step,'No free capacity')
                    require(event_index<len(state.get('view_events',[])),step,'Missing view event')
                    expected={'chunk':chunk_index+1,'evicted_ids':evict,'restored_ids':restore,'reason':answer['reason'],'before':view,'after':revised}
                    require(state['view_events'][event_index]==expected,step,'Recorded eviction/restoration differs')
                    event_index+=1;view=revised
            else:
                require(chunk_index<len(state['chunks']),step,'Missing checkpoint/chunk')
                c=state['chunks'][chunk_index]
                require(c['initial_view']==chunk_start_view and set(c['evidence_before'])==set(chunk_start_ids),step,'Chunk start differs')
                require(c['batches']==chunk_batches,step,'Chunk expansion journal differs')
                before={k:q['cursor'] for k,q in query_snapshots[chunk_start_page].items() if q['status']=='pending'}
                after_pending={k:q['cursor'] for k,q in query_snapshots[page_index].items() if q['status']=='pending'}
                require(c['pending_before']==before and c['pending_after']==after_pending,step,'Checkpoint pending scopes/cursors differ')
                require(c['final_view']==view,step,'Checkpoint view differs')
                if 'runtime_delta' in c['checkpoint']:
                    expected_delta={'new_rows':len(known)-len(chunk_start_ids),'query_pages':page_index-chunk_start_page,'view_revisions':event_index-chunk_start_event}
                    require(c['checkpoint']['runtime_delta']==expected_delta,step,'Checkpoint runtime delta differs')
                if 'chunk_delta' in payload:
                    delta=payload['chunk_delta'];new=[i for i in known if i not in chunk_start_ids]
                    require(delta['new_evidence_count']==len(new) and delta['new_evidence_ids_tail']==new[-150:] and delta['new_rows_visible']==[i for i in view if i in new],step,'Checkpoint evidence delta differs')
                    require(delta['pages_fetched']==page_index-chunk_start_page,step,'Checkpoint page delta differs')
                if c['reason']=='row_allowance':require(len(view)==state['limits']['view_rows'],step,'Full-view handoff below limit')
                require(all(c['checkpoint'].get(k)==v for k,v in answer.items()),step,'Saved checkpoint differs from model response')
                require(set(answer['boundary_ids'])<=set(view),step,'Unknown boundary row')
                presented=list(dict.fromkeys(presented+view));chunk_index+=1
                view=list(dict.fromkeys([state['seed']]+answer['boundary_ids']))[:8]
                view.extend([i for i in known if i not in presented and i not in view][:state['limits']['view_rows']-len(view)])
                chunk_start_view=list(view);chunk_start_ids=list(known);chunk_start_page=page_index;chunk_start_event=event_index;chunk_batches=[]
                if chunk_index<len(state['chunks']):
                    nxt=state['chunks'][chunk_index]
                    require(nxt['initial_view']==view and set(nxt['evidence_before'])==set(known),step,'Handoff lost evidence or boundary state')
        require(page_index==len(state['actions']) and chunk_index==len(state['chunks']),'replay','Unconsumed actions or chunks')
        require(event_index==len(state.get('view_events',[])),'replay','Unconsumed view events')
        require(state['notes']==[c['checkpoint'] for c in state['chunks']],'notes','Handoff notes differ from committed checkpoints')
        if state['chunks']:require(state['anchors']==state['chunks'][-1]['checkpoint']['boundary_ids'],'anchors','Saved boundary anchors differ')
        require(set(presented)==set(state['presented']),'presentation','Presented evidence differs')
        require(state.get('active_view') is None,'replay','Open segment cannot be certified as a completed handoff')
        if state['status']=='frontier_exhausted':require(all(q['status']=='complete' for q in queries.values()),'completion','Pending scope marked exhausted')

        queue=state.get('review_queue');pending=0
        if queue:
            require(queue['evidence_fingerprint']==hashlib.sha256(json.dumps(sorted(evidence)).encode()).hexdigest(),'queue','Evidence fingerprint differs')
            expected,eligible=candidates(evidence)
            require([f['candidate'] for f in queue['findings']]==expected,'queue','Generated candidate inventory differs (missing/extra/reordered path)')
            coverage=queue['coverage']
            require(coverage['eligible_start_edges']==eligible and coverage['selected_paths']==len(expected) and coverage['deduplicated_subpaths']==eligible-len(expected) and coverage['omitted_start_edges']==0,'queue','Candidate coverage differs')
            for f in queue['findings']:
                ids=f['candidate']['ids'];rows=[evidence[i] for i in ids]
                valid=len(ids)==len(set(ids)) and all(source(r)!=dest(r) for r in rows) and all(dest(a)==source(b) and a['timestamp']<b['timestamp'] for a,b in zip(rows,rows[1:]))
                require(valid and f['check']['valid'],'path/'+f['id'],'Path fails independent connectivity/time check')
                require(f['check']['transaction_ids']==[r['transaction_id'] for r in rows],'path/'+f['id'],'Verification references different edges')
            expected_packets=packets(evidence,expected,state['limits']['review_view_rows'])
            require(queue['packets']==expected_packets,'queue','Missing/extra/altered review packet')
            require(len(queue['completed'])<=len(expected_packets),'queue','Too many committed packets')
            require(len(review_results)==len(queue['completed']),'queue','Committed assessments do not match recorded review calls')
            for n,done in enumerate(queue['completed']):
                packet=expected_packets[n];record=review_results[n];ids=[p['id'] for p in packet['paths']];step=f'review-packet/{n+1}'
                require(done['view']==packet['view'] and done['path_ids']==ids,step,'Not the next pending packet')
                require(record['payload']['rows']==[compact(evidence[i]) for i in packet['view']],step,'Reviewer saw different evidence')
                require(record['payload']['verified_paths']==[f for f in queue['findings'] if f['id'] in ids],step,'Reviewer saw different verified paths')
                require(done['assessment']==record['answer'],step,'Saved assessment differs from model output')
                decisions=done['assessment']['decisions']
                require(len(decisions)==len(ids) and {d['id'] for d in decisions}==set(ids),step,'Missing/duplicate assessment')
            pending=len(expected_packets)-len(queue['completed'])
            require((state.get('review_status')=='complete')==(pending==0),'queue','Review completion status differs')
            if pending==0:
                review=state.get('review');require(review is not None,'review','Completed queue has no final review')
                expected_decisions=[d for p in queue['completed'] for d in p['assessment']['decisions']]
                expected_limitations=[x for p in queue['completed'] for x in p['assessment']['limitations']]
                expected_view=list(dict.fromkeys(i for p in queue['completed'] for i in p['view']))
                require(review['findings']==queue['findings'] and review['final']=={'decisions':expected_decisions,'limitations':expected_limitations},'review','Final review differs from committed queue')
                require(review['presented_ids']==expected_view and review['investigation_complete']==(state['status']=='frontier_exhausted'),'review','Final review coverage/completion differs')
            else:require(state.get('review') is None,'review','Pending queue published as complete review')
        else:require(not review_results,'queue','Review calls without a persistent queue are not supported by this auditor')
        return {'status':'passed','directory':str(directory),'source_sha256':sha,'source_rows_checked':len(evidence),
                'pages_replayed':page_index,'navigation_calls_replayed':navigation_calls,'chunks_replayed':chunk_index,
                'view_changes_replayed':event_index,'review_packets_replayed':len(review_results),'pending_review_packets':pending,
                'failed_calls_replayed':sum(c.get('outcome') in ('rejected','transport_error') for c in state['calls']),
                'limitations':['Structural replay only; model interpretations and relevance are not certified.',
                               'Assumes the pinned local source database and complete artifacts are trustworthy; not a tamper-proof signature or formal proof.']}
    finally:db.close();receipts.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--database',type=Path,default=HERE/'generated/transactions.sqlite');parser.add_argument('--base-run',type=Path)
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    try:result=audit(args.directory,args.database,args.base_run)
    except (AuditFailure,KeyError,ValueError,TypeError,sqlite3.Error) as error:
        result={'status':'failed','error':str(error)}
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='passed' else 1)
