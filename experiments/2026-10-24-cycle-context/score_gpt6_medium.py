"""Score saved isolated-subagent answers; makes no model calls."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'prototype/local-data'))
from cycle_context_scoring import oracle_cycles, score_answer

OUT = ROOT / 'prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1'
protocol = json.loads((OUT / 'protocol.json').read_text())
baseline = json.loads((OUT / 'single-1500-p0/evaluator.json').read_text())
full_oracle = set(map(tuple, oracle_cycles(baseline['rows'])))
targets = set(map(tuple, baseline['targets']))
runs, aggregates = [], []
for condition, views in protocol['conditions'].items():
    visible = set()
    for view in views:
        evaluator = json.loads((OUT / view['key'] / 'evaluator.json').read_text())
        visible.update(map(tuple, oracle_cycles(evaluator['rows'])))
    for repetition in range(1, protocol['repetitions'] + 1):
        accepted, raw, invalid, completed = set(), set(), 0, 0
        for view in views:
            directory = OUT / view['key']
            response = directory / f'run-{repetition}-response.json'
            if not response.exists():
                continue
            evaluator = json.loads((directory / 'evaluator.json').read_text())
            answer = json.loads(response.read_text())
            score = score_answer(evaluator['rows'], answer, evaluator['targets'], evaluator['labels'])
            (directory / f'run-{repetition}-score.json').write_text(json.dumps(score, indent=2) + '\n')
            completed += 1
            accepted.update(map(tuple, score['accepted_cycles']))
            raw.update(map(tuple, score['raw_valid_cycles']))
            invalid += score['invalid_true_claims']
            runs.append({'condition': condition, 'view': view['key'], 'repetition': repetition,
                         'response_sha256': hashlib.sha256(response.read_bytes()).hexdigest(),
                         'reference_assessments': [{'path': o['transaction_ids'], 'status': o['status']}
                                                   for o in answer.get('observations', [])
                                                   if tuple(o['transaction_ids']) in targets and o['pattern_present']],
                         'score': score})
        aggregates.append({'condition': condition, 'repetition': repetition,
                           'views_completed': completed, 'views_planned': len(views),
                           'view_rows': [v['rows'] for v in views],
                           'structural_denominator': len(full_oracle),
                           'structural_visible': len(visible & full_oracle),
                           'structural_recovered': len(accepted & full_oracle),
                           'raw_structural_recovered': len(raw & full_oracle),
                           'reference_denominator': len(targets),
                           'reference_visible': len(targets & visible),
                           'reference_recovered': len(targets & accepted),
                           'invalid_true_claims': invalid,
                           'complete': completed == len(views),
                           'structural_exact': completed == len(views) and accepted == full_oracle and invalid == 0})
results = {'model_requested': protocol['model_requested'], 'reasoning_effort': protocol['reasoning_effort'],
           'runs': runs, 'aggregates': aggregates, 'provider_tokens': None, 'dollar_cost': None}
(OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
baseline_results = [a for a in aggregates if a['condition'] == 'single-1500']
baseline_complete = all(a['complete'] for a in baseline_results)
baseline_exact = baseline_complete and all(a['structural_exact'] for a in baseline_results)
grouped_ran = any(a['views_completed'] for a in aggregates if a['condition'] != 'single-1500')
grouped_exact = all(a['structural_exact'] for a in aggregates if a['condition'] != 'single-1500')
if baseline_exact:
    outcome = 'Both fresh medium-reasoning runs recovered all six structural cycles and the reference target from the 1,500-row packet, with no invalid cycle claims.'
elif baseline_complete:
    recoveries = ' and '.join(str(a['structural_recovered']) for a in baseline_results)
    invalid_total = sum(a['invalid_true_claims'] for a in baseline_results)
    outcome = f'The two 1,500-row runs recovered {recoveries} of {len(full_oracle)} structural cycles, with {invalid_total} invalid claims. The incomplete recovery triggered the predeclared grouping comparison.'
else:
    outcome = 'The baseline is incomplete; missing results are not model-detection failures.'
if grouped_exact:
    outcome += ' Every grouped repetition recovered all six cycles with no invalid claims. Two groups matched three and four groups on this case while requiring fewer calls.'
lines = ['# GPT-6 medium: 1,500-row evaluation', '', outcome, '',
         'The reference is the return from account `(15231, 80266F880)` to `(23691, 8021353D0)` at 09:06 on 1 September 2022, followed by the reverse transaction at 11:02: `T619282 → T619283`. Hidden reference IDs and laundering labels were available only to the scorer.', '',
         '| Condition | Repeat | Completed views | Rows per view | Structural recovery | Reference recovery | Invalid claims |',
         '|---|---:|---:|---|---:|---:|---:|']
for a in aggregates:
    if not a['views_completed']:
        continue
    lines.append(f"| {a['condition']} | {a['repetition']} | {a['views_completed']}/{a['views_planned']} | {', '.join(map(str, a['view_rows']))} | {a['structural_recovered']}/{a['structural_denominator']} | {a['reference_recovered']}/{a['reference_denominator']} | {a['invalid_true_claims']} |")
lines += ['', 'Structural recovery uses the original 1,500-row denominator, deduplicated across views. Raw valid paths are also saved separately from whole-response acceptance.', '',
          '## Design and controls', '',
          'Requested model: `gpt-6-sol`, reasoning `medium`, fresh subagents with `fork_turns="none"`. Two repetitions use identical input. These are repeats of one constructed case, not independent source cases. The baseline contains 1,500 exact source transactions, including six qualifying structural cycles. All source fields were audited and all six oracle paths were independently verified with the runtime verifier.', '',
          'The supplied task system instructions, CSV evidence and function schema reuse the saved Nemotron requests. No expected paths, cycle counts, labels, other agents’ answers or conversation history are supplied. Subjects are instructed to read only their assigned packet, solve with model reasoning, and write only their response; code-based graph search is prohibited.', '',
          'To avoid tool-output truncation, each view is delivered as instructions plus consecutive files of up to 150 rows. These are transport chunks retained in one agent context, not independently evaluated groups. Subjects must read the whole view before answering. This transport differs from the original one-message API call.', '',
          'The existing graph partitioner uses ordinary account connectivity and keeps source-account bundles together, without hidden labels or known paths. Each split covers the same 1,500 unique rows exactly once. In this case all six cycles and the reference remain wholly visible under every split. Grouping changes row ordering as well as view size; those effects are not isolated.', '',
          '## Conditional grouping', '']
if baseline_exact and not grouped_ran:
    lines += ['The user requested grouping if the model struggled. Both baseline repetitions were structurally exact, so the 2-, 3- and 4-group arms were prepared and audited but not run. There is no measured grouping advantage or disadvantage.']
else:
    lines += ['Grouping is triggered if either completed baseline is not structurally exact, misses the reference, or makes invalid claims. Each group is examined by a separate fresh agent, with two repetitions per policy. Incomplete arms remain inconclusive.']
lines += ['', '## Economic assessment, reported separately', '',
          '| Condition | Repeat | Assessment of the reference cycle |',
          '|---|---:|---|']
for run in runs:
    for assessment in run['reference_assessments']:
        lines.append(f"| {run['condition']} | {run['repetition']} | {assessment['status']} |")
lines += ['', 'These statuses are model judgments, not validated laundering predictions. Changes in assessment with grouping should be calibrated separately from structural discovery.']
lines += ['', '## Interpretation and accounting', '',
          'Cycle detection is separate from laundering classification. A recovered reference with `insufficient_evidence` still counts as a structural detection. Free-text economic reasoning is not certified by this scorer. All six cycles in this case have two edges; three- and four-edge detection remains untested by this run. This case does not estimate population precision/recall, establish a universal 1,500-row boundary, or test graph screenshots and autonomous navigation.', '',
          'The baseline CSV request previously consumed 121,913 input tokens under the Nemotron tokenizer/provider. That is a historical reference, not a GPT-6 token count. Provider tokens, reasoning tokens, output limits and dollar tariff are unavailable through the subagent interface. No zero-cost claim is made. The subagent runtime has ambient instructions and returns JSON instead of a natively forced function call.', '',
          f"Saved responses: {len(runs)}. Planned maximum: {protocol['max_subjects']} subjects. Original baselines and paused full-source runs are unchanged.", '',
          '## Evidence and reproduction', '',
          '- [Machine-readable results](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/results.json)',
          '- [Frozen protocol, exact packet hashes and input files](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/protocol.json)',
          '- [Source audit](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/input-audit.json)',
          '- [Results audit](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/results-audit.json) and [subject execution record](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/execution.json)',
          '- [Baseline response 1](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/single-1500-p0/run-1-response.json)',
          '- [Baseline response 2](../../prototype/local-data/generated/cycle-context-gpt6-medium-1500-v1/single-1500-p0/run-2-response.json)', '',
          'Recompute scores and this report without model calls:', '',
          '```sh', 'python3 experiments/2026-10-24-cycle-context/score_gpt6_medium.py', '```', '']
(Path(__file__).parent / 'GPT6-MEDIUM-1500.md').write_text('\n'.join(lines))
print(json.dumps({'saved_responses': len(runs), 'baseline_complete': baseline_complete,
                  'baseline_exact': baseline_exact, 'aggregates': aggregates}, indent=2))
