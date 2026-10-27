# Verified-path review and readiness for the full dataset

2026-10-23. Development evidence using NVIDIA Nemotron and the existing HI-Small SQLite index. This is not a laundering-detection benchmark.

## Implemented

The investigator chooses one to four branches, requesting 25 rows each. Investigator and reviewer working views are capped at 150 rows; final pages may be smaller to respect the cap. The previous three-chunk/three-expansion-per-chunk and 36-page development limits remain in force.

Code constructs paths from all collected case evidence, including rows collected in different chunks. Each candidate is independently checked against the source database before review. The model assesses supplied path IDs; it no longer constructs or edits paths. All supporting rows accompany each path. Decisions must cover exactly the supplied IDs.

Construction deliberately remains bounded: one earliest-later continuation per starting edge, at most six edges per path, at most 24 candidates, chronological/numeric-ID selection. This can miss alternative paths, longer cycles and branching motifs. Candidate truncation is explicit. Verification covers endpoints, strict time, source existence/scope and claimed closure; it does not establish conserved funds or laundering. Model explanations are hypotheses, not code-verified economic conclusions.

## Evidence

- **34 automated tests pass.** These include bank identity, strict timestamps, self transfers, numeric tie breaks, cross-boundary support, page/view bounds, failed-check quarantine and incomplete-review rejection.
- **48 existing context packets pass deterministic regression checks.** All 48 generated candidate paths were independently database-valid. Expected seed traces stayed evaluator-side; no-continuation controls produced no seed path. This moves the structural task into code; it does not demonstrate improved model graph-reading ability.
- **Four final live reviewer fixtures complete**, each containing 150 source rows. The two reference fixtures each supplied two verified paths, and all four paths received assessments. The two no-continuation controls supplied zero paths and received zero path assessments. Raw remaining rows are presented separately from path packets.
- **The live three-chunk investigation completes review of 287 unique rows**, with working views of 104, 82 and 128 rows, nine expansion calls and 31 underlying query pages. All requested page sizes were 25. Both handoffs preserved evidence, anchors and cursors. All evidence matches the full source database.
- It had **97 eligible starting edges**, selected **24 verified paths**, and explicitly omitted 73 eligible starts. All 24 selected paths received assessments; all 287 collected rows were presented. There are still **63 pending scopes**. Review completion is not investigation completeness.
- The main run used 12 investigator/checkpoint calls, one failed original review, and six successful review calls after the fix. The corrected review reused the saved evidence in a copied run directory; navigation was not repeated.
- Across the main run and both fixture attempts: **29 real model calls, 236,807 provider-reported tokens, zero unknown-usage calls**. Dollar cost is unavailable. Original main calls copied into the resumed run are counted once.

The first live attempt failed on two reference fixtures and the main review: one truncated output and two incomplete decision lists. The original requests/responses remain saved. The correction forces the named reviewer tool, disables parallel calls, constrains the exact decision count and requests short reasons. Runtime ID validation remains mandatory. All four fixture reruns and the resumed main review passed afterward; this small sample does not establish general provider reliability.

## What “five million rows” means here

The data layer already contains **5,078,345 real source rows** from the synthetic HI-Small dataset. Existing and new model runs query that entire indexed database; their evidence budgets restrict how much is retrieved per case. We refreshed the full row count, SQLite integrity check, account/time index checks and 52 distributed CSV-to-database row comparisons. Those checks passed.

Under the current scope:

| Population | Rows |
|---|---:|
| Entire stored file | 5,078,345 |
| Authorized history plus reporting interval, Sep 1–10 | 5,077,237 |
| Reporting interval, Sep 4–10 | 3,000,485 |
| Stored later rows excluded by the cutoff | 1,108 |

A literal all-file detection run would require changing the reporting/cutoff policy. No such scope change was made. The data is publisher-generated synthetic data, not production financial records.

We are ready for a **larger, bounded multi-case pilot against the full database**. We are not ready to claim dataset-wide detection coverage. The remaining work is:

1. **Define the population and case seeds.** Freeze a label-free seeding policy and a reproducible stratified pilot, such as 100 seeds spanning low/high-degree accounts and reporting days. Keep publisher-labelled challenge cases separate. Report coverage of the population, not just number of model calls.
2. **Add the dataset scheduler.** Queue/checkpoint cases, resume deferred scopes, deduplicate overlapping evidence/findings, enforce global token/time budgets and handle provider rate limits. Current durability covers a case's pages; it is not a complete multi-case job system.
3. **Make candidate coverage adequate and measurable.** The current 24-path/six-edge greedy generator and three-chunk budget are mechanics limits. A bounded prioritized candidate queue, longer-path handling and explicit fan-in/fan-out representations are needed before testing broad detection claims. More rows alone do not solve these omissions.
4. **Freeze detection outputs and evaluate them.** Decide what constitutes a reported finding and how it maps to source rows/publisher groups. Measure precision, recall, false positives, unresolved/deferred cases and cost on held-out cases; never expose labels to investigator/reviewer. Structural path validity is a separate metric from detection accuracy.

The next useful milestone is a reproducible 100-case pilot with those scheduling and measurement controls, still using 25-row pages and 150-row working views. Measure unique coverage, deduplication, deferral, latency and tokens before estimating a full sweep. One selected neighborhood cannot support a defensible whole-dataset cost estimate.

## Artifacts

- Current behavior and commands: `CHUNKING.md`.
- Final deterministic/live fixture evidence: `generated/verified-review-v2/` (`offline.json`, `completion.json`, four case directories).
- Original failed fixture evidence/source: `generated/verified-review/`.
- Original investigation: `generated/verified-paths-live-01/`; resumed successful review/audit: `generated/verified-paths-live-02/`.
- Updated database validation: `generated/verification.json`; scope counts: `generated/verified-review/scale-counts.json`.
- Previous threshold code: `generated/thresholds-v2/frozen-source/`. Its independent audit still passes for all 392 saved cases and 48 packets.

Generated directories and credentials are excluded from the source-only ZIP. Historical threshold results remain unchanged; 150 rows is an experimental working allowance, not a newly validated safe context threshold.
