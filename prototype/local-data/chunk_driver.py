"""Run the direct scheduler with a fresh Python process for every chunk."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from tools import HERE
from chunk_case import DEFAULTS

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('directory',type=Path)
    for name in ('view_rows','review_view_rows','max_request_bytes','max_query_pages','max_model_calls'):
        p.add_argument('--'+name.replace('_','-'),type=int,default=DEFAULTS[name])
    p.add_argument('--resume',action='store_true')
    p.add_argument('--additional-query-pages',type=int,default=0)
    p.add_argument('--additional-model-calls',type=int,default=0)
    p.add_argument('--review-partial',action='store_true')
    args=p.parse_args()
    def command(action):
        options=[]
        if action=='init':
            for name in ('view_rows','review_view_rows','max_request_bytes','max_query_pages','max_model_calls'):
                options.extend(['--'+name.replace('_','-'),str(getattr(args,name))])
        if action=='resume':
            options=['--additional-query-pages',str(args.additional_query_pages),'--additional-model-calls',str(args.additional_model_calls)]
        result=subprocess.run([sys.executable,str(HERE/'chunk_case.py'),action,str(args.directory),*options],
                              input='{}',capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stderr)
        data=json.loads(result.stdout)
        print(json.dumps({'phase':action,'result':data}),flush=True)
        return data
    command('resume' if args.resume else 'init')
    while json.loads((args.directory/'state.json').read_text())['status']=='active': command('segment')
    state=json.loads((args.directory/'state.json').read_text())
    if state['status']=='frontier_exhausted' or args.review_partial: command('review')
    command('audit')
