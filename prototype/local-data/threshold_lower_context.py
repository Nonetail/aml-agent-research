"""Predeclared downward bracket after all original sizes produced invalid-edge answers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
from pathlib import Path
import random

from threshold_eval import ROOT, BudgetModel, context_run, digest, ordered, trace, verify_manifest, navigate
from chunk_case import alias
from run_case import save

SIZES=[40,75]


def live():
    verify_manifest()
    # The primary batch must finish first: provider-budget.json has one process owner.
    for policy in ['broad','cautious','adaptive']:
        for number in range(1,5):
            for repetition in range(2):
                d=ROOT/f'live-{policy}-case-{number}-{repetition}'
                if not (d/'result.json').exists() and not (d/'failure.json').exists():raise ValueError('Primary batch still incomplete')
    for size in [150,300,750,1500]:
        for number in range(1,5):
            for repetition in range(2):
                d=ROOT/f'context-case-{number}-{size}-{repetition}'
                if not (d/'result.json').exists() and not (d/'failure.json').exists():raise ValueError('Primary context batch still incomplete')
    saved=ROOT/'lower-context-manifest.json'
    if not saved.exists():
        files={}
        for number in range(1,5):
            base=json.loads((ROOT/f'packet-case-{number}-150-0.json').read_text())
            byid={alias(r):r for r in base['rows']};core=[byid[i] for i in base['expected']]
            distractors=[r for r in base['rows'] if alias(r) not in base['expected']]
            for size in SIZES:
                rows=core+distractors[:size-len(core)]
                for repetition in range(2):
                    view=ordered(rows) if repetition==0 else random.Random(1701+size).sample(rows,len(rows))
                    packet={'case':base['case'],'size':size,'repetition':repetition,'seed':base['seed'],'rows':view,'expected':trace(view,base['seed'])}
                    path=ROOT/f"packet-{base['case']}-{size}-{repetition}.json";save(path,packet);files[path.name]=digest(path)
        save(saved,{'runner_sha256':digest(Path(__file__)),'fixture_hashes':files,'sizes':SIZES,
             'reason':'All original sizes had at least one invalid-edge response; test smaller contexts without changing task or scoring gate.',
             'gate':'At least 7/8 exact, zero invalid-edge answers, at most one failed call. Same four cases, no holdout claim.',
             'budget':'Same cumulative 240-request and 6-million-token provider budget, including configuration pilot.'})
    manifest=json.loads(saved.read_text());assert manifest['runner_sha256']==digest(Path(__file__))
    for name,sha in manifest['fixture_hashes'].items():assert digest(ROOT/name)==sha
    model=BudgetModel();jobs=[]
    for name in manifest['fixture_hashes']:
        packet=ROOT/name;directory=ROOT/('context-'+packet.stem.removeprefix('packet-'))
        if directory.exists():continue
        jobs.append((directory,packet))
    random.Random(601).shuffle(jobs)
    def execute(job):
        d,p=job
        try:return d.name,context_run(d,p,model)['status']
        except Exception as exc:
            d.mkdir(exist_ok=True);save(d/'failure.json',{'status':'failed','error':type(exc).__name__,'detail':str(exc)})
            return d.name,'failed'
    with ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(execute,jobs):print(json.dumps({'job':result}),flush=True)

def offline():
    verify_manifest();cases=json.loads((ROOT/'reference-sweep/cases.json').read_text())
    output=ROOT/'lower-view-sweep';output.mkdir(exist_ok=True)
    manifest={'source_sha256':digest(Path(__file__)),'cases_sha256':digest(ROOT/'reference-sweep/cases.json'),
              'settings':{'branches':4,'pages':[25,100],'views':SIZES},
              'purpose':'Downward context bracket; same retrieval caps and reference cases as the broader offline sweep.'}
    if (output/'manifest.json').exists():assert json.loads((output/'manifest.json').read_text())==manifest
    else:save(output/'manifest.json',manifest)
    results=[]
    for size in SIZES:
        for page in [25,100]:
            for spec in cases:
                directory=output/f"v{size}-p{page}-{spec['id']}"
                if (directory/'result.json').exists():result=json.loads((directory/'result.json').read_text())
                else:result=navigate(directory,spec,4,page,size)
                results.append({**result,'family':spec['family']})
            print(json.dumps({'view':size,'page':page,'cases':len(cases)}),flush=True)
    save(output/'results.json',results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['offline','live'])
    globals()[parser.parse_args().action]()
