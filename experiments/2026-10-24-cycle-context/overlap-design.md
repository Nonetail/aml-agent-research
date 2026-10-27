# Grouping and snapshot-overlap controls

24 October 2026. Pure scenario construction in `prototype/local-data/cycle_view_scenarios.py`; no model inference, labels, cycle discovery, or source writes occur in this module.

## Partition comparison

`partition_views(rows, partitions, strategy='graph', anchor_id=None)` returns exact ID lists for 2, 3, or 4 disjoint views covering the same input rows once. Graph grouping builds an undirected account adjacency graph from ordinary transactions, visits accounts breadth-first from the anchor's source account (otherwise highest incident degree), and sorts neighbors by observed edge multiplicity and exact `(bank, account)` identity. Disconnected components use the same deterministic degree ordering. Each account's outgoing transactions remain one bundle; consecutive bundles are packed near equal remaining row targets. No temporal-cycle supports inform grouping. Timestamps and exact row ordinals give stable row ordering within a bundle.

The chronological control splits the timestamp/ordinal-sorted pool into nearly equal row counts. Graph grouping may produce unequal row counts because a source-account bundle is indivisible. Report actual per-view rows and tokens; do not attribute a difference entirely to graph organization if context sizes differ. An account appears as a destination in other views without owning its outgoing rows there.

`cut_edges` counts displayed edges whose destination has an outgoing bundle in other views and none in its current view. Edges reaching destination-only accounts are separately listed. This metric describes this grouping's boundaries; it is not a cycle-loss metric. The evaluator independently reports whether every support edge of each verified cycle is together in one view, across the union only, or missing from the pool. Unit tests include both graph grouping that preserves separated connected cycles and a four-edge cycle that graph grouping splits.

## Overlap comparison

`overlap_views(rows, anchor_id, view_rows, overlap_fraction, retained_ids=None, first_view_ids=None)` returns two equal-sized exact-ID views plus actual set metrics. Supplying `first_view_ids` fixes the baseline rows and order. Both snapshots retain the anchor and every optional `retained_ids` entry; all must exist in the baseline. The remaining shared and novel rows use label-blind graph priority. The second view is serialized chronologically.

The requested overlap is the shared row count divided by the second view's row count, with nearest-integer rounding (ties upward). The mandatory boundary and finite pool can raise the actual overlap. Requested 0% is therefore a **minimum-overlap condition**, not literally zero when an anchor remains. With 1,500 rows and one retained anchor, the actual minimum is 1/1,500, approximately 0.067%. With a retained four-edge candidate it is at least 4/1,500, approximately 0.267%. The output reports requested shared rows, mandatory retained rows, pool-forced minimum shared rows, actual overlap fraction, Jaccard, union size, and number/fraction of novel rows. Novel rows mean newly displayed evidence; they need not add useful information about the candidate.

A model-centered condition should use a valid support returned from the identical baseline request: retain its first edge as anchor, and separately test retaining its full exact-ID boundary. If no valid model support exists, an unlabeled anchor fallback is a separately reported condition. A support chosen by an external structural enumerator is an **externally seeded sensitivity analysis**, even if the enumerator never reads laundering labels. It must not be described as a model-discovered candidate.

## Durable evidence and candidate boundary

Row overlap controls repeated visible evidence. A durable evidence ledger should retain the union of exact source IDs independently of what the next snapshot displays. Candidate continuity additionally requires retaining the proposed support or partial path, its verification status, and unresolved account/time/direction scope. A set of previously seen IDs alone does not represent that investigation boundary.

Measure snapshot recovery, cross-snapshot/ledger recovery, novel rows, and cost separately. A low-overlap condition that loses the closing edge or cannot reconstruct a candidate must count that loss; its higher novelty is not success. Boundary-retention conditions use only model/runtime evidence, never evaluator supports. Full-cycle containment and recovery remain outside the scenario module so an evaluation answer cannot decide what evidence is shown.
