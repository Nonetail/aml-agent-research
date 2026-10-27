# Two-case evidence-format probe

Date: 23 October 2026. Purpose: try the proposed transaction-table format on one label-positive and one label-negative IBM example, with isolated model assessments. This is a deliberately selected illustration, not an accuracy benchmark or calibrated classifier evaluation.

## Source and selection

Use the existing pinned HI-Small transactions, account metadata and publisher pattern file. Source hashes are recorded in the [research manifest](../../research/evidence/download-manifest.json). No user-supplied document is used.

Positive eligibility: a publisher CYCLE group with exactly six strictly time-ordered edges and six distinct accounts, starting on or after 2 September and ending before 10 September 2022, with duration at most three days. Choose with fixed seed `20261023`. These readability/coverage criteria deliberately select a recognizable reference pattern. There is only one eligible group in this file; selection is not representative.

The common observation window runs from twelve hours before the group's first transfer to twelve hours after its last transfer. For either case retrieve **every transaction touching any of six focus accounts in that window**, without payment-channel filtering or row truncation. The positive focus accounts are the complete reference group's accounts. Stop rather than silently truncate if its packet exceeds 150 rows.

For the negative example, reservoir-sample 64 zero-labeled non-self ACH transactions from the same window using the fixed seed. For each anchor, begin with its two endpoints and add the earliest distinct neighbors of its sender until there are six focus accounts. Retrieve the same complete incident context. Select the first candidate whose entire packet has zero labels and whose row count is between half and twice the positive packet's count, capped at 150. Do not filter candidate topology or require the absence of a suspicious shape. This matches window and focus-account count and roughly matches row count; it does not match all graph properties, currency mixtures or selection mechanisms.

The selection code is [build_packets.py](build_packets.py). The private [truth record](evaluator/truth.json) contains the original source row positions, complete source rows, original identifiers, labels, selection details and derived packet-level truth. Row positions exclude the CSV header. Labels are used for selection and evaluation only.

## Inputs and model isolation

Apply the same formatter to both cases: stable local account/entity/transaction aliases, original timestamps, paid/received amounts and currencies, payment formats, focus-account statistics, and explicit coverage/missing-context metadata. No label, pattern-file title, original row position or selection rationale is included in model inputs. Original identities remain in the private evaluator mapping.

Use the [same six guidelines and assessment prompt](common_prompt.md) for both. These are qualitative behavior guidelines; numerical thresholds have not been fitted or claimed to be official. This experiment tests evidence interpretation, not compliance with a frozen executable rule engine. No precomputed cycle/risk classification is supplied; only exact account statistics accompany the transactions.

Freeze and hash inputs before starting assessment. Spawn fresh subagents with `fork_turns="none"`; give each one input file containing only the common prompt and its own Markdown packet. Do not disclose the other case or the positive/negative balance. Permit one initial read of that input file; prohibit any other tool use, file access, external sources or communication with other agents. This is instruction-level isolation in a shared environment, not an OS sandbox. Preserve the first complete response, and record any retry explicitly.

## Target and reporting

The derived packet label is 1 if at least one displayed row has `Is Laundering=1`, otherwise 0. IBM does not publish a natural whole-packet label. An all-zero packet does not prove its entities are clean outside the selected view.

Ask for an uncalibrated subjective probability of this target and a separate further-review recommendation. A probability at least 50 produces predicted label 1. Report both original assessments, label counts and whether the thresholded predictions match this derived target. Verify cited IDs and important factual graph/time/amount claims against the raw source mapping.

Do not rerun to get a preferred result, tune the prompt after seeing scores, or report two correct cases as a reliable accuracy estimate. Both cases are now development examples and must be excluded from any claimed untouched evaluation. The selector knows the labels, and model pretraining exposure to this public dataset is unknown.
