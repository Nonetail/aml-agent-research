# Downloaded IBM data

These are unmodified files from version 8 of the [IBM synthetic AML dataset](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml), downloaded for the research dated 23 October 2026. [Source repository](https://github.com/IBM/AML-Data).

| File | Bytes | Role |
|---|---:|---|
| [HI-Small_Trans.csv](HI-Small_Trans.csv) | 475,664,283 | Transactions with an `Is Laundering` label column |
| [HI-Small_accounts.csv](HI-Small_accounts.csv) | 34,053,187 | Synthetic account-to-entity metadata |
| [HI-Small_Patterns.txt](HI-Small_Patterns.txt) | 323,844 | Publisher reference pattern groups for evaluation |
| [HI-Large_Trans.csv](HI-Large_Trans.csv) | 17,052,760,651 | Complete transaction file for the largest variant; downloaded for the full-component audit |

Source URLs and SHA-256 hashes are recorded in the [HI-Small download manifest](../research/evidence/download-manifest.json) and the [HI-Large download manifest](../experiments/2026-10-23-full-components/hi-large-download-manifest.json). The data license is CDLA-Sharing-1.0 as recorded by the publisher; the repository's code license is a separate matter. See the [data research](../research/ibm-data-and-evaluation.md) for details and source links.

The raw transactions and pattern file contain answers. Use them for controlled data preparation and evaluation. Build label-free transaction/account views for detection and investigation; do not give runtime agents filesystem access to these raw files or the evaluator profiles.

The four source files occupy 17,562,801,965 bytes in total. HI-Large account metadata and pattern files have not been downloaded; its transaction file alone supplies the endpoints needed for the connectivity audit. They are included here so the research package and downloaded data share one location. No trained detector or prepared runtime database has been created.
