# Independent review: effectiveness and prototype practicality

Reviewed the complete `PROPOSAL.md`, SHA-256 `be66520da19d3ec90c03864cbfcc079e21c6169155be5a78c8252dd414d182d6`, including its flowchart, all eleven sections and supporting evaluation contribution. Review only; no implementation, source-data examination or inference was performed.

Overall: the design captures the user's intended adaptive investigator, durable evidence, resumable unfinished work and separate review. It correctly treats 1,000 rows as an experimental working size, avoids relying on labels for navigation, preserves exact evidence across refreshes and keeps frameworks/concurrency optional. Two small contract clarifications should be incorporated before implementation; the remaining items improve the first experiment without expanding the architecture.

## Must fix

### M1 — Define the population and scheduling units behind the coverage ledger

**Sections:** 4, 6, 10; flowchart final coverage output. **Priority:** medium.

The proposal requires distinguishing every scheduled, deferred and never-scheduled region, but does not define a region or an inventory from which that distinction can be computed. Cases overlap and grow adaptively, so counting cases or visited accounts cannot supply that denominator. This leaves a central user requirement—identifying what remains to investigate—underspecified.

**Fix:** record a finite eligible population and scheduling-unit definition in the run contract. For the initial prototype this can simply be a manifest of selected transaction seeds plus a declared reporting-row universe. Distinguish (a) seed/work-item coverage, (b) unique rows retrieved/presented, and (c) agent-recorded scoped assessments. Unscheduled rows can be computed relative to the declared universe without pretending they are enumerated unexamined episodes. State explicitly that exhausting the seed manifest is not exhaustively searching all paths. No new graph partitioning system is needed.

### M2 — Give no-finding cases an explicit terminal route in the core flow

**Sections:** 2, 8, 10. **Priority:** medium.

The prose acknowledges cases without findings, but the chart always routes a finished case through candidate checks and candidate review. A routine case with no candidate has no review packet or supported/unsupported decision. Implementing the diagram literally risks fabricating an unsupported finding, skipping the coverage report, or spending reviewer budget on an empty packet. A paused case with no findings also must retain its frontier rather than become a negative verdict.

**Fix:** branch after the investigation pass on whether any provisional candidates exist. Cases without candidates go directly to recorded case status, pending-work/coverage output and evaluator inclusion. Candidate-bearing cases enter verification/review. Keep any audit of no-finding cases a separately identified sample, rather than implying every empty case receives candidate review.

## Improvements for the prototype

### I1 — Pin the fixed-expansion policy and ordering before comparing navigation

**Sections:** 4, 5, 10, 11. **Priority:** medium; required when the comparison gate is implemented.

“Fixed expansion” is not yet reproducible: direction, time window, traversal ordering and behavior when a high-degree neighborhood exceeds the allowance remain unspecified. These choices can determine which evidence appears at all. The adaptive arm's paginated results also need stable ordering so a prefix is interpretable and repeatable.

**Fix:** add these fields to the experiment configuration. Use a simple declared policy and deterministic time/source-row tie-breaking. Both arms should receive identical truncation metadata and be charged for all returned evidence. It is reasonable to leave numerical bounds for the experiment, but explicitly list the configuration choices that must be frozen. Do not describe an arbitrarily weak fixed policy as a general baseline for all deterministic investigation.

### I2 — Preserve the investigator's pre-review snapshot and define scored statuses

**Sections:** 8, 10. **Priority:** medium.

Before/after-review metrics are valuable, but reviewer-directed follow-up can change a candidate and add implicated IDs. Versioning alone does not identify which version forms the pre-review prediction set. “Unresolved” and “unreviewed” could also be counted differently across reports.

**Fix:** freeze the initial investigator prediction set before any reviewer feedback. Define the primary post-review set as unique implicated IDs in current supported findings, and report provisional/unresolved IDs separately. Attribute added or removed detections and the extra resource cost to the complete review-plus-follow-up stage. This makes a recall loss or gain measurable without claiming that reviewer judgment alone caused it.

### I3 — Make the holdout policy explicit at the comparison gate

**Sections:** 4, 10, 11. **Priority:** low; experiment configuration, not a new system.

“Genuinely unexamined evaluation population” is the right requirement, but the supporting evaluation contribution contains an important warning missing from the integrated proposal: random transaction-row splits can place connected episode evidence in both development and evaluation sets.

**Fix:** add that warning and require a declared temporal/episode-boundary policy, including which earlier context is legitimately available. Prior observed examples remain development material. Do not require globally account-disjoint splits if that would change the intended longitudinal use case.

## Review disposition recommendation

Accept the architecture after M1 and M2. Incorporate I1–I3 as concise run/evaluation-contract additions. No reason was found to require Markovian, branch workers, a graph database, probability calibration or population-scale infrastructure before the proposed single-case prototype. The existing evidence-integrity, label-isolation, bounded follow-up and explicit uncertainty safeguards should remain.

## Targeted resolution check

Checked the revised proposal and `REVIEW-RESOLUTIONS.md` on 23 October 2026 against these five findings only.

- **M1 addressed:** sections 4 and 6 define the finite seed manifest, reporting-row universe, unique activity sets and separate pending-work inventory, with explicit limits on what coverage means.
- **M2 addressed:** the diagram and section 8 explicitly bypass candidate review for zero-finding cases, preserving case accounting and unfinished work. Section 11 includes the corresponding boundary fixture.
- **I1 addressed:** section 10 lists the fixed-policy choices that must be frozen; section 5 supplies stable pagination ordering and separates retrieval tie-breaking from causal order.
- **I2 addressed:** section 10 freezes the initial pre-feedback prediction set, defines the supported post-review set, separates other statuses and attributes changes to review plus follow-up.
- **I3 addressed:** section 10 declares a temporal/episode holdout policy and warns against random row splitting while allowing explicitly declared historical context.

No remaining must-fix findings from this review. The proposal is suitable to take into the scoped prototype gates. This conclusion validates the design resolutions, not implementation correctness or detection performance.
