"""Explicit post-screen smaller-context diagnostics, sharing the frozen call budget."""
import argparse
import fcntl
import json
from pathlib import Path

from cycle_context_eval import ROOT, RESEARCH, Runner, ordered, save, digest


def run(confirm=False):
    with (ROOT/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        runner=Runner()
        for filename in ('jobs.json','followup-jobs.json'):
            jobs=json.loads((ROOT/filename).read_text())
            if any(not (ROOT/'calls'/job['id']/'result.json').exists() for job in jobs):
                raise ValueError('Finish the frozen experiment before post-screen diagnostics')
        if confirm:
            diagnostic=json.loads((ROOT/'supplemental-jobs.json').read_text())
            records=[json.loads((ROOT/'calls'/job['id']/'result.json').read_text())
                     for job in diagnostic if job['condition']=='single-32']
            if (len(records)!=6 or any(r['status']!='received' for r in records) or
                sum(r.get('score',{}).get('target_recovered',0) for r in records)<5 or
                any(r.get('score',{}).get('invalid_true_claims',0) or r.get('score',{}).get('unknown_ids') for r in records)):
                save(ROOT/'diagnostic-confirmation-status.json',{'status':'not_selected','reason':'32-row development screen did not pass'})
                return
            names=('holdout-2','holdout-3','holdout-4')
            filename='diagnostic-confirmation-jobs.json'
        else:
            names=('dev-2','dev-3','dev-4')
            filename='supplemental-jobs.json'
        path=ROOT/filename
        if path.exists():
            manifest=json.loads((ROOT/(filename.replace('-jobs','-manifest'))).read_text())
            if (digest(path)!=manifest['jobs_sha256'] or digest(Path(__file__))!=manifest['implementation_sha256'] or
                digest(RESEARCH/'PROTOCOL-DIAGNOSTIC.md')!=manifest['protocol_sha256']):
                raise ValueError('Frozen diagnostic input, implementation or protocol changed')
            jobs=json.loads(path.read_text())
        else:
            jobs=[]
            for name in names:
                pool=json.loads((ROOT/'runtime'/f'{name}.json').read_text())
                for repetition in (1,2):
                    jobs.append({'id':f'{name}--single-32--r{repetition}','case':name,
                        'condition':'single-32','repetition':repetition,
                        'row_ids':[r['transaction_id'] for r in ordered(pool[:32])]})
                if not confirm:
                    evaluator=json.loads((ROOT/'evaluator'/f'{name}.json').read_text())
                    jobs.append({'id':f'{name}--core-only--r1','case':name,'condition':'core-only',
                        'repetition':1,'row_ids':[r['transaction_id'] for r in ordered(pool[:evaluator['core_rows']])]})
            if len(runner.records)+len(jobs)>runner.manifest['max_calls']:
                save(ROOT/(filename.replace('-jobs','-status')),{'status':'not_selected','reason':'Insufficient remaining call budget'})
                return
            save(path,jobs)
            save(ROOT/(filename.replace('-jobs','-manifest')),{'jobs_sha256':digest(path),
                'implementation_sha256':digest(Path(__file__)),
                'protocol_sha256':digest(RESEARCH/'PROTOCOL-DIAGNOSTIC.md'),
                'selection':'Post-screen diagnostic after main results; same frozen request builder and budget.'})
        for job in jobs:
            runner.execute(job)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm',action='store_true')
    run(parser.parse_args().confirm)
