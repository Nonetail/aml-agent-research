# Independent measurement review

23 October 2026. Reviewed `measure.py`, `fit_budgets.py`, the recorded benchmark, all 20 ladder packets, canonical fixtures and private provenance. No material correctness or format-comparison issue found.

## Verified findings

- **Selection is label independent.** The script scans the complete HI-Small transaction file, counts a self-row once for its account, chooses the largest incident-row count and breaks ties by canonical bank/account key. Labels and publisher pattern membership do not affect selection or enter retained evidence. The selected root has 169,756 incident rows.
- **Formats contain equivalent evidence.** Markdown, CSV, positional JSON and minified object JSON share the same metadata/schema header, account/bank/entity aliases and nine transaction fields. Both paid and received amounts/currencies remain exact source strings. Source identities and names are excluded consistently and remain resolvable through the private mapping.
- **Round trips passed independent review.** A separate standard-library parser decoded all 20 saved ladder packets, checked their SHA-256 values and compared each decoded object with its canonical fixture. All matched. Transaction IDs were unique within each packet. Endpoints, timestamps, both amount/currency pairs, payment format and account bank/entity mappings reconstructed exactly from the private source records.
- **Source validation is recorded and implemented.** The benchmark script rereads all 5,000 selected source rows and checks every retained transaction field. Its audit reports success and unique source-row ordinals. Retaining original row ordinals distinguishes duplicate-looking transactions; self and parallel rows are not deduplicated. The reviewer separately verified that retained transaction source records contain exactly the ten unlabeled fields.
- **Accounting is explicit.** Whole-packet counts include metadata, schema, account dictionaries, all transaction fields and section separators. Independently counted sections are reconciled by a boundary-token delta, which is zero in these results. Private provenance, model instructions, tool declarations, protocol overhead, generated output and reasoning are excluded. Counts use named `o200k_base` and `cl100k_base` reference encodings with `tiktoken` 0.14.0; they are not measured model-request usage.

## Limits on interpretation

These are chronological prefixes of one unusually active account's incident rows. They form a high-degree star view, not a complete connected component or a representative multi-hop investigation. Neighbor-to-neighbor transactions are absent. Prefix caps are explicitly marked truncated and can split equal-minute timestamp groups; source-row ordering breaks ties for reproducibility, not causal inference.

Every sampled transaction is in US Dollar; there are no self-transfers or currency conversions in this ladder. Only Cash, Cheque and Credit Card occur. The 2,000-row sample contains 1,059 accounts and 1,058 directed account pairs, with 942 additional rows on repeated pairs, spanning just 00:00–00:25 on 1 September. These properties limit extrapolation to other graphs, currencies, payment formats and time spans. Keeping both amount/currency pairs preserves the schema but does not make this sample a test of FX reasoning.

`fit_budgets.py` regenerates metadata and the used-account dictionary for every tested prefix, counts the whole packet and verifies both a fitting prefix and its immediate over-budget successor. Its binary search is explicitly described as a verified fitting prefix within the audited 5,000-row fixture, not an exhaustive global maximality proof. The 70k/85k/100k evidence budgets are scenarios.

No model inference calls were made. A 120k operating cap and any resulting row allowance remain planning assumptions; token fit alone establishes neither detection quality nor a safe reasoning limit.
