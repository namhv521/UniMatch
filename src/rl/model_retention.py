"""Immutable references separating retained weights from a rejected context.

A rejected/inconclusive attempt advances the known logical context, not the
accepted model's counters or training provenance. No native bundle is copied,
rewritten, or relabeled as accepted by this module.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


SCHEMA = 'nested-rl-retention/1.0'
REPRESENTATION_KEYS = ('state_contract', 'feature_contract_sha256', 'taxonomy_feature_order_sha256')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _bundle(path):
    # Lazy import avoids a module cycle when the engine resolves a ledger.
    from src.rl.nested_learning import _checkpoint_digest, verify_round
    path = Path(path).resolve()
    if not path.is_dir():
        raise ValueError('retention_source_bundle_directory_required')
    report = verify_round(path)
    inputs = _read(path / 'input.json')
    identity = ('algorithm', 'seed', 'semester_id', 'round_id', 'round_index')
    if any(report.get(key) != inputs['round'].get(key) for key in identity):
        raise ValueError('retention_report_input_identity_mismatch')
    if _checkpoint_digest(path / 'checkpoint') != report.get('checkpoint_sha256'):
        raise ValueError('retention_checkpoint_digest_mismatch')
    return path, report, inputs


def _reference(bundle):
    path, report, _ = bundle
    return {'path': str(path), 'manifest_sha256': _digest(path / 'manifest.json'),
            'input_sha256': _digest(path / 'input.json'), 'checkpoint_sha256': report['checkpoint_sha256'],
            **{key: report[key] for key in ('round_id', 'semester_id', 'round_index', 'steps_before', 'steps_added', 'steps_after')}}


def _binding(accepted, attempt):
    accepted_bundle, attempt_bundle = _bundle(accepted), _bundle(attempt)
    _, approved, weight_input = accepted_bundle
    _, rejected, logical_input = attempt_bundle
    if approved.get('decision') != 'accepted' or rejected.get('decision') not in ('rejected', 'inconclusive'):
        raise ValueError('accepted_weights_and_unaccepted_attempt_required')
    if any(approved.get(key) != rejected.get(key) for key in ('algorithm', 'seed')):
        raise ValueError('retention_algorithm_seed_mismatch')
    if any(key not in weight_input['contract'] or key not in logical_input['contract']
           or weight_input['contract'][key] != logical_input['contract'][key] for key in REPRESENTATION_KEYS):
        raise ValueError('retention_representation_mismatch')
    if rejected.get('parent_checkpoint_sha256') != approved['checkpoint_sha256']:
        raise ValueError('retention_parent_checkpoint_mismatch')
    if (rejected.get('parent_round_id') != approved['round_id'] or rejected.get('start_weights_equal_parent') is not True
            or rejected.get('steps_before') != approved.get('steps_after')):
        raise ValueError('retention_actual_parent_identity_or_counter_mismatch')
    if (type(rejected.get('steps_added')) is not int or rejected['steps_added'] <= 0
            or rejected.get('steps_after') != rejected['steps_before'] + rejected['steps_added']):
        raise ValueError('retention_attempt_compute_accounting_mismatch')
    summary = {'schema_version': SCHEMA, 'selection': 'retain_accepted_weights',
               'algorithm': approved['algorithm'], 'seed': approved['seed'], 'accepted_training_claim': False,
               'actual_weight_source': _reference(accepted_bundle),
               'logical_context': {**_reference(attempt_bundle), 'attempt_decision': rejected['decision']},
               'discarded_compute': {'attempt_steps_added': rejected['steps_added'],
                                     'attempt_steps_after': rejected['steps_after'], 'added_to_weight_steps': False}}
    return summary, accepted_bundle, attempt_bundle


def create_retention(accepted, logical_attempt, output):
    """Record a logical attempt while retaining its exact accepted parent weights."""
    accepted, logical_attempt, output = Path(accepted).resolve(), Path(logical_attempt).resolve(), Path(output).resolve()
    if output.is_relative_to(accepted) or output.is_relative_to(logical_attempt):
        raise ValueError('retention_output_must_not_modify_bundle')
    if output.exists():
        raise FileExistsError('immutable_retention_ledger_already_exists')
    summary, _, _ = _binding(accepted, logical_attempt)
    summary['created_at'] = datetime.now(timezone.utc).isoformat()
    summary['ledger_sha256'] = _hash(summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return {**summary, 'ledger_path': str(output), 'ledger_file_sha256': _digest(output)}


def resolve_retention(ledger):
    """Return engine-parent inputs with distinct logical and weight-source data."""
    ledger = Path(ledger).resolve()
    data = _read(ledger)
    claimed = data.pop('ledger_sha256', None)
    if claimed != _hash(data):
        raise ValueError('retention_ledger_hash_mismatch')
    if data.get('schema_version') != SCHEMA:
        raise ValueError('retention_ledger_schema_required')
    summary, accepted, attempt = _binding(data['actual_weight_source']['path'], data['logical_context']['path'])
    if any(data.get(key) != value for key, value in summary.items()):
        raise ValueError('retention_source_binding_mismatch')
    if ledger.is_relative_to(accepted[0]) or ledger.is_relative_to(attempt[0]):
        raise ValueError('retention_output_must_not_modify_bundle')
    verified = {**data, 'ledger_sha256': claimed, 'ledger_path': str(ledger), 'ledger_file_sha256': _digest(ledger)}
    return {'path': accepted[0], 'report': accepted[1], 'input': attempt[2],
            'weight_input': accepted[2], 'retention': verified}
