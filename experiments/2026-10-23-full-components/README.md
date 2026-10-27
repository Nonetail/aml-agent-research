# Dataset sizes and complete connected-component inventories

Measured 23 October 2026 against Kaggle release v8. This report distinguishes independent dataset variants, date-filtered views, and fully expanded connected components.

## Which data was used?

The earlier two-case LLM probe used **HI-Small**, whose complete transaction file contains **5,078,345 rows**. It did not use the largest variant. For this follow-up, the complete **HI-Large** transaction CSV was downloaded and scanned: **179,702,229 rows**, excluding the header. These are measured counts, not rounded estimates.

The publisher distributes six independent simulations. Small is not a subset of Medium or Large; accounts and components must not be merged across variants. HI means higher illicit ratio and LI lower illicit ratio. The approximate publisher counts are:

| Size | HI transactions, approximate | LI transactions, approximate |
|---|---:|---:|
| Small | 5 million | 7 million |
| Medium | 32 million | 31 million |
| Large | 180 million | 176 million |

[Publisher paper, Table 4](https://arxiv.org/html/2306.16424v3#A1), [Kaggle dataset](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml), [live metadata snapshot](publisher-metadata.json).

HI-Large is the largest individual published variant. Its transaction file is 17,052,760,651 bytes. All 509 HTTP ranges were checked for the expected range and byte count; the full file was hashed. [Download manifest](hi-large-download-manifest.json). Only the largest variant's transaction file was downloaded; its account metadata and pattern file were not needed for this connectivity audit and are not present. The other four variants were not audited for connectivity.

## Full-file results: no date filter or expansion cap

| Measure | HI-Small | HI-Large |
|---|---:|---:|
| Transaction rows | 5,078,345 | 179,702,229 |
| Active bank/account pairs | 515,088 | 2,116,168 |
| Fully expanded components | 114,139 | 200,065 |
| Transactions in largest component | 4,874,569 | 179,166,217 |
| Accounts in largest component | 372,089 | 1,904,340 |
| Share of transactions in largest | 95.99% | 99.70% |
| Other components | 114,138 | 200,064 |
| Transactions in all other components combined | 203,776 | 536,012 |
| Maximum transactions in any other component | 95 | 297 |
| Maximum accounts in any other component | 24 | 9 |

Each component is disjoint from every other component **within the same full source file**: no account is shared, and each original transaction belongs to exactly one component. These are weak connected components, following payment connections in either direction. Isolation is an observed-data property, not a claim that accounts cannot have unobserved connections, common control, or future transactions.

The largest component dominates both files. Component partitioning therefore does not turn either dataset into a collection of similarly sized model inputs. This finding says nothing by itself about whether transactions are laundering.

## Size distribution of every component

Here size means original transaction rows, not accounts. The giant is listed separately; there are no components between 1,000 transactions and the giant in either audited file.

| Transactions per component | HI-Small component count | HI-Large component count |
|---|---:|---:|
| 1 | 73,888 | 96,624 |
| 2–9 | 39,341 | 101,114 |
| 10–99 | 909 | 2,301 |
| 100–999 | 0 | 25 |
| 1,000 through one less than the giant's size | 0 | 0 |
| Giant: 4,874,569 / 179,166,217 transactions respectively | 1 | 1 |
| **All components** | **114,139** | **200,065** |

The complete inventories contain one row per component, including its representative account, account count and transaction count:

- [All 114,139 HI-Small components](hi-small/component-inventory.csv), [exact distributions and checks](hi-small/summary.json).
- [All 200,065 HI-Large components](hi-large/HI-Large.components.csv), [exact distributions](hi-large/HI-Large.summary.json), [independent inventory checks and grouped distribution](hi-large/verified-inventory-summary.json).

HI-Small's ten largest transaction counts are 4,874,569; 95; 87; 66; 62; 62; 60; 58; 56; 56. HI-Large's ten largest are 179,166,217; 297; 292; 284; 230; 225; 182; 172; 167; 167.

## What the earlier 92-hour window meant

The previous probe selected the interval **[2022-09-02 01:07, 2022-09-05 21:21)** in HI-Small: 92 hours 14 minutes, using the source's unspecified timezone. This interval covered the known example cycle plus twelve hours of context on either side. It was a date filter chosen for the illustration, not another Kaggle variant.

```text
Complete HI-Small transaction file:                    5,078,345 rows
    Keep only rows whose timestamps fall in the window: 1,551,162 rows
        Largest component in that filtered view:        1,492,740 rows
            Original six-focus-account evidence query:         76 rows
```

The filtered view has 33,869 components, while the full HI-Small file has 114,139. Removing dates can both remove accounts and break connections, so these counts need not move in one direction. A component isolated in the filtered view can reconnect through transactions outside it. [Original scope audit](../2026-10-23-graph-scope/README.md).

The full HI-Large audit includes every record, including its sparse tail: observed timestamps run from 2022/08/01 00:00 to 2023/01/12 16:49. The publisher's 97-day primary activity period is not the complete raw timestamp range. Tail labels and detection quality were not analysed in this follow-up.

## Method and verification

- Vertices are `(normalized bank ID, unchanged account number)`. Normalization removes bank-ID leading zeroes; account numbers remain strings. Sharing a bank alone does not connect accounts.
- Every source row is an edge. Self-transfers, parallel payments and exact repeated rows are retained and counted once per source occurrence. Inactive metadata accounts are excluded.
- Connectivity ignores direction; there is no time-order requirement, date filter, hop limit, amount/channel filter, or ownership edge. Laundering labels do not influence grouping.
- Union-find computes the transitive closure of observed account connectivity without enumerating transaction paths.
- The C++ scanner passed 18 fixtures. Its HI-Small results exactly matched all 114,139 component sizes and both histograms from an independent Python implementation.
- HI-Large inventory IDs are unique; component row/account sums and both exact histograms reconcile. An independent `wc -l` count found 179,702,230 lines, matching the header plus 179,702,229 parsed records.
- The full HI-Large connectivity scan took approximately 63 seconds locally and used approximately 421 MB maximum resident memory. Downloading took approximately six minutes. These are local observations, not detection/inference performance benchmarks.

[Python HI-Small method](hi-small/README.md), [C++ scanner source](hi-large/scan_components.cpp), [scanner validation](hi-large/scanner-validation/README.md), [HI-Large runtime log](hi-large/HI-Large.runtime.txt).

To reproduce the HI-Large scan from its `hi-large` directory:

```sh
clang++ -std=c++17 -O3 -DNDEBUG -Wall -Wextra -Wpedantic scan_components.cpp -o scan_components
./scan_components '../../../data/HI-Large_Trans.csv' 'HI-Large'
```

The [download script](download_hi_large.py) can recover the public file using the pinned byte size. The manifest records its SHA-256. No LLM assessment, detector discovery run or model training was performed on HI-Large in this audit.
