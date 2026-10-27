"""Independently audit persisted threshold results against source rows and receipts."""
import json
from pathlib import Path
import sqlite3

from threshold_eval import ROOT, VIEWS, verify_manifest, trace, check_trace, TRACE_INSTRUCTION, TRACE_SYSTEM, COLUMNS
from chunk_case import alias, compact
from tools import Tools
from run_case import save


def audit_directory(path,tools):
    state=json.loads((path/'state.json').read_text())
    source=[];ids=[r['transaction_id'] for r in state['evidence'].values()]
    for start in range(0,len(ids),500):source.extend(tools.get_transactions(ids[start:start+500])['rows'])
    assert {alias(r):r for r in source}==state['evidence'],path
    assert len(state['actions'])<=24,path
    log=sqlite3.connect(path/'receipts.sqlite');last={};returned=0
    for action in state['actions']:
        stored=log.execute('SELECT tool,parameters,result FROM receipts WHERE id=?',(action['receipt_id'],)).fetchone()
        assert stored and stored[0]=='fetch_transactions',path
        assert json.loads(stored[1])==action['arguments'],path
        result=json.loads(stored[2]);key=action['query_id']
        assert action['arguments'].get('cursor')==last.get(key),path
        assert action['next_cursor']==result['next_cursor'],path
        assert action['returned_ids']==[alias(r) for r in result['rows']],path
        assert len(result['rows'])<=action['arguments']['limit']<=500,path
        last[key]=action['next_cursor'];returned+=len(result['rows'])
    log.close()
    assert returned<=599,path
    assert all(state['queries'][k]['cursor']==v for k,v in last.items()),path
    assert len(state['evidence'])<=returned+1,path
    if (path/'navigation.json').exists():
        nav=json.loads((path/'navigation.json').read_text())
        assert len(nav['steps'])<=12,path
        assert all(s['view_size']<=state['limits']['view_rows'] for s in nav['steps']),path
        for h in nav['handoffs']:
            assert set(h['before'])<=set(state['evidence']),path
            assert h['after']==list(dict.fromkeys([state['seed']]+h['before'][-6:])),path
    for request in path.glob('*request.json'):
        raw=request.read_text()
        assert 'is_laundering' not in raw.lower() and 'target_ids' not in raw and 'pattern_index' not in raw,request
    if state['review']:
        assert set(state['review']['presented_ids'])==set(state['evidence']),path
        for finding in state['review']['findings']:
            candidate=finding['candidate'];expected=tools.verify_path([state['evidence'][i]['transaction_id'] for i in candidate['ids']],strict=True,cycle=candidate['cycle'])
            assert expected['valid']==finding['check']['valid'],path
    return {'directory':path.name,'rows':len(ids),'actions':len(state['actions']),'review_complete':bool(state['review'])}


def main():
    manifest=verify_manifest();tools=Tools(receipts=ROOT/'verification-receipts.sqlite')
    runs=[];packets=[]
    try:
        assert tools.sha==manifest['source_sha256']
        directories=list(ROOT.iterdir())
        for name in ['reference-sweep','lower-view-sweep']:
            if (ROOT/name).exists():directories.extend((ROOT/name).iterdir())
        for directory in sorted(directories):
            if directory.is_dir() and (directory/'state.json').exists():runs.append(audit_directory(directory,tools))
        for path in sorted(ROOT.glob('packet-*.json')):
            packet=json.loads(path.read_text());rows=packet['rows']
            assert len(rows)==packet['size'] and len({alias(r) for r in rows})==packet['size']
            assert trace(rows,packet['seed'])==packet['expected']
            ids=[r['transaction_id'] for r in rows];exact=[]
            for start in range(0,len(ids),500):exact.extend(tools.get_transactions(ids[start:start+500])['rows'])
            assert {alias(r):r for r in exact}=={alias(r):r for r in rows},path
            directory=ROOT/('context-'+path.stem.removeprefix('packet-'))
            if (directory/'request.json').exists():
                request=json.loads((directory/'request.json').read_text())
                payload=json.loads(request['messages'][-1]['content'])
                assert request['messages'][0]['content']==TRACE_SYSTEM
                assert payload=={'seed':packet['seed'],'columns':COLUMNS,'rows':[compact(r) for r in rows],'instruction':TRACE_INSTRUCTION}
            if (directory/'result.json').exists():
                result=json.loads((directory/'result.json').read_text())
                expected=check_trace(rows,packet['seed'],result['returned'])
                assert all(result[k]==v for k,v in expected.items()),path
            packets.append(path.name)
    finally:tools.close()
    report={'source_identity':manifest['source_sha256'],'runs_audited':len(runs),'packets_audited':len(packets),
            'all_source_rows_match':True,'row_and_page_budgets_valid':True,'receipt_cursor_chains_valid':True,
            'context_requests_exclude_answers':True,'deterministic_scores_recomputed':True,
            'run_details':runs,'note':'Only current saved runs/packets audited; this does not imply all planned model jobs completed.'}
    save(ROOT/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='run_details'}))

if __name__=='__main__':main()
