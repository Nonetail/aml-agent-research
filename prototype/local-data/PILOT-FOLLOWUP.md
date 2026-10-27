# Recovery findings from the first pilot smoke cases

The v1 baseline is immutable. These findings describe needed follow-up work; no runtime repairs were applied during the run.

- Case 001 returned 25 restoration IDs that were already visible. The runtime rejected the action before mutation. Its preceding valid work remains stored.
- Case 002 repeated an eviction ID. The runtime rejected the action before mutation.
- Case 003 encountered a provider read timeout. Provider usage for that request is unknown and retains a conservative budget reservation.
- Case 004 proposed a view revision that freed no capacity. It was rejected.

A received model response is not necessarily an applied action: semantic validation follows schema validation. Results therefore distinguish execution failure from structural replay failure.

The prototype preserves evidence and cursors, but `segment()` does not persist its complete in-progress batch journal. Calling it again on an unfinished chunk overwrites the chunk-start artifact and resets local batch history. Do not silently rerun failed baseline directories or claim their replay is certified.

A subsequent iteration should persist the original chunk start, batch journal and view-event offset after every applied action. Record applied/rejected actions explicitly, and have the auditor prove rejected actions made no changes. Clarify keep/evict/restore semantics and enforce unique IDs. A single corrective retry can remain within the existing case budget, followed by an explicit resumable pause if it fails. Provider timeouts also require explicit unknown-outcome accounting.

Verify recovery using interrupted fixtures and the saved rejected-response fixtures before freezing a new live baseline. The current failure rates are descriptive results from selected smoke cases, not population estimates.
