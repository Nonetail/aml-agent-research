# First real NVIDIA model run

Model: `nvidia/nemotron-3-ultra-550b-a55b`. Connection and native tool calling verified on 23 October 2026.

Completed run: `20261023T162304`. Seven model calls, five model-requested queries, three deterministic path checks, and 22 distinct presented transaction records. About 55 seconds elapsed. Provider-reported usage: 28,630 input tokens + 1,875 output tokens = 30,505 total tokens for the completed run only. Currency cost is unknown.

The investigator exhausted its four-turn allowance; its retrieved evidence still went to the separately budgeted reviewer. The reviewer requested additional evidence, submitted three exploratory path candidates, received factual check failures, and marked all three unsupported. Failures included disconnected endpoints, self-transfers presented as external path edges, and invalid temporal order. This is a working integration and validation loop, not a successful laundering detection result or proof that the account is benign. No hidden labels were consulted.

Two earlier development attempts remain under `generated/runs/`: one truncated reviewer output and one provider timeout. They must not be omitted when accounting for experimentation cost; timed-out consumption is unknown. The final run uses shorter source-row aliases, bounded structured submissions, and a reviewer packet without duplicate row payloads.

The fixture suite contains 14 passing tests. Run details are in [report.json](generated/runs/20261023T162304/report.json), [proposal.json](generated/runs/20261023T162304/proposal.json), and [checks.json](generated/runs/20261023T162304/checks.json). These generated files stay local and are excluded from the source-only handover ZIP.

Remaining work: explicit operational rules, stronger investigative behavior and context continuation, durable case reopening, and a controlled comparison against deterministic detection.
