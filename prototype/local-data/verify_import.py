"""Read-only source crosscheck and local tool timing; no model or detection claims."""
import csv
import json
from pathlib import Path
import sqlite3
import statistics
import time
from tools import HERE, Tools


def main():
    generated=HERE/'generated'
    manifest=json.loads((generated/'manifest.json').read_text())
    api=Tools()
    try:
        selected=set(range(1,manifest['rows']+1,100003)) | {manifest['rows']}
        checked=0
        with (HERE.parents[1]/'data/HI-Small_Trans.csv').open(newline='') as f:
            reader=csv.reader(f); next(reader)
            for n,r in enumerate(reader,1):
                if n not in selected: continue
                found=api.db.execute('SELECT * FROM transactions WHERE row_id=?',(n,)).fetchone()
                actual=[found['timestamp'],found['raw_source_bank'],found['source_account'],found['raw_destination_bank'],found['destination_account'],found['received_amount'],found['received_currency'],found['paid_amount'],found['paid_currency'],found['payment_format']]
                assert actual == r[:10], n
                checked += 1
        assert n == manifest['rows'] == api.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
        columns=[r[1] for r in api.db.execute('PRAGMA table_info(transactions)')]
        assert not any('launder' in c.lower() for c in columns)
        assert api.db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        busy=api.db.execute('SELECT source_bank,source_account,COUNT(*) n FROM transactions GROUP BY source_bank,source_account ORDER BY n DESC LIMIT 1').fetchone()
        ordinary=api.db.execute('SELECT source_bank,source_account FROM transactions WHERE row_id=100003').fetchone()
        timings=[]
        for name,account in [('ordinary',ordinary),('busiest_outgoing',busy)]:
            query=dict(bank=account[0],account=account[1],start='2022/09/01 00:00',end='2022/09/11 00:00',direction='outgoing')
            for tool in ('fetch_transactions','summarize_activity'):
                samples=[]
                for _ in range(5):
                    started=time.perf_counter(); result=api.dispatch(tool,query); samples.append(time.perf_counter()-started)
                    assert 'error' not in result, result
                timings.append({'account_kind':name,'tool':tool,'runs':5,'median_seconds':statistics.median(samples), 'max_seconds':max(samples),'complete':result['complete'],'returned_or_scanned_rows':len(result['rows']) if 'rows' in result else result['rows_scanned']})
        plans={direction:[list(r) for r in api.db.execute(f'EXPLAIN QUERY PLAN SELECT * FROM transactions WHERE {side}_bank=? AND {side}_account=? AND timestamp>=? AND timestamp<? ORDER BY timestamp,row_id LIMIT 101',(*ordinary,'2022/09/01 00:00','2022/09/11 00:00'))] for direction,side in [('outgoing','source'),('incoming','destination')]}
        assert all(any('INDEX' in r[-1] for r in plan) for plan in plans.values())
        report={'source_rows':n,'source_rows_crosschecked':checked,'integrity':'ok','query_plans':plans,'timings':timings,'database_bytes':{p.name:p.stat().st_size for p in generated.glob('*.sqlite')},'timing_scope':'Five sequential local calls per tool/account, includes receipt commit; not cold-cache or model latency'}
        (generated/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        api.close()

if __name__=='__main__': main()
