"""Pure, label-blind view construction; cycle containment belongs to the evaluator.

Rows use CycleTools field names. Results contain exact IDs, never copied labels.
Graph grouping is a source-account bundle heuristic, not a cycle-preserving oracle.
"""
from collections import Counter, defaultdict, deque


def _endpoint(row, side):
    return row[side+'_bank'], row[side+'_account']


def _key(row):
    ident = row['transaction_id']
    ordinal = ident.rsplit(':', 1)[-1].removeprefix('T')
    return row['timestamp'], int(ordinal) if ordinal.isdecimal() else 0, ident


def _rows(rows):
    result = sorted(rows, key=_key)
    ids = [r['transaction_id'] for r in result]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Rows require distinct, nonempty transaction IDs')
    return result


def _account_order(rows, anchor_id):
    adjacency, sources, byid = defaultdict(Counter), set(), {}
    for row in rows:
        source, destination = _endpoint(row, 'source'), _endpoint(row, 'destination')
        adjacency[source][destination] += 1
        adjacency[destination][source] += 1
        sources.add(source)
        byid[row['transaction_id']] = row
    if anchor_id is not None and anchor_id not in byid:
        raise ValueError('Anchor is absent from rows')
    roots = sorted(adjacency, key=lambda a: (-sum(adjacency[a].values()), a))
    if anchor_id is not None:
        roots.insert(0, _endpoint(byid[anchor_id], 'source'))
    visited, order = set(), []
    for root in roots:
        if root in visited:
            continue
        queue = deque([root])
        visited.add(root)
        while queue:
            account = queue.popleft()
            if account in sources:
                order.append(account)
            neighbors = sorted(adjacency[account], key=lambda a: (-adjacency[account][a], a))
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
    return order


def partition_views(rows, partitions, strategy='graph', anchor_id=None):
    """Partition every ID once into 2/3/4 views, without consulting cycle supports.

    Graph views keep source-account bundles intact, so row sizes may differ. Cuts
    count edges whose destination has outgoing rows assigned to another view;
    destination-only accounts have no assigned bundle and are reported separately.
    """
    if type(partitions) is not int or partitions not in (2, 3, 4):
        raise ValueError('partitions must be 2, 3 or 4')
    rows = _rows(rows)
    if anchor_id is not None and anchor_id not in {r['transaction_id'] for r in rows}:
        raise ValueError('Anchor is absent from rows')
    if strategy == 'chronological':
        groups, offset = [], 0
        for index in range(partitions):
            count = len(rows)//partitions + (index < len(rows) % partitions)
            groups.append(rows[offset:offset+count])
            offset += count
    elif strategy == 'graph':
        bundles = defaultdict(list)
        for row in rows:
            bundles[_endpoint(row, 'source')].append(row)
        accounts = _account_order(rows, anchor_id)
        groups, offset, remaining = [], 0, len(rows)
        for index in range(partitions):
            group, target = [], remaining/(partitions-index)
            while offset < len(accounts):
                bundle = bundles[accounts[offset]]
                if group and abs(len(group)-target) < abs(len(group)+len(bundle)-target):
                    break
                group.extend(bundle)
                offset += 1
                if len(accounts)-offset <= partitions-index-1:
                    break
            groups.append(sorted(group, key=_key))
            remaining -= len(group)
    else:
        raise ValueError('strategy must be graph or chronological')
    source_groups = defaultdict(set)
    for index, group in enumerate(groups):
        for row in group:
            source_groups[_endpoint(row, 'source')].add(index)
    cuts, unassigned = [], []
    for index, group in enumerate(groups):
        for row in group:
            destination_groups = source_groups[_endpoint(row, 'destination')]
            if not destination_groups:
                unassigned.append(row['transaction_id'])
            elif index not in destination_groups:
                cuts.append(row['transaction_id'])
    return {'strategy': strategy, 'partitions': partitions,
            'views': [[r['transaction_id'] for r in group] for group in groups],
            'view_rows': [len(group) for group in groups], 'cut_edge_ids': cuts,
            'cut_edges': len(cuts), 'destination_without_source_bundle_ids': unassigned,
            'split_source_accounts': sum(len(g) > 1 for g in source_groups.values())}


def overlap_metrics(views):
    """Unique-ID accounting; overlap denominator is the later view, not union."""
    if len(views) != 2:
        raise ValueError('Provide exactly two views')
    left, right = map(set, views)
    shared, union, novel = left & right, left | right, right-left
    return {'first_rows': len(left), 'second_rows': len(right),
            'shared_rows': len(shared), 'union_rows': len(union), 'new_rows': len(novel),
            'overlap_fraction': len(shared)/len(right) if right else 0.0,
            'jaccard': len(shared)/len(union) if union else 0.0,
            'novelty_fraction': len(novel)/len(right) if right else 0.0}


def overlap_views(rows, anchor_id, view_rows, overlap_fraction, retained_ids=None, first_view_ids=None):
    """Construct two equal-sized views with a retained anchor and optional boundary.

    Caller may retain model-proposed evidence IDs. These are never inferred from
    gold supports here. A zero-overlap target still keeps that mandatory boundary.
    Pool exhaustion raises actual overlap instead of silently shrinking a view.
    first_view_ids freezes the baseline view and its order; retained IDs must be
    present there so the later condition cannot alter the baseline retroactively.
    """
    rows = _rows(rows)
    if type(view_rows) is not int or not 1 <= view_rows <= len(rows):
        raise ValueError('view_rows must be positive and no larger than the pool')
    if isinstance(overlap_fraction, bool) or not 0 <= overlap_fraction <= 1:
        raise ValueError('overlap_fraction must be between zero and one')
    byid = {r['transaction_id']: r for r in rows}
    mandatory = list(dict.fromkeys([anchor_id]+list(retained_ids or [])))
    if any(ident not in byid for ident in mandatory):
        raise ValueError('Retained IDs and anchor must exist in rows')
    if len(mandatory) > view_rows:
        raise ValueError('Mandatory retained boundary exceeds view_rows')
    ranks = {account: index for index, account in enumerate(_account_order(rows, anchor_id))}
    ordered = sorted(rows, key=lambda r: (ranks[_endpoint(r, 'source')], _key(r)))
    mandatory_set = set(mandatory)
    priority = mandatory+[r['transaction_id'] for r in ordered if r['transaction_id'] not in mandatory_set]
    first = priority[:view_rows] if first_view_ids is None else list(first_view_ids)
    if len(first) != view_rows or len(set(first)) != view_rows or any(i not in byid for i in first):
        raise ValueError('First view must contain view_rows distinct known IDs')
    if not mandatory_set <= set(first):
        raise ValueError('First view must contain the retained boundary and anchor')
    requested = int(view_rows*overlap_fraction+0.5)
    shared = max(requested, len(mandatory), 2*view_rows-len(rows))
    first_set = set(first)
    kept = [i for i in priority if i in first_set][:shared]
    novel = [i for i in priority if i not in first_set][:view_rows-shared]
    second = sorted(kept+novel, key=lambda i: _key(byid[i]))
    views = [first, second]
    return {'views': views, 'anchor_id': anchor_id, 'retained_ids': mandatory,
            'requested_overlap_fraction': overlap_fraction,
            'requested_shared_rows': requested, 'minimum_boundary_rows': len(mandatory),
            'pool_forced_minimum_shared_rows': max(0, 2*view_rows-len(rows)),
            'metrics': overlap_metrics(views)}
