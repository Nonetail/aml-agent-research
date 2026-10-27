#!/usr/bin/env python3
"""Deterministic scanner fixtures; standard library only."""
import csv
import json
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "scanner-validation"
HEADER = "Timestamp,From Bank,Account,To Bank,Account,Amount Received,Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering"
OUT.mkdir(exist_ok=True)
facts = []


def row(bank_a, account_a, bank_b, account_b, stamp="2022/09/01 00:00", label="0"):
    return [stamp, bank_a, account_a, bank_b, account_b, "1.00", "US Dollar", "1.00", "US Dollar", "ACH", label]


def scan(name, content, succeeds=True):
    source = OUT / f"{name}.csv"
    prefix = OUT / name
    source.write_bytes(content.encode())
    result = subprocess.run([str(ROOT / "scan_components"), str(source), str(prefix)], capture_output=True, text=True)
    assert (result.returncode == 0) == succeeds, (name, result.stderr)
    if succeeds:
        return json.loads(prefix.with_suffix(".summary.json").read_text()), prefix
    assert "error at input line" in result.stderr
    facts.append({"fixture": name, "rejected": True, "diagnostic": result.stderr.strip()})


start = time.perf_counter()
rows = [
    row("0001", "alpha", "2", "beta", "2022/09/02 23:59"),
    row("1", "alpha", "02", "beta", "2022/09/02 23:59"),  # Duplicate row after bank normalization.
    row("2", "beta", "1", "alpha", label="1"),  # Reversed edge and laundering label.
    row("0001", "alpha", "1", "alpha"),
    row("3", "alpha", "0003", "alpha"),  # Same account text, different bank.
    row("4", "gamma", "5", "delta"),
    row("6", "case", "6", "Case"),  # Account case remains significant.
    row("0", "zero", "000", "zero"),
    row("5", "delta", "2", "beta"),  # Bridge two preexisting components.
    row("1", " alpha", "1", "alpha", "2022/08/31 01:00"),  # Whitespace is significant.
]
rows.append(rows[0].copy())  # A byte-for-byte duplicate transaction is still a row.
content = HEADER + "\n" + "\n".join(",".join(r) for r in rows) + "\n"
summary, prefix = scan("fixture", content)
assert {key: summary[key] for key in ("transactions", "accounts", "components", "self_rows")} == {
    "transactions": 11, "accounts": 9, "components": 4, "self_rows": 3
}
assert summary["min_timestamp"] == "2022/08/31 01:00"
assert summary["max_timestamp"] == "2022/09/02 23:59"
assert summary["totals_verified"] is True
with prefix.with_suffix(".components.csv").open(newline="") as file:
    inventory = list(csv.DictReader(file))
assert [(int(c["component_id"]), c["representative_bank"], c["representative_account"], int(c["accounts"]), int(c["transactions"])) for c in inventory] == [
    (0, "1", "alpha", 5, 8), (2, "3", "alpha", 1, 1), (5, "6", "case", 2, 1), (7, "0", "zero", 1, 1)
]
assert summary["component_account_size_histogram"] == [{"size": 1, "components": 2}, {"size": 2, "components": 1}, {"size": 5, "components": 1}]
assert summary["component_transaction_size_histogram"] == [{"size": 1, "components": 3}, {"size": 8, "components": 1}]
assert summary["largest_components_by_transactions"][0]["component_id"] == 0
facts.append({"fixture": "fixture", "passed": True, "checks": "self rows; duplicate/parallel/reversed rows; bridge merge; disconnected components; normalized decimal banks including zero; exact account case and whitespace; same account at different banks; source-first stable IDs; unsorted timestamp extrema; exact histograms; inventory totals"})

relabelled = [r[:-1] + ["ignored-label"] for r in rows]
other, _ = scan("labels-ignored", HEADER + "\n" + "\n".join(",".join(r) for r in relabelled) + "\n")
for key in summary:
    if key not in {"input", "scan_seconds"}:
        assert other[key] == summary[key], key
facts.append({"fixture": "labels-ignored", "passed": True})

empty, _ = scan("header-only", HEADER + "\n")
assert empty["accounts"] == empty["transactions"] == empty["components"] == 0
assert empty["min_timestamp"] is None and empty["max_timestamp"] is None
facts.append({"fixture": "header-only", "passed": True})
crlf, _ = scan("bom-crlf", "\ufeff" + content.replace("\n", "\r\n"))
assert crlf["transactions"] == 11
facts.append({"fixture": "bom-crlf", "passed": True})

root_rows = [row("1", "first", "1", "first"), row("2", "second", "2", "third"), row("2", "second", "1", "first")]
roots, _ = scan("size-wins-over-first", HEADER + "\n" + "\n".join(",".join(r) for r in root_rows) + "\n")
assert roots["largest_components_by_transactions"] == [{"component_id": 0, "representative_bank": "1", "representative_account": "first", "accounts": 3, "transactions": 3}]
facts.append({"fixture": "size-wins-over-first", "passed": True, "checks": "stable representative survives union-by-size changing the root"})
bank = "123456789012345678901234567890"
huge, _ = scan("large-bank-id", HEADER + "\n" + ",".join(row("000" + bank, "same", bank, "same")) + "\n")
assert huge["accounts"] == huge["self_rows"] == 1
assert huge["largest_components_by_transactions"][0]["representative_bank"] == bank
facts.append({"fixture": "large-bank-id", "passed": True, "checks": "bank normalization never converts to a bounded integer"})

scan("bad-header", HEADER.replace("From Bank", "FromBank") + "\n", False)
scan("missing-field", HEADER + "\n" + ",".join(rows[0][:-1]) + "\n", False)
scan("extra-field", HEADER + "\n" + ",".join(rows[0]) + ",extra\n", False)
scan("quote", HEADER + "\n" + ",".join(row("1", '"alpha"', "2", "beta")) + "\n", False)
for bank in ("", "-1", "1.0", " 1", "1x"):
    scan("invalid-bank-" + str(len(facts)), HEADER + "\n" + ",".join(row(bank, "alpha", "2", "beta")) + "\n", False)
scan("empty-account", HEADER + "\n" + ",".join(row("1", "", "2", "beta")) + "\n", False)
scan("bad-timestamp", HEADER + "\n" + ",".join(row("1", "alpha", "2", "beta", "2022-09-01 00:00")) + "\n", False)
scan("blank-row", HEADER + "\n\n", False)
report = {"passed": True, "fixture_cases": len(facts), "runtime_seconds": time.perf_counter() - start, "facts": facts}
(OUT / "fixture-tests.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
