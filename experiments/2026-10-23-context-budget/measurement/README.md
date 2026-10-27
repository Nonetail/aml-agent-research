# IBM transaction packet token measurements

This experiment measures the size of four lossless serializations of the **same transaction evidence**, including a common scope/schema header and the account dictionary. It makes **no LLM calls** and does not measure AML detection accuracy. The user's 120k total context working cap is a planning assumption, not a validated quality limit or a model specification.

## Sampling and evidence contract

`measure.py` scans all **5,078,345 transactions** in local `HI-Small_Trans.csv`, counts incident rows for each of **515,088 canonical accounts**, and selects the account with the highest count. A self-transfer counts once for that account. Ties use the canonical `(bank ID with leading zeros removed, raw account number)` key. Neither labels nor the patterns file enter selection, formatting, or retained evidence.

The selected root, alias `A1`, has **169,756 incident rows**, from `2022/09/01 00:00` through `2022/09/10 23:59`. A second full-source pass retrieves all its incident rows, sorts by exact source timestamp and original row ordinal, then takes prefixes of 500, 1,000, 2,000, 3,000, and 5,000 rows. These are deliberately truncated star-shaped sizing samples. They are not complete cases, complete time windows, multi-hop neighborhoods, or representative customer samples. **Every ladder cutoff splits a tied timestamp group**, as independently checked in `prefix-boundaries.json`.

Each canonical packet has:

- Identical metadata and schema information across all four formats, including root aliases, the complete incident query count, truncation, time coverage, and unavailable context.
- An account table with three fields: account alias, bank alias, and recorded entity alias. Entity membership comes from local `HI-Small_accounts.csv` and is not independently verified ownership.
- Nine transaction fields: row alias, exact time string, sender alias, receiver alias, paid amount string, paid currency string, received amount string, received currency string, and payment format.

Both monetary sides stay as exact source strings. No aggregation, deduplication, currency conversion, or self-transfer filtering occurs. A unique transaction alias distinguishes parallel source rows. Account, bank, and entity aliases are stable across the maximum 5,000-row fixture and its prefixes; each packet contains only its used account records. Raw identifiers, bank/entity names, and geography are omitted from every format. External tools would resolve aliases through `private/provenance.json`; that map is **not sent or charged** in these measurements. KYC, business purpose, verified beneficial ownership, and external risk signals are unavailable.

The measured corpus is narrow: all selected rows use US Dollar on both sides, with no self-transfer or FX rows, and only Cash, Cheque, and Credit Card formats. The serializer retains these fields and would retain self/FX rows, but these samples do not empirically exercise those transaction types.

| Transactions | Accounts | Directed pairs | Parallel excess¹ | Final timestamp, Sep 1 |
|---:|---:|---:|---:|:---|
| 500 | 436 | 435 | 65 | 00:06 |
| 1,000 | 743 | 742 | 258 | 00:12 |
| 2,000 | 1,059 | 1,058 | 942 | 00:25 |
| 3,000 | 1,465 | 1,464 | 1,536 | 01:11 |
| 5,000 | 2,425 | 2,424 | 2,576 | 03:23 |

¹ Sum of `count(pair) - 1` over distinct ordered account pairs. This is not a count of identical duplicate records. The 5,000-row sample contains 524 distinct bank aliases and 2,422 recorded entity aliases.

## Measured tokens

Pinned tokenizer library: **tiktoken 0.14.0**. Both `o200k_base` and `cl100k_base` are measured. These are named tokenizer encodings, not assertions about an unspecified model's tokenizer. The complete raw packet is encoded once for its authoritative count; the header, account table, and transaction table are also encoded separately. `boundary_token_delta` reconciles the section counts to the whole packet (zero in this run). Markers, separators, table headers, and schema text are included. Chat framing, system instructions, tool schemas/results outside the packet, private provenance, reasoning, and output are excluded.

Whole packet tokens with `o200k_base`:

| Transactions | Markdown tables | Compact CSV tables | Positional JSON | Minified JSON objects |
|---:|---:|---:|---:|---:|
| 500 | 25,259 | 22,421 | 25,245 | 37,889 |
| 1,000 | 48,525 | 43,266 | 48,511 | 73,190 |
| 2,000 | 92,742 | 83,535 | 92,728 | 139,987 |
| 3,000 | 137,662 | 124,237 | 137,648 | 207,937 |
| 5,000 | 228,483 | 206,178 | 228,469 | 345,558 |

Markdown uses compact pipe tables; CSV has a header row and no unnecessary quoting; positional JSON repeats column names once per table and then uses arrays; minified JSON objects repeat field names for every row. No whitespace indentation is added to any measured JSON. All variants include the same common schema header, even when a format repeats column names in its table.

The 1,000→2,000-row marginal increase, including growth in the account dictionary, is **44.217 / 40.269 / 44.217 / 66.797 tokens per added transaction** for those four formats under `o200k_base`. These are local measured slopes, not general constants. `benchmark.json`, `benchmark.csv`, and `marginal-slopes.csv` contain exact counts for both encodings, section breakdowns, sample statistics, sizes, and hashes.

## Verified budget-fitting prefixes

`fit_budgets.py` searches inside the already audited 5,000-row fixture. It regenerates the entire header and used-account dictionary for each candidate and counts the whole packet. It uses binary search and verifies both the fitting prefix and the immediately following over-budget prefix. These are **verified fitting examples**, not an exhaustive proof of global maximality or model-quality limits.

Fitting transaction counts with `o200k_base`:

| Evidence budget | Markdown tables | Compact CSV tables | Positional JSON | Minified JSON objects |
|---:|---:|---:|---:|---:|
| 70,000 | 1,478 | 1,659 | 1,478 | 953 |
| 85,000 | 1,819 | 2,037 | 1,819 | 1,172 |
| 100,000 | 2,171 | 2,421 | 2,171 | 1,393 |

At 70k, CSV's 1,659-row packet uses **69,965 tokens** and the 1,660-row packet uses **70,003**. Markdown's 1,478 rows use **69,994**; positional JSON's same 1,478 rows use **69,980**. JSON objects fit 953 rows at **69,938**. These tight fits leave almost no allowance inside the chosen evidence budget; they are measurements, not operational thresholds. The surrounding request needs separately reserved space.

`budget-fits.json`/`.csv` contain 24 scenarios across both encodings, exact fitting/next-prefix counts, and hashes. `fitted-packets/` contains the measured fitting packets. All 186 tested count/format candidates round-trip to their regenerated canonical packet.

## Audit and reproducibility

After selection, an independent third source pass rereads all selected 5,000 transaction rows and checks retained fields exactly. Every saved ladder packet decodes back to its canonical object (**20/20**); no source row is collapsed. `private/provenance.json` retains source file SHA-256, 1-based source data row ordinals, original first-ten transaction fields, original account records, and mappings for all aliases. It excludes the label field entirely. The independent read-only review is recorded in `REVIEW.md`.

Source SHA-256:

- `HI-Small_Trans.csv`: `b19d39f515523373f991b689c07e11e7b0b95c17a2c27a87d91584ae16c5b040`
- `HI-Small_accounts.csv`: `786808526e33cfc441212dd6fccda7edfc24172149bed59c6ef59b186836b014`

Run from this directory with an isolated Python environment and a disposable cache:

```sh
python3 -m venv /tmp/aml-token-venv
/tmp/aml-token-venv/bin/python -m pip install -r requirements.txt
export TIKTOKEN_CACHE_DIR=/tmp/aml-token-cache
/tmp/aml-token-venv/bin/python measure.py --source-dir ../../../data
/tmp/aml-token-venv/bin/python fit_budgets.py
```

`measure.py` defaults to the same sibling `data` directory and writes outputs here. `benchmark.json` records Python, platform, tokenizer version/vocabulary fingerprint, script hash, source hashes, packet hashes, and run duration. `canonical/` holds the five common evidence fixtures; `packets/` holds the twenty measured serializations. Identical source files and the pinned tokenizer should reproduce counts; durations/platform strings can differ.
