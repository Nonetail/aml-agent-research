# Full-CSV weak-component scanner validation

The standalone C++17 scanner is `../scan_components.cpp`, compiled to `../scan_components` with Apple clang 21.0.0 for arm64 macOS. It has no external dependencies.

Build and run from the `hi-large` directory:

```sh
clang++ -std=c++17 -O3 -DNDEBUG -Wall -Wextra -Wpedantic scan_components.cpp -o scan_components
python3 test_scanner.py
/usr/bin/time -l ./scan_components '../../../data/HI-Small_Trans.csv' 'scanner-validation/HI-Small'
./scan_components '../../../data/HI-Large_Trans.csv' 'HI-Large'
```

The last command is the prepared large-file invocation; this validation run did not run HI-Large.

## Semantics

- Each node is `(normalized decimal bank, exact account string)`. Leading zeroes are removed from bank IDs, with an all-zero bank represented as `0`; bank IDs never pass through a bounded integer conversion. Account case and whitespace remain significant.
- Nodes are allocated in first appearance order, reading the source endpoint before the destination. A component ID is its smallest zero-based node ordinal, and that node supplies its representative bank and account. Component IDs are stable for a fixed input row order.
- Union by size and path compression compute undirected connectivity. Every transaction row is counted exactly once, including self-transactions, parallel edges, reversed edges and byte-identical duplicates. The laundering label does not affect grouping.
- Only endpoints in the input transaction CSV create nodes. No separate account catalog or inactive accounts enter the graph.
- Each component stores its 64-bit transaction count. The scanner checks the component node and row totals against the input totals before producing results.
- The accepted input has the exact IBM transaction header and 11 unquoted fields per row. UTF-8 BOM and CRLF are supported. Quoted CSV, wrong field counts, nondecimal or empty banks, empty accounts, and malformed timestamp formats are rejected with a line number. Timestamp format is `YYYY/MM/DD HH:MM`; timestamp extrema use lexical order. Node IDs are 32-bit with an explicit capacity guard.

Outputs are `OUTPUT_PREFIX.components.csv` (every component, ordered by stable ID) and `OUTPUT_PREFIX.summary.json` (totals, timestamp extrema, self-row count, largest 20 components by transaction count, and exact component-size histograms by nodes and rows). Progress is printed to stderr every 10 million transactions.

## Results

All 18 fixture cases passed. The fixtures cover duplicate/self/parallel/reversed edges, disconnected components, joining existing components, bank normalization including zero and oversized decimal IDs, exact account text, account names reused by different banks, stable representatives after the union root changes, timestamp extrema, histograms, empty input, BOM/CRLF, ignored laundering labels and malformed-input rejection. See `fixture-tests.json`.

The full HI-Small scan produced:

| Measure | Result |
|---|---:|
| Transaction rows | 5,078,345 |
| Active accounts | 515,088 |
| Weak components | 114,139 |
| Largest component transaction rows | 4,874,569 |
| Largest component accounts | 372,089 |
| Self-transaction rows | 591,212 |
| First timestamp | 2022/09/01 00:00 |
| Last timestamp | 2022/09/18 16:18 |
| Scan runtime | 1.450593333 seconds |
| End-to-end wall runtime | 1.48 seconds |
| Maximum resident memory | 86,654,976 bytes |

The inventory and both histograms sum to the complete input totals. An independent Python implementation matched the exact multiset of `(accounts, transactions)` for all 114,139 components, comprising 202 distinct pairs; both complete histograms also matched. A separate source review found no critical correctness issue.

`HI-Small-crosscheck.json` records the expected-count checks. `HI-Small.runtime.txt` retains the raw macOS `time -l` output. `validation-report.json` records the compiler, source/binary SHA-256 values and machine-readable validation results. The runtime above is one HI-Small measurement, not a full HI-Large benchmark.
