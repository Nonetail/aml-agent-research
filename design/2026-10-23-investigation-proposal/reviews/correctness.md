# Independent correctness review

Reviewed the complete `PROPOSAL.md` draft identified by SHA-256 `be66520da19d3ec90c03864cbfcc079e21c6169155be5a78c8252dd414d182d6`. Review scope: design correctness, evidence, graph coverage, persistence, context continuation and review transitions. No implementation or new model experiment was reviewed. Cross-checked the existing data/evaluation, indicator/graph-semantics and framework research; excluded original documents were not consulted.

Overall: the design is coherent and addresses the important distinctions between retrieved versus assessed evidence, source facts versus suspicion, overlapping cases versus full-component coverage, and input capacity versus detection quality. Three bounded changes are needed before treating it as the implementation contract.

## Must fix

### C1 — Make the flowchart branch per finding and provide a no-finding exit

**Priority:** medium. **Sections:** 2 and 8.

The chart freezes a case and sends it through a single valid/invalid evidence gate. It has no explicit path for a case without findings, for `not checkable`, or for a mixture of valid and invalid claims. Section 8 correctly says checks run per claim and one invalid path must not discard other valid findings. The main flow currently contradicts that contract: one defective candidate can appear to send the entire case back for investigation and delay valid candidates. A no-finding case can appear to require a reviewer packet that does not exist.

**Fix:** after freezing the case, record its scope/stop reason independently and process each candidate version through checks/review. No findings proceeds directly to case accounting. Valid candidates continue; invalid claims retain defects and targeted work; not-checkable claims retain explicit limitations and become unresolved unless the reviewer can assess a clearly narrower supported claim. Aggregate finding outcomes into the final report. Include budget/interruption exits so recorded provisional findings can use the reserved review allowance.

**Acceptance example:** one case has two candidates, one valid and one broken path. The valid candidate can be reviewed, the broken one remains invalid/pending, and both retain the same case. A zero-candidate case still produces a coverage/stop record.

### C2 — Define stable pagination and expansion-frontier semantics

**Priority:** medium. **Sections:** 5–6.

The proposal requires cursors, atomic progress and exact row identities but does not specify a stable total result order or what a cursor binds to. This is material for this dataset: timestamps have minute precision, file order is not chronological, and parallel transfers must survive. Timestamp-only pagination can skip all remaining rows sharing the last timestamp; a cursor reused after changing filters can silently mark the wrong scope complete. Atomic writes alone do not prevent these failures.

**Fix:** require a deterministic order with original source-row identity as a tie-breaker (for example timestamp plus source row ID); state expressly that the tie-breaker establishes pagination order, not causal chronology. Bind cursors to the immutable dataset and canonical query parameters. For multi-account/multi-branch expansion, identify each remaining branch/page explicitly, or specify a single deterministic union ordering that preserves every row. A query is complete only after that exact scope is exhausted.

**Acceptance example:** more than one page of transactions has the same timestamp, including parallel rows. Page traversal and interruption/resume return each source row exactly once, with no omission. Changed query parameters require a new cursor/scope.

### C3 — Give the coverage ledger a concrete denominator

**Priority:** medium. **Sections:** 4, 6 and 10.

“Every region scheduled, deferred or never scheduled” and “coverage denominators” remain undefined. Arbitrary account/time/direction/filter regions overlap and have no finite universal region count. A pending-action ledger can describe known unfinished work, but it cannot by itself enumerate unknown regions or establish percentage coverage of the overall graph. This is central to the user's requirement to distinguish explored from unexplored data.

**Fix:** use the reporting population's unique transaction IDs as the basic finite accounting universe. Report separate unique-row counts for exact rows retrieved, presented, agent-recorded assessments and reviewed candidate evidence, each with its definition and denominator. Separately report seed-manifest/work-item states and query-scope completeness. Aggregate query scans do not imply that all underlying rows were presented or assessed. Rows outside the tracked sets remain not covered by that measure; do not call them benign. Supporting history is accounted for separately from the scored reporting population. Motif/path-search completeness remains unknown outside specifically exhausted query scopes.

**Acceptance example:** two cases retrieve the same 100 rows; the run counts 100 unique rows for retrieval coverage, not 200. An aggregate over another 10,000 rows does not add those rows to presented-row coverage. A finished seed queue is reported as queue completion, not graph coverage.

## Optional improvement

### C4 — Freeze explicit timestamp boundary semantics in the run contract

**Sections:** 4–5. Existing project research uses half-open reporting/history windows and excludes transactions at the cutoff; the proposal refers to a cutoff without spelling out inclusivity. Add a short convention such as `[start, cutoff)` and repeat it in tool validation fixtures. State that source timestamps have minute precision and no declared timezone. This avoids boundary disagreement without adding features.

## Checked and retained

- Source identity, both monetary sides/currencies, parallel rows and cautious temporal-path claims align with the project data research.
- Label/pattern isolation, global recall denominator and incomplete reference-pattern coverage are correctly separated.
- Context refresh preserves one logical case and durable exact evidence; summaries are not the authority.
- Candidate versions, stale-review protection and bounded follow-up are sound design choices.
- Markovian is accurately optional and is not claimed to provide graph navigation, transaction caps or durable recovery.
- One writer plus idempotent actions is suitably small for the initial prototype; no production concurrency machinery is required now.

## Targeted resolution check

Re-read the revised diagram and sections 4–6, 8 and 11 against C1–C4, with `REVIEW-RESOLUTIONS.md`. All four findings are addressed at design level:

- **C1:** candidates now process independently, zero-candidate cases reach accounting, and invalid/not-checkable/unreviewed outcomes have explicit routes. Final reporting waits for all candidate statuses; mixed findings and interrupted work are covered in prose and fixtures.
- **C2:** stable timestamp/source-row ordering, scope-bound cursors and branch/union pagination are specified; equal-minute and parallel-row fixtures exercise the boundary.
- **C3:** unique reporting-row sets have a finite denominator, seed/work inventories remain separate, historical support is separate, and aggregate results cannot inflate presented/assessed coverage.
- **C4:** half-open reporting/history intervals, exclusive cutoff and source timestamp precision/timezone limitations are explicit.

No remaining must-fix from this review. This confirms incorporation of the design corrections only; implementation behavior and detection quality remain untested.
