# Revision 2: review decisions

23 October 2026. The user requested applying the assessment of the supplied review. This is a document revision, not an implementation or new empirical experiment. The original three drafting contributions and two reviewers remain historical evidence; their earlier approvals do not imply they reviewed revision 2.

The governing role clarification is now: investigator gathers evidence → reviewer proposes candidates → bounded deterministic checks → reviewer finalizes or asks for targeted investigation. The investigator may retain leads but does not supply the prediction set. Packet assessment is required even when the investigator has no lead; an unassessed packet is distinct from a reviewer finding no candidates.

| Review item | Decision and implementation |
|---|---|
| R1: rules and deterministic baseline | Accepted the comparison gap. Sections 3, 5 and 9 require indicator mapping and distinguish mechanics, navigation and complete-system comparisons. Added a non-LLM detector with explicit flagging semantics. Kept exploratory hypotheses separately rather than forcing every discovery into an existing motif catalogue. The earlier draft did permit prioritized seeds; it had not prohibited them. |
| R2: weak arbitrary seeds | Accepted mechanics/detection separation and pilot-based sample sizing. Arbitrary starts remain mechanics inputs. Priority seeds and separate exploration are label-free. Positive-seed prevalence is not treated as the probability of reaching positive evidence through navigation. |
| R3: periods and tail | Excluded the HI-Small tail from ordinary reporting/seeding, retained separate diagnostics. Proposed a concrete seven-day HI-Small development window with three days of preceding history, explicitly not a fresh holdout. Named primary HI-Large for later confirmatory work subject to exposure audit and frozen dates. LI-Small does not extend duration. A date artifact is not automatically direct label leakage. |
| R4: repetition and uncertainty | Added a development starting default of at least three repetitions, then pilot-informed confirmatory counts/power. Report dispersion/failures and account for overlapping cases/episodes in uncertainty. Repeats do not create independent episodes. |
| R5: support rubric | Added explicit factual validity, observable indicator conditions, contrary evidence, claim-specific completeness and implicated IDs. Qualified the suggestion to rule out every alternative: remaining plausible explanations must be disclosed, not necessarily eliminated. Initial evidence presentation avoids investigator persuasion. |
| R6: structured claims | Added path and aggregate schemas, with narrative separate. Temporal bursts can use aggregate/time scopes; recorded-entity claims are optional with validated metadata. |
| R7: checking/review budgets | Separated automatic retrieval integrity checks, reserved factual-verification resources and LLM finalization. Factual results survive lack of reviewer tokens. Expensive deterministic queries still obey limits; inability to finish is recorded. |
| R8: reopening and re-review | Added explicit logged reopen-for-follow-up, candidate revisions and checks only for new/affected candidates. Unchanged supported findings are not re-reviewed automatically. |
| R9: ownership and levels | Rebuilt chart with a case subgraph and run-level reporting. Runtime owns hard stops; model may request stop. Added a provisional three-action no-progress rule with explicit signals; negative evidence can resolve a question. |
| R10: fixed context policy | Require identical bounded-view selection, ordering, compaction and synthesis policies for navigation arms; freeze handling of oversized neighborhoods. |
| R11: actual cost/cache | Retained equal ceilings and added actual cost-quality curves. Arm/run caches are isolated with a common cold or predeclared warm policy; infrastructure conditions and usage are reported. |
| R12: reviewer discovery | Now a main responsibility: reviewer discoveries create candidate IDs and typed claims. Reviewer retrieval/presentation counts in role-specific coverage and deduplicated run union. |
| R13: success criterion | Defined recall improvement at a fixed false-positive/review allowance and total-cost ceiling. Numerical limits, meaningful difference, uncertainty rule and sample sizes must be locked before confirmatory execution; missing fields block launch. Exploratory development can measure yield before this lock but cannot claim confirmatory success. |

## Minor comments

- Renamed knowledge cutoff to data-availability cutoff, defined separately from model training.
- Declared per-currency aggregation and no general FX-rate inference in the initial prototype.
- Added bounded hub-summary/pagination behavior, with explicit unknown counts.
- Added a worked case through two queries, refresh, candidate, checks and decision.
- Consolidated general limitations and clarified why the prior brainstorming document is excluded.
- Used Meterless Markovian consistently as an optional adapter.

## Current status

The proposal is ready to guide mechanics prototyping, not a fully configured confirmatory study. Model/provider, backend, frozen operational rules, numerical resource/review limits, final held-out dates and minimum worthwhile detection improvement remain experiment-manifest choices. These must be selected on development evidence and user/product constraints before confirmatory evaluation. No held-out data or new runtime inference was inspected in this revision.

[Revised proposal](PROPOSAL.md) · [Supplied review](reviews/goal-and-experiment.md)
