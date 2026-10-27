# Why the NVIDIA 100-row evaluation was slow

The saved evidence points to prolonged generation with thinking enabled, rather than rejection of the input size. It does not establish the exact server-side cause of the single timeout.

| Thinking requested | Output cap | Repeat | Seconds | Output tokens | Result | Valid cycles found | Invalid claims |
|---|---:|---:|---:|---:|---|---:|---:|
| on | 8192 | 1 | 66.1 | 8192 | unscorable_response | unavailable | unavailable |
| on | 8192 | 2 | 90.4 | unknown | response_unavailable | unavailable | unavailable |
| on | 16384 | 1 | 112.2 | 16384 | unscorable_response | unavailable | unavailable |
| on | 16384 | 2 | 148.2 | 16048 | received | 4/6 | 0 |
| off | 8192 | 1 | 5.7 | 455 | received | 2/6 | 0 |
| off | 8192 | 2 | 6.7 | 569 | received | 0/6 | 2 |

## Direct observations

The two truncated thinking-on responses contain analysis-like prose in ordinary `message.content`, with no native tool call. They already describe valid cycle candidates, then continue checking graph paths and considering economic assessment. This is evidence of incomplete output despite identifying candidates; it is not a completed, validated detection answer.

- rows-100-r1: 12,384 content characters, 0 tool calls, provider finish reason `length`.
- rows-100-extended-r1: 28,009 content characters, 0 tool calls, provider finish reason `length`.

The timeout record is a client timeout after approximately 90 seconds, with no HTTP error status, response body or token usage. Our adapter uses non-streaming requests. It does not record connection/queue time, first-token time or generation progress, so that individual event cannot be attributed conclusively to a particular server stage.

## Controlled follow-up

The two new requests change only `chat_template_kwargs.enable_thinking` from true to false. The model, 100 rows, system prompt, schema, named tool choice, temperature, 8,192-token cap and 90-second timeout match the initial comparison. Both new calls promptly completed native tool calls, but neither found the reference. One found two valid cycles; the other made two invalid cycle claims and had no raw valid cycle claims.

This supports a contribution from the reasoning-enabled generation path to the latency and output-budget problem. It does not make thinking-off a successful detection configuration. The calls were not randomized or concurrent, so serving-load changes are not controlled.

## Remaining uncertainty

[NVIDIA documents a limitation in the OSS vLLM runtime bundled with Dynamo 1.4.0](https://docs.nvidia.com/dynamo/dev/recipes/nemotron-3-ultra): thinking-enabled requests with a required or named tool can yield ordinary content instead of tool calls. The hosted endpoint’s runtime/version is unknown, and our truncations differ from the documented `stop` example. This is a relevant hypothesis, not a confirmed diagnosis of the hosted service.

The prompt requests exhaustive discovery of two-to-four-edge cycles plus economic assessment and limitations. It therefore asks more than a yes/no cycle check. We have not isolated exhaustive search, assessment instructions or the named-tool requirement as separate causes.

Sol’s short final JSON is not a measure of its total internal reasoning. Its subagent interface did not expose provider token accounting, so output length is not an apples-to-apples reasoning-cost comparison.

Additional diagnostic usage: 20,786 provider-reported tokens. Dollar tariff unavailable. The original timeout retains unknown usage.

- [Comparison data](../../prototype/local-data/generated/cycle-context-nvidia-thinking-off-v1/comparison.json)
- [Follow-up protocol](../../prototype/local-data/generated/cycle-context-nvidia-thinking-off-v1/protocol.json)
- [Thinking-off run 1](../../prototype/local-data/generated/cycle-context-nvidia-thinking-off-v1/rows-100-r1/result.json)
- [Thinking-off run 2](../../prototype/local-data/generated/cycle-context-nvidia-thinking-off-v1/rows-100-r2/result.json)

Regenerate offline with `python3 experiments/2026-10-24-cycle-context/report_nvidia_thinking.py`.
