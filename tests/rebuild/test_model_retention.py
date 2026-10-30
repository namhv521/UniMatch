"""Retention carries logical context without counting rejected model training."""
import hashlib
import importlib
import json

import pytest


def module():
    return importlib.import_module('src.rl.model_retention')


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def seal(directory):
    dump(directory / 'manifest.json', {'schema_version': 'nested-rl-round/1.0',
        'artifacts': {p.relative_to(directory).as_posix(): digest(p) for p in directory.rglob('*') if p.is_file() and p.name != 'manifest.json'}})


def bundles(tmp_path, *, inner=False, attempt_decision='rejected'):
    accepted, attempt = tmp_path / 'accepted', tmp_path / 'attempt'
    contract = {'state_contract': {'advisor_ids': ['a', 'b'], 'dimension': 19},
                'feature_contract_sha256': 'f' * 64, 'taxonomy_feature_order_sha256': 'a' * 64}
    reports = []
    for directory, term, index, decision, weights in (
        (accepted, '2024.1', 1, 'accepted', b'accepted-weights'),
        (attempt, '2024.1' if inner else '2024.2', 2 if inner else 1, attempt_decision, b'discarded-attempt-weights')):
        (directory / 'checkpoint').mkdir(parents=True)
        (directory / 'checkpoint/weights.bin').write_bytes(weights)
        checkpoint = record_hash({'weights.bin': digest(directory / 'checkpoint/weights.bin')})
        spec = {'algorithm': 'dqn', 'seed': 42, 'semester_id': term, 'round_index': index,
                'round_id': term + '-r' + str(index), 'cutoff_timestamp': '2024-12-31T23:59:59+07:00' if term == '2024.1' else '2025-06-30T23:59:59+07:00'}
        report = {'decision': decision, **{k: spec[k] for k in ('algorithm', 'seed', 'semester_id', 'round_index', 'round_id')},
                  'checkpoint_sha256': checkpoint, 'steps_before': 0 if decision == 'accepted' else 131072,
                  'steps_added': 131072, 'steps_after': 131072 if decision == 'accepted' else 262144,
                  'parent_checkpoint_sha256': reports[0]['checkpoint_sha256'] if reports else None,
                  'parent_round_id': reports[0]['round_id'] if reports else None,
                  'start_weights_equal_parent': True if reports else None}
        inputs = {'round': spec, 'contract': contract, 'train': [{'student_ids': ['train-a']}],
                  'validation': {'student_ids': ['val-a']}, 'historical_validation': {},
                  'memberships': {'train': ['train-a'], 'validation': ['val-a']}}
        dump(directory / 'input.json', inputs)
        dump(directory / 'report.json', report)
        dump(directory / 'decision.json', {'decision': decision})
        seal(directory)
        reports.append(report)
    return accepted, attempt


@pytest.mark.parametrize('inner', [False, True])
@pytest.mark.parametrize('attempt_decision', ['rejected', 'inconclusive'])
def test_retention_keeps_actual_weights_and_counters_but_latest_logical_context(tmp_path, inner, attempt_decision):
    accepted, attempt = bundles(tmp_path, inner=inner, attempt_decision=attempt_decision)
    old_manifests = [digest(p / 'manifest.json') for p in (accepted, attempt)]
    ledger = tmp_path / 'retentions/context.json'
    summary = module().create_retention(accepted, attempt, ledger)
    resolved = module().resolve_retention(ledger)
    assert resolved['path'] == accepted.resolve()
    assert resolved['report']['steps_after'] == 131072
    assert resolved['input']['round']['round_id'] == json.loads((attempt / 'input.json').read_text())['round']['round_id']
    assert resolved['weight_input']['round']['round_id'] == '2024.1-r1'
    assert summary['accepted_training_claim'] is False
    assert summary['discarded_compute']['attempt_steps_added'] == 131072
    assert summary['discarded_compute']['added_to_weight_steps'] is False
    assert [digest(p / 'manifest.json') for p in (accepted, attempt)] == old_manifests
    with pytest.raises(FileExistsError):
        module().create_retention(accepted, attempt, ledger)


def test_retention_rejects_unrelated_weight_parent(tmp_path):
    accepted, attempt = bundles(tmp_path)
    report = json.loads((attempt / 'report.json').read_text())
    report['parent_checkpoint_sha256'] = '0' * 64
    dump(attempt / 'report.json', report)
    seal(attempt)
    with pytest.raises(ValueError, match='retention_parent_checkpoint_mismatch'):
        module().create_retention(accepted, attempt, tmp_path / 'ledger.json')


def test_retention_detects_tampered_ledger_and_source_bundle(tmp_path):
    accepted, attempt = bundles(tmp_path)
    ledger = tmp_path / 'ledger.json'
    module().create_retention(accepted, attempt, ledger)
    original = ledger.read_bytes()
    data = json.loads(original)
    data['seed'] = 43
    dump(ledger, data)
    with pytest.raises(ValueError, match='retention_ledger_hash_mismatch'):
        module().resolve_retention(ledger)
    ledger.write_bytes(original)
    (accepted / 'checkpoint/weights.bin').write_bytes(b'changed')
    with pytest.raises(ValueError, match='artifact_hash_mismatch'):
        module().resolve_retention(ledger)


def test_retention_rejects_incompatible_representation_and_protects_bundles(tmp_path):
    accepted, attempt = bundles(tmp_path)
    with pytest.raises(ValueError, match='retention_output_must_not_modify_bundle'):
        module().create_retention(accepted, attempt, accepted / 'ledger.json')
    inputs = json.loads((attempt / 'input.json').read_text())
    inputs['contract']['feature_contract_sha256'] = 'b' * 64
    dump(attempt / 'input.json', inputs)
    seal(attempt)
    with pytest.raises(ValueError, match='retention_representation_mismatch'):
        module().create_retention(accepted, attempt, tmp_path / 'ledger.json')


def test_retention_rejects_different_seed(tmp_path):
    accepted, attempt = bundles(tmp_path)
    inputs, report = json.loads((attempt / 'input.json').read_text()), json.loads((attempt / 'report.json').read_text())
    inputs['round']['seed'] = report['seed'] = 43
    dump(attempt / 'input.json', inputs)
    dump(attempt / 'report.json', report)
    seal(attempt)
    with pytest.raises(ValueError, match='retention_algorithm_seed_mismatch'):
        module().create_retention(accepted, attempt, tmp_path / 'ledger.json')
