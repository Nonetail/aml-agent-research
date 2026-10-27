# External review supplied by the user

Review input for the preceding proposal revision. Recommendations were assessed, not automatically accepted. See [revision decisions](../REVISION-2-DECISIONS.md).

Review of PROPOSAL.md

Overall

The engineering contract is strong. It keeps evidence identity, retrieval versus assessment, case versus finding lifecycles, and version-specific review separate, and it handles pagination and coverage denominators carefully. The two earlier reviews fixed real problems.

Both of those reviews only checked whether the design holds together internally. Neither checked it against the project goal or against what the data allows. Measured that way, the main risk is not a bug in the control flow. The risk is that gate 4 (the fixed-versus-adaptive comparison) gives a result nobody can interpret. The arbitrary-seed design, the missing deterministic baseline, a single run per arm and HI-Small's time span together leave the experiment with almost no statistical signal.

Must address

R1. The rules and the deterministic baseline from the project goal have gone missing

The goal in HANDOFF.md is to compare detection against a deterministic baseline, using reproducible rules grounded in AUSTRAC indicators. The proposal lists "frozen indicator/rule versions" in the run contract (§4) and then never uses them:
- Seeds don't come from rule hits.
- Findings don't cite an indicator.
- The reviewer has no indicator to test a claim against.
- The only baseline is "fixed expansion", and that baseline uses the same LLM to assess candidates (§10). That isolates navigation quality only. It doesn't answer whether the agent beats a deterministic detector.

The research plan (ibm-data-and-evaluation.md:193) explicitly starts the investigation test "from exactly the same seed alerts". The proposal quietly changed that to arbitrary seeds.

Fix:
- State which claim gate 4 tests.
- Add a non-LLM arm: rule hits plus deterministic expansion, flagged without model assessment. Otherwise "detection value" in gate 4 has nothing to be measured against.
- Make every finding cite an indicator or rule ID.

R2. Arbitrary seeds give almost no signal

In the primary period 0.089% of rows are positive (4,522 of 5,077,237). A few dozen uniformly sampled transaction seeds will expect well under one laundering seed. Recall over all of P (§10) will then be near zero in both arms, whatever the navigation quality. Gate 4 says "establish detection value", but under §4's seed policy it can't.

Fix:
- Separate the mechanics test (arbitrary seeds are fine) from the detection comparison, which needs label-free prioritized seeds and so depends on R1.
- Add a rough power or sample-size estimate before choosing the seed count. Include the expected number of positive seeds and positive rows reachable within budget.
- Keep §10's label-enriched diagnostic set, but report it as diagnostic only, as it already says.

R3. HI-Small's dates don't fit the planned windows, and the tail isn't mentioned

- §4 resolves "last seven days" against a simulated cutoff. HI-Small has 10 primary days (1–10 Sept).
- §10 also needs development data for tuning, an "unexamined" evaluation population and a temporal holdout. All three plus history can't fit in 10 days.
- The proposal never mentions the 11–18 Sept tail: 1,108 rows, 59% positive, holding 12.65% of all positives. If the reporting window reaches the last timestamp, recall and precision are dominated by an artifact. A "recent activity" seed rule would also leak labels through the date.

Fix:
- Exclude the tail from P explicitly, or report it separately (ibm-data-and-evaluation.md:66,148 already recommends this).
- State the dev/eval split for the first comparison. Either use a shorter reporting window on Small, or name Medium or Large or LI-Small for evaluation.

R4. One run per arm can't support a comparison

LLM agents are stochastic. The proposal never mentions repeated runs, dispersion, or uncertainty estimated per case rather than per transaction. The project's own research requires all three (ibm-data-and-evaluation.md:183).

Fix: in §10, require N repeated runs per arm on the same seeds. Report variance and failure rates, and bootstrap by case or episode.

R5. "Supported" has no definition, so review decisions can't be reproduced

§8 says what the reviewer must not do (just endorse the investigator's prose) but never what "supported" means. Without a rubric, a supported/unsupported decision is whatever the model happens to say, and the primary post-review prediction set (§10) depends on it.

Fix: define "supported" as:
- every required deterministic check is valid;
- the claim matches a cited indicator's observable conditions;
- each recorded alternative explanation has been addressed or ruled out with evidence;
- no required page is still missing.

Also reduce anchoring: show the reviewer the claim and evidence before the investigator's rationale, or leave the rationale out.

R6. Claims need a structured schema or most will be "not checkable"

record_finding stores "a claim" (§5, §6), but verify_evidence can only check structured assertions. If claims are free text, "not checkable" becomes the default and the deterministic layer does almost nothing.

Fix: define a small set of typed claim kinds. Free-text narrative should sit alongside the typed claim, not replace it. For example:
- path claim: ordered IDs plus a strict or non-decreasing time rule;
- aggregate claim: scope, function, currency and threshold;
- temporal-burst claim;
- shared-entity claim.

Should address

R7. Deterministic checks are gated on review budget. In the flowchart (§2), J{Review allowance available?} comes before V[Deterministic evidence checks]. The checks are cheap and code-only, so they should always run. Only the reviewer call should be gated. As drawn, a run that exhausts its budget leaves candidates unchecked when they could have been marked valid or invalid.

R8. Follow-up reopens a closed case without a defined transition. G -->|Yes| C sends follow-up work back to "open or resume a case", but the case lifecycle in §2 (queued, active, paused, closed) has no reopen transition. The loop also runs through F → H → K again. As drawn, that re-freezes and may re-review candidates that are already supported. Specify:
- a reopen-for-follow-up transition (or "follow-up work item on a closed case");
- that only the revised candidate re-enters K.

R9. Mixed levels and unclear ownership in the flowchart.
- The chart is per-case, but Z and T are run-level.
- F has two outgoing edges (to H and to Y), which reads as parallel flow.
- Nothing says who decides N{Continue investigation?}. Section 3 doesn't assign it: the model chooses to stop, code enforces the budget.
- "Repeated unproductive actions" (§7) needs a detector. Who measures it, and on what signal, such as no new rows or candidates in k steps?

R10. Fixed-arm assessment is underspecified. §10 says the fixed arm "uses the same candidate-assessment … procedure". A fixed neighborhood can exceed one context. Is the fixed arm then assessed in one pass, paged in multiple passes, or summarized? That choice can decide the comparison, so freeze it alongside the expansion parameters.

R11. Use cost-quality curves, not equal ceilings. The fixed arm spends no tokens choosing queries, so equal resource ceilings don't mean equal spend. Report detection against actual consumed cost, and say whether the query cache from §6 is shared across arms (it shouldn't be, or charge as if uncached).

R12. Reviewer discoveries have nowhere to go. The reviewer can run its own bounded queries (§8). If it finds a new suspicious chain rather than judging the existing one, is that a new candidate, a pending action, or ignored? Also say whether reviewer-retrieved rows count toward the "presented" coverage set.

R13. Gate 4 has no pre-registered success criterion. REVIEW-RESOLUTIONS defers quality thresholds until "before held-out evaluation", but gate 4 already says "establish detection value before population scale". Pre-register the primary metric and the minimum difference that counts as value before the first comparison run. Otherwise the gate can be passed after the fact.

Minor / clarity

- "Knowledge cutoff" (§4) is ambiguous next to data cutoff T. It could mean the model's training cutoff. Rename it or define it.
- Currency conversion policy. 72,170 rows have different paid and received currencies. "Cannot be silently summed" is right, but declare whether rates implied by the paid/received pairs may be used, or whether multi-currency aggregates are always reported per currency.
- Hub accounts. The fixed policy specifies how high-degree neighborhoods are truncated (§10); the adaptive tools should too. Either expand_frontier defaults to summarize_activity above a degree threshold, or the model is told the degree before it expands.
- Readability. About a dozen "this does not prove / establish …" disclaimers make the document hard to implement from. One limitations paragraph plus one worked case (seed, two queries, a context reset, a finding, a check, a review decision) would show the contract more clearly than the prose does.
- Inconsistent naming. "Meterless Markovian" (§1) versus "Markovian" (§9).
- Unexplained reference. "The excluded original proposal and its suggested rule list are not inputs" means nothing to a new reader without a sentence of context.

What I'd keep as is

The two-axis coverage ledger, the half-open intervals, stable pagination with source-row tie-breakers, one writer per case with idempotent actions, separating implicated from supporting IDs, the frozen pre-review prediction set, and keeping branch workers and Markovian out of v1.

Suggested order

R1–R3 change what the first experiment is, so settle them first. R4–R6 are contract additions. R7–R9 are diagram edits.

I can save this as reviews/goal-and-experiment.md next to the other two reviews, or apply the diagram fixes (R7–R9) directly.