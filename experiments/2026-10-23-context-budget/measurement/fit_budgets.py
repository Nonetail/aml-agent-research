#!/usr/bin/env python3
"""Verify fitting prefixes inside the audited 5,000-row fixture; no LLM calls."""

import copy
import csv
import json
import os
from pathlib import Path

import tiktoken

from measure import ENCODINGS, FORMATS, decode_packet, encode_packet, sha256, write_json

OUT = Path(__file__).resolve().parent
BUDGETS = [70_000, 85_000, 100_000]


def main():
    assert os.environ.get("TIKTOKEN_CACHE_DIR"), "Set a disposable TIKTOKEN_CACHE_DIR."
    fixture_path = OUT / "canonical" / "5000.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    search_bound = len(fixture["transactions"])
    encoders = {name: tiktoken.get_encoding(name) for name in ENCODINGS}
    (OUT / "fitted-packets").mkdir(exist_ok=True)
    cache, rows = {}, []

    def candidate(count, kind):
        key = (count, kind)
        if key not in cache:
            transactions = fixture["transactions"][:count]
            used = {row[field] for row in transactions for field in ("from", "to")}
            accounts = [row for row in fixture["accounts"] if row["id"] in used]
            metadata = copy.deepcopy(fixture["metadata"])
            metadata["scope"]["selected_transaction_count"] = count
            metadata["scope"]["selected_time_max"] = transactions[-1]["time"]
            metadata["scope"]["truncated"] = count < metadata["scope"]["complete_incident_query_count"]
            canonical = {"metadata": metadata, "accounts": accounts, "transactions": transactions}
            packet = "".join(encode_packet(canonical, kind).values())
            assert decode_packet(packet, kind) == canonical
            cache[key] = (packet, {name: len(encoder.encode(packet)) for name, encoder in encoders.items()}, len(accounts))
        return cache[key]

    for kind in FORMATS:
        for encoding in ENCODINGS:
            for budget in BUDGETS:
                low, high = 1, search_bound
                while low < high:
                    middle = (low + high + 1) // 2
                    if candidate(middle, kind)[1][encoding] <= budget:
                        low = middle
                    else:
                        high = middle - 1
                packet, counts, account_count = candidate(low, kind)
                assert counts[encoding] <= budget
                next_tokens = candidate(low + 1, kind)[1][encoding] if low < search_bound else None
                assert next_tokens is None or next_tokens > budget
                path = OUT / "fitted-packets" / f"{budget}.{encoding}.{kind}.{low}.txt"
                path.write_text(packet, encoding="utf-8")
                assert decode_packet(path.read_text(encoding="utf-8"), kind) == decode_packet(packet, kind)
                rows.append({"evidence_budget_tokens": budget, "format": kind, "encoding": encoding,
                             "verified_fitting_prefix_transactions": low, "whole_packet_tokens": counts[encoding],
                             "remaining_tokens": budget - counts[encoding], "unique_accounts": account_count,
                             "next_prefix_transactions": low + 1 if low < search_bound else None,
                             "next_prefix_whole_packet_tokens": next_tokens,
                             "packet_path": str(path.relative_to(OUT)), "packet_sha256": sha256(path)})
    result = {
        "method": "Binary search over the audited chronological 5,000-row fixture; whole packet regenerated and tokenized for each candidate. Returned fitting prefix and immediate successor verified. Not an exhaustive global maximality proof.",
        "search_bound_transactions": search_bound, "fixture_sha256": sha256(fixture_path),
        "script_sha256": sha256(Path(__file__)), "tiktoken": tiktoken.__version__,
        "budgets_are_scenarios": True, "llm_calls": 0,
        "all_tested_candidate_round_trips_passed": True, "unique_count_format_candidates_tested": len(cache),
        "measurements": rows,
    }
    write_json(OUT / "budget-fits.json", result)
    with (OUT / "budget-fits.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
