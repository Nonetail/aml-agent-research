"""Evaluator-only exact scoring of label-blind, supplied-row cycle detection."""
from collections import Counter, defaultdict

from cycle_prompts import review_definition, validate_review
from run_case import validate


def oracle_cycles(rows):
    """Enumerate all simple 2..4-edge strict-time returns in this supplied table.

    This standalone adjacency DFS does not use CycleTools or its verifier. The
    fixed-width source timestamp format sorts chronologically. Each source row
    instance needs its own transaction_id, including identical parallel edges.
    """
    by_id = {r['transaction_id']: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError('Repeated transaction_id in supplied table')
    outgoing = defaultdict(list)
    for row in rows:
        source = row['source_bank'], row['source_account']
        destination = row['destination_bank'], row['destination_account']
        if source != destination:
            outgoing[source].append((destination, row['timestamp'], row['transaction_id']))
    found = set()

    def extend(start, node, last_time, visited, path):
        for destination, timestamp, transaction_id in outgoing[node]:
            if last_time is not None and timestamp <= last_time:
                continue
            following = path + (transaction_id,)
            if destination == start:
                if len(following) >= 2:
                    found.add(following)
            elif len(following) < 4 and destination not in visited:
                extend(start, destination, timestamp, visited | {destination}, following)

    for node in list(outgoing):
        extend(node, node, None, {node}, ())
    return sorted(found)


def score_answer(rows, answer, target_paths=(), labels=None):
    """Strict accepted recovery plus diagnostic claims; labels never infer truth.

    An invalid response contributes zero accepted cycles, while raw valid claims
    remain visible for diagnosis. Target paths may include supports split across
    views: their denominator is retained and their visibility reported separately.
    A valid pattern_present=false observation is not a detected cycle. Labels are
    evaluator-only transaction_id -> 0/1; missing labels stay unknown.
    """
    labels = labels or {}
    oracle = set(oracle_cycles(rows))
    available = {r['transaction_id'] for r in rows}
    targets = {tuple(path) for path in target_paths}
    visible_targets = targets & oracle
    errors = []
    schema_valid = True
    try:
        validate(review_definition(available, [])['parameters'], answer)
    except (ValueError, TypeError, KeyError) as error:
        schema_valid = False
        errors.append(str(error))
    observations = answer.get('observations', []) if isinstance(answer, dict) else []
    if not isinstance(observations, list):
        observations = []
    raw_valid = set()
    unknown_ids = set()
    false_valid = 0
    claim_mismatches = 0
    invalid_true_paths = []
    false_claims_of_valid_cycles = 0
    duplicates = 0
    seen = set()
    statuses = Counter()
    investigate_ids = set()
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        path = observation.get('transaction_ids')
        if not isinstance(path, list) or not all(isinstance(x, str) for x in path):
            continue
        path = tuple(path)
        support = frozenset(path)
        duplicates += support in seen
        seen.add(support)
        unknown_ids.update(set(path) - available)
        valid = path in oracle
        claim = observation.get('pattern_present')
        if type(claim) is bool and claim != valid:
            claim_mismatches += 1
        if claim is True and not valid:
            invalid_true_paths.append(list(path))
        if claim is False and valid:
            false_claims_of_valid_cycles += 1
        if valid and claim is True:
            raw_valid.add(path)
            if observation.get('status') == 'investigate':
                investigate_ids.update(path)
        if not valid and claim is False and set(path) <= available:
            false_valid += 1
        status = observation.get('status')
        if isinstance(status, str):
            statuses[status] += 1

    def verify(path):
        return {'valid': tuple(path) in oracle, 'unavailable_ids': sorted(set(path) - available)}

    response_valid = False
    if schema_valid:
        try:
            validate_review(answer, available, [], verify)
            response_valid = True
        except (ValueError, TypeError, KeyError) as error:
            errors.append(str(error))
    accepted = raw_valid if response_valid else set()
    accepted_ids = {transaction_id for path in accepted for transaction_id in path}
    known_positive = {transaction_id for transaction_id in available if labels.get(transaction_id) == 1}
    flagged_ids = investigate_ids if response_valid else set()
    true_claims = sum(isinstance(o, dict) and o.get('pattern_present') is True for o in observations)
    compositions = Counter()
    for path in accepted:
        values = [labels.get(transaction_id) for transaction_id in path]
        if any(value not in (0, 1) for value in values):
            compositions['unknown'] += 1
        elif all(value == 0 for value in values):
            compositions['zero_positive'] += 1
        elif all(value == 1 for value in values):
            compositions['all_positive'] += 1
        else:
            compositions['mixed'] += 1
    return {
        'schema_valid': schema_valid, 'response_valid': response_valid, 'errors': errors,
        'oracle_cycles': [list(path) for path in sorted(oracle)],
        'oracle_cycle_count': len(oracle),
        'accepted_cycles': [list(path) for path in sorted(accepted)],
        'raw_valid_cycles': [list(path) for path in sorted(raw_valid)],
        'structural_recovered': len(accepted),
        'structural_recall': len(accepted) / len(oracle) if oracle else None,
        'structural_precision': len(accepted) / true_claims if true_claims else None,
        'structural_exact': response_valid and accepted == oracle,
        'target_count': len(targets), 'target_visible': len(visible_targets),
        'target_recovered': len(accepted & targets),
        'target_recall': len(accepted & targets) / len(targets) if targets else None,
        'target_visibility_ceiling': len(visible_targets) / len(targets) if targets else None,
        'target_conditional_recall': len(accepted & targets) / len(visible_targets) if visible_targets else None,
        'valid_false_observations': false_valid, 'claim_mismatches': claim_mismatches,
        'invalid_true_paths': invalid_true_paths, 'invalid_true_claims': len(invalid_true_paths),
        'false_claims_of_valid_cycles': false_claims_of_valid_cycles,
        'duplicate_supports': duplicates, 'unknown_ids': sorted(unknown_ids),
        'true_claim_count': true_claims, 'status_distribution': dict(statuses),
        'accepted_cycle_label_composition': dict(compositions),
        'supplied_rows': len(rows), 'supplied_known_label_rows': sum(x in labels for x in available),
        'supplied_positive_rows': len(known_positive),
        'recovered_positive_row_ids': sorted(accepted_ids & known_positive),
        'investigate_positive_row_ids': sorted(flagged_ids & known_positive),
        'investigate_zero_label_row_ids': sorted(x for x in flagged_ids if labels.get(x) == 0),
        'positive_row_recovery': len(accepted_ids & known_positive) / len(known_positive) if known_positive else None,
    }
