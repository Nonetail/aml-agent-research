# Two independent assessments using actual IBM evidence

23 October 2026. **Both first-response classifications matched the hidden packet labels.** The estimates were 88% for the packet containing laundering-labeled transactions and 40% for the all-zero-label packet. These are subjective, uncalibrated estimates. Both assessors recommended further review.

This demonstrates that the table-plus-metadata format was usable for these selected examples. It does not establish reliable AML detection, calibrated probabilities, or an improvement over deterministic graph analysis.

**Scope follow-up:** a subsequent [full-data connectivity and context audit](../2026-10-23-graph-scope/README.md) confirmed both packets were complete for their six-focus-account queries, but were not complete isolated graphs. Expanding the positive query to all 21 displayed accounts gives 258 transactions; both cases lie in the same 1,492,740-transaction weak component within their observation window. Saved request text counts as 4,459 and 5,376 tokens under the `o200k_base` reference encoding; actual provider usage was not captured.

## Results

The assessed target was whether **at least one displayed transaction** has IBM's `Is Laundering=1` label. This packet-level target is derived from transaction labels; IBM does not publish a whole-case label for these constructed neighborhoods.

| Case | Displayed transactions | Hidden positive rows | Estimated probability of any positive row | Predicted packet label at 50% | Assessor's confidence | Further review |
|---|---:|---:|---:|---|---|---|
| [case-c193](inputs/case-c193.md) | 76 | 6 | 88% | Positive — matched | Moderate | Yes |
| [case-7b4e](inputs/case-7b4e.md) | 97 | 0 | 40% | Negative — matched | Low | Yes |

The negative result means the assessor leaned toward no positive label. It did not confidently clear the activity. If the operational output were simply “send for review,” both packets would be sent for review, including the packet with no positive labels.

## What each assessor saw

Each input contained actual transaction rows, account/entity aliases, code-computed account counts, coverage metadata and missing-context notes. Times, directions, amounts, currencies and payment formats were unchanged. Original bank/account identifiers and source row positions are retained in the evaluator's provenance mapping.

Both packets cover `[2022/09/02 01:07, 2022/09/05 21:21)`. Each contains six focus accounts and 21 accounts in total, with 21 distinct recorded synthetic entities. Every transaction touching a focus account in that window is included, with no truncation. Other accounts' activity outside this query is unknown.

Both received the same [six behavior guidelines](common_prompt.md): multiple-source receipts, multiple-destination payments, receipt followed by outgoing transfer, time-ordered return paths, gather then disperse, and split then reconverge. These are qualitative research guidelines, not fitted numerical rule thresholds.

They did **not** receive labels, publisher pattern names, original source-row positions, the other packet, the class balance, selection rationale or a precomputed cycle/risk result. Exact account counts were supplied, so this was not unaided arithmetic from raw rows alone.

Two fresh subagents were spawned with no inherited conversation, no model/settings override, and separate input files containing the identical prompt plus only their own packet. Each was permitted to read that one file and instructed to use no other tools, files, external sources or agents. This was instruction-level isolation in a shared environment, not an OS access-control boundary. One first response per case was retained; no rescoring or prompt adjustment followed the scores. The exact model identifier, token usage and sampling settings were not separately exposed or recorded by this run.

## Positive case: a recovered six-account cycle

The assessor identified this path from the 76-row packet:

```text
A07 → A06 → A10 → A21 → A12 → A15 → A07
```

These six rows were cited as its strongest evidence. All six coincide with the publisher-labeled reference cycle. The table below is a post-assessment extract; the assessor originally saw all 76 rows without labels.

| Packet ID | Source row, excluding header | Time | From → to | Amount | Currency |
|---|---:|---|---|---:|---|
| T014 | 1,546,401 | 2022/09/02 13:07 | A07 → A06 | 12,633.54 | Euro |
| T041 | 1,546,402 | 2022/09/04 00:45 | A06 → A10 | 11,619.65 | Euro |
| T043 | 1,546,404 | 2022/09/04 04:05 | A10 → A21 | 1,352,779.07 | Yen |
| T046 | 1,546,407 | 2022/09/04 06:08 | A21 → A12 | 10,953.15 | Euro |
| T053 | 1,546,410 | 2022/09/04 17:54 | A12 → A15 | 72,471.22 | Brazil Real |
| T066 | 1,546,412 | 2022/09/05 09:21 | A15 → A07 | 11,766.38 | Euro |

All six use ACH. On each individual row the paid and received amounts/currencies match; currencies differ between some rows. The path lasts **68 hours 14 minutes**, independently verified. Neither the model nor this report claims that the same monetary units were conserved through the path.

There are also two zero-labeled parallel transfers alongside edges in this route: T045 alongside T046, and T052 alongside T053. Bounded enumeration therefore finds four temporal edge-level cycle variants over the same account-level cycle. The assessor's chosen six IDs happened to match the positive reference set exactly. It was not asked to label every individual row, so this is evidence selection agreement, not a complete transaction-level classification result.

Read the [full positive assessment](assessments/case-c193.json).

## Negative case: suspicious-looking activity with a plausible recurring-payment explanation

The second packet contains 97 transactions, all labeled zero. The assessor observed multiple counterparties, chronological gathering/dispersal and receipt-to-payment gaps as short as two or three minutes. It nevertheless leaned negative because recurring counterparty/amount/payment-format combinations supported an ordinary recurring-payment hypothesis, and it found no return path in the displayed graph.

One verified recurring sequence is:

| Packet ID | Time | From → to | Paid/received amount | Currency | Format |
|---|---|---|---:|---|---|
| T019 | 2022/09/02 11:31 | A19 → A06 | 25.02 | US Dollar | ACH |
| T056 | 2022/09/03 12:42 | A19 → A06 | 25.02 | US Dollar | ACH |
| T065 | 2022/09/04 04:10 | A19 → A06 | 25.02 | US Dollar | ACH |
| T092 | 2022/09/05 16:25 | A19 → A06 | 25.02 | US Dollar | ACH |

Three other amount/format combinations between those accounts also recur on all four days. This verifies repetition; it does not verify payroll, invoices, settlement or any particular business purpose. The model appropriately described that explanation as a hypothesis.

Read the [full negative assessment](assessments/case-7b4e.json).

## Which guidelines distinguished the packets?

| Guideline | case-c193 assessment | case-7b4e assessment |
|---|---|---|
| Multiple-source receipts | Observed | Observed |
| Multiple-destination payments | Observed | Observed |
| Receipt followed by outgoing transfer | Observed | Observed |
| Time-ordered return paths | Observed | Not observed |
| Gather then disperse | Observed | Observed |
| Split then reconverge | Not observed | Not observed |

Several broad indicators occurred in both packets. The return path was the clear structural difference. A deterministic cycle-presence rule would also separate these two examples, so this probe provides no evidence that the LLM improves detection over that baseline.

## Verification and limitations

Verification re-read all **173 source transaction rows** from the full CSV and checked packet fields, identities, recorded entity mapping, labels and account statistics. All cited transaction IDs exist. Checks also verified four stated receipt-to-payment gaps per case, cited gather/disperse sequences, the positive cycle's exact edges/duration, the negative graph's absence of any non-self directed cycle, and the recurring-payment example above. See [source/structure checks](evaluator/structural-checks.json) and [assessment checks](evaluator/results.json).

The examples were deliberately chosen with evaluator access to labels. Positive selection starts from a publisher cycle; only one group satisfied the chosen six-edge/coverage criteria. Negative selection starts from a zero-labeled ACH anchor and retains an all-zero incident neighborhood. A fixed seed makes this reproducible, not representative.

The packets have the same window and focus-account count, but different selection mechanisms, topology and currencies. The negative's non-self account graph has 21 nodes and 20 undirected edges and is a tree; the positive has an account-level cycle. These are relatively easy structural contrasts, not topology-matched controls. The results cannot quantify false-positive rate, recall, general accuracy or calibration. Possible model pretraining exposure to the public dataset is unknown.

The subjective probability, confidence category and review recommendation are separate outputs. Confidence categories had no fitted shared rubric. “All displayed rows have label zero” does not establish that the accounts are clean outside the packet.

These examples and the inspected source window are development material. Do not use them as untouched final-test evidence. A useful next evaluation would include benign cycles, positive non-cycle cases and cases with incomplete context, with a deterministic baseline and a fresh, larger held-out sample.

## Files and reproduction

- [Protocol](PROTOCOL.md), [common prompt](common_prompt.md), [frozen input hashes](evaluator/input-manifest.json).
- [Positive packet as Markdown](inputs/case-c193.md) or [JSON](inputs/case-c193.json).
- [Negative packet as Markdown](inputs/case-7b4e.md) or [JSON](inputs/case-7b4e.json).
- Exact submitted requests: [case-c193](inputs/case-c193.request.md), [case-7b4e](inputs/case-7b4e.request.md).
- First responses: [case-c193](assessments/case-c193.json), [case-7b4e](assessments/case-7b4e.json).
- [Private labels and full original-row mappings](evaluator/truth.json): evaluator material, not an assessor input.
- [Packet builder](build_packets.py), [source verifier](verify_evidence.py), [assessment verifier](verify_assessments.py).

Run the two verification scripts to recheck source provenance and saved results. The builder deliberately refuses to overwrite a frozen experiment. The verifiers do not rerun the models. Do not distribute evaluator files to a future blind assessor.
