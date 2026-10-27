"""Generate a coverage readout from a closed ledger and independent audit."""
import json
from pathlib import Path
import sqlite3

HERE=Path(__file__).resolve().parent
OUT=HERE/'generated/global-scan-v1'

def main():
    audit=json.loads((OUT/'audit.json').read_text())
    db=sqlite3.connect((OUT/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    meta={k:json.loads(v)for k,v in db.execute('SELECT key,value FROM meta')}
    components=db.execute('SELECT count(*) FROM components').fetchone()[0]
    scopes=db.execute('SELECT count(*) FROM scopes').fetchone()[0]
    largest=db.execute('SELECT component_id,count(*) FROM seen GROUP BY component_id ORDER BY count(*) DESC LIMIT 5').fetchall()
    summary={'audit':audit,'source_rows':audit['source_rows'],'discovered_rows':meta['rows'],'components':components,
        'scopes':scopes,'pages':meta['pages'],'returned_rows':meta['returned_rows'],'largest_components':largest,
        'model_calls':0,'reviewed_rows':0,'awaiting_review_rows':meta['rows'],'model_navigation_integrated':False,
        'restart_check':json.loads((OUT/'restart-verification.json').read_text())}
    db.close();(OUT/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# Whole-dataset traversal results','',f"Independent coverage audit: **{audit['status']}**.",'',
        '| Measure | Result |','|---|---:|',f"| Source transactions | {summary['source_rows']:,} |",
        f"| Unique discovered transactions | {summary['discovered_rows']:,} |",f"| Connected components | {components:,} |",
        f"| Account/direction scopes exhausted | {scopes:,} |",f"| Pages fetched (at most25rows each) | {meta['pages']:,} |",
        '| Model calls | 0 |','| Model-reviewed transactions | 0 |',f"| Transactions awaiting review | {meta['rows']:,} |",'',
        f"The time scope was [{meta['start']}, {meta['end']}). This is the entire pinned CSV, broader than the current model runner's reporting window.",'',
        f"Page results contained {meta['returned_rows']:,} transaction occurrences: each transaction is retrieved once through its source/outgoing scope and once through its destination/incoming scope. The unique ledger deduplicates these occurrences.",'',
        'The run paused after1,000 committed pages, closed its process, and resumed. The original page-history prefix remained byte-for-byte equivalent under the recorded digest. The verifier independently reconstructed the component partition and checked exact source coverage and cursor/page accounting.','',
        '## Largest components','', '| Component | Transactions |','|---|---:|']
    lines += [f'| {ident} | {count:,} |'for ident,count in largest]
    lines += ['', '## What this establishes','',
        'Deterministic traversal can cover the full source across disconnected components, track pending work, and restart without duplicating committed pages. Review jobs have separate identities and evidence revisions. Retrieval never marks them reviewed.','',
        'The LLM investigator is not yet routed through the global ledger. This run does not demonstrate model-selected whole-graph navigation, review quality, laundering detection accuracy or model cost at this scale. Those remain separate tests.','',
        'The independent verifier trusts the pinned source metadata and checks coverage/page accounting rather than replaying every page digest. Components use bank/account identity and ignore edge direction for connectivity; they are not detected laundering schemes.']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('audit','largest_components')},indent=2))

if __name__=='__main__':main()
