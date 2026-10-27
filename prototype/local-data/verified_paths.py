"""Bounded deterministic path candidates from collected evidence, never labels.

One earliest-later continuation per starting edge; this is not exhaustive search.
Independent database verification remains mandatory before model review.
"""
from bisect import bisect_right
import hashlib
import json


def identity(row,side):
    return row[side+'_bank'],row[side+'_account']


def build_paths(evidence,max_paths=None,max_edges=6):
    ordered=sorted(evidence,key=lambda i:(evidence[i]['timestamp'],int(i[1:])))
    outgoing={}
    for i in ordered:
        row=evidence[i]
        if identity(row,'source')!=identity(row,'destination'):
            outgoing.setdefault(identity(row,'source'),[]).append(i)
    times={key:[evidence[i]['timestamp'] for i in ids] for key,ids in outgoing.items()}
    paths=[];eligible=0
    for start in ordered:
        first=evidence[start]
        if identity(first,'source')==identity(first,'destination'): continue
        ids=[start]
        while len(ids)<max_edges:
            last=evidence[ids[-1]];key=identity(last,'destination')
            options=outgoing.get(key,[])
            pos=bisect_right(times.get(key,[]),last['timestamp'])
            if pos==len(options): break
            ids.append(options[pos])
            if identity(evidence[ids[-1]],'destination')==identity(first,'source'): break
        if len(ids)<2: continue
        eligible+=1
        paths.append({'id':'P'+str(len(paths)+1),'ids':ids,
                      'cycle':identity(evidence[ids[-1]],'destination')==identity(first,'source')})
    # Collapse contained non-cyclic subpaths; keep closed cycles and partially overlapping routes distinct.
    retained=[]; covered=set()
    for path in sorted(paths,key=lambda p:(-len(p['ids']),tuple(p['ids']))):
        signature=tuple(path['ids'])
        if signature in covered and not path['cycle']: continue
        path['id']='P'+hashlib.sha256(json.dumps(path['ids']).encode()).hexdigest()[:16]
        retained.append(path)
        for start in range(len(signature)-1):
            for end in range(start+2,len(signature)+1):covered.add(signature[start:end])
    deduplicated=len(paths)-len(retained)
    selected=retained if max_paths is None else retained[:max_paths]
    return selected,{'eligible_start_edges':eligible,'selected_paths':len(selected),
                  'deduplicated_subpaths':deduplicated,'omitted_start_edges':len(retained)-len(selected),
                  'max_paths':max_paths,'max_edges':max_edges,
                  'method':'Earliest strictly later external edge, numeric row-ID tie break, stop at closure or edge cap; collapse contiguous subpaths.',
                  'limitation':'Collected evidence only; alternative continuations and longer paths are not enumerated. No path is not evidence of benign activity.'}


def review_packets(evidence,paths,row_limit):
    packets=[];view=[];batch=[];seen=set()
    for path in paths:
        merged=list(dict.fromkeys(view+path['ids']))
        if len(merged)>row_limit or len(batch)==6:
            packets.append({'view':view,'paths':batch});seen.update(view)
            view=[];batch=[];merged=list(path['ids'])
        view=merged;batch.append(path)
    if view:
        packets.append({'view':view,'paths':batch});seen.update(view)
    remaining=[i for i in evidence if i not in seen]
    for offset in range(0,len(remaining),row_limit):
        packets.append({'view':remaining[offset:offset+row_limit],'paths':[]})
    return packets
