"""Resumable cycle discovery and model-ready requests; no hosted inference calls.

The source is read-only. This ledger owns unfinished paths, exact cursor progress,
candidate facts and versioned assessment receipts. Discovery completion is scoped
to this source, time interval and cycle predicate, never a laundering verdict.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from cycle_tools import CycleTools
from cycle_prompts import (RULE_VERSION, NAVIGATOR_SYSTEM, REVIEWER_SYSTEM,
                           navigation_definition, review_definition,
                           validate_navigation, validate_review)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def candidate_id(path):
    return hashlib.sha256(encoded(path).encode()).hexdigest()


class CycleWorkflow:
    def __init__(self, database, ledger, start, end, max_edges=4, max_duration_minutes=None):
        ledger = Path(ledger)
        source = Path(database)
        if ledger.resolve() == source.resolve() or (ledger.exists() and ledger.samefile(source)):
            raise ValueError('Cycle ledger must be a different file from the read-only source')
        ledger.parent.mkdir(parents=True, exist_ok=True)
        self.lock = ledger.with_suffix('.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError('Another writer owns this cycle ledger') from None
        self.tools = None
        self.db = None
        try:
            self.tools = CycleTools(database, start, end, max_edges, max_duration_minutes)
            self.db = sqlite3.connect(ledger)
            self.db.row_factory = sqlite3.Row
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS frontier(id INTEGER PRIMARY KEY,path TEXT UNIQUE,
                    cursor TEXT,done INTEGER NOT NULL DEFAULT 0,priority INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS pending ON frontier(done,priority DESC,id);
                CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,path TEXT UNIQUE,facts TEXT,
                    assessed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,kind TEXT,body TEXT);
                CREATE TABLE IF NOT EXISTS packets(id TEXT PRIMARY KEY,role TEXT,body TEXT);
                CREATE TABLE IF NOT EXISTS assessments(packet_id TEXT PRIMARY KEY,answer TEXT);
                CREATE TABLE IF NOT EXISTS navigation_receipts(packet_id TEXT PRIMARY KEY,answer TEXT,result TEXT);
                CREATE TABLE IF NOT EXISTS followups(candidate_id TEXT,scope_id INTEGER,
                    PRIMARY KEY(candidate_id,scope_id));
                CREATE TABLE IF NOT EXISTS followup_evidence(candidate_id TEXT,transaction_id TEXT,
                    PRIMARY KEY(candidate_id,transaction_id));
            ''')
            self.config = {'rule_version': RULE_VERSION, 'source_identity': self.tools.identity,
                           'source_sha256': self.tools.sha, 'start': start, 'end': end,
                           'max_edges': max_edges, 'max_duration_minutes': max_duration_minutes}
            if self.get('config') is None:
                with self.db:
                    self.put('config', self.config)
                    self.put('seed_cursor', None)
                    self.put('seeds_complete', False)
                    self.put('seeded_edges', 0)
            elif self.get('config') != self.config:
                raise ValueError('Source, scope or rule differs from the saved cycle ledger')
        except Exception:
            self.close()
            raise

    def close(self):
        if self.db is not None:
            self.db.close()
        if self.tools is not None:
            self.tools.close()
        self.lock.close()

    def get(self, key):
        row = self.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key, encoded(value)))

    def _enqueue(self, path):
        self.db.execute('INSERT OR IGNORE INTO frontier(path) VALUES(?)', (encoded(path),))

    def _candidate(self, path, facts=None):
        facts = facts or self.tools.verify_cycle(path)
        if not facts['valid']:
            raise ValueError('Discovery returned an invalid cycle')
        ident = candidate_id(path)
        self.db.execute('INSERT OR IGNORE INTO candidates(id,path,facts) VALUES(?,?,?)',
                        (ident, encoded(path), encoded(facts)))
        return ident

    def pending(self, limit=128):
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError('Frontier limit must be 1..128')
        return self.db.execute('SELECT * FROM frontier WHERE done=0 ORDER BY priority DESC,id LIMIT ?',
                               (limit,)).fetchall()

    def advance(self, scope_ids=None, seed_rows=1000, row_budget=1000, _navigation=None):
        """Commit one substantial retrieval action; limits are I/O, not model sizes."""
        if scope_ids is not None and (not isinstance(scope_ids, list) or
                any(type(i) is not int for i in scope_ids) or len(set(scope_ids)) != len(scope_ids)):
            raise ValueError('Scope IDs must be distinct integers')
        self.tools._budget(seed_rows)
        self.tools._budget(row_budget)
        if scope_ids:
            if len(scope_ids) > min(128, row_budget):
                raise ValueError('Too many selected scopes for one retrieval action')
            work = [self.db.execute('SELECT * FROM frontier WHERE id=? AND done=0', (i,)).fetchone()
                    for i in scope_ids]
            if any(row is None for row in work):
                raise ValueError('Selected scope is unavailable or already complete')
        else:
            work = self.pending(min(128, row_budget))
        with self.db:
            if not work:
                if self.get('seeds_complete'):
                    if _navigation:
                        self.db.execute('INSERT INTO navigation_receipts VALUES(?,?,?)',
                                        (*_navigation, encoded(self.status())))
                    return self.status()
                page = self.tools.seed_page(seed_rows, self.get('seed_cursor'))
                for row in page['rows']:
                    self._enqueue([row['transaction_id']])
                self.put('seed_cursor', page['next_cursor'])
                self.put('seeds_complete', page['complete'])
                self.put('seeded_edges', self.get('seeded_edges')+len(page['rows']))
                self.db.execute('INSERT INTO events(kind,body) VALUES(?,?)',
                                ('seed', encoded({'ids': [r['transaction_id'] for r in page['rows']],
                                                  'next_cursor': page['next_cursor'], 'complete': page['complete']})))
            else:
                result = self.tools.expand_frontier([json.loads(row['path']) for row in work],
                                                   row_budget, [row['cursor'] for row in work])
                for row, branch in zip(work, result['branches']):
                    for path in branch['continuations']:
                        self._enqueue(path)
                    for path in branch['cycles']:
                        self._candidate(path)
                    self.db.execute('UPDATE frontier SET cursor=?,done=?,priority=0 WHERE id=?',
                                    (branch['next_cursor'], int(branch['complete']), row['id']))
                    affected = self.db.execute('SELECT candidate_id FROM followups WHERE scope_id=?',
                                               (row['id'],)).fetchall()
                    self.db.executemany('INSERT OR IGNORE INTO followup_evidence VALUES(?,?)',
                                        [(r[0], evidence['transaction_id']) for r in affected for evidence in branch['rows']])
                self.db.execute('INSERT INTO events(kind,body) VALUES(?,?)',
                                ('expand', encoded({'scope_ids': [r['id'] for r in work],
                                                    'branches': [{k: v for k, v in b.items() if k != 'rows'}
                                                                 for b in result['branches']]})))
            if _navigation:
                self.db.execute('INSERT INTO navigation_receipts VALUES(?,?,?)',
                                (*_navigation, encoded(self.status())))
        return self.status()

    def status(self):
        pending = self.db.execute('SELECT count(*) FROM frontier WHERE done=0').fetchone()[0]
        found, assessed = self.db.execute('SELECT count(*),coalesce(sum(assessed),0) FROM candidates').fetchone()
        return {'rule_version': RULE_VERSION, 'source_sha256': self.tools.sha,
                'scope': [self.tools.start, self.tools.end], 'seeded_external_edges': self.get('seeded_edges'),
                'pending_scopes': pending, 'structural_candidates': found, 'assessed_candidates': assessed,
                'discovery_complete': bool(self.get('seeds_complete') and not pending),
                'retrieval_actions': self.db.execute('SELECT count(*) FROM events').fetchone()[0],
                'prototype_provider_calls': 0,
                'limitation': 'Scoped structural discovery only; no laundering or model-quality conclusion.'}

    def _scopes(self):
        scopes = []
        for row in self.pending(16):
            path = json.loads(row['path'])
            evidence = self.tools.get_transactions(path)['rows']
            last = evidence[-1]
            scopes.append({'scope_id': row['id'], 'transaction_ids': path,
                           'next_account': {'bank': last['destination_bank'], 'account': last['destination_account']},
                           'direction': 'outgoing', 'strictly_after': last['timestamp'],
                           'end': self.tools.end, 'has_continuation_cursor': row['cursor'] is not None})
        return scopes

    def packet(self, role, candidate_limit=8, extra_ids=None):
        """Persist a fresh request without calling a provider or claiming token fit.

        candidate_limit is a caller-selected packet assembly limit, not a measured
        context threshold. Live dispatch still needs calibrated token admission.
        """
        if role not in ('navigator', 'reviewer'):
            raise ValueError('Role must be navigator or reviewer')
        if type(candidate_limit) is not int or not 1 <= candidate_limit <= 128:
            raise ValueError('candidate_limit must be 1..128')
        scopes = self._scopes()
        scope_ids = [s['scope_id'] for s in scopes]
        selected = list(self.db.execute('''SELECT * FROM candidates c WHERE assessed=0 AND NOT EXISTS
                        (SELECT 1 FROM followups f JOIN frontier w ON w.id=f.scope_id
                         WHERE f.candidate_id=c.id AND w.done=0) ORDER BY id LIMIT ?''',
                                       (candidate_limit,))) if role == 'reviewer' else []
        followup_ids = [r[0] for candidate in selected for r in self.db.execute(
            'SELECT transaction_id FROM followup_evidence WHERE candidate_id=? ORDER BY transaction_id', (candidate['id'],))]
        ids = list(dict.fromkeys([i for row in selected for i in json.loads(row['path'])]+
                                [i for s in scopes for i in s['transaction_ids']]+followup_ids+list(extra_ids or [])))
        evidence = self.tools.get_transactions(ids) if ids else {'rows': [], 'unavailable_ids': []}
        if evidence['unavailable_ids']:
            raise ValueError('Packet evidence is unavailable in this source scope')
        if role == 'reviewer' and not selected and not extra_ids:
            raise ValueError('No candidate review is ready; explicit evidence is required for exploratory review')
        definition = navigation_definition(scope_ids) if role == 'navigator' else review_definition(ids, scope_ids)
        payload = {'rule': self.config, 'scopes': scopes, 'rows': evidence['rows'],
                   'verified_candidates': [json.loads(row['facts']) for row in selected],
                   'completed_followup_scopes': sorted({r[0] for c in selected for r in self.db.execute(
                       'SELECT scope_id FROM followups WHERE candidate_id=?', (c['id'],))}),
                   'coverage': self.status()}
        previous = self.db.execute('SELECT packet_id,answer FROM assessments ORDER BY rowid DESC LIMIT 1').fetchone()
        if role == 'reviewer' and previous:
            payload['previous_review'] = {'packet_id': previous['packet_id'],
                                          'assessment': json.loads(previous['answer'])['accepted']}
        request = {'messages': [{'role': 'system', 'content': NAVIGATOR_SYSTEM if role == 'navigator' else REVIEWER_SYSTEM},
                                {'role': 'user', 'content': encoded(payload)}],
                   'tools': [{'type': 'function', 'function': definition}],
                   'tool_choice': {'type': 'function', 'function': {'name': definition['name']}},
                   'max_tokens': 4096}
        body = {'role': role, 'request': request, 'transaction_ids': ids, 'scope_ids': scope_ids,
                'candidate_ids': [row['id'] for row in selected],
                'request_bytes': len(encoded(request).encode()), 'token_admission': 'not_evaluated'}
        ident = hashlib.sha256(encoded(body).encode()).hexdigest()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO packets VALUES(?,?,?)', (ident, role, encoded(body)))
        return {'packet_id': ident, **body}

    def accept_navigation(self, packet_id, answer, **retrieval_settings):
        packet = self._packet(packet_id, 'navigator')
        previous = self.db.execute('SELECT answer,result FROM navigation_receipts WHERE packet_id=?',
                                   (packet_id,)).fetchone()
        if previous:
            if json.loads(previous['answer']) != answer:
                raise ValueError('Completed navigation is immutable')
            return json.loads(previous['result'])
        checked = validate_navigation(answer, packet['scope_ids'])
        return self.advance(checked['scope_ids'], _navigation=(packet_id, encoded(answer)), **retrieval_settings)

    def _packet(self, ident, role):
        row = self.db.execute('SELECT * FROM packets WHERE id=? AND role=?', (ident, role)).fetchone()
        if row is None:
            raise ValueError('Unknown packet or incorrect role')
        return json.loads(row['body'])

    def accept_review(self, packet_id, answer):
        packet = self._packet(packet_id, 'reviewer')
        previous = self.db.execute('SELECT answer FROM assessments WHERE packet_id=?', (packet_id,)).fetchone()
        if previous:
            saved = json.loads(previous[0])
            if saved['submitted'] != answer:
                raise ValueError('Completed assessment is immutable')
            return saved['accepted']
        checked = validate_review(answer, packet['transaction_ids'], packet['scope_ids'], self.tools.verify_cycle)
        checked['followup_dispositions'] = [
            {'scope_id': request['scope_id'],
             'status': 'already_complete' if self.db.execute('SELECT done FROM frontier WHERE id=?',
                                                            (request['scope_id'],)).fetchone()[0] else 'prioritized'}
            for request in checked['evidence_requests']]
        with self.db:
            affected = set(packet['candidate_ids'])
            for observation in checked['observations']:
                if observation['pattern_present']:
                    ident = self._candidate(observation['transaction_ids'], observation['verification'])
                    affected.add(ident)
                    self.db.execute('UPDATE candidates SET assessed=1 WHERE id=?', (ident,))
            retrieved = {request['scope_id']: set() for request in checked['evidence_requests']}
            if affected and retrieved:
                placeholders = ','.join('?' for _ in retrieved)
                events = self.db.execute(f'''SELECT e.body FROM events e WHERE e.kind='expand' AND EXISTS
                    (SELECT 1 FROM json_each(e.body,'$.scope_ids') WHERE value IN ({placeholders}))''',
                    list(retrieved))
                for row in events:
                    event = json.loads(row['body'])
                    for scope, branch in zip(event['scope_ids'], event['branches']):
                        if scope in retrieved:
                            retrieved[scope].update(path[-1] for path in branch['continuations']+branch['cycles'])
            for request in checked['evidence_requests']:
                self.db.execute('UPDATE frontier SET priority=1 WHERE id=? AND done=0', (request['scope_id'],))
                for ident in affected:
                    self.db.execute('INSERT OR IGNORE INTO followups VALUES(?,?)', (ident, request['scope_id']))
                    self.db.executemany('INSERT OR IGNORE INTO followup_evidence VALUES(?,?)',
                        ((ident, transaction) for transaction in retrieved[request['scope_id']]))
                    self.db.execute('UPDATE candidates SET assessed=0 WHERE id=?', (ident,))
            self.db.execute('INSERT INTO assessments VALUES(?,?)',
                            (packet_id, encoded({'submitted': answer, 'accepted': checked})))
        return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'advance', 'discover', 'navigator-packet', 'reviewer-packet'])
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--start', default='2022/09/01 00:00')
    parser.add_argument('--end', default='2022/09/19 00:00')
    parser.add_argument('--max-edges', type=int, default=4)
    parser.add_argument('--max-duration-minutes', type=int)
    parser.add_argument('--seed-rows', type=int, default=1000)
    parser.add_argument('--row-budget', type=int, default=1000)
    args = parser.parse_args()
    workflow = CycleWorkflow(args.database, args.ledger, args.start, args.end,
                             args.max_edges, args.max_duration_minutes)
    try:
        result = workflow.status()
        if args.command in ('advance', 'discover'):
            while not result['discovery_complete']:
                result = workflow.advance(seed_rows=args.seed_rows, row_budget=args.row_budget)
                if args.command == 'advance':
                    break
                if result['retrieval_actions'] % 500 == 0:
                    print(encoded(result), flush=True)
        elif args.command.endswith('-packet'):
            result = workflow.packet(args.command.split('-')[0])
        print(json.dumps(result, indent=2))
    finally:
        workflow.close()


if __name__ == '__main__':
    main()
