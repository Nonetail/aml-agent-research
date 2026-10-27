"""Corrupt disposable copies of saved live runs; original evidence is never edited."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from replay_audit import audit, AuditFailure, HERE


def scenarios():
    return [
        ('alter_source_amount','navigation','source_row'),
        ('invent_visible_id','navigation','visible_id'),
        ('drop_stored_evidence','navigation','drop_evidence'),
        ('break_page_cursor','navigation','cursor'),
        ('exceed_view_limit','navigation','view_limit'),
        ('alter_eviction_result','navigation','eviction'),
        ('lose_handoff_scope','navigation','handoff'),
        ('alter_checkpoint_counts','navigation','delta'),
        ('delete_call_artifact','navigation','artifact'),
        ('alter_receipt_rows','navigation','receipt'),
        ('remove_queued_packet','queue','packet'),
        ('remove_queued_candidate','queue','candidate'),
        ('duplicate_committed_batch','queue','duplicate'),
        ('alter_saved_assessment','queue','assessment'),
        ('false_review_completion','queue','completion'),
    ]


def corrupt(root,kind):
    path=root/'state.json';state=json.loads(path.read_text())
    if kind=='source_row':state['evidence'][state['seed']]['paid_amount']='999999999999.99'
    elif kind=='drop_evidence':del state['evidence'][next(i for i in state['evidence'] if i!=state['seed'])]
    elif kind=='cursor':state['actions'][1]['arguments']['cursor']='broken'
    elif kind=='eviction':state['view_events'][0]['after']=state['view_events'][0]['before']
    elif kind=='delta':state['chunks'][0]['checkpoint']['runtime_delta']['new_rows']+=1
    elif kind=='handoff':state['chunks'][0]['pending_after'].pop(next(iter(state['chunks'][0]['pending_after'])))
    elif kind=='packet':state['review_queue']['packets'].pop()
    elif kind=='candidate':state['review_queue']['findings'].pop()
    elif kind=='duplicate':state['review_queue']['completed'].append(state['review_queue']['completed'][0])
    elif kind=='assessment':state['review_queue']['completed'][0]['assessment']['decisions'][0]['reason']='Fabricated justification'
    elif kind=='completion':state['review_status']='complete'
    elif kind in ('visible_id','view_limit','artifact'):
        file=sorted(root.glob('*investigator-request.json'))[0]
        if kind=='artifact':file.unlink()
        else:
            request=json.loads(file.read_text());payload=json.loads(request['messages'][-1]['content'])
            if kind=='visible_id':payload['rows'][0][0]='T999999999'
            else:payload['rows']*=state['limits']['view_rows']+1
            request['messages'][-1]['content']=json.dumps(payload);file.write_text(json.dumps(request))
    elif kind=='receipt':
        with sqlite3.connect(root/'receipts.sqlite') as db:
            ident,raw=db.execute("SELECT id,result FROM receipts WHERE tool='fetch_transactions' LIMIT 1").fetchone()
            result=json.loads(raw);result['rows']=[]
            db.execute('UPDATE receipts SET result=? WHERE id=?',(json.dumps(result),ident))
    path.write_text(json.dumps(state))


def run(navigation,queue,base,database):
    protected=[f for root in (navigation,queue,base) for f in Path(root).iterdir() if f.is_file() and (f.suffix=='.json' or f.name=='receipts.sqlite')]
    before={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in protected}
    clean=[audit(navigation,database),audit(queue,database,base)]
    results=[]
    for name,target,kind in scenarios():
        origin=navigation if target=='navigation' else queue
        with tempfile.TemporaryDirectory(prefix='aml-replay-corruption-') as temporary:
            root=Path(temporary)
            for file in Path(origin).iterdir():
                if file.is_file() and (file.suffix=='.json' or file.name=='receipts.sqlite'):shutil.copy2(file,root/file.name)
            corrupt(root,kind)
            try:audit(root,database,base if target=='queue' else None)
            except AuditFailure as error:results.append({'scenario':name,'detected':True,'failure':str(error)})
            else:results.append({'scenario':name,'detected':False})
    unchanged=all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==sha for f,sha in before.items())
    return {'original_artifacts_unchanged':unchanged,'clean_runs':clean,'corruptions':results,'all_corruptions_detected':all(r['detected'] for r in results),
            'method':'Mutated disposable copies only; originals and source database remain read-only. No model calls.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--navigation',type=Path,default=HERE/'generated/working-view-live-01')
    p.add_argument('--queue',type=Path,default=HERE/'generated/review-queue-live-01')
    p.add_argument('--base',type=Path,default=HERE/'generated/continuous-live-01')
    p.add_argument('--database',type=Path,default=HERE/'generated/transactions.sqlite')
    p.add_argument('--output',type=Path,default=HERE/'generated/replay-corruptions.json')
    args=p.parse_args();report=run(args.navigation,args.queue,args.base,args.database)
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['all_corruptions_detected'] and report['original_artifacts_unchanged'] else 1)
