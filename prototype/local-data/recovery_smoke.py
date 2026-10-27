"""Two serial real-model regression cases; preserves the failed v1 baseline."""
import fcntl
import hashlib
import json
from pathlib import Path
import pilot
from run_case import save
from tools import HERE

OUT=HERE/'generated/recovery-smoke-v2'

def main():
    OUT.mkdir(exist_ok=False)
    specs=json.loads((HERE/'generated/pilot-100-v1/cases.json').read_text())[:2]
    save(OUT/'cases.json',specs)
    snapshot=OUT/'frozen-source';snapshot.mkdir()
    hashes={}
    for path in HERE.glob('*.py'):
        (snapshot/path.name).write_bytes(path.read_bytes())
        hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    save(OUT/'manifest.json',{'source_hashes':hashes,'cases':specs,'limits':pilot.DEFAULTS,
        'token_budget':4_000_000,'workers':1,'model':pilot.MODEL,'endpoint':pilot.ENDPOINT,
        'success':'Both cases reach a closed budget/frontier checkpoint, complete or explicitly defer review and pass independent replay; no detection-accuracy claim.',
        'recovery':'One semantic view correction; one provider retry after20seconds, all attempts within existing160call budget. No case retries by this harness.'})
    pilot.OUT=OUT;pilot.TOKEN_BUDGET=4_000_000
    with (OUT/'pilot.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        budget=pilot.Budget();results=[]
        for spec in specs:
            results.append(pilot.run_one(spec,budget))
            save(OUT/'results.json',{'cases':results,'budget':budget.state})
        passed=all(r['failure'] is None and r['replay']['status']=='passed' for r in results)
        summary={'passed':passed,'cases':results,'budget':budget.state}
        save(OUT/'results.json',summary)
        lines=['# Recovery smoke v2','',f'Passed: {passed}. Two original failed seeds, serial execution.','',
            f"Reported tokens: {budget.state['reported_tokens']:,}; conservatively charged: {budget.state['charged_tokens']:,}.",'',
            '| Case | Pages | Calls | Rows | Exploration | Review | Replay | Failure |','|---|---:|---:|---:|---|---|---|---|']
        for r in results:lines.append(f"| {r['id']} | {r['pages']} | {r['calls']} | {r['rows']} | {r['status']} | {r['review_status']} | {r['replay']['status']} | {r['failure']} |")
        lines+=['','This checks execution/recovery mechanics, not detection accuracy. Reaching the page budget does not mean the graph was exhausted. Currency pricing remains unavailable. The original ten failed pilot traces are unchanged.']
        (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
        print(json.dumps({'passed':passed,'budget':budget.state}),flush=True)

if __name__=='__main__':main()
