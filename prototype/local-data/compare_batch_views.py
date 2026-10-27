"""Reproducible offline capacity comparison; scripted judgments are not model evals."""
from datetime import datetime,timedelta
import json
from pathlib import Path
import sqlite3
from batch_agent import BatchAgent
from batch_audit import audit
from test_batch_agent import Scripted

root=Path('generated/batch-view-comparison-v1');root.mkdir(parents=True,exist_ok=True);source=root/'source.sqlite'
if source.exists():raise SystemExit('Comparison exists; preserve previous results and use a fresh directory.')
with sqlite3.connect(source) as c:
    c.executescript("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);INSERT INTO metadata VALUES('source_sha256','capacity-fixture-v1');CREATE TABLE transactions(row_id INTEGER PRIMARY KEY,timestamp TEXT,source_bank TEXT,source_account TEXT,destination_bank TEXT,destination_account TEXT,paid_amount REAL,paid_currency TEXT,received_amount REAL,received_currency TEXT,payment_format TEXT);")
    c.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?)',[(i,(datetime(2022,9,1)+timedelta(minutes=i)).strftime('%Y/%m/%d %H:%M'),'1','A','1','A',100,'USD',100,'USD','Wire')for i in range(1,1601)])
results=[]
for ceiling in (150,500,1500):
    a=BatchAgent(root/str(ceiling),source,model=Scripted(),row_ceiling=ceiling,context_budget=60000,burst_rows=750,min_interval=0)
    try:
        result=a.run_batches(20)
        sizes=[];counts=[]
        for r in a.db.execute("SELECT request FROM agent_calls WHERE role='batch-reviewer'"):
            req=json.loads(r[0]);sizes.append(len(json.dumps(req).encode())+2400+2048);counts.append(len(json.loads(req['messages'][-1]['content'])['rows']))
        result.update(max_review_rows=max(counts),max_reserved_context=max(sizes),audit=audit(a.directory,source))
        assert result['status']=='complete' and result['rows_presented_for_review']==1600
        results.append(result)
    finally:a.close()
(root/'result.json').write_text(json.dumps({'results':results,'limitations':'Scripted-model capacity and coverage test; no detection-quality or real-token measurement.'},indent=2)+'\n')
print(json.dumps([{'ceiling':r['config']['row_ceiling'],'max_view':r['max_review_rows'],'max_reserved_context':r['max_reserved_context'],'calls':r['calls_by_role']}for r in results],indent=2))
