#!/usr/bin/env python3
"""Measure four lossless encodings of label-blind IBM AML incident-row prefixes."""

import argparse
import collections
import csv
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import sys
import time

import tiktoken

ACCOUNT_COLUMNS = ["id", "bank", "entity"]
TRANSACTION_COLUMNS = ["id", "time", "from", "to", "paid_amount", "paid_currency",
                       "received_amount", "received_currency", "format"]
FORMATS = ["markdown_tables", "compact_csv_tables", "positional_json", "minified_json_objects"]
ENCODINGS = ["o200k_base", "cl100k_base"]
LEVELS = [500, 1000, 2000, 3000, 5000]


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def account_key(bank, account):
    return (bank.lstrip("0") or "0", account)


def endpoints(row):
    return account_key(row[1], row[2]), account_key(row[3], row[4])


def scan_counts(path):
    counts = collections.Counter()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = csv.reader(stream)
        header = next(rows)
        assert header[:10] == ["Timestamp", "From Bank", "Account", "To Bank", "Account",
                               "Amount Received", "Receiving Currency", "Amount Paid",
                               "Payment Currency", "Payment Format"]
        for row_count, row in enumerate(rows, 1):
            sender, receiver = endpoints(row)
            counts[sender] += 1
            if receiver != sender:
                counts[receiver] += 1
    root = min(counts, key=lambda key: (-counts[key], key))
    return root, counts[root], row_count, len(counts)


def collect_incident(path, root):
    incident = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = csv.reader(stream)
        next(rows)
        for ordinal, row in enumerate(rows, 1):
            if root in endpoints(row):
                # Only the ten unlabeled source columns enter any retained object.
                incident.append((ordinal, row[:10]))
    incident.sort(key=lambda item: (item[1][0], item[0]))
    return incident


def read_accounts(path, needed):
    records = {}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for ordinal, row in enumerate(csv.DictReader(stream), 1):
            key = account_key(row["Bank ID"], row["Account Number"])
            if key in needed:
                if key in records:
                    assert records[key]["record"] == row, f"Conflicting account record: {key}"
                else:
                    records[key] = {"source_row_ordinal": ordinal, "record": row}
    return records


def tx_object(ordinal, row, aliases, index):
    sender, receiver = endpoints(row)
    return dict(zip(TRANSACTION_COLUMNS, [f"T{index}", row[0], aliases[sender], aliases[receiver],
                                         row[7], row[8], row[5], row[6], row[9]]))


def table_encode(columns, rows, kind):
    values = [[row[column] for column in columns] for row in rows]
    if kind == "minified_json_objects":
        return compact(rows)
    if kind == "positional_json":
        return compact({"columns": columns, "rows": values})
    text_values = [["" if value is None else value for value in row] for row in values]
    if kind == "compact_csv_tables":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(text_values)
        return buffer.getvalue().rstrip("\n")
    # The measured source fields contain none of Markdown's structural characters.
    assert all(not any(char in cell for char in "|\\\n\r") for row in text_values for cell in row)
    return "\n".join(["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
                     + ["|" + "|".join(row) + "|" for row in text_values])


def table_decode(text, columns, kind):
    if kind == "minified_json_objects":
        result = json.loads(text)
        assert all(list(row) == columns for row in result)
        return result
    if kind == "positional_json":
        table = json.loads(text)
        assert table["columns"] == columns
        values = table["rows"]
    elif kind == "compact_csv_tables":
        rows = list(csv.reader(io.StringIO(text)))
        assert rows[0] == columns
        values = rows[1:]
    else:
        rows = [line[1:-1].split("|") for line in text.splitlines()]
        assert rows[0] == columns
        assert rows[1] == ["---"] * len(columns)
        values = rows[2:]
    assert all(len(row) == len(columns) for row in values)
    result = [dict(zip(columns, row)) for row in values]
    for row in result:
        if "entity" in row and row["entity"] == "":
            row["entity"] = None
    return result


def encode_packet(canonical, kind):
    header = "CONTEXT\n" + compact(canonical["metadata"]) + "\n"
    accounts = "ACCOUNTS\n" + table_encode(ACCOUNT_COLUMNS, canonical["accounts"], kind) + "\n"
    transactions = "TRANSACTIONS\n" + table_encode(TRANSACTION_COLUMNS, canonical["transactions"], kind) + "\n"
    return {"header": header, "accounts": accounts, "transactions": transactions}


def decode_packet(text, kind):
    header, rest = text.split("\nACCOUNTS\n", 1)
    accounts, transactions = rest.split("\nTRANSACTIONS\n", 1)
    assert header.startswith("CONTEXT\n")
    return {"metadata": json.loads(header[len("CONTEXT\n"):]),
            "accounts": table_decode(accounts, ACCOUNT_COLUMNS, kind),
            "transactions": table_decode(transactions.rstrip("\n"), TRANSACTION_COLUMNS, kind)}


def sample_stats(transactions):
    pairs = collections.Counter((row["from"], row["to"]) for row in transactions)
    return {
        "transactions": len(transactions),
        "unique_accounts": len({row[key] for row in transactions for key in ("from", "to")}),
        "distinct_directed_account_pairs": len(pairs),
        "self_transactions": sum(row["from"] == row["to"] for row in transactions),
        "pairs_with_multiple_transactions": sum(count > 1 for count in pairs.values()),
        "parallel_transaction_excess": sum(count - 1 for count in pairs.values()),
        "currency_conversion_transactions": sum(row["paid_currency"] != row["received_currency"] for row in transactions),
        "payment_formats": dict(sorted(collections.Counter(row["format"] for row in transactions).items())),
        "paid_currencies": dict(sorted(collections.Counter(row["paid_currency"] for row in transactions).items())),
        "received_currencies": dict(sorted(collections.Counter(row["received_currency"] for row in transactions).items())),
        "time_min": transactions[0]["time"], "time_max": transactions[-1]["time"],
    }


def audit_source(path, selected, transactions, aliases):
    expected = {ordinal: (row, transactions[index - 1], index)
                for index, (ordinal, row) in enumerate(selected, 1)}
    matched = 0
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = csv.reader(stream)
        next(rows)
        for ordinal, row in enumerate(rows, 1):
            if ordinal in expected:
                original, canonical, index = expected[ordinal]
                assert row[:10] == original
                assert tx_object(ordinal, row[:10], aliases, index) == canonical
                matched += 1
                if matched == len(expected):
                    break
    assert matched == len(selected)
    return matched


def vocabulary_hash(encoding):
    digest = hashlib.sha256()
    for token, rank in sorted(encoding._mergeable_ranks.items(), key=lambda pair: pair[1]):
        digest.update(rank.to_bytes(8, "big") + len(token).to_bytes(8, "big") + token)
    digest.update(compact(sorted(encoding._special_tokens.items())).encode())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).resolve().parents[3] / "data")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    assert os.environ.get("TIKTOKEN_CACHE_DIR"), "Set TIKTOKEN_CACHE_DIR to a disposable directory."
    assert importlib.metadata.version("tiktoken") == "0.14.0"
    started = time.perf_counter()
    out = args.output_dir
    for directory in [out, out / "packets", out / "canonical", out / "private"]:
        directory.mkdir(parents=True, exist_ok=True)
    source = args.source_dir / "HI-Small_Trans.csv"
    account_source = args.source_dir / "HI-Small_accounts.csv"
    print("Pass 1: count every account's incident rows, without using any label.", flush=True)
    root, incident_count, row_count, account_count = scan_counts(source)
    assert row_count == 5_078_345
    print(f"Scanned {row_count:,} rows and {account_count:,} accounts; maximum incident count {incident_count:,}.", flush=True)
    print("Pass 2: retrieve all root-incident rows and sort by timestamp, then source ordinal.", flush=True)
    incident = collect_incident(source, root)
    assert len(incident) == incident_count
    levels = [count for count in LEVELS if count <= incident_count]
    if incident_count < max(LEVELS) and incident_count not in levels:
        levels.append(incident_count)
    selected = incident[:max(levels)]
    needed = {key for _, row in selected for key in endpoints(row)}
    ordered_keys = [root] + sorted(needed - {root})
    aliases = {key: f"A{index}" for index, key in enumerate(ordered_keys, 1)}
    bank_aliases = {bank: f"B{index}" for index, bank in enumerate(sorted({key[0] for key in needed}), 1)}
    records = read_accounts(account_source, needed)
    entity_ids = sorted({record["record"]["Entity ID"] for record in records.values() if record["record"]["Entity ID"]})
    entity_aliases = {entity: f"E{index}" for index, entity in enumerate(entity_ids, 1)}
    accounts = []
    for key in ordered_keys:
        record = records.get(key, {}).get("record", {})
        accounts.append({"id": aliases[key], "bank": bank_aliases[key[0]],
                         "entity": entity_aliases.get(record.get("Entity ID"))})
    transactions = [tx_object(ordinal, row, aliases, index) for index, (ordinal, row) in enumerate(selected, 1)]
    print("Pass 3: independently reread selected source rows and check every retained field.", flush=True)
    audited_count = audit_source(source, selected, transactions, aliases)
    source_info = {
        "transactions": {"file": source.name, "sha256": sha256(source), "rows": row_count, "bytes": source.stat().st_size},
        "accounts": {"file": account_source.name, "sha256": sha256(account_source), "bytes": account_source.stat().st_size},
    }
    write_json(out / "prefix-boundaries.json", {
        "source_sha256": source_info["transactions"]["sha256"], "complete_incident_query_count": incident_count,
        "boundaries": [{"prefix_transactions": count, "last_selected_timestamp": incident[count - 1][1][0],
                        "next_incident_timestamp": incident[count][1][0] if count < incident_count else None,
                        "cutoff_splits_timestamp": count < incident_count and incident[count - 1][1][0] == incident[count][1][0]}
                       for count in levels],
    })
    private = {
        "source": source_info, "source_row_ordinal_convention": "1-based data row, excluding CSV header",
        "root_canonical_key": list(root),
        "accounts": [{"id": aliases[key], "canonical_bank_id": key[0], "raw_account": key[1],
                      "bank_alias": bank_aliases[key[0]], "account_source": records.get(key)} for key in ordered_keys],
        "banks": {alias: bank for bank, alias in bank_aliases.items()},
        "entities": {alias: entity for entity, alias in entity_aliases.items()},
        "transactions": [{"id": f"T{index}", "source_row_ordinal": ordinal, "source_first_ten_fields": row}
                         for index, (ordinal, row) in enumerate(selected, 1)],
    }
    write_json(out / "private" / "provenance.json", private)
    encoders = {name: tiktoken.get_encoding(name) for name in ENCODINGS}
    measurements, samples = [], []
    for count in levels:
        chosen = transactions[:count]
        used = {row[key] for row in chosen for key in ("from", "to")}
        chosen_accounts = [row for row in accounts if row["id"] in used]
        stats = sample_stats(chosen)
        stats.update({"unique_banks": len({row["bank"] for row in chosen_accounts}),
                      "unique_recorded_entities": len({row["entity"] for row in chosen_accounts if row["entity"] is not None}),
                      "accounts_without_recorded_entity": sum(row["entity"] is None for row in chosen_accounts)})
        metadata = {
            "schema_version": "aml-star-sizing-v1",
            "purpose": "Format capacity only; not detection quality or a complete investigation case.",
            "dataset": "IBM AML-Data HI-Small",
            "scope": {"kind": "chronological_prefix_of_root_incident_rows", "root": "A1", "root_rank": 1,
                      "selection": "Maximum incident row count; self rows counted once; ties by canonical bank/account key.",
                      "complete_incident_query_count": incident_count, "selected_transaction_count": count,
                      "truncated": count < incident_count, "order": ["source_timestamp", "source_row_ordinal"],
                      "complete_incident_time_min": incident[0][1][0], "complete_incident_time_max": incident[-1][1][0],
                      "selected_time_min": stats["time_min"], "selected_time_max": stats["time_max"],
                      "coverage": "Only rows touching root; rows between its neighbors are not retrieved. Prefix cap is not a complete time window."},
            "schema": {"accounts": {"columns": ACCOUNT_COLUMNS, "cell_types": ["string", "string", "string_or_null"]},
                       "transactions": {"columns": TRANSACTION_COLUMNS, "cell_types": ["string"] * len(TRANSACTION_COLUMNS)}},
            "semantics": {"account": "Alias of (bank ID with leading zeros removed, raw account number).",
                          "bank": "Alias of canonical bank ID; bank names and geography not sent.",
                          "entity": "Alias of recorded Entity ID; not independently verified. Null means unavailable; empty CSV/Markdown entity cell means null.",
                          "aliases": "Stable across this prefix ladder; source identifiers and names omitted, resolvable through private external mapping.",
                          "transaction": "Unique row alias; from/to is directed. Self and parallel rows retained.",
                          "amounts": "Exact source strings, with both original paid/received currencies. No currency conversion applied.",
                          "time": "Source minute string; no timezone supplied."},
            "root_account": accounts[0],
            "unavailable_context": ["KYC", "business purpose", "verified beneficial ownership", "external risk signals"],
        }
        canonical = {"metadata": metadata, "accounts": chosen_accounts, "transactions": chosen}
        canonical_path = out / "canonical" / f"{count}.json"
        write_json(canonical_path, canonical)
        stats["canonical_sha256"] = sha256(canonical_path)
        samples.append(stats)
        for kind in FORMATS:
            sections = encode_packet(canonical, kind)
            packet = "".join(sections.values())
            packet_path = out / "packets" / f"{count}.{kind}.txt"
            packet_path.write_text(packet, encoding="utf-8")
            assert decode_packet(packet_path.read_text(encoding="utf-8"), kind) == canonical
            for encoding_name, encoding in encoders.items():
                tokens = len(encoding.encode(packet))
                section_tokens = {f"{name}_tokens": len(encoding.encode(value)) for name, value in sections.items()}
                measurements.append({"transactions": count, "format": kind, "encoding": encoding_name,
                                     "whole_packet_tokens": tokens, **section_tokens,
                                     "boundary_token_delta": tokens - sum(section_tokens.values()),
                                     "tokens_per_transaction": tokens / count,
                                     "utf8_bytes": len(packet.encode("utf-8")), "packet_sha256": sha256(packet_path),
                                     "packet_path": str(packet_path.relative_to(out)),
                                     "unique_accounts": stats["unique_accounts"], "unique_banks": stats["unique_banks"],
                                     "unique_recorded_entities": stats["unique_recorded_entities"]})
        print(f"Verified {count:,}-row fixture and all four serialized packets.", flush=True)
    slopes = []
    for kind in FORMATS:
        for encoding_name in ENCODINGS:
            series = [row for row in measurements if row["format"] == kind and row["encoding"] == encoding_name]
            for low, high in zip(series, series[1:]):
                slopes.append({"format": kind, "encoding": encoding_name, "from_transactions": low["transactions"],
                               "to_transactions": high["transactions"],
                               "additional_whole_packet_tokens": high["whole_packet_tokens"] - low["whole_packet_tokens"],
                               "marginal_tokens_per_added_transaction": (high["whole_packet_tokens"] - low["whole_packet_tokens"]) / (high["transactions"] - low["transactions"])})
    result = {
        "run": {"python": platform.python_version(), "tiktoken": importlib.metadata.version("tiktoken"),
                "script_sha256": sha256(Path(__file__)), "elapsed_seconds": time.perf_counter() - started,
                "platform": platform.platform(), "llm_calls": 0},
        "tokenizers": {name: {"n_vocab": encoding.n_vocab, "vocabulary_sha256": vocabulary_hash(encoding),
                              "fingerprint_algorithm": "SHA256 of rank-sorted 8-byte rank + 8-byte byte-length + token bytes, then compact sorted special-token pairs"}
                       for name, encoding in encoders.items()},
        "source": source_info,
        "selection": {"method": "All-source incident counts; highest count; ties by canonical bank/account key; chronological prefix.",
                      "label_blind": True, "label_or_pattern_fields_retained": False, "all_source_unique_accounts": account_count,
                      "root": "A1", "root_rank": 1, "complete_incident_query_count": incident_count,
                      "complete_incident_time_min": incident[0][1][0], "complete_incident_time_max": incident[-1][1][0],
                      "requested_prefix_sizes": LEVELS, "actual_prefix_sizes": levels,
                      "not_representative_of": ["full connected components", "multi-hop investigations", "typical customer activity", "model detection quality"]},
        "accounting": {"unit": "Raw UTF-8 packet encoded with named tiktoken encoding; no chat-message wrapper or tool envelope.",
                       "includes": ["common metadata and schema header", "account/bank/entity alias table", "all nine transaction fields", "section markers and separators"],
                       "excludes": ["private provenance map", "source identities and names", "hidden reasoning", "model output", "system prompts", "tool definitions", "chat protocol overhead"],
                       "section_note": "Each section includes its marker and trailing newline. Boundary delta reconciles independently encoded sections to the full concatenated packet.",
                       "context_limit_note": "120k is a user-selected working cap, not a validated model-quality limit or model context specification."},
        "audit": {"selected_source_rows_reread": audited_count, "exact_source_field_checks_passed": True,
                  "all_round_trips_equal_canonical": True, "round_trip_packets": len(levels) * len(FORMATS),
                  "no_label_or_pattern_file_used_for_selection": True, "source_ordinal_coverage_unique": len({row[0] for row in selected}) == len(selected)},
        "samples": samples, "measurements": measurements, "marginal_slopes": slopes,
    }
    write_json(out / "benchmark.json", result)
    with (out / "benchmark.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(measurements[0]))
        writer.writeheader()
        writer.writerows(measurements)
    with (out / "marginal-slopes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(slopes[0]))
        writer.writeheader()
        writer.writerows(slopes)
    print(f"Complete: {len(measurements)} measurements, {len(levels) * len(FORMATS)} round trips; {time.perf_counter() - started:.1f}s.", flush=True)


if __name__ == "__main__":
    main()
