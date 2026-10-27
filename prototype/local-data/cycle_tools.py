"""Read-only, label-free navigation for simple, strictly time-ordered cycles.

The caller persists partial paths and page cursors. Row budgets bound one response;
an incomplete response always carries the cursor needed to finish that branch.
"""
import base64
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

from tools import timestamp


COLUMNS = ('row_id,timestamp,source_bank,source_account,destination_bank,'
           'destination_account,received_amount,received_currency,paid_amount,'
           'paid_currency,payment_format,raw_source_bank,raw_destination_bank')
LIMITATION = ('Checks simple cycle topology and recorded chronology only; does not '
              'establish the same funds, beneficial ownership, intent, or laundering.')
PAGE_MEANING = ('Complete means no eligible rows remain after this page; retain '
                'earlier pages to cover the full query.')


class CycleTools:
    def __init__(self, database, start, end, max_edges=4, max_duration_minutes=None):
        self.start, self.end = timestamp(start), timestamp(end)
        if self.start >= self.end:
            raise ValueError('start must precede end; scope is [start,end)')
        if type(max_edges) is not int or not 2 <= max_edges <= 4:
            raise ValueError('max_edges must be 2..4')
        if max_duration_minutes is not None and (type(max_duration_minutes) is not int or max_duration_minutes < 1):
            raise ValueError('max_duration_minutes must be a positive integer or None')
        self.max_edges, self.max_duration_minutes = max_edges, max_duration_minutes
        path = Path(database).resolve()
        self.db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)
        self.db.row_factory = sqlite3.Row
        try:
            self.sha = self.db.execute("SELECT value FROM metadata WHERE key='source_sha256'").fetchone()[0]
            stat = path.stat()
            self.identity = hashlib.sha256(json.dumps([
                str(path), stat.st_size, stat.st_mtime_ns, self.sha,
                start, end, max_edges, max_duration_minutes,
            ]).encode()).hexdigest()
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    @staticmethod
    def _budget(value):
        if type(value) is not int or not 1 <= value <= 10000:
            raise ValueError('Row budget must be 1..10000')

    @staticmethod
    def _source(row):
        return row['source_bank'], row['source_account']

    @staticmethod
    def _destination(row):
        return row['destination_bank'], row['destination_account']

    def _row(self, row):
        result = dict(row)
        result['transaction_id'] = f"{self.sha}:{result.pop('row_id')}"
        return result

    def _ordinal(self, ident):
        if not isinstance(ident, str) or ':' not in ident:
            raise ValueError('Invalid transaction identity')
        source, ordinal = ident.rsplit(':', 1)
        if (source != self.sha or not ordinal.isdecimal() or
                len(ordinal) > 19 or not 0 < int(ordinal) <= 9223372036854775807 or str(int(ordinal)) != ordinal):
            raise ValueError('Invalid transaction identity')
        return int(ordinal)

    def _cursor(self, query, after):
        return base64.urlsafe_b64encode(json.dumps({
            'source_scope': self.identity, 'query': query, 'after': after,
        }, separators=(',', ':')).encode()).decode()

    def _position(self, cursor, query):
        if cursor is None:
            return None
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor))
            if decoded['source_scope'] != self.identity or decoded['query'] != query:
                raise ValueError('Cursor belongs to another source, scope, path, or policy')
            return decoded['after']
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError('Invalid cursor') from error

    def seed_page(self, limit=300, cursor=None):
        """Page external edges by original row ordinal, not by global chronology."""
        self._budget(limit)
        after = self._position(cursor, 'seeds')
        if after is not None and (type(after) is not int or not 0 < after <= 9223372036854775807):
            raise ValueError('Invalid seed cursor position')
        rows = self.db.execute(f'''SELECT {COLUMNS} FROM transactions
            WHERE row_id>? AND timestamp>=? AND timestamp<?
                AND (source_bank<>destination_bank OR source_account<>destination_account)
            ORDER BY row_id LIMIT ?''', (after or 0, self.start, self.end, limit+1)).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        return {'rows': [self._row(row) for row in rows],
                'next_cursor': self._cursor('seeds', rows[-1]['row_id']) if more else None,
                'complete': not more, 'completeness_meaning': PAGE_MEANING,
                'order': 'original_row_id', 'authorized_scope': [self.start, self.end]}

    def get_transactions(self, transaction_ids):
        """Return authoritative evidence in requested order, without evaluator data."""
        if not isinstance(transaction_ids, list) or not 1 <= len(transaction_ids) <= 10000:
            raise ValueError('Provide 1..10000 transaction IDs as a list')
        ordinals = [self._ordinal(ident) for ident in transaction_ids]
        unique = list(dict.fromkeys(ordinals))
        found = {}
        for offset in range(0, len(unique), 400):
            batch = unique[offset:offset+400]
            placeholders = ','.join('?' for _ in batch)
            rows = self.db.execute(f'''SELECT {COLUMNS} FROM transactions
                WHERE row_id IN ({placeholders}) AND timestamp>=? AND timestamp<?''',
                batch+[self.start, self.end]).fetchall()
            found.update((row['row_id'], self._row(row)) for row in rows)
        return {'rows': [found[ordinal] for ordinal in ordinals if ordinal in found],
                'unavailable_ids': [ident for ident, ordinal in zip(transaction_ids, ordinals) if ordinal not in found]}

    def _path_facts(self, transaction_ids, cycle):
        minimum, maximum = (2, self.max_edges) if cycle else (1, self.max_edges-1)
        if not isinstance(transaction_ids, list) or not minimum <= len(transaction_ids) <= maximum:
            raise ValueError(f'Provide {minimum}..{maximum} ordered transaction IDs')
        evidence = self.get_transactions(transaction_ids)
        errors, rows = [], evidence['rows']
        result = dict(evidence, transaction_ids=transaction_ids, elapsed_minutes=None,
                      nodes=[], currencies=[], limitation=LIMITATION)
        if evidence['unavailable_ids']:
            return dict(result, valid=False, errors=['Missing or out-of-scope transaction IDs'])
        if len(set(transaction_ids)) != len(transaction_ids):
            errors.append('Repeated transaction edge')
        if any(self._source(row) == self._destination(row) for row in rows):
            errors.append('Self-transfer is not an external path edge')
        for left, right in zip(rows, rows[1:]):
            if self._destination(left) != self._source(right):
                errors.append('Disconnected bank/account endpoints')
            if left['timestamp'] >= right['timestamp']:
                errors.append('Timestamps are not strictly increasing at source minute precision')
        nodes = [self._source(rows[0])]+[self._destination(row) for row in rows]
        closed = nodes[-1] == nodes[0]
        if cycle and not closed:
            errors.append('Path does not close to the starting bank/account')
        if not cycle and closed:
            errors.append('Partial path already closes')
        distinct_nodes = nodes[:-1] if cycle and closed else nodes
        if len(set(distinct_nodes)) != len(distinct_nodes):
            errors.append('Repeated internal bank/account node')
        elapsed = int((datetime.strptime(rows[-1]['timestamp'], '%Y/%m/%d %H:%M') -
                       datetime.strptime(rows[0]['timestamp'], '%Y/%m/%d %H:%M')).total_seconds()/60)
        if self.max_duration_minutes is not None and elapsed > self.max_duration_minutes:
            errors.append('Path exceeds configured maximum duration')
        return dict(result, valid=not errors, errors=sorted(set(errors)), elapsed_minutes=elapsed,
                    nodes=[{'bank': bank, 'account': account} for bank, account in nodes],
                    currencies=sorted({row[side+'_currency'] for row in rows for side in ('paid', 'received')}))

    def verify_cycle(self, transaction_ids):
        """Validate cycle facts, independently of any model's assessment."""
        return self._path_facts(transaction_ids, cycle=True)

    def expand_frontier(self, paths, row_budget=300, cursors=None):
        """Batch all eligible continuations; preserve competing branches and closures.

        A path is an ordered list of IDs. cursors is a parallel list, initially None.
        Resume only branches with complete=False; None starts a branch from its first
        page. Results contain all eligible extensions on the page, not a chosen path.
        """
        self._budget(row_budget)
        if not isinstance(paths, list) or not 1 <= len(paths) <= 128 or len(paths) > row_budget:
            raise ValueError('Provide 1..128 paths and at least one budgeted row per path')
        if cursors is None:
            cursors = [None]*len(paths)
        if not isinstance(cursors, list) or len(cursors) != len(paths):
            raise ValueError('cursors must be a parallel list matching paths')
        branches = []
        for index, (path, cursor) in enumerate(zip(paths, cursors)):
            facts = self._path_facts(path, cycle=False)
            if not facts['valid']:
                raise ValueError('Invalid partial path: '+'; '.join(facts['errors']))
            evidence = facts['rows']
            first, last = evidence[0], evidence[-1]
            query = {'path': path}
            after = self._position(cursor, query)
            if after is not None:
                if (not isinstance(after, list) or len(after) != 2 or type(after[1]) is not int or
                        not 0 < after[1] <= 9223372036854775807 or
                        not last['timestamp'] < timestamp(after[0]) < self.end):
                    raise ValueError('Invalid continuation cursor position')
            clauses = ['source_bank=?', 'source_account=?', 'timestamp>?', 'timestamp<?',
                       '(source_bank<>destination_bank OR source_account<>destination_account)']
            params = [*self._destination(last), last['timestamp'], self.end]
            if self.max_duration_minutes is not None:
                deadline = (datetime.strptime(first['timestamp'], '%Y/%m/%d %H:%M')+
                            timedelta(minutes=self.max_duration_minutes)).strftime('%Y/%m/%d %H:%M')
                clauses.append('timestamp<=?')
                params.append(deadline)
            if len(path) == self.max_edges-1:
                clauses.extend(['destination_bank=?', 'destination_account=?'])
                params.extend(self._source(first))
            else:
                # Revisiting the root closes a cycle; other visited nodes cannot recur.
                for row in evidence:
                    clauses.append('NOT (destination_bank=? AND destination_account=?)')
                    params.extend(self._destination(row))
            if after is not None:
                clauses.append('(timestamp,row_id)>(?,?)')
                params.extend(after)
            limit = row_budget//len(paths)+(index < row_budget % len(paths))
            rows = self.db.execute(f'''SELECT {COLUMNS} FROM transactions
                WHERE {' AND '.join(clauses)} ORDER BY timestamp,row_id LIMIT ?''', params+[limit+1]).fetchall()
            more = len(rows) > limit
            rows = rows[:limit]
            next_cursor = self._cursor(query, [rows[-1]['timestamp'], rows[-1]['row_id']]) if more else None
            records = [self._row(row) for row in rows]
            cycles, continuations = [], []
            for row in records:
                target = cycles if self._destination(row) == self._source(first) else continuations
                target.append(path+[row['transaction_id']])
            branches.append({'transaction_ids': path, 'rows': records, 'cycles': cycles,
                             'continuations': continuations, 'next_cursor': next_cursor, 'complete': not more})
        return {'branches': branches, 'rows_returned': sum(len(branch['rows']) for branch in branches),
                'complete': all(branch['complete'] for branch in branches),
                'completeness_meaning': PAGE_MEANING,
                'eligible_extension_policy': 'External, strictly later, simple paths; final permitted edge must close.',
                'authorized_scope': [self.start, self.end]}
