"""Bounded, label-free tools. Expose dispatch(), never SQL or filesystem access."""
import argparse
import base64
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid

HERE = Path(__file__).resolve().parent

def timestamp(value):
    if datetime.strptime(value, '%Y/%m/%d %H:%M').strftime('%Y/%m/%d %H:%M') != value:
        raise ValueError('Use YYYY/MM/DD HH:MM source timestamps')
    return value

class Tools:
    def __init__(self, database=HERE/'generated/transactions.sqlite', receipts=HERE/'generated/receipts.sqlite',
                 history_start='2022/09/01 00:00', cutoff='2022/09/11 00:00', timeout=5):
        self.history_start, self.cutoff = timestamp(history_start), timestamp(cutoff)
        if self.history_start >= self.cutoff:
            raise ValueError('Invalid run scope')
        self.timeout = timeout
        self.db = sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)
        self.db.row_factory = sqlite3.Row
        self.sha = self.db.execute("SELECT value FROM metadata WHERE key='source_sha256'").fetchone()[0]
        self.log = sqlite3.connect(receipts)
        self.log.execute('''CREATE TABLE IF NOT EXISTS receipts
            (id TEXT PRIMARY KEY, tool TEXT, parameters TEXT, result TEXT, seconds REAL)''')
        self.log.commit()

    def close(self):
        self.db.close(); self.log.close()

    def _row(self, row):
        result = dict(row)
        result['transaction_id'] = f"{self.sha}:{result.pop('row_id')}"
        return result

    def _scope(self, bank, account, start, end, direction):
        timestamp(start); timestamp(end)
        if not self.history_start <= start < end <= self.cutoff:
            raise ValueError('Query is outside the authorized history/cutoff')
        if direction not in ('incoming', 'outgoing'):
            raise ValueError('direction must be incoming or outgoing')
        if not isinstance(bank, str) or not bank.isdecimal() or not isinstance(account, str) or not account:
            raise ValueError('bank/account must be nonempty string identifiers')
        return {'bank': bank.lstrip('0') or '0', 'account': account, 'start': start, 'end': end, 'direction': direction}

    def _fetch(self, bank, account, start, end, direction, limit=100, cursor=None):
        scope = self._scope(bank, account, start, end, direction)
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('limit must be 1..500')
        identity = hashlib.sha256(json.dumps([self.sha, scope], sort_keys=True).encode()).hexdigest()
        prefix = 'source' if direction == 'outgoing' else 'destination'
        where = f'{prefix}_bank=? AND {prefix}_account=? AND timestamp>=? AND timestamp<?'
        params = [scope['bank'], account, start, end]
        if cursor:
            decoded = json.loads(base64.urlsafe_b64decode(cursor))
            if decoded['scope'] != identity:
                raise ValueError('Cursor belongs to another query/source')
            after = decoded['after']
            if len(after) != 2 or type(after[1]) is not int or not start <= timestamp(after[0]) < end:
                raise ValueError('Invalid cursor position')
            where += ' AND (timestamp,row_id)>(?,?)'
            params.extend(after)
        rows = self.db.execute(f'SELECT * FROM transactions WHERE {where} ORDER BY timestamp,row_id LIMIT ?', params+[limit+1]).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = None
        if more:
            next_cursor = base64.urlsafe_b64encode(json.dumps({'scope': identity, 'after': [rows[-1]['timestamp'], rows[-1]['row_id']]}).encode()).decode()
        return {'scope': scope, 'rows': [self._row(r) for r in rows], 'next_cursor': next_cursor,
                'complete': not more, 'completeness_meaning': 'no remaining rows after this page; prior pages are required for full scope'}

    def fetch_transactions(self, **args):
        return self._fetch(**args)

    def get_transactions(self, transaction_ids):
        if not 1 <= len(transaction_ids) <= 500:
            raise ValueError('Provide 1..500 transaction IDs')
        rows, unavailable = [], []
        for ident in transaction_ids:
            source, ordinal = ident.rsplit(':', 1)
            if source != self.sha or not ordinal.isdecimal() or not 0 < int(ordinal) <= 9223372036854775807:
                raise ValueError('Invalid transaction identity')
            row = self.db.execute('SELECT * FROM transactions WHERE row_id=? AND timestamp>=? AND timestamp<?',
                                  (int(ordinal), self.history_start, self.cutoff)).fetchone()
            if row is None:
                unavailable.append(ident)
            else:
                rows.append(self._row(row))
        return {'rows': rows, 'unavailable_ids': unavailable}

    def get_accounts(self, accounts):
        if not 1 <= len(accounts) <= 100:
            raise ValueError('Provide 1..100 bank/account pairs')
        result = []
        for key in accounts:
            scope = self._scope(key['bank'], key['account'], self.history_start, self.cutoff, 'outgoing')
            row = self.db.execute('SELECT * FROM accounts WHERE bank=? AND account=?',
                                  (scope['bank'], scope['account'])).fetchone()
            result.append(dict(row) if row else {'bank': scope['bank'], 'account': scope['account'], 'unavailable': True})
        return {'accounts': result, 'limitation': 'Static synthetic entity metadata; not verified beneficial ownership'}

    def expand_frontier(self, queries):
        if not 1 <= len(queries) <= 8 or sum(q.get('limit', 100) for q in queries) > 500:
            raise ValueError('At most 8 branches and 500 total requested rows')
        return {'branches': [self._fetch(**query) for query in queries]}

    def summarize_activity(self, bank, account, start, end, direction):
        scope = self._scope(bank, account, start, end, direction)
        cursor, count, totals, counterparties = None, 0, defaultdict(Decimal), set()
        first = last = None
        with localcontext() as ctx:
            ctx.prec = 100
            while count < 10000:
                page = self._fetch(**scope, limit=500, cursor=cursor)
                for r in page['rows']:
                    count += 1
                    first = first or r['timestamp']; last = r['timestamp']
                    side = 'paid' if direction == 'outgoing' else 'received'
                    totals[r[side+'_currency']] += Decimal(r[side+'_amount'])
                    other = 'destination' if direction == 'outgoing' else 'source'
                    key = (r[other+'_bank'], r[other+'_account'])
                    if key != (scope['bank'], account):
                        counterparties.add(key)
                cursor = page['next_cursor']
                if cursor is None:
                    break
        return {'scope': scope, 'rows_scanned': count, 'external_counterparties': len(counterparties),
                'totals_by_currency': {k: str(v) for k,v in totals.items()}, 'first': first, 'last': last,
                'complete': cursor is None, 'next_cursor': cursor,
                'limitation': None if cursor is None else 'Partial totals only: 10000-row work cap reached'}

    def verify_path(self, transaction_ids, strict=True, cycle=False):
        if type(strict) is not bool or type(cycle) is not bool or not 2 <= len(transaction_ids) <= 100:
            raise ValueError('Path needs 2..100 IDs and boolean options')
        result = self.get_transactions(transaction_ids)
        errors = []
        if result['unavailable_ids']:
            return {'valid': False, 'errors': ['Missing or out-of-scope transaction IDs']}
        rows = result['rows']
        if len(set(transaction_ids)) != len(transaction_ids):
            errors.append('Repeated transaction edge')
        source = lambda r: (r['source_bank'], r['source_account'])
        dest = lambda r: (r['destination_bank'], r['destination_account'])
        if any(source(r) == dest(r) for r in rows):
            errors.append('Self-transfer is not an external path edge')
        for a,b in zip(rows, rows[1:]):
            if dest(a) != source(b): errors.append('Disconnected endpoints')
            if a['timestamp'] > b['timestamp'] or (strict and a['timestamp'] == b['timestamp']):
                errors.append('Time ordering failed')
        if cycle and dest(rows[-1]) != source(rows[0]): errors.append('Path does not close')
        minutes = int((datetime.strptime(rows[-1]['timestamp'], '%Y/%m/%d %H:%M')-datetime.strptime(rows[0]['timestamp'], '%Y/%m/%d %H:%M')).total_seconds()/60)
        return {'valid': not errors, 'errors': sorted(set(errors)), 'elapsed_minutes': minutes,
                'transaction_ids': transaction_ids, 'limitation': 'Checks connectivity/time only; does not establish conserved funds or laundering'}

    def dispatch(self, tool, arguments, action_id=None):
        allowed = {'fetch_transactions', 'get_transactions', 'get_accounts', 'expand_frontier', 'summarize_activity', 'verify_path'}
        if tool not in allowed:
            raise ValueError('Unknown tool')
        parameters=json.dumps(arguments, sort_keys=True)
        if action_id:
            previous=self.log.execute('SELECT tool,parameters,result FROM receipts WHERE id=?',(action_id,)).fetchone()
            if previous:
                result=json.loads(previous[2])
                if previous[:2] != (tool,parameters) or result.get('source_sha256') != self.sha or result.get('authorized_scope') != [self.history_start,self.cutoff]:
                    raise ValueError('Action ID belongs to another request or authorized scope')
                return result
        started = time.monotonic()
        self.db.set_progress_handler(lambda: int(time.monotonic()-started > self.timeout), 1000)
        try:
            result = getattr(self, tool)(**arguments)
        except (ValueError, TypeError, KeyError, sqlite3.Error) as e:
            result = {'error': str(e), 'complete': False}
        finally:
            self.db.set_progress_handler(None, 0)
        receipt = action_id or str(uuid.uuid4())
        result.update(receipt_id=receipt, source_sha256=self.sha, authorized_scope=[self.history_start,self.cutoff])
        self.log.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',
            (receipt, tool, parameters, json.dumps(result), time.monotonic()-started))
        self.log.commit()
        return result

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tool')
    p.add_argument('arguments', help='JSON object')
    args = p.parse_args()
    tools = Tools()
    try:
        print(json.dumps(tools.dispatch(args.tool, json.loads(args.arguments)), indent=2))
    finally:
        tools.close()
