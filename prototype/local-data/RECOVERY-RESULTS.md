# Recovery validation results

The recovery implementation passes offline validation. The real-model regression is incomplete because both cases exhausted bounded provider retries. The 100-case pilot was not restarted.

Changes: distinct bounded eviction lists, advertised restoration choices, one corrective view response, one bounded transient-provider retry, durable chunk and batch journals, cached-response reuse, and independent verification of rejected actions.

## Validation

- 74 automated tests passed.
- 6 original saved view-manager responses were rejected without mutating evidence, cursors or views; corrective handoffs succeeded.
- Two saved real-model states resumed using scripted offline responses. Both passed independent replay at120pages each, covering 5 retained failures and 95 review packets.
- Scripted continuation is not evidence of real-model end-to-end success.

## Real-model regression

- Two original failed seeds, serial, unchanged120page/160call limits, shared4M token ceiling.
- 15 attempted provider calls; 86,327 reported tokens; 246,314 conservatively charged tokens; 5 unknown-usage calls.
- Both cases paused on repeated provider failures. The request error types were not captured by this frozen regression version, so the report does not attribute them to a specific HTTP status. Sanitized error type/message recording has since been added.
- Original baseline and live regression artifacts remain unchanged. Resume newer journaled cases only with appropriate shared-budget accounting. Legacy v1 open chunks cannot be retroactively certified.

Remaining limitation: a paused open chunk receives no full replay certificate until it is resumed and closed. Dollar cost is unverified. These results assess execution mechanics, not laundering detection accuracy.
