# A small benchmark for the first AML rule family

Research checked: 24 October 2026, Australia/Sydney. This is a research/design note; no model calls, investigation restarts, full transaction scans, or benchmark extraction were performed. The filename follows the 23 October investigation. New measurements below read only the 323,844-byte publisher pattern file; full-file quantities come from the existing audit.

The proposed smaller dataset is a good development step. Use complete known motifs together with their original surrounding transactions, plus difficult controls. Keep three distinct evaluations: deliberately constructed correctness fixtures, source-preserving neighbourhood challenges, and an untouched chronological sample. Only the last can estimate alert workload under its observed base rate. A fixed number of invented noise transactions cannot substitute for the last two.

## What the current labels can support

IBM describes AML-Data as wholly synthetic, with a laundering tag on each transaction. The paper distinguishes named graph patterns from laundering labels propagated through subsequent transfers of illicit funds. It also models ordinary commercial and personal activity. Consequently a transaction label is not a rule-family label, and a graph shape alone does not identify illicit intent. [IBM AML-Data](https://github.com/IBM/AML-Data), [publisher paper, sections 3.2–3.4](https://arxiv.org/html/2306.16424v3#S3.SS2).

The locally pinned version-8 audit records:

| Scope | Rows | Positive transaction labels | Positive rate |
|---|---:|---:|---:|
| Complete HI-Small file | 5,078,345 | 5,177 | 0.10194% |
| Primary activity, 1–10 September inclusive | 5,077,237 | 4,522 | 0.08906% |
| Tail from 11 September | 1,108 | 655 | 59.12% |

The primary period therefore has about one positive per 1,123 rows, or approximately 1,122 negative rows per positive. These are **transaction** proportions, not proportions of cases, accounts, or motifs. A set with 99 negatives per positive has 1% prevalence, approximately 11.2 times the primary-period prevalence. It is useful as an intentionally enriched challenge, but its precision cannot be presented as operational precision. The tail is an extreme artifact and belongs in a separate completion/stress test. [Existing evaluator profile](evidence/evaluator-hi-small-profile.json).

The pattern answer file contains 370 groups and 3,209 unique positive transaction records. The existing full-file audit matched every pattern record to exactly one transaction row. The remaining 1,968 positive transaction rows have no membership in these supplied pattern records. Absence from the pattern file is therefore **not** a negative label. [Pattern profile](evidence/patterns-profile.json), [full audit](ibm-data-and-evaluation.md).

| Publisher family | Groups | Pattern rows | Groups entirely before 11 September | Groups with elapsed span ≤24h |
|---|---:|---:|---:|---:|
| CYCLE | 54 | 287 | 43 | 5 |
| FAN-IN | 40 | 318 | 27 | 6 |
| FAN-OUT | 48 | 342 | 36 | 10 |
| GATHER-SCATTER | 51 | 716 | 24 | 8 |
| SCATTER-GATHER | 44 | 626 | 28 | 1 |
| BIPARTITE | 49 | 263 | 40 | 23 |
| STACK | 43 | 466 | 31 | 9 |
| RANDOM | 41 | 191 | 32 | 17 |

The last column concerns whole groups across the complete pattern file; it is not an intersection with the preceding column. A family name records generator membership, not proof that every member meets a later rule predicate. Some FAN-IN/FAN-OUT/BIPARTITE groups contain only one record. Validate observable shape and timing separately rather than importing the group name as an observation.

## The short-cycle slice is small enough already

Read-only measurements give a useful concrete starting point:

- All 54 CYCLE groups form closed directed chains in file order, using normalized bank/account pairs. They contain 2–12 edges; median group duration is 71.88 hours and maximum is 95.62 hours.
- Only 49 of the 54 groups admit strictly increasing timestamps around the cycle. Five have multiple backward time steps, whichever edge is chosen as the start. None contains equal timestamps. All remain publisher-labelled laundering examples; five simply do not demonstrate the proposed temporal predicate with their supplied edges.
- Of the 43 groups wholly within the primary period, 40 are time-respecting.
- There are **28 primary-period 2–4-edge cycles, of which 27 are simple, time-respecting cycles**. Those 27 contain 20 account-overlap clusters: sizes 4, 3, 2, 2, and sixteen singletons.
- Within these 27, full elapsed spans fit 24h / 48h / 72h / 96h in **5 / 10 / 18 / 27** cases respectively. All five ≤24h cycles have two edges. Four of those five use a single currency.
- Fourteen of the 27 use one currency throughout. A single-currency requirement would exclude valid structural cycles and is unnecessary when detecting topology. Amount compatibility is a separate supporting observation.

These counts do not prescribe a 96h rule or claim that AUSTRAC specifies any of these time limits. Freeze the operational hypothesis and development window before evaluating it; report its eligible denominator explicitly. The 96h figure describes this known-case collection, not an independently justified risk threshold.

For the entire 54-group cycle collection, 93 adjacent legs have directly comparable received/next-paid currencies. Their next-paid/previous-received ratios range from approximately 0.6993 to 680.79, with median 1.0. The 43 primary groups contain 54 comparable legs, range 0.9070–680.79. This does not establish that the same money passed through: no account balances, provenance tracing, FX conversion ledger, or customer explanation is available in the CSV. Do not demand exact conservation or invent an exchange rate to make a known label fit.

Minute-resolution timestamps require a declared tie policy in the eventual rule. The absence of ties in these particular cycles does not establish that the dataset has none. Treat equal-time edges as unordered at the available resolution unless the rule explicitly accepts non-decreasing time; add a correctness fixture for that choice.

## Three small evaluations with different purposes

### 1. Correctness fixtures: test the contract cheaply

Create approximately a dozen tiny hand-designed graphs, each with an explicit expected **structural result** and expected factual explanation. Include a 2-edge return, 3-edge cycle, broken closing edge, reversed direction, backwards timing, equal-minute ambiguity, same account number at different banks, self-transfer, parallel row instances, currency mismatch, large amount change, and a high-degree hub with no cycle.

Some fixtures should have the same topology and different time/value evidence. They test whether the system calculates and describes observations correctly; a hand-authored positive fixture is not proof of laundering detection. If an IBM example is edited, its original laundering label is no longer authoritative for the edited example. Keep those counterfactuals in this fixture tier with explicit construction provenance.

### 2. Source-preserving challenge: recover hidden whole episodes

Use the 27 eligible short temporal cycles as a small initial catalogue, subject to the frozen time-window rule. They are enough to debug graph traversal, evidence packets, resumption and explanations. They are too few for a precise effectiveness estimate.

The evaluator may use the answer file to prepare cases; the detection agent may not. The preparation procedure should be:

1. Resolve exact pattern records to stable original transaction-row IDs, with the source checksum/version recorded. Preserve the two different `Account` columns by position, raw amount/currency values, and composite bank/account identity. Do not deduplicate parallel transactions into one edge.
2. Form partitions from whole motif/account-overlap clusters before designing prompts or thresholds. A practical desired allocation is roughly 40% development, 20% calibration, 40% blind challenge, but actual group counts must respect clusters. After extracting context, audit overlap again: one-hop neighbours or other motif families can reconnect cases. Move, merge, or purge intersecting episodes; report what was lost. The current 20-cluster count covers only the 27 target motifs, not their unextracted neighbourhoods or shared entities.
3. Define a label-independent extraction recipe that can be applied identically to positive and control seeds. For example: all source rows incident to a seed account in a fixed evidence window, followed by the rule's permitted bounded directional expansion. Use fixed lookback/end-cutoff semantics and explicit continuation cursors. Include earlier available history as permitted evidence, but no rows after the cutoff.
4. Include every target edge in a designated **reviewer-only** packet experiment, so this experiment asks whether the model can assess supplied evidence. Separately test **discovery** from uniformly presented seed accounts/windows. In discovery mode, do not inject all hidden target accounts as seeds or reveal a path-shaped case boundary. A positive-derived starting account makes this conditional investigation evaluation, which must be named as such.
5. Keep every source row selected by the recipe, whatever its hidden label. Real surrounding synthetic-source transactions can include other positive labels, other pattern families, mundane activity and competing paths. Do not silently remove them to obtain an exact ratio. The evaluator records their labels and memberships separately.
6. Deduplicate overlapping packets using stable row IDs and disclose any truncation. A case too large for one review remains one database case with multiple views; do not cut away context just to meet a row quota or make the positive easy.
7. Add source controls matched on time window, transaction format, degree, row count, currency mix and broad amount/activity scale where feasible. Mine shape-similar controls with the same label-blind deterministic candidate logic, then have the evaluator select wholly zero-label examples for a control stratum. Do not claim such matched controls represent source prevalence.

Aim initially at roughly one difficult source-negative case and one ordinary source-negative case per positive case, with the total rows determined by the extraction recipe. This is a proposed diagnostic workload, not an evidence-based optimum. No fixed “300 rows per case” or final corpus size is justified before neighbourhood-size measurements. The 27-case catalogue, not all five million rows, bounds initial reasoning experiments.

Useful difficult controls include observed zero-label circular movements, large fan-in/out hubs, return payments with an incompatible temporal order, and value/currency mismatches. Describe them only by fields actually present. Without invoices or business-purpose metadata, calling a particular pattern “payroll”, “refund”, or “treasury management” would invent a legitimate explanation. Label-zero source controls test discrimination in the simulator, not knowledge of real customer intent.

### 3. Untouched mini-stream: test discovery and false-alert burden

Freeze the entire detector before evaluating a timestamp-defined slice of the primary period selected without consulting its positive count. Use all rows in the chosen scored interval and the allowed lookback history; preserve source base rate and endpoint connectivity within that scope. If the slice has too few target episodes, report that limitation or expand using a predeclared rule independent of observed performance. Do not handpick a label-rich interval and call it representative.

“Small” here means a bounded time range and scoped objective, not exactly the same number of rows as the neighbourhood challenge. A one-day source window can contain 207,000–1,115,000 rows in this file; the database can process them while the LLM sees only selected evidence. Choose the operational unit and budget before seeing labels. The scored stream should be disjoint from disclosed development episodes to the extent claimed; if chronology allows the same accounts, describe it as future activity on known accounts, not unseen-customer generalization.

IBM's paper uses temporal train/validation/test partitions and permits earlier graph history for later evaluation, while scoring only the appropriate partition. It excludes account identifiers as predictive features and emphasizes minority-class performance. These are useful precedents, but its published supervised-model results are not directly comparable to a tiny enriched agent challenge. [Publisher evaluation design](https://arxiv.org/html/2306.16424v3#S4).

## Why “add 99 noise rows” needs a precise interpretation

A ten-edge positive motif plus 990 zero-label rows has 1% positive **transaction** prevalence only if there are no additional positive context rows. One positive motif plus 99 negative **cases** instead describes 1% case prevalence, with an unrelated transaction prevalence. Adding disconnected random rows may create a visually easy target while leaving the difficult connected neighbourhood almost unchanged.

A manually generated-noise tier can still test stress sensitivity: preserve a fixed positive motif, increase distractors, and check recovery and explanations. Mark it as a planted fixture. For the source challenge, prefer unmodified incident context and match distractors by graph/time characteristics, not just count. For operational precision, use the untouched stream. Do not reweight enriched-case precision using a transaction prevalence: case-selection mechanisms and graph dependencies differ.

## Keep answers outside the runtime

Create separate preparation/evaluation and detection environments. Raw CSV labels, pattern text, evaluator profiles, benchmark manifests, positive-derived filenames and answer-containing notes must be inaccessible to the runtime agent and its tools. Merely dropping a column from one request is insufficient if the same agent can read the underlying files.

Expose opaque case/row IDs consistently across positive and negative cases. Keep the original-row mapping in evaluator storage. Do not make target IDs predictable from file order, special naming, or packet layout. Strip the laundering column and all pattern delimiters/type names from evidence. Give both source and planted data identical serialization. Preserve labels outside the accessible database, including logs and error messages. The extraction manifest records source hashes, recipe/version, window, seed-selection policy, inclusion/exclusion reasons, truncation and split membership for later reproducibility.

The benchmark-design agent can inspect answers; it must not also run the blind investigation with those answers in memory. Use a fresh, restricted process/context for the blind run. Once a blind result informs a prompt or rule change, it becomes development evidence; reserve fresh cases for the next performance claim.

## Compare systems with the same opportunity to succeed

Start with a deterministic implementation of the chosen temporal-cycle predicate as the baseline. Compare:

| Comparison | Question isolated |
|---|---|
| Deterministic candidate enumeration vs candidate enumeration plus LLM review, identical candidates | Does review improve ranking/explanation or reduce false alerts without losing eligible targets? |
| Deterministic bounded expansion vs agent-directed expansion, identical seeds and evidence/query budget | Does adaptive investigation recover more complete targets per unit of work? |
| Reviewer packets of increasing measured size/composition, identical hidden targets | Where does reviewer accuracy or factual support deteriorate? |

Keep search recall separate from review recall. A reviewer cannot recover a target its candidate interface never permits it to express. An empty-candidate batch returning an empty list is not a successful negative review. Record useful work explicitly: new eligible target discovered, missing leg retrieved, hypothesis rejected with evidence, or no relevant information gained.

For each known target motif `M` and a returned case's **implicated** row set `A`, record `|M ∩ A| / |M|` and whether `M ⊆ A`. Also report added implicated rows `A \\ M`; separately identify zero-label false additions and labelled rows from another episode. Context rows shown only to support the explanation are not automatically implicated rows. Exact recovery (`A = M`) can be useful but penalizes valid extra discoveries, so report complete recovery and extra-edge burden alongside it.

The minimum scorecard should contain:

- Eligible motifs recovered at all, complete motif recovery, edge coverage and completion latency; missing/truncated motifs counted explicitly.
- Unique alert cases at the fixed budget, case precision under a declared matching rule, false alerts on source-negative controls, and false alerts per scored day/10,000 rows in the untouched stream.
- Unique implicated-transaction precision/recall, reported separately for target-family pattern rows, other labelled rows, and all labels. No general-laundering recall claim from only the target family.
- Evidence-ID validity, factual claim support, verified direction/timing, invented-relationship count, and whether uncertainty or missing context was preserved.
- Total database queries/rows/bytes, LLM reviews/tokens/cost, latency and failures. Count repeated retrieval and duplicate alerts as work.

Repeat stochastic reviews on the same frozen cases and report dispersion. For only a few dozen episodes, raw numerators/denominators matter more than precise-looking percentages; uncertainty should respect episode/account clusters. The initial success criterion is complete, reproducible recovery on correctness fixtures, followed by measurable benefit over the deterministic baseline at equal budget on hidden source cases. No numeric effectiveness target is justified by the current research alone.

## Reproduce the new pattern-only measurements

Run this read-only Python snippet from the repository root. It reads no transaction CSV and writes no files. The expected pattern-file hash is `2c546b5ce6009e73851f0139af053cf845f08bf92f3bc82fe1eb937dec2ef39b`. Primary means every group timestamp is earlier than `2022-09-11 00:00`. Elapsed duration is latest minus earliest; comparison is inclusive at each threshold. A temporal cycle needs strictly increasing time after some cyclic rotation; equal times are reported separately. Comparable amount ratios use the incoming edge's received currency/amount and the next edge's paid currency/amount, excluding the last-to-first edge because that would cross backwards in time.

```python
import csv, hashlib, json, statistics
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

blob = Path('data/HI-Small_Patterns.txt').read_bytes()
assert hashlib.sha256(blob).hexdigest() == (
    '2c546b5ce6009e73851f0139af053cf845f08bf92f3bc82fe1eb937dec2ef39b'
)
groups = []
for line in blob.decode().splitlines():
    if line.startswith('BEGIN LAUNDERING ATTEMPT - '):
        group = {'kind': line.split(' - ', 1)[1].split(':', 1)[0], 'rows': []}
        groups.append(group)
    elif line.startswith('2022/'):
        group['rows'].append(next(csv.reader([line])))

def account(row, column):
    return str(int(row[column])), row[column + 1]

for group in groups:
    rows = group['rows']
    times = [datetime.strptime(row[0], '%Y/%m/%d %H:%M') for row in rows]
    group.update(
        times=times, primary=max(times) < datetime(2022, 9, 11),
        hours=(max(times) - min(times)).total_seconds() / 3600,
        accounts={account(row, c) for row in rows for c in (1, 3)},
        same_currency=len({r[6] for r in rows} | {r[8] for r in rows}) == 1,
    )

family = {}
for kind in sorted({g['kind'] for g in groups}):
    chosen = [g for g in groups if g['kind'] == kind]
    family[kind] = {
        'groups': len(chosen), 'rows': sum(len(g['rows']) for g in chosen),
        'primary': sum(g['primary'] for g in chosen),
        'span_le_24h': sum(g['hours'] <= 24 for g in chosen),
    }
cycles = [g for g in groups if g['kind'] == 'CYCLE']
for g in cycles:
    rows, times = g['rows'], g['times']
    g['closed'] = all(account(a, 3) == account(b, 1)
                      for a, b in zip(rows, rows[1:] + rows[:1]))
    g['simple'] = len({account(r, 1) for r in rows}) == len(rows)
    g['ties'] = len(times) != len(set(times))
    descents = sum(a > b for a, b in zip(times, times[1:] + times[:1]))
    g['temporal'] = descents == 1 and not g['ties']

def cycle_summary(chosen):
    ratios = [Decimal(b[7]) / Decimal(a[5]) for g in chosen
              for a, b in zip(g['rows'], g['rows'][1:]) if a[6] == b[8]]
    return {
        'groups': len(chosen), 'closed': sum(g['closed'] for g in chosen),
        'temporal': sum(g['temporal'] for g in chosen),
        'ties': sum(g['ties'] for g in chosen),
        'lengths': dict(sorted(Counter(len(g['rows']) for g in chosen).items())),
        'same_currency': sum(g['same_currency'] for g in chosen),
        'hours_min_median_max': [min(g['hours'] for g in chosen),
                                statistics.median(g['hours'] for g in chosen),
                                max(g['hours'] for g in chosen)],
        'comparable_legs': len(ratios),
        'ratios_min_median_max': list(map(str, (
            min(ratios), statistics.median(ratios), max(ratios)))),
    }

eligible = [g for g in cycles if g['primary'] and g['simple']
            and g['temporal'] and 2 <= len(g['rows']) <= 4]
parents = list(range(len(eligible)))
def root(i):
    while parents[i] != i:
        i = parents[i]
    return i
for i, g in enumerate(eligible):
    for j, h in enumerate(eligible[:i]):
        if g['accounts'] & h['accounts']:
            parents[root(i)] = root(j)
print(json.dumps({
    'families': family, 'cycles_all': cycle_summary(cycles),
    'cycles_primary': cycle_summary([g for g in cycles if g['primary']]),
    'eligible_short_cycles': len(eligible),
    'eligible_same_currency': sum(g['same_currency'] for g in eligible),
    'eligible_window_counts': {h: sum(g['hours'] <= h for g in eligible)
                               for h in (24, 48, 72, 96)},
    'eligible_account_cluster_sizes': sorted(
        Counter(root(i) for i in range(len(eligible))).values(), reverse=True),
}, indent=2))
```

Remaining work is extraction and controlled evaluation after agreeing the rule contract. No neighbourhood-size distribution, source-negative cycle count, actual blind split, reviewer-size optimum, or detection result has been measured here.
