"""Paired, teacher-forced dev diagnostics. Semantic quality requires human review."""
from pathlib import Path

from ..learning.model import parse_response
from .training_data import canonical, context_for_model, digest, load_prepared, write_json


def evaluate_policy(dataset_path, policy, captured, output):
    prepared = load_prepared(dataset_path)
    if prepared['receipt']['split'] != 'dev':
        raise ValueError('Only development data may be used for model selection')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'raw.jsonl').open('x', encoding='utf-8') as stream:
        for index, example in enumerate(prepared['examples']):
            captured.clear()
            error = None
            try:
                policy(context_for_model(example['input'], dataset_path))
            except ValueError as exc:
                error = str(exc)  # malformed responses count; never repair or retry
            finally:
                finished = [r for r in captured if r.get('stage') == 'finished']
                last = finished[-1] if finished else {}
                row = dict(index=index, input_sha256=digest(example['input']), raw=last.get('raw'),
                           error=last.get('error') or error, provenance=getattr(policy, 'provenance', {}),
                           raw_trace=list(captured))
                stream.write(canonical(row) + '\n')
                stream.flush()
    write_json(output / 'evaluation.json', dict(dataset_sha256=prepared['receipt']['dataset_sha256'],
               mode='teacher_forced_accepted_context', quality_measured=False,
               sequential_rollout=False, examples=len(prepared['examples'])))


def _score(examples, rows):
    if len(rows) != len(examples):
        raise ValueError('Missing or extra dev outputs')
    result = dict(examples=len(examples), contract_valid=0, active_target_valid=0,
                  target_action_agreement=0, generation_errors=0, actions={},
                  unsupported_caption_rate=None, coverage=None, incorrect_revisions=None,
                  unsupported_withdrawals=None, mobile_latency_ms=None)
    errors = []
    for index, (example, row) in enumerate(zip(examples, rows)):
        if row.get('index') != index or row.get('input_sha256') != digest(example['input']):
            raise ValueError('Dev outputs must match the identical ordered inputs')
        result['generation_errors'] += bool(row.get('error'))
        try:
            predicted = parse_response(row.get('raw'), example['input'])
        except (ValueError, TypeError):
            continue
        result['contract_valid'] += 1
        action = predicted['action']
        result['actions'][action] = result['actions'].get(action, 0) + 1
        active_ok = True
        if action in ('REVISE', 'WITHDRAW'):
            old = next((e for e in example['input']['active_events'] if e['record_id'] == predicted['previous_record_id']), None)
            active_ok = old is not None and (action != 'WITHDRAW' or all(old[k] == predicted[k] for k in ('start_ms', 'end_ms', 'event_status')))
        result['active_target_valid'] += active_ok
        target = example['target']
        result['target_action_agreement'] += action == target['action']
        if active_ok and action == target['action'] and action != 'WAIT':
            errors.append(abs(predicted['start_ms'] - target['start_ms']))
            if predicted['end_ms'] is not None and target['end_ms'] is not None:
                errors.append(abs(predicted['end_ms'] - target['end_ms']))
    result['target_boundary_absolute_error_ms'] = sum(errors)/len(errors) if errors else None
    result['boundary_pairs'] = len(errors)
    result['contract_valid_rate'] = result['contract_valid']/len(examples)
    return result


def compare_traces(dataset_path, baseline, candidate):
    prepared = load_prepared(dataset_path)
    if prepared['receipt']['split'] != 'dev':
        raise ValueError('Only dev comparison is supported; final test stays closed')
    keys = ('checkpoint', 'revision', 'input_route', 'device', 'dtype', 'max_tokens', 'max_input_tokens', 'prompt_format')
    settings = None
    for row in baseline + candidate:
        provenance = row.get('provenance', {})
        if any(k not in provenance for k in keys):
            raise ValueError('Missing paired generation settings')
        current = {k: provenance[k] for k in keys}
        if settings is not None and current != settings:
            raise ValueError('Paired generation settings differ')
        settings = current
    return dict(dataset_sha256=prepared['receipt']['dataset_sha256'],
                mode='teacher_forced_accepted_context', sequential_rollout=False,
                baseline=_score(prepared['examples'], baseline),
                candidate=_score(prepared['examples'], candidate), quality_accepted=False,
                semantic_review='PENDING_HUMAN_REVIEW',
                limitation='Action agreement and boundary differences are diagnostics, not semantic event matching or coverage.')
