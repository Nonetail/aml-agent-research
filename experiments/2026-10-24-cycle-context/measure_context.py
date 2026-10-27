"""Reproducible local row-size measurements; source stays read-only and label-free."""
import csv
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
from importlib.metadata import version

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'prototype/local-data'))
from cycle_tools import CycleTools
from cycle_prompts import REVIEWER_SYSTEM, NAVIGATOR_SYSTEM, review_definition, navigation_definition
from cycle_workflow import encoded
from chunk_case import compact
from context_tokens import ContextTokens, TOKENIZER_REVISION

COLUMNS = ['id','time','from_bank','from_account','to_bank','to_account','paid',
           'paid_currency','received','received_currency','format']
FORMAT = ('Transaction IDs Tn resolve to original source row n under source_sha256. '
          'Rows are CSV with the declared columns. Find short temporal cycles using '
          'only these rows; no verified candidates or pending scopes are supplied.')


def request(rows, source_sha, serialization):
    metadata = {'source_sha256':source_sha, 'scope':['2022/09/01 00:00','2022/09/11 00:00'],
                'max_edges':4, 'max_duration_minutes':None, 'scopes':[], 'verified_candidates':[]}
    if serialization == 'raw_json':
        user = encoded({**metadata, 'rows':rows})
    else:
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(COLUMNS)
        writer.writerows(compact(row) for row in rows)
        user = encoded(metadata) + '\n' + stream.getvalue()
    definition = review_definition([], [])
    return {'messages':[{'role':'system','content':REVIEWER_SYSTEM + '\n' + FORMAT},
                        {'role':'user','content':user}],
            'tools':[{'type':'function','function':definition}],
            'tool_choice':{'type':'function','function':{'name':definition['name']}},
            'max_tokens':4096}


def main():
    counter = ContextTokens()
    source = ROOT / 'prototype/local-data/generated/transactions.sqlite'
    tools = CycleTools(source, '2022/09/01 00:00', '2022/09/11 00:00')
    try:
        rows = tools.seed_page(10000)['rows']
        sha = tools.sha
    finally:
        tools.close()
    result = {'tokenizer_revision':TOKENIZER_REVISION, 'python':platform.python_version(),
              'packages':{name:version(name) for name in ['transformers','tokenizers','jinja2']},
              'source_sha256':sha, 'sampling':'First 10000 external edges by original row ordinal; full ten-day source scope; no labels read.',
              'sample_rows':len(rows), 'row_identifiers_sha256':hashlib.sha256(encoded([r['transaction_id'] for r in rows]).encode()).hexdigest(),
              'system_tokens':{'reviewer':counter.text(REVIEWER_SYSTEM), 'navigator':counter.text(NAVIGATOR_SYSTEM)},
              'measurements':[], 'fits':[]}
    for serialization in ['raw_json','compact_csv']:
        empty = counter.count_request(request([],sha,serialization))
        for n in [0,500,1000,1500,2000,3000,4000,5000]:
            req = request(rows[:n],sha,serialization)
            prompt = counter.count_request(req)
            result['measurements'].append({'serialization':serialization, 'rows':n,
                'prompt_tokens':prompt, 'fixed_request_tokens':empty,
                'row_increment_tokens':prompt-empty, 'user_content_bytes':len(req['messages'][1]['content'].encode()),
                'with_output_4096_and_safety_4096':prompt+8192})
        for cap in [120000,200000,262144]:
            low,high=0,len(rows)
            while low < high:
                mid=(low+high+1)//2
                if counter.count_request(request(rows[:mid],sha,serialization))+8192<=cap:
                    low=mid
                else:
                    high=mid-1
            fit=counter.count_request(request(rows[:low],sha,serialization))
            next_count=counter.count_request(request(rows[:low+1],sha,serialization))
            result['fits'].append({'serialization':serialization,'total_cap':cap,
                'output_reserve':4096,'safety_reserve':4096,'rows':low,
                'prompt_tokens':fit,'next_prefix_prompt_tokens':next_count,
                'boundary_verified':fit+8192<=cap<next_count+8192})
    (HERE/'context-measurements.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
