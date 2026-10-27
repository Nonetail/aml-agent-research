"""Broader offline sensitivity sweep: deterministic, label-separated reference selection."""
import csv
import json
from pathlib import Path

from threshold_eval import ROOT, BRANCHES, PAGES, VIEWS, SCOPE, digest, navigate, ordered, verify_manifest
from chunk_case import alias
from tools import HERE, Tools
from run_case import save

OUT=ROOT/'reference-sweep'


def prepare():
    OUT.mkdir(exist_ok=True)
    if (OUT/'cases.json').exists():return json.loads((OUT/'cases.json').read_text())
    tools=Tools(receipts=OUT/'preparation-receipts.sqlite');groups=[]
    for line in (HERE.parents[1]/'data/HI-Small_Patterns.txt').read_text().splitlines():
        if line.startswith('BEGIN'):groups.append({'name':line,'rows':[]})
        elif line.startswith('2022/'):groups[-1]['rows'].append(next(csv.reader([line])))
    cases=[]
    try:
        for family in ['CYCLE','RANDOM','FAN-IN','FAN-OUT']:
            selected=0
            for index,g in enumerate(groups):
                if f' - {family}:' not in g['name'] or not 3<=len(g['rows'])<=12 or not all(SCOPE[0]<=r[0]<SCOPE[1] for r in g['rows']):continue
                matched=[]
                for r in g['rows']:
                    hits=tools.db.execute('''SELECT * FROM transactions WHERE source_bank=? AND source_account=? AND timestamp=?
                        AND destination_bank=? AND destination_account=? AND received_amount=? AND received_currency=?
                        AND paid_amount=? AND paid_currency=? AND payment_format=?''',
                        (r[1].lstrip('0') or '0',r[2],r[0],r[3].lstrip('0') or '0',r[4],*r[5:10])).fetchall()
                    if len(hits)!=1:raise ValueError('Ambiguous reference row')
                    matched.append(tools._row(hits[0]))
                matched=ordered(matched)
                cases.append({'id':f'{family.lower()}-{index}','description':g['name'],'family':family,'pattern_index':index,
                              'seed_id':int(alias(matched[0])[1:]),'target_ids':[alias(r) for r in matched]})
                selected+=1
                if selected==4:break
            if selected<4:raise ValueError('Fewer than four eligible references for '+family)
    finally:tools.close()
    save(OUT/'cases.json',cases)
    save(OUT/'manifest.json',{'selection':'First four fully in-scope publisher groups of 3..12 edges per CYCLE/RANDOM/FAN-IN/FAN-OUT family. Enriched development sensitivity analysis; not prevalence or model accuracy.',
        'cases_sha256':digest(OUT/'cases.json'),'runner_sha256':digest(Path(__file__)),
        'main_manifest_sha256':digest(ROOT/'manifest.json'),'decision_rule':'Within 0.05 of best macro additional reference recall, then lowest returned rows, then lowest query pages.'})
    return cases


def main():
    verify_manifest();cases=prepare();manifest=json.loads((OUT/'manifest.json').read_text())
    assert digest(OUT/'cases.json')==manifest['cases_sha256'] and digest(Path(__file__))==manifest['runner_sha256']
    results=[]
    settings=[(b,p,300) for b in BRANCHES for p in PAGES]+[(4,100,v) for v in VIEWS if v!=300]
    for branches,page,view in settings:
        for spec in cases:
            directory=OUT/f"b{branches}-p{page}-v{view}-{spec['id']}"
            if (directory/'result.json').exists():result=json.loads((directory/'result.json').read_text())
            else:result=navigate(directory,spec,branches,page,view)
            results.append({**result,'family':spec['family']})
        print(json.dumps({'branches':branches,'page':page,'view':view,'completed_cases':len(cases)}),flush=True)
    save(OUT/'results.json',results)
    print(json.dumps({'completed_runs':len(results),'reference_cases':len(cases)}),flush=True)

if __name__=='__main__':main()
