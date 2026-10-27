# Review resolutions

Historical note: this file records revision 1. [Revision 2 decisions](REVISION-2-DECISIONS.md) supersede its agent-role ordering and prediction-snapshot definition. The two reviewers' confirmations below apply to revision 1, not the later rewrite.

23 October 2026. Three drafting agents contributed flow, state/tools, and verification/evaluation. Two different agents then independently reviewed the entire combined draft with SHA-256 `be66520da19d3ec90c03864cbfcc079e21c6169155be5a78c8252dd414d182d6`. The proposal was held unchanged while those full reviews ran.

The findings concern design completeness, not measured runtime bugs. All requested fixes and improvements below were incorporated into [PROPOSAL.md](PROPOSAL.md).

| Review finding | Resolution | Location |
|---|---|---|
| Correctness C1; Effectiveness M2: no-finding and mixed-finding paths missing from diagram | Added no-candidate exit, independent candidate checks, explicit not-checkable/unreviewed routes and case accounting separate from findings | Sections 2, 8, 11 |
| Correctness C2: pagination could omit equal-time or parallel transfers | Defined stable timestamp/source-row order, scope-bound cursors and branch/union pagination semantics; tie-breaking does not establish chronology | Sections 5, 11 |
| Correctness C3; Effectiveness M1: coverage denominator and scheduling inventory undefined | Defined reporting-row universe, distinct unique-row sets, separate seed manifest/work queues, history accounting and limits on motif coverage | Sections 4, 6, 11 |
| Correctness C4: timestamp inclusivity unclear | Defined reporting/history half-open intervals and exclusive cutoff; no invented timezone or order within a minute | Section 4 |
| Effectiveness I1: fixed expansion insufficiently specified | Listed policy parameters and ordering that must be frozen before comparison; limited conclusions to the tested baseline | Section 10 |
| Effectiveness I2: before-review predictions and scored statuses ambiguous | Defined immutable initial investigator set and current supported post-review set; separate unresolved/rejected/unreviewed outputs; attribute change to review plus follow-up | Section 10 |
| Effectiveness I3: holdout boundary policy missing | Required declared temporal/episode policy, warned against random row splits, distinguished historical monitoring from unseen-entity evaluation | Section 10 |

The three contributions also supplied provisions already integrated before review: automatic evidence receipts, separate case/work/finding lifecycles, reserved reviewer resources, version-specific review, supporting-versus-implicated IDs, incomplete pattern annotations and bounded follow-up.

Both reviewers subsequently performed targeted checks of the revisions and appended confirmations to their review files. Correctness C1–C4 and Effectiveness M1/M2/I1–I3 are addressed, with no remaining must-fix findings from those reviews. This confirms design resolutions only; runtime mechanics and detection quality remain untested.

## What remains open

Numerical budgets, provider/model, query backend, exact seed sample and operational thresholds must be recorded before an experiment. They are deliberately not invented as validated settings here. Prototype mechanics and detection acceptance targets are different: the design supplies concrete mechanics checks; empirical quality thresholds must be chosen before held-out evaluation.

No reviewer identified a need for additional frameworks, production-scale infrastructure or branch agents in the first prototype. Markovian and investigation subagents remain controlled later comparisons. Neither design review nor a second runtime agent constitutes proof of detection accuracy.

## Files

- [Draft contribution: flow](contributions/flow.md)
- [Draft contribution: state and tools](contributions/state-and-tools.md)
- [Draft contribution: verification and evaluation](contributions/verification-and-evaluation.md)
- [Full review: correctness](reviews/correctness.md)
- [Full review: effectiveness](reviews/effectiveness.md)
