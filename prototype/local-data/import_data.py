"""Disposable, reproducible HI-Small import. No third-party dependencies."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from decimal import Decimal

HERE = Path(__file__).resolve().parent
HEADER = ['Timestamp', 'From Bank', 'Account', 'To Bank', 'Account', 'Amount Received', 'Receiving Currency', 'Amount Paid', 'Payment Currency', 'Payment Format', 'Is Laundering']

def bank(raw):
    return raw.lstrip('0') or '0'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def build(data, output, expected=None):
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    trans = data / 'HI-Small_Trans.csv'
    accounts = data / 'HI-Small_accounts.csv'
    hashes = {p.name: digest(p) for p in (trans, accounts)}
    if expected and hashes != expected:
        raise ValueError('Source hashes do not match pinned HI-Small release')
    db = sqlite3.connect(output / 'transactions.sqlite')
    evaluator = sqlite3.connect(output / 'evaluator.sqlite')
    db.executescript('''
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE accounts(bank TEXT, account TEXT, raw_bank TEXT, bank_name TEXT,
            entity_id TEXT, entity_name TEXT, PRIMARY KEY(bank, account));
        CREATE TABLE transactions(row_id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL,
            source_bank TEXT, source_account TEXT, destination_bank TEXT, destination_account TEXT,
            received_amount TEXT, received_currency TEXT, paid_amount TEXT, paid_currency TEXT,
            payment_format TEXT, raw_source_bank TEXT, raw_destination_bank TEXT);
    ''')
    evaluator.execute('CREATE TABLE labels(row_id INTEGER PRIMARY KEY, is_laundering INTEGER NOT NULL)')
    with accounts.open(newline='') as f:
        db.executemany('INSERT INTO accounts VALUES(?,?,?,?,?,?)',
            ((bank(r['Bank ID']), r['Account Number'], r['Bank ID'], r['Bank Name'], r['Entity ID'], r['Entity Name']) for r in csv.DictReader(f)))
    rows, labels = [], []
    with trans.open(newline='') as f:
        reader = csv.reader(f)
        if next(reader) != HEADER:
            raise ValueError('Unexpected transaction schema')
        count = 0
        for count, r in enumerate(reader, 1):
            if len(r) != 11 or r[10] not in ('0', '1'):
                raise ValueError(f'Malformed source row {count}')
            for amount in (r[5], r[7]):
                if not Decimal(amount).is_finite():
                    raise ValueError(f'Invalid amount at row {count}')
            rows.append((count, r[0], bank(r[1]), r[2], bank(r[3]), r[4], *r[5:10], r[1], r[3]))
            labels.append((count, int(r[10])))
            if len(rows) == 20000:
                db.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
                evaluator.executemany('INSERT INTO labels VALUES(?,?)', labels)
                rows.clear(); labels.clear()
            if count % 1000000 == 0:
                print(f'Imported {count:,} rows', flush=True)
    db.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
    evaluator.executemany('INSERT INTO labels VALUES(?,?)', labels)
    db.commit(); evaluator.commit(); evaluator.close()
    print('Building account/time indexes', flush=True)
    db.executescript('''
        CREATE INDEX outgoing ON transactions(source_bank,source_account,timestamp,row_id);
        CREATE INDEX incoming ON transactions(destination_bank,destination_account,timestamp,row_id);
        ANALYZE;
    ''')
    missing = db.execute('''SELECT COUNT(*) FROM transactions t
        LEFT JOIN accounts s ON (t.source_bank=s.bank AND t.source_account=s.account)
        LEFT JOIN accounts d ON (t.destination_bank=d.bank AND t.destination_account=d.account)
        WHERE s.account IS NULL OR d.account IS NULL''').fetchone()[0]
    if missing:
        raise ValueError(f'{missing} rows have unmatched accounts')
    manifest = {'schema_version': 1, 'hashes': hashes, 'rows': count,
                'accounts': db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0],
                'unmatched_rows': missing, 'seconds': round(time.monotonic()-started, 3),
                'timestamp_range': list(db.execute('SELECT MIN(timestamp),MAX(timestamp) FROM transactions').fetchone()),
                'id_format': 'transaction-file-sha256:original-data-row-ordinal (header excluded)'}
    db.executemany('INSERT INTO metadata VALUES(?,?)', [('source_sha256', hashes[trans.name]), ('manifest', json.dumps(manifest))])
    db.commit()
    if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        raise ValueError('SQLite integrity check failed')
    db.close()
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2), flush=True)
    return manifest

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir', type=Path, default=HERE.parents[1] / 'data')
    args = p.parse_args()
    expected = {'HI-Small_Trans.csv': 'b19d39f515523373f991b689c07e11e7b0b95c17a2c27a87d91584ae16c5b040',
                'HI-Small_accounts.csv': '786808526e33cfc441212dd6fccda7edfc24172149bed59c6ef59b186836b014'}
    build(args.data_dir, HERE / 'generated', expected)
