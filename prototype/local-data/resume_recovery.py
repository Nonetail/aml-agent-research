"""Resume the two journaled live cases under their cumulative budget."""
import fcntl
import hashlib
import json
import shutil
import time
from chunk_case import Case
from replay_audit import audit
from run_case import save
from tools import HERE
import pilot

OUT=HERE/'generated/recovery-resume-v3'
SOURCE=HERE/'generated/recovery-smoke-v2'

def main():
    assert json.loads((OUT/'preflight-result.json').read_text())['passed']
    pilot.OUT=OUT;pilot.TOKEN_BUDGET=4_000_000
    with (OUT/'pilot.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        snapshot=OUT/'frozen-source';snapshot.mkdir()
        for p in HERE.glob('*.py'):(snapshot/p.name).write_bytes(p.read_bytes())
        save(OUT/'resume-source-hashes.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in HERE.glob('*.py')})
        budget=pilot.Budget();results=[]
        for name in ('case-001','case-002'):
            directory=OUT/name;shutil.copytree(SOURCE/name,directory)
            (directory/'result.json').rename(directory/'prior-result.json')
            case=Case(directory,model=pilot.BudgetModel(budget));start=time.monotonic()
            before={'calls':len(case.state['calls']),'pages':len(case.state['actions']),'rows':len(case.state['evidence'])}
            failure=None;replay={'status':'not_certified'}
            try:
                while case.state['status']=='active':case.segment()
                case.review()
            except Exception as exc:
                failure={'type':type(exc).__name__,'message':str(exc)[:300]}
            finally:case.close()
            if failure is None:
                try:replay=audit(directory)
                except Exception as exc:replay={'status':'failed','message':str(exc)[:500]}
            state=json.loads((directory/'state.json').read_text())
            result={'case':name,'before':before,'calls':len(state['calls']),'pages':len(state['actions']),
                'rows':len(state['evidence']),'status':state['status'],'review_status':state.get('review_status','not_started'),
                'failure':failure,'replay':replay,'seconds':time.monotonic()-start,
                'last_errors':[c['error'] for c in state['calls'] if 'error' in c][-3:]}
            save(directory/'result.json',result);results.append(result)
            save(OUT/'results.json',{'cases':results,'budget':budget.state})
            print(json.dumps(result),flush=True)
            if failure is not None or replay['status']!='passed':break
        passed=len(results)==2 and all(r['failure'] is None and r['replay']['status']=='passed' for r in results)
        save(OUT/'results.json',{'passed':passed,'cases':results,'budget':budget.state})
        lines=['# Live recovery resumption','',f'Two-case gate passed: {passed}. Cases attempted: {len(results)}.','',
            f"Cumulative reported tokens: {budget.state['reported_tokens']:,}; charged tokens: {budget.state['charged_tokens']:,}. Includes inherited live regression and the connection probe.",'',
            '| Case | Pages | Calls | Rows | Exploration | Review | Replay |','|---|---:|---:|---:|---|---|---|']
        for r in results:lines.append(f"| {r['case']} | {r['pages']} | {r['calls']} | {r['rows']} | {r['status']} | {r['review_status']} | {r['replay']['status']} |")
        for r in results:
            if r['failure']:lines+=['',f"{r['case']}: {json.dumps(r['failure'])}. Recent errors: {json.dumps(r['last_errors'])}"]
        lines+=['','No wider pilot runs unless this gate passes. A page-budget stop leaves exploration incomplete. Provider usage can be unknown for failed requests; dollar pricing is unverified. Original baseline and paused source cases remain unchanged.']
        (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
        print(json.dumps({'passed':passed,'budget':budget.state}),flush=True)

if __name__=='__main__':main()
