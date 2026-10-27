"""Profile publisher HI-Small with only Python's standard library.

The row-level labels and pattern answers are evaluator material. This script
emits aggregate statistics only and does not select or inspect held-out cases.
"""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import urllib.request
import argparse

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, default=ROOT.parents[1] / "data")
DATA = parser.parse_args().data_dir
DATA.mkdir(parents=True, exist_ok=True)
URL = "https://www.kaggle.com/api/v1/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/HI-Small_Trans.csv"
PATH = DATA / "HI-Small_Trans.csv"
EXPECTED_BYTES = 475664283
if not PATH.exists():
    with urllib.request.urlopen(URL, timeout=60) as response, PATH.with_suffix(".partial").open("wb") as out:
        total = 0
        while block := response.read(4 * 1024 * 1024):
            out.write(block)
            total += len(block)
            if total > EXPECTED_BYTES + 1000:
                raise ValueError("Response exceeds expected dataset size")
            if total // (64 * 1024 * 1024) != (total - len(block)) // (64 * 1024 * 1024):
                print(f"Downloaded {total} bytes", flush=True)
    if total != EXPECTED_BYTES:
        raise ValueError(f"Unexpected response size {total}")
    PATH.with_suffix(".partial").rename(PATH)

sha = hashlib.sha256()
with PATH.open("rb") as inp:
    while block := inp.read(4 * 1024 * 1024):
        sha.update(block)
if sha.hexdigest() != "b19d39f515523373f991b689c07e11e7b0b95c17a2c27a87d91584ae16c5b040":
    raise ValueError("Source file differs from the audited release")

def bank_id(raw):
    return raw.lstrip("0") or "0"

accounts = {}
for row in csv.DictReader((DATA / "HI-Small_accounts.csv").open()):
    key = (bank_id(row["Bank ID"]), row["Account Number"])
    if key in accounts:
        raise ValueError("Account metadata normalization collision")
    accounts[key] = row["Entity ID"]

pattern_rows = Counter()
for row in csv.reader((DATA / "HI-Small_Patterns.txt").open()):
    if row and row[0].startswith("2022/"):
        pattern_rows[tuple(row)] = 0

day_rows = Counter()
day_labels = Counter()
formats = Counter()
paid_currencies = Counter()
received_currencies = Counter()
labels = Counter()
active_accounts = set()
unmatched_accounts = set()
previous_timestamp = None
previous_row = None
out_of_order = adjacent_duplicate_rows = self_transfers = cross_currency = missing_cells = 0
earliest = latest = None
non_decimal_bank_ids = 0
with PATH.open(newline="") as inp:
    reader = csv.reader(inp)
    header = next(reader)
    assert header == ["Timestamp", "From Bank", "Account", "To Bank", "Account", "Amount Received", "Receiving Currency", "Amount Paid", "Payment Currency", "Payment Format", "Is Laundering"]
    for count, row in enumerate(reader, start=1):
        if len(row) != 11:
            raise ValueError(f"Malformed row {count}")
        timestamp = row[0]
        day = timestamp[:10]
        day_rows[day] += 1
        labels[row[10]] += 1
        day_labels[day] += int(row[10])
        formats[row[9]] += 1
        paid_currencies[row[8]] += 1
        received_currencies[row[6]] += 1
        earliest = timestamp if earliest is None else min(earliest, timestamp)
        latest = timestamp if latest is None else max(latest, timestamp)
        out_of_order += previous_timestamp is not None and timestamp < previous_timestamp
        previous_timestamp = timestamp
        row_tuple = tuple(row)
        adjacent_duplicate_rows += row_tuple == previous_row
        previous_row = row_tuple
        if row_tuple in pattern_rows:
            pattern_rows[row_tuple] += 1
        source = (bank_id(row[1]), row[2])
        destination = (bank_id(row[3]), row[4])
        for key in (source, destination):
            active_accounts.add(key)
            if key not in accounts:
                unmatched_accounts.add(key)
        self_transfers += source == destination
        cross_currency += row[6] != row[8]
        missing_cells += sum(not cell for cell in row)
        non_decimal_bank_ids += not row[1].isdecimal() or not row[3].isdecimal()
        if count % 1000000 == 0:
            print(f"Profiled {count} rows", flush=True)

def period(start, end):
    days = [day for day in day_rows if start <= day < end]
    n = sum(day_rows[d] for d in days)
    positive = sum(day_labels[d] for d in days)
    return {"start_inclusive": start, "end_exclusive": end, "transactions": n,
            "positive_labels": positive, "positive_rate": positive / n if n else None}

profile = {
    "source": URL, "publisher_version": 8, "file_bytes": PATH.stat().st_size,
    "sha256": sha.hexdigest(), "rows": count, "header": header,
    "earliest_timestamp": earliest, "latest_timestamp": latest,
    "labels": dict(labels), "positive_rate": labels["1"] / count,
    "per_day": [{"day": day, "transactions": day_rows[day], "positive_labels": day_labels[day],
                 "positive_rate": day_labels[day] / day_rows[day]} for day in sorted(day_rows)],
    "source_activity_periods": {"primary": period("2022/09/01", "2022/09/11"),
                                "tail": period("2022/09/11", "2022/09/19")},
    "payment_formats": dict(formats), "paid_currencies": dict(paid_currencies),
    "received_currencies": dict(received_currencies), "active_bank_account_pairs": len(active_accounts),
    "active_entity_ids": len({accounts[k] for k in active_accounts if k in accounts}),
    "unmatched_bank_account_pairs": len(unmatched_accounts), "non_decimal_bank_id_rows": non_decimal_bank_ids,
    "self_transfer_rows": self_transfers, "cross_currency_rows": cross_currency,
    "missing_cells": missing_cells, "adjacent_timestamp_regressions": out_of_order,
    "adjacent_duplicate_full_rows": adjacent_duplicate_rows,
    "full_nonadjacent_duplicate_check": "separate audit; run audit_duplicates.py and see duplicate-profile.json",
    "pattern_row_match_multiplicities": dict(Counter(pattern_rows.values())),
}
(ROOT / "evaluator-hi-small-profile.json").write_text(json.dumps(profile, indent=2))
public_profile = {k: v for k, v in profile.items() if k not in ["labels", "positive_rate", "per_day", "source_activity_periods", "pattern_row_match_multiplicities"]}
public_profile["per_day"] = [{"day": day, "transactions": day_rows[day]} for day in sorted(day_rows)]
(ROOT / "hi-small-profile.json").write_text(json.dumps(public_profile, indent=2))
print(json.dumps(profile, indent=2), flush=True)
