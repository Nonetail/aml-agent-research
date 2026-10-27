# Complete HI-Small component inventory

This audit reads **every row** in the pinned local `data/HI-Small_Trans.csv`.
A graph is a weak connected component of observed accounts: keep expanding through
either endpoint of every transaction until no account can be added. Direction and
timestamps do not constrain connectivity. Each account is identified by bank ID
(leading zeroes removed) plus the unchanged account number. Transaction labels,
entity ownership, and inactive accounts in metadata do not form edges or groups.

`component-inventory.csv` contains one row for every component, with its account
count and transaction row count. Every source transaction row counts once,
including self-transfers and duplicate rows; no deduplication is performed.
Component IDs use the minimum 1-based account metadata row in the component,
excluding the header. They are stable for the hashed local inputs, regardless of
transaction processing order or union-find root. The representative bank and
account are included in the CSV.

`summary.json` contains exact and binned size distributions for both account counts
and transaction row counts, the top ten in both ranking orders, maxima outside the
largest transaction component, input hashes, and verification results. Source data
is read-only. No existing experiment outputs are changed.

Run from any directory with Python 3:

```sh
python3 '/Users/notail.wang/Obsidian/n0tail/AML Agent Research/experiments/2026-10-23-full-components/hi-small/audit_hi_small.py'
```

The script checks a small fixture containing duplicate, reverse, self, and inactive
accounts; checks the known full-file totals; and reads the output CSV back to check
unique IDs and exact count sums. Expected totals are **5,078,345 transaction rows**,
**515,088 active accounts**, **114,139 components**, and **4,874,569 transaction rows**
in the largest component.
