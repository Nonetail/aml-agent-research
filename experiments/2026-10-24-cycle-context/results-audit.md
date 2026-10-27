# Independent results audit

Audit UTC: 2026-10-23T14:25:01.409110+00:00. Data and arithmetic checks: PASS.

The saved matrices contain **66 initial + 30 follow-up + 9 post-hoc diagnostic calls = 105 unique attempts**. All 105 have terminal saved outcomes: 102 received/parsed, 2 returned truncations, 1 provider TimeoutError. Held-out 32-row confirmation was not scheduled after the 6-call development screen recovered 0/6 references.

Independently checked every asserted true path in the 102 parsed answers directly against supplied rows, exact account pairs, chronology, closure and simple-node constraints. **Both raw individually valid claims and strictly accepted responses recover zero cycles outside the three core-only diagnostics.** Each 2-, 3- and 4-row core-only diagnostic recovered its single known reference exactly. The zero result is therefore not an artefact of rejecting a whole response that also contained a valid support.

Provider accounting independently totals **7,372,214 input + 30,776 output = 7,402,990 known tokens**, across 104 returned responses. The one unknown-usage timeout retains **130,851 reserved token units** separately; conservative known-plus-reservation consumption is 7,533,841. No duplicate attempt IDs or double-charged reused baseline responses were found.

All 12 overlap calls used degree-fallback anchors. No initial model-valid path was available for the three whole-path carryover interventions. Zero nominal overlap still retains one anchor row: 1,499 new rows and 2,999 union rows. Other overlap settings expose 1,125/750/375 new rows respectively; none recovered a reference.

**Scope:** This measures the configured model, prompt/schema and selected packet construction. It supports no reliable view size or grouping advantage under those settings. It does not prove that every model fails above 32 rows or that a 1M context claim guarantees comprehension. Core-only success shows minimal rule/format capability, not cluttered discovery. The 1,500-row development gate remains incomplete because of one provider timeout. Dev-4’s 219-cycle exhaustive answer remains output-budget-confounded.

## Reporting issues corrected and independently rechecked

- Movement JSON says whole_path_intervention_available=true for degree-fallback snapshots although no valid discovered path exists. Snapshot availability and whole-path intervention availability must be distinguished.
- Summary case_results and Markdown omit explicit raw-valid recovery. Per-call scores preserve it. Independent audit establishes raw-valid recovery also zero outside core-only, so strict whole-response rejection does not explain zero.

Both issues were corrected in the regenerated report: raw valid cycle/reference counts are explicit for every case, and every fallback movement correctly has whole-path intervention availability set to false. Token totals are unchanged. No unresolved audit findings remain.
