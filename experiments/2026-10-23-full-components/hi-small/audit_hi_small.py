"""Inventory every weak account component in the full, pinned IBM HI-Small file."""
import csv
import hashlib
import json
import time
from array import array
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[2] / "data"
EXPECTED = {
    "transaction_rows": 5078345,
    "active_accounts": 515088,
    "components": 114139,
    "largest_component_transaction_rows": 4874569,
}


def account_key(bank, account):
    return bank.lstrip("0") or "0", account


class Components:
    def __init__(self, count):
        self.parent = array("I", range(count))
        self.size = array("I", [1]) * count
        self.active = bytearray(count)
        self.source_rows = array("Q", [0]) * count
        self.row_count = 0
        self.self_row_count = 0

    def find(self, node):
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def add(self, source, destination):
        self.row_count += 1
        self.self_row_count += source == destination
        self.active[source] = self.active[destination] = 1
        self.source_rows[source] += 1
        left, right = self.find(source), self.find(destination)
        if left != right:
            if self.size[left] < self.size[right]:
                left, right = right, left
            self.parent[right] = left
            self.size[left] += self.size[right]

    def inventory(self):
        accounts, rows, representatives = Counter(), Counter(), {}
        for node, active in enumerate(self.active):
            if active:
                root = self.find(node)
                accounts[root] += 1
                rows[root] += self.source_rows[node]
                representatives.setdefault(root, node)
        return [(representatives[root], accounts[root], rows[root]) for root in accounts]


def check_fixture():
    assert account_key("0007", "A") == account_key("7", "A")
    assert account_key("000", "A") == ("0", "A")
    graph = Components(7)
    # Duplicate A->B, reverse B->A, self A->A, C->D, self E->E; F and G inactive.
    for source, destination in [(0, 1), (0, 1), (1, 0), (0, 0), (2, 3), (4, 4)]:
        graph.add(source, destination)
    assert sorted(graph.inventory()) == [(0, 2, 4), (2, 2, 1), (4, 1, 1)]
    assert graph.row_count == 6 and graph.self_row_count == 2
    reordered = Components(7)
    for source, destination in [(4, 4), (3, 2), (1, 0), (1, 0), (0, 1), (0, 0)]:
        reordered.add(source, destination)
    assert sorted(reordered.inventory()) == sorted(graph.inventory())


def distribution(values):
    exact = Counter(values)
    bounds = [("1", 1, 1), ("2-9", 2, 9), ("10-99", 10, 99),
              ("100-999", 100, 999), ("1000-9999", 1000, 9999),
              ("10000-99999", 10000, 99999), ("100000-999999", 100000, 999999),
              ("1000000+", 1000000, float("inf"))]
    bands = {label: sum(count for size, count in exact.items() if low <= size <= high)
             for label, low, high in bounds}
    return {"exact_size_to_component_count": dict(sorted(exact.items())),
            "size_band_to_component_count": bands}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    begin = time.perf_counter()
    check_fixture()
    keys, index = [], {}
    with (DATA / "HI-Small_accounts.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            key = account_key(row["Bank ID"], row["Account Number"])
            assert key not in index, key
            index[key] = len(keys)
            keys.append(key)
    graph = Components(len(keys))
    with (DATA / "HI-Small_Trans.csv").open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        assert header[:5] == ["Timestamp", "From Bank", "Account", "To Bank", "Account"]
        for row_number, row in enumerate(reader, 1):
            graph.add(index[account_key(row[1], row[2])], index[account_key(row[3], row[4])])
            if row_number % 1000000 == 0:
                print(f"Read {row_number:,} rows in {time.perf_counter() - begin:.1f}s", flush=True)
    records = []
    for representative, accounts, rows in sorted(graph.inventory()):
        bank, account = keys[representative]
        records.append({"component_id": f"HI-Small-C{representative + 1:09d}",
                        "representative_metadata_row_1based": representative + 1,
                        "representative_bank_id": bank,
                        "representative_account_number": account,
                        "account_count": accounts, "transaction_row_count": rows})
    by_rows = sorted(records, key=lambda item: (-item["transaction_row_count"],
                     -item["account_count"], item["representative_metadata_row_1based"]))
    by_accounts = sorted(records, key=lambda item: (-item["account_count"],
                         -item["transaction_row_count"], item["representative_metadata_row_1based"]))
    totals = {"transaction_rows": graph.row_count,
              "active_accounts": sum(item["account_count"] for item in records),
              "components": len(records),
              "largest_component_transaction_rows": by_rows[0]["transaction_row_count"]}
    assert totals == EXPECTED, totals
    assert sum(item["transaction_row_count"] for item in records) == graph.row_count
    assert totals["active_accounts"] == sum(graph.active)
    csv_path = ROOT / "component-inventory.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    with csv_path.open(newline="") as handle:
        saved = list(csv.DictReader(handle))
    assert len({item["component_id"] for item in saved}) == len(saved) == totals["components"]
    assert sum(int(item["account_count"]) for item in saved) == totals["active_accounts"]
    assert sum(int(item["transaction_row_count"]) for item in saved) == totals["transaction_rows"]
    outside = [item for item in records if item["component_id"] != by_rows[0]["component_id"]]
    summary = {
        "dataset": "IBM HI-Small, complete pinned local transaction file",
        "definition": "Weak connected components of observed accounts. Ignore transaction direction for connectivity; count every transaction row, including self-transfers and duplicates. No time filter, hop limit, label filter, entity ownership edges, or inactive metadata accounts.",
        "account_identity": "(bank ID with leading zeroes removed, unchanged account number); all-zero bank IDs normalize to 0",
        "component_id": "HI-Small-C followed by the zero-padded 1-based minimum account metadata row number in the component, excluding the header; deterministic for these hashed input files and independent of union root or transaction order",
        "inventory_order": "Increasing representative_metadata_row_1based",
        "ranking_tiebreaks": "Rows ranking: rows descending, accounts descending, representative row ascending. Accounts ranking: accounts descending, rows descending, representative row ascending.",
        "source_sha256": {name: sha256(DATA / name) for name in ["HI-Small_Trans.csv", "HI-Small_accounts.csv"]},
        "totals": totals,
        "metadata_accounts": len(keys),
        "inactive_metadata_accounts_excluded": len(keys) - totals["active_accounts"],
        "self_transaction_rows_included": graph.self_row_count,
        "account_size_distribution": distribution(item["account_count"] for item in records),
        "transaction_row_size_distribution": distribution(item["transaction_row_count"] for item in records),
        "largest_components_by_transaction_rows": by_rows[:10],
        "largest_components_by_accounts": by_accounts[:10],
        "outside_largest_transaction_component": {
            "components": len(outside),
            "accounts": sum(item["account_count"] for item in outside),
            "transaction_rows": sum(item["transaction_row_count"] for item in outside),
            "maximum_account_count": max(item["account_count"] for item in outside),
            "maximum_transaction_row_count": max(item["transaction_row_count"] for item in outside),
        },
        "checks": {"small_fixture_including_duplicate_self_reverse_and_inactive_nodes": "passed",
                   "matches_previous_full_file_counts": "passed",
                   "inventory_unique_component_ids": "passed",
                   "inventory_account_sum_equals_observed_active_accounts": "passed",
                   "inventory_transaction_row_sum_equals_source_rows": "passed",
                   "csv_readback_count_and_sums": "passed"},
        "inventory_sha256": sha256(csv_path),
        "elapsed_seconds": round(time.perf_counter() - begin, 3),
    }
    for name in ["account_size_distribution", "transaction_row_size_distribution"]:
        assert sum(summary[name]["size_band_to_component_count"].values()) == totals["components"]
        assert sum(summary[name]["exact_size_to_component_count"].values()) == totals["components"]
    assert sum(size * count for size, count in summary["account_size_distribution"]["exact_size_to_component_count"].items()) == totals["active_accounts"]
    assert sum(size * count for size, count in summary["transaction_row_size_distribution"]["exact_size_to_component_count"].items()) == totals["transaction_rows"]
    summary["checks"]["exact_distributions_weighted_sums_match_totals"] = "passed"
    (ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"totals": totals, "outside_largest_transaction_component": summary["outside_largest_transaction_component"],
                      "account_size_bands": summary["account_size_distribution"]["size_band_to_component_count"],
                      "transaction_row_size_bands": summary["transaction_row_size_distribution"]["size_band_to_component_count"],
                      "elapsed_seconds": summary["elapsed_seconds"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
