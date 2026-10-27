"""Offline experiment: identical account scopes, different retrieval page sizes.

Reads the source and an existing scope inventory without changing either ledger.
This measures retrieval, not model direction selection or detection quality.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time


def retrieve(source,scopes,page_rows):
    seen=set();returned=0;pages=0;started=time.monotonic()
    for scope in scopes:
        side=scope['direction'];after=None
        while True:
            sql=f'SELECT row_id,timestamp FROM transactions WHERE {side}_bank=? AND {side}_account=? AND timestamp>=? AND timestamp<?'
            args=[scope['bank'],scope['account'],scope['start'],scope['end']]
            if after:
                sql+=' AND (timestamp,row_id)>(?,?)';args.extend(after)
            rows=source.execute(sql+' ORDER BY timestamp,row_id LIMIT ?',args+[page_rows+1]).fetchall()
            complete=len(rows)<=page_rows;rows=rows[:page_rows];pages+=1;returned+=len(rows)
            seen.update(r['row_id'] for r in rows)
            if complete:break
            after=(rows[-1]['timestamp'],rows[-1]['row_id'])
    ids=sorted(seen)
    return {'page_rows':page_rows,'sql_pages':pages,'returned_occurrences':returned,'unique_rows':len(ids),
            'duplicate_occurrences':returned-len(ids),'seconds':round(time.monotonic()-started,4),
            'row_set_sha256':hashlib.sha256(json.dumps(ids).encode()).hexdigest(),'row_ids':ids}


def experiment(ledger,database,scope_count=100):
    with sqlite3.connect(Path(ledger).resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        meta={r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM meta')}
        scopes=[dict(r,start=meta['start'],end=meta['end']) for r in db.execute('SELECT bank,account,direction FROM scopes ORDER BY id LIMIT ?',(scope_count,))]
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as source:
        source.row_factory=sqlite3.Row
        results=[retrieve(source,scopes,size) for size in (25,250)]
    if results[0]['row_ids']!=results[1]['row_ids']:raise AssertionError('Retrieval variants returned different evidence')
    for result in results:result.pop('row_ids')
    return {'scope_count':len(scopes),'source_sha256':meta['source_sha256'],'variants':results,'exact_row_set_match':True,'model_calls':0,
            'limitations':['Fixed scopes from a partially explored component, not representative dataset sampling.',
                          'Timing includes cache effects; page counts and exact row equality are the primary measurements.',
                          'Does not test model direction quality, reviewer quality or persisted batch recovery.']}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('ledger',type=Path);parser.add_argument('--database',type=Path,default=Path('generated/transactions.sqlite'));parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=experiment(args.ledger,args.database);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
