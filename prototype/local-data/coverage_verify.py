"""Independent read-only certification of whole-dataset traversal coverage.

Checks source coverage, weak components, and scope/page accounting. It does not
certify model judgments or replay the contents represented by page digests.
"""
import argparse
import json
from pathlib import Path
import sqlite3


class AuditFailure(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditFailure(message)


def audit(ledger, database):
    db = sqlite3.connect(Path(ledger).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        db.execute('ATTACH DATABASE ? AS source', (Path(database).resolve().as_uri() + '?mode=ro',))
        db.execute('PRAGMA query_only=ON')
        meta = {key: json.loads(value) for key, value in db.execute('SELECT key,value FROM meta')}
        source_sha = db.execute("SELECT value FROM source.metadata WHERE key='source_sha256'").fetchone()
        require(source_sha and source_sha[0] == meta['source_sha256'], 'Source identity mismatch')
        start, end = meta['start'], meta['end']
        require(start < end, 'Invalid traversal time scope')
        source_count = db.execute('SELECT count(*) FROM source.transactions WHERE timestamp>=? AND timestamp<?', (start, end)).fetchone()[0]
        seen_count = db.execute('SELECT count(*) FROM seen').fetchone()[0]
        invalid = db.execute('''SELECT s.row_id FROM seen s LEFT JOIN source.transactions t USING(row_id)
            WHERE t.row_id IS NULL OR t.timestamp<? OR t.timestamp>=? LIMIT 1''', (start, end)).fetchone()
        require(invalid is None, 'Unknown or out-of-scope seen transaction')
        report = {'status': 'incomplete', 'source_sha256': meta['source_sha256'], 'start': start, 'end': end,
                  'source_rows': source_count, 'seen_rows': seen_count, 'missing_rows': source_count - seen_count,
                  'checks': [], 'limitations': ['Does not certify review or detection quality.',
                  'Page digest contents are not replayed; source coverage and page accounting are checked.',
                  'Source identity relies on database metadata; CSV bytes are not rehashed.']}
        if meta['status'] != 'complete':
            report['reason'] = 'Traversal has not declared completion; no full-coverage certification.'
            return report
        require(source_count == seen_count, 'Complete traversal is missing source transactions')

        # Account-sized memory: never retain the millions of transaction rows.
        nodes, parents, owners, counts, masks = {}, [], [], [], []
        def node(bank, account, component):
            key = (bank, account)
            index = nodes.get(key)
            if index is None:
                index = len(parents)
                nodes[key] = index
                parents.append(index)
                owners.append(component)
                counts.append([0, 0])
                masks.append(0)
            require(owners[index] == component, 'Connected transactions assigned to different components')
            return index

        def root(index):
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        components = {row[0]: row[1:] for row in db.execute('SELECT id,seed,status,revision FROM components')}
        for component, (seed, status, revision) in components.items():
            require(status == 'complete', 'Complete traversal contains an unfinished component')
            require(revision > 0, 'Invalid component revision')
            found = db.execute('SELECT component_id FROM seen WHERE row_id=?', (seed,)).fetchone()
            require(found and found[0] == component, 'Component seed is not owned by its component')
        for row_id, sb, sa, dbank, da, component in db.execute('''SELECT t.row_id,t.source_bank,t.source_account,
            t.destination_bank,t.destination_account,s.component_id FROM source.transactions t
            LEFT JOIN seen s USING(row_id) WHERE t.timestamp>=? AND t.timestamp<?''', (start, end)):
            require(component in components, 'Seen transaction has no valid component')
            left, right = node(sb, sa, component), node(dbank, da, component)
            counts[left][0] += 1
            counts[right][1] += 1
            lroot, rroot = root(left), root(right)
            if lroot != rroot:
                parents[rroot] = lroot
        component_roots = {}
        for index, owner in enumerate(owners):
            representative = root(index)
            previous = component_roots.setdefault(owner, representative)
            require(previous == representative, 'Disconnected graphs merged into one component')
        require(set(component_roots) == set(components), 'Empty or missing component')
        report['checks'].extend(['Exact source/seen row equality in scope', 'Exact weak-component partition'])

        # Pages are grouped by scope so only one page chain is held at a time.
        scope_count = page_count = 0
        page_rows = iter(db.execute('''SELECT scope_id,before_time,before_id,after_time,after_id,returned_count,complete
            FROM pages ORDER BY scope_id,id'''))
        next_page = next(page_rows, None)
        for scope in db.execute('SELECT id,bank,account,direction,component_id,after_time,after_id,status,pages FROM scopes ORDER BY id'):
            sid, bank, account, direction, owner, after_time, after_id, status, pages = scope
            index = nodes.get((bank, account))
            require(index is not None, 'Scope refers to an undiscovered account')
            require(owners[index] == owner, 'Scope belongs to the wrong component')
            require(direction in ('source', 'destination'), 'Invalid scope direction')
            position = 0 if direction == 'source' else 1
            bit = 1 << position
            require(not masks[index] & bit, 'Duplicate account/direction scope')
            masks[index] |= bit
            require(status == 'complete', 'Complete traversal contains an unfinished scope')
            previous = (None, None)
            total = number = 0
            terminal = False
            require(next_page is None or next_page[0] >= sid, 'Orphaned page records')
            while next_page is not None and next_page[0] == sid:
                _, before_t, before_id, after_t, page_after_id, returned, complete = next_page
                next_page = next(page_rows, None)
                require(not terminal, 'Page follows an exhausted scope')
                require((before_t, before_id) == previous, 'Broken page cursor chain')
                require(returned >= 0, 'Negative page row count')
                current = (after_t, page_after_id)
                if returned:
                    require(after_t is not None and page_after_id is not None, 'Nonempty page has no cursor')
                    require(start <= after_t < end, 'Page cursor outside time scope')
                    require(previous[0] is None or current > previous, 'Page cursor did not advance')
                else:
                    require(current == previous, 'Empty page changed cursor')
                    require(complete == 1, 'Empty page did not exhaust scope')
                require(complete in (0, 1), 'Invalid page completion marker')
                previous = current
                total += returned
                number += 1
                terminal = bool(complete)
            require(number == pages and number > 0, 'Scope page count mismatch')
            require(terminal, 'Complete scope has no final exhausted page')
            require(previous == (after_time, after_id), 'Scope cursor differs from final page')
            require(total == counts[index][position], 'Scope pages do not account for every source row')
            scope_count += 1
            page_count += number
        require(all(mask == 3 for mask in masks), 'Missing account/direction scope')
        require(next_page is None, 'Orphaned page records')
        report['checks'].append('Complete direction-scope inventory, cursor chains and exact row-count accounting')
        report.update(status='passed', accounts=len(nodes), components=len(components), scopes=scope_count, pages=page_count)
        return report
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger')
    parser.add_argument('--database', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        result = audit(args.ledger, args.database)
    except (AuditFailure, sqlite3.Error, KeyError, ValueError) as error:
        result = {'status': 'failed', 'error': str(error)}
    rendered = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + '\n')
    print(rendered)
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
