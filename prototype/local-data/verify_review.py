"""Regression check on previous context packets; optional four real-model reviews.

Uses existing development fixtures. No detection or representative-sample claim.
Expected traces stay evaluator-side and are never passed to the reviewer.
"""
import argparse
import json
from chunk_case import Case, init, alias
from tools import HERE, Tools
from verified_paths import build_paths, review_packets
from run_case import save

ROOT=HERE/'generated/verified-review-v2'


def main(live=False):
    ROOT.mkdir(exist_ok=True)
    api=Tools(receipts=ROOT/'verification-receipts.sqlite');results=[]
    try:
        for file in sorted((HERE/'generated/thresholds-v2').glob('packet-*.json')):
            packet=json.loads(file.read_text());evidence={alias(r):r for r in packet['rows']}
            paths,coverage=build_paths(evidence)
            for path in paths:
                result=api.verify_path([evidence[i]['transaction_id'] for i in path['ids']],strict=True,cycle=path['cycle'])
                assert result['valid'],(file.name,path,result)
            expected=packet['expected'];seed_paths=[p for p in paths if p['ids'][0]==packet['seed']]
            if len(expected)==1: assert not seed_paths,(file.name,seed_paths)
            else: assert seed_paths and seed_paths[0]['ids'][:len(expected)]==expected,(file.name,seed_paths)
            for p in review_packets(evidence,paths,150):
                assert len(p['view'])<=150
                assert all(set(x['ids'])<=set(p['view']) for x in p['paths'])
            results.append({'packet':file.name,'paths':len(paths),'seed_trace_matches':True,'coverage':coverage})
        save(ROOT/'offline.json',{'packets':len(results),'all_paths_database_valid':True,'seed_controls_passed':True,'results':results})
    finally: api.close()
    if live:
        for n in range(1,5):
            packet=json.loads((HERE/f'generated/thresholds-v2/packet-case-{n}-150-0.json').read_text())
            directory=ROOT/f'live-case-{n}'
            init(directory)
            case=Case(directory)
            try:
                case.state.update(evidence={alias(r):r for r in packet['rows']},seed=packet['seed'],
                                  anchors=[packet['seed']],queries={},status='review_fixture',presented=[])
                case.persist();case.review();case.audit()
                print(json.dumps({'case':n,'status':'completed','calls':len(case.state['calls'])}),flush=True)
            except Exception as e:
                save(directory/'failure.json',{'error':str(e),'type':type(e).__name__})
                print(json.dumps({'case':n,'status':'failed','error':str(e)}),flush=True)
            finally:case.close()
    print(json.dumps({'offline_packets':len(results),'all_paths_database_valid':True}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--live',action='store_true')
    main(p.parse_args().live)
