# Short-cycle context, grouping and movement experiment

24 October 2026. Freeze this protocol, source code, case manifests, rendered requests and tokenizer configuration before the first hosted call. The intended implementation is `prototype/local-data/cycle_context_eval.py`; the frozen manifest identifies the executable actually used. This study measures exact short-cycle discovery in supplied transaction evidence. It does not measure laundering classification, production prevalence or source-wide investigation completeness.

The preparing and scoring agents have seen evaluator answers. They construct and score the experiment; they are not its blind detector. Hosted inference receives only the frozen common system prompt, unlabelled rows, format and scope metadata, and the response schema. Each request starts a fresh context. No conversation history, files, shell access, evaluator labels, publisher group IDs, target paths, known cycle count, precomputed candidate list or previous scoring result is exposed. Do not identify a packet as positive, negative, seeded or held out in its model input.

## Questions and fixed meaning of success

1. Can the model discover exact known positive 2-, 3- and 4-edge temporal cycles among 1,500 ordinary rows without a supplied starting edge or candidate?
2. How do 300-, 750-, 1,500-row views and much larger token-budgeted inputs affect discovery, invalid claims, token use and latency? A request fitting the advertised context is distinct from successful evidence use.
3. Do two, three or four graph-based views improve discovery over a single view and chronological splitting? How much apparent loss comes from breaking the supporting cycle across views?
4. At the next view, what do 0%, 25%, 50% and 75% overlap trade in unique evidence coverage and retained/recovered support? Does retaining a complete model-discovered path help more than arbitrary row overlap?

The predicate is [short-temporal-cycle-v1](../../prototype/local-data/CYCLE-RULE.md): 2–4 external edges, exact `(bank, account)` identities, simple directed closure, strictly increasing recorded timestamps, all within declared scope. No implicit 24-hour duration limit or equal-currency requirement applies. Existing dataset and source files remain read-only.

The fixed reviewer asks the model to discover eligible cycles from the table and report exact ordered transaction IDs. It separates `pattern_present` from `investigate`, `insufficient_evidence` and `not_supported`. Empty observations are permitted. Structural discovery does not require an `investigate` recommendation. Any explicit discovery instruction added to the existing reviewer prompt is fixed and hashed for every condition.

## Cases and contamination boundary

Use the full original source and its evaluator catalogue to obtain six distinct eligible-episode account clusters. V2's 300,000-row corpus contains only two eligible publisher episodes and no publisher-labelled four-edge case; it is insufficient on its own for this comparison. The wider source contains 29 eligible publisher short cycles, as documented in [CYCLE-DATASET.md](../../prototype/local-data/CYCLE-DATASET.md).

| Case role, evaluator only | Publisher group | Edges | Account-overlap cluster |
|---|---:|---:|---:|
| Development reference | 24 | 2 | 24 |
| Development reference | 74 | 3 | 74 |
| Development reference | 68 | 4 | 68 |
| Held-out confirmation | 143 | 2 | 143 |
| Held-out confirmation | 167 | 3 | 167 |
| Held-out confirmation | 155 | 4 | 155 |

Freeze the actual selected source rows and clustering output in evaluator-only artifacts. Group 127 was a previous threshold study's live reference (`pattern_index=126`) and is deliberately excluded from the held-out set. V1/V2 and earlier probes are development evidence. “Held out” means not used for this experiment's policy selection and not knowingly used as a previous live reference; source-publication exposure and prior incidental background exposure are unknown. Distinct reference account clusters do not guarantee fully disjoint background or statistical independence. Report actual shared rows and accounts across cases; exclude any other selected reference cluster from a case's constructed background.

Three additional development controls are fixed before inference:

- A packet with an exact structurally valid cycle whose members all have zero evaluator labels. Recovering this cycle is a structural success, not a false positive. If the full packet contains other positive rows, identify that evaluator-only limitation; prefer a wholly zero-labelled control when feasible without altering source rows.
- A packet whose complete supplied graph has no eligible cycle, confirmed by the independent oracle. Build from real source rows by retaining only edges whose source composite account sorts before its destination composite account; this global ordering forbids directed cycles. This is a topology-selected control, not a natural negative sample. An acyclic sampled packet does not establish benign source accounts.
- A naturally selected, label-blind source window without screening for labels or cycles. Take the first 1,500 transactions at or after original row ordinal 2,000,000 within the full declared interval, ordered by source ordinal; self-transfers remain present. Report actual label and cycle counts after selection. The case pool extends the same selection to 6,000 rows. One window is only a natural-selection sanity check; it cannot estimate population prevalence or reliable precision.

Positive cases deliberately seed complete source reference supports into real background. They are stress cases, not naturally prevalent alerts. Preserve exact source fields and row-instance identities; do not fabricate distractors or merge parallel rows. Background combines a seeded uniform source-row sample and incoming/outgoing rows incident to the selected reference accounts from 24 hours before its first edge through 24 hours after its last edge. This padding is an extraction choice, not a cycle-duration threshold. Record any context cap/subsampling policy and the exact source counts. Use the same 1,500 unique-row packet for baseline, grouping and chronological controls. Nested 300/750 subsets keep the selected reference support and a fixed prefix of the same background; this label-informed inclusion is an evaluator construction choice and is not disclosed to the model. Record all other cycles and positive labels appearing incidentally.

Preserve the same table order and aliases on exact repetitions. This isolates repeated inference variability. Grouping and ordering interventions are identified separately and are not described as identical-prompt repeats. Save full source-ID mappings privately. The output alias cannot encode a label or publisher group.

## Staged matrix and call budget

| Stage | Conditions | Maximum hosted calls |
|---|---|---:|
| A: baseline | Six development cases × 1,500 rows × two identical-packet fresh-context repetitions | 12 |
| B: small views | Three development references × 300/750 rows × two repetitions | 12 |
| C: graph grouping | Three development references × 2/3/4 groups, one call per group, one repetition | 27 |
| D: chronological comparator | Three development references × three chronological views | 9 |
| E: large context | Three development references × approximately 150,000/190,000 input tokens | 6 |
| F: next-view overlap | Three development references × 0/25/50/75% overlap | 12 |
| G: whole-path carryover | Three development references × zero generic overlap plus complete model-validated path retention | 3 |
| H: confirmation | Three held-out references × two repetitions × (single 1,500-row view + selected graph policy of at most four views) | 30 |
| **Maximum planned total** | Stage H uses fewer calls if the selected policy has two or three groups | **111** |

The configuration ceiling is 120 attempted provider requests and 10 million token units, with conservative reservation for in-flight and unknown-usage calls. Approximately 3–7 million tokens are anticipated; this is a planning range, not a measured cost. No dollar estimate is asserted without the actual account tariff. There are no hidden retries. Each additional attempt has a new recorded identity and consumes the same ceiling. Incomplete stage execution is reported explicitly.

Stages use the same frozen cases. Run A/B before selecting a working-view recommendation. Run C/D before choosing a graph policy. Grouping development has only one repetition and is a screen; two held-out repetitions assess the chosen policy. Do not use held-out scores to switch policies and then call the replacement held out.

Large inputs are a separate stress probe, not a full factorial crossing of all sizes, orderings, group counts and overlap settings. They are not skipped simply because the advertised maximum is large or small. If the measured endpoint/template limit cannot admit a planned condition, record it as ineligible with its measured token count rather than sending an invalid request or silently shrinking it. There is no full autonomous-navigation arm in this study.

## Grouping and retention

Graph grouping uses an undirected account-adjacency breadth-first traversal, with edge-weighted neighbor order and deterministic ties. Keep all outgoing rows from the same source account together as one bundle, then pack successive bundles toward balanced group sizes. Freeze the exact neighbor/tie ordering, packing implementation and parameters. This uses ordinary connectivity, without labels, reference memberships, precomputed cycles or oracle feedback. Each original edge is assigned to exactly one base group; group unions must equal the 1,500-row source packet with zero duplicated edges. Do not repair groups to ensure that a known cycle fits. Report actual group sizes, connected-account statistics and any imbalance rather than calling all groups equal-sized by assumption.

Chronological grouping sorts by timestamp with stable source-row tie breaking and divides the same rows into three consecutive balanced views. Row ordering never changes the strict-time predicate. Fresh isolated requests inspect each group; aggregate their accepted supports by exact transaction tuple. No summary or observation from one group reaches another group.

Before inference, compute for every grouping:

- Unique union edges and total displayed rows, including duplicates if the implementation later adds any.
- Eligible cycles in the whole original packet and eligible cycles wholly present in at least one individual view.
- Reference supports wholly present in at least one view, and references split across views.
- Structural/reference retention ceiling: wholly visible supports divided by all original packet supports.

Report model recovery against both the original packet denominator and the visible-support denominator. A model cannot recover a complete exact support absent from every view; that loss belongs to the grouping policy. Recovery conditional on visibility alone can conceal a bad partition. Do not pool individual view oracle denominators without deduplicating shared supports.

## Controlled next-view movement and overlap

Use the saved first baseline response for each positive development case as the common starting observation. Select the first independently valid returned path in response order and use its first edge as the navigation anchor. When no valid path was returned, use a deterministic degree-based anchor selected from ordinary first-view rows. Record the fallback explicitly. No reference answer may choose or repair the anchor. Reusing the same saved response consumes no new call and is not another independent observation.

Reuse the case's prebuilt 6,000-row source pool: reference support, capped incident context, then seeded background. This pool was deliberately constructed with a known reference episode; it is not an independently retrieved neighbourhood selected by the model. The model-discovered or label-blind fallback anchor changes graph priority inside that fixed pool. This is a controlled movement and candidate-retention sensitivity test, not an autonomous database-navigation experiment or a source-wide coverage claim. Record the source extraction caps, pool size and anchor origin. The first 1,500-row view remains identical across overlap conditions.

For each overlap condition, construct a 1,500-row next view from a deterministic subset of the original view plus the same ordered new-row pool. Targets are 0, 375, 750 and 1,125 repeated rows. Cap by actual available rows, deduplicate IDs and report achieved counts; do not quietly substitute unrelated rows. As overlap increases, the number of new rows decreases. Where possible use nested retained-row sets and nested new-row prefixes to avoid changing two unrelated selections.

The whole-path variant has zero generic overlap and retains every edge of the first model-discovered, independently valid path, filling remaining positions from the new-row pool. If the first response has no valid path, mark this intervention unavailable; do not supply a reference path. The path is carried as ordinary table rows, without a candidate hint. If any metadata or prior prose is carried, that is a separately named intervention and cannot be pooled with the ordinary-row arm.

For each view and each first-plus-next sequence report total displayed rows, unique rows, duplicate rows, new-row count, unique accounts, fully visible cycles, target retention, newly discovered cycles and recovered references. Define duplication as `total_displayed_rows - unique_union_rows`; report its fraction of total displayed rows. Report accepted-cycle union across the two responses separately from recovery in the second view. Initial recovery cannot be credited as new recovery. Plot recovery against cumulative unique rows and actual input/output tokens, not overlap percentage alone.

## Tokens and the context claim

Freeze provider, exact model identifier, endpoint, reasoning settings, sampling parameters, maximum output and tokenizer/template version in the manifest. The planned endpoint budget is 200,000 tokens with 4,096 output tokens and a 4,096-token safety margin. This is the experiment's configured operating ceiling; an advertised roughly one-million-token model capability is not proof that this provider endpoint accepts or reliably uses that amount.

Count the complete locally rendered request, including system text, table, tool/schema and chat-template overhead. Record the template method and whether special/tool tokens are estimated. Require estimated input + output reserve + safety margin within the configured limit. Save provider-reported prompt/completion usage and the difference from the local estimate. If exact server serialization is unavailable, local counting is a documented estimate, not a provider-certified exact count.

Large packet construction targets approximately 150,000 and 190,000 **input** tokens while retaining the same reference source support and adding real source rows in a deterministic nested order. Never pad with repeated meaningless text. Record achieved rows, unique edges, input tokens, source hash, dilution ratio and token margin. The near-ceiling condition must satisfy the full-request guard; token fit and completion success are reported separately from discovery quality.

Use measured token counts and latency for comparisons. A three-view grouping can reduce peak input while increasing call count and repeated system/schema overhead. Compare total cost, peak context and unique evidence together; “smaller context” does not imply lower total cost.

## Scoring and predeclared decisions

`cycle_context_scoring.py` independently enumerates every eligible cycle in the exact supplied rows using an adjacency traversal separate from CycleTools. Test fixtures cover four edges, bank identity, timestamp ties, repeated internal nodes, self-transfers, parallel row instances, omissions, duplicate supports, unsupported IDs and false claims. Enumeration is offline and evaluator-only.

Keep the following outcomes separate:

- **Structural exactness:** all and only the eligible supplied-table cycles returned as `pattern_present=true`, in exact chronological edge order. Structural recall is recovered eligible cycles divided by the oracle count. When the count is zero, recall is undefined; a valid empty cycle set can still be structurally exact.
- **Known-reference recovery:** exact complete publisher reference support recovered, independent of assessment status. Partial edges and a valid alternative cycle do not recover that episode. Report source-reference denominator, visible-reference denominator and retention ceiling.
- **Claim validity:** unknown IDs, wrong path order, invalid closure/identity/time, inconsistent `pattern_present`, duplicate supports, unsupported scopes and schema failures. A valid `pattern_present=false` observation is checked but is not a detected cycle. Whole-response contract failure contributes zero strictly accepted supports; raw otherwise-valid supports remain diagnostic.
- **Label composition:** zero-positive, all-positive, mixed or unknown-label membership of accepted cycles; positive source rows covered; and label composition of rows in `investigate` assessments. All-zero structurally valid cycles are not structural false positives. Hidden labels do not determine whether a model should have assigned `investigate`, and are not proof of real-world criminal intent.

The 1,500-row positive screening gate is at least five of six reference recoveries across the three positive cases and two repetitions, with zero invalid-edge/unsupported-ID claims. All six positive response slots must have completed for this gate to pass. A missing provider response leaves the screen incomplete. Schema failure or model truncation after a returned response counts as a quality failure. Report controls separately; the acyclic control must have no accepted or asserted invalid cycle to pass its control check. The zero-labelled-cycle control should be judged by structural recovery and restrained interpretation separately.

The same five-of-six gate applies to each small size and to the single-view held-out confirmation, with the same failure handling. Passing is provisional evidence on deliberately constructed cases, not a reliability guarantee. Do not relax gates after seeing results.

For grouping selection, rank candidate policies by original-packet reference recovery, then the sum of per-case original-packet structural recalls, then fewer invalid or unavailable responses, then fewer total measured input/output tokens, then fewer groups. An incomplete screen remains inconclusive regardless of this diagnostic ranking. Always show retention ceilings beside this ranking. A zero-recovery screen does not establish a useful policy: mark no demonstrated grouping advantage and still report the diagnostic comparison if confirmation is run. Claims of advantage require a visible improvement over the paired single-view baseline; an equivalent result with lower peak context is described as a peak-context benefit with its total-call/token tradeoff.

Overlap conditions are exploratory mechanisms on three fixed cases. Report paired case-level changes and the Pareto tradeoff among new coverage, retained support, new discovery and tokens. Do not declare an optimal universal overlap percentage from this sample. Whole-path carryover may be compared only on cases where an initial valid model-discovered path existed.

HTTP/rate-limit/network failures have no assessable model answer and are excluded from the completed-response quality denominator, but remain in an all-attempt operational denominator with usage/reservation and latency. Report both denominators side by side. Never turn a provider error into evidence that the model could not understand the table; never omit it from execution reliability. No silent retry or success-only report is permitted.

## Provenance and report

Store immutable source hashes, source-ID mappings, evaluator target paths/labels, packet/request hashes, exact model settings, tokenizer identity, grouping/overlap manifests, complete requests/responses, attempts, failures, usage and elapsed times in the new experiment output directory. Existing outputs are not overwritten. Resume skips recorded attempts; any deliberate repeat requires a new identity. A changed prompt, source packet, algorithm or schema requires a new condition/version and is not pooled with the frozen original.

The report must include the actual executed matrix, omitted/ineligible conditions, source and grouping retention, all-attempt operational results, completed-response quality, case-level paired outcomes, duplicate/unique coverage and total versus peak tokens. Include every control and both repeat outcomes. Natural-window results and seeded stress cases occupy separate tables. State explicitly that short-cycle topology, hidden-positive recovery, economic concern and a laundering verdict are different claims.
