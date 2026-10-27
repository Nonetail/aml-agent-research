"""Offline comparison of Ultra generation behavior with thinking on and off."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / 'prototype/local-data/generated'
ON = GEN / 'cycle-context-nvidia-ultra-mini-v1'
OFF = GEN / 'cycle-context-nvidia-thinking-off-v1'
rows = []
for enabled, directory, names in (
    (True, ON, ['rows-100-r1', 'rows-100-r2', 'rows-100-extended-r1', 'rows-100-extended-r2']),
    (False, OFF, ['rows-100-r1', 'rows-100-r2']),
):
    for name in names:
        result = json.loads((directory / name / 'result.json').read_text())
        request = json.loads((directory / name / 'request.json').read_text())
        response_file = directory / name / 'response.json'
        response = json.loads(response_file.read_text()) if response_file.exists() else {}
        message = response.get('message', {})
        rows.append({'thinking_requested': enabled, 'run': name,
                     'output_cap': request['max_tokens'], 'status': result['status'],
                     'seconds': result['seconds'], 'usage': result.get('usage'),
                     'score': result.get('score'), 'finish_reason': result.get('finish_reason'),
                     'content_characters': len(message.get('content', '')),
                     'tool_call_count': len(message.get('tool_calls', []))})
for repetition in (1, 2):
    left = json.loads((ON / f'rows-100-r{repetition}/request.json').read_text())
    right = json.loads((OFF / f'rows-100-r{repetition}/request.json').read_text())
    left['chat_template_kwargs']['enable_thinking'] = False
    assert left == right
usage = sum(r['usage']['total_tokens'] for r in rows if not r['thinking_requested'])
result = {'comparison': rows, 'only_request_difference': 'chat_template_kwargs.enable_thinking',
          'timeout_initial_comparator_and_off_seconds': 90, 'additional_known_tokens': usage,
          'additional_dollar_cost': None,
          'limits': 'Two non-randomized calls per initial profile; backend version and first-token latency unavailable.'}
(OFF / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
lines = ['# Why the NVIDIA 100-row evaluation was slow', '',
         'The saved evidence points to prolonged generation with thinking enabled, rather than rejection of the input size. It does not establish the exact server-side cause of the single timeout.', '',
         '| Thinking requested | Output cap | Repeat | Seconds | Output tokens | Result | Valid cycles found | Invalid claims |',
         '|---|---:|---:|---:|---:|---|---:|---:|']
for r in rows:
    score = r['score']
    found = f"{score['structural_recovered']}/{score['oracle_cycle_count']}" if score else 'unavailable'
    invalid = score['invalid_true_claims'] if score else 'unavailable'
    tokens = (r['usage'] or {}).get('completion_tokens', 'unknown')
    lines.append(f"| {'on' if r['thinking_requested'] else 'off'} | {r['output_cap']} | {r['run'][-1]} | {r['seconds']:.1f} | {tokens} | {r['status']} | {found} | {invalid} |")
lines += ['', '## Direct observations', '',
          'The two truncated thinking-on responses contain analysis-like prose in ordinary `message.content`, with no native tool call. They already describe valid cycle candidates, then continue checking graph paths and considering economic assessment. This is evidence of incomplete output despite identifying candidates; it is not a completed, validated detection answer.', '']
for r in rows:
    if r['finish_reason'] == 'length':
        lines.append(f"- {r['run']}: {r['content_characters']:,} content characters, {r['tool_call_count']} tool calls, provider finish reason `length`.")
lines += ['', 'The timeout record is a client timeout after approximately 90 seconds, with no HTTP error status, response body or token usage. Our adapter uses non-streaming requests. It does not record connection/queue time, first-token time or generation progress, so that individual event cannot be attributed conclusively to a particular server stage.', '',
          '## Controlled follow-up', '',
          'The two new requests change only `chat_template_kwargs.enable_thinking` from true to false. The model, 100 rows, system prompt, schema, named tool choice, temperature, 8,192-token cap and 90-second timeout match the initial comparison. Both new calls promptly completed native tool calls, but neither found the reference. One found two valid cycles; the other made two invalid cycle claims and had no raw valid cycle claims.', '',
          'This supports a contribution from the reasoning-enabled generation path to the latency and output-budget problem. It does not make thinking-off a successful detection configuration. The calls were not randomized or concurrent, so serving-load changes are not controlled.', '',
          '## Remaining uncertainty', '',
          '[NVIDIA documents a limitation in the OSS vLLM runtime bundled with Dynamo 1.4.0](https://docs.nvidia.com/dynamo/dev/recipes/nemotron-3-ultra): thinking-enabled requests with a required or named tool can yield ordinary content instead of tool calls. The hosted endpoint’s runtime/version is unknown, and our truncations differ from the documented `stop` example. This is a relevant hypothesis, not a confirmed diagnosis of the hosted service.', '',
          'The prompt requests exhaustive discovery of two-to-four-edge cycles plus economic assessment and limitations. It therefore asks more than a yes/no cycle check. We have not isolated exhaustive search, assessment instructions or the named-tool requirement as separate causes.', '',
          'Sol’s short final JSON is not a measure of its total internal reasoning. Its subagent interface did not expose provider token accounting, so output length is not an apples-to-apples reasoning-cost comparison.', '',
          f'Additional diagnostic usage: {usage:,} provider-reported tokens. Dollar tariff unavailable. The original timeout retains unknown usage.', '',
          '- [Comparison data](../../prototype/local-data/generated/cycle-context-nvidia-thinking-off-v1/comparison.json)',
          '- [Follow-up protocol](../../prototype/local-data/generated/cycle-context-nvidia-thinking-off-v1/protocol.json)',
          '- [Thinking-off run 1](../../prototype/local-data/generated/cycle-context-nvidia-thinking-off-v1/rows-100-r1/result.json)',
          '- [Thinking-off run 2](../../prototype/local-data/generated/cycle-context-nvidia-thinking-off-v1/rows-100-r2/result.json)', '',
          'Regenerate offline with `python3 experiments/2026-10-24-cycle-context/report_nvidia_thinking.py`.', '']
(Path(__file__).parent / 'NVIDIA-TIMEOUT-DIAGNOSIS.md').write_text('\n'.join(lines))
print(json.dumps({'additional_tokens': usage, 'only_request_difference_verified': True, 'compared_runs': len(rows)}))
