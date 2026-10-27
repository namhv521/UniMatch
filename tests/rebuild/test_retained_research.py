"""Scheduler fixtures only: no academic feedback and no actual model training."""
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import pytest


def module():
    assert importlib.util.find_spec('scripts.continue_retained_research'), 'retention continuation runner missing'
    return importlib.import_module('scripts.continue_retained_research')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_fixture(tmp_path, *, second='rejected'):
    root = tmp_path / 'data_rebuild/nested_rl_20261028/run'
    output, suites = root / 'long_research', root / 'suites'
    index = {'scope': 'retrospective_document_proxy', 'seed': 42,
        'requested_timesteps_per_round': 131072, 'eval_interval': 8192,
        'accept_non_regression': True, 'checkpoint_selection': 'final_only',
        'test_evaluated': False, 'production_promoted': False, 'suites': {},
        'rounds': {'dqn': {}}, 'from_scratch_controls': {'dqn': {'V2': {'artifact': 'controls/untouched'}}}}
    for version in ('V1', 'V2', 'V3', 'V4'):
        folder = suites / version
        ready = version != 'V4'
        payload = {'train': [{'student_ids': [version + '-train']}],
            'validation': {'student_ids': [version + '-val']}, 'contract': {'scope': 'synthetic_test_only'},
            'round': {'round_id': version + '-r1', 'semester_id': {'V1': '2024.1', 'V2': '2024.2', 'V3': '2025.1', 'V4': '2025.2'}[version],
                      'decision_thresholds': {'accept_non_regression': False, 'min_improvement': 0., 'max_new_drop': 0., 'max_old_drop': 0.}}}
        write(folder / 'suite.json', payload)
        write(folder / 'readiness.json', {'status': 'ready_research_only' if ready else 'blocked_data_insufficient'})
        write(folder / 'manifest.json', {'artifacts': {p.name: sha(p) for p in folder.iterdir()}})
        index['suites'][version] = {'status': 'ready_research_only' if ready else 'blocked_data_insufficient',
            'source_manifest_sha256': sha(folder / 'manifest.json')}
        if version in ('V1', 'V2') or version == 'V3' and second == 'accepted':
            decision = 'accepted' if version != 'V2' else second
            number = int(version[1])
            report = {'decision': decision, 'algorithm': 'dqn', 'semester_id': payload['round']['semester_id'],
                'steps_before': (number - 1) * 131072, 'steps_added': 131072,
                'steps_after': number * 131072, 'checkpoint_sha256': version + '-weights',
                'start_weights_equal_parent': None if version == 'V1' else True}
            target = output / 'rounds/dqn' / version
            recorded = copy.deepcopy(payload)
            recorded['round'].update(algorithm='dqn', seed=42, round_id=payload['round']['round_id'] + '-dqn-long')
            recorded['round']['decision_thresholds']['accept_non_regression'] = True
            write(target / 'input.json', recorded)
            write(target / 'report.json', report)
            write(target / 'manifest.json', {'fixture': True, 'created_at': '2026-10-27T20:30:00+00:00'})
            index['rounds']['dqn'][version] = {'decision': decision, 'artifact': target.relative_to(output).as_posix()}
        else:
            index['rounds']['dqn'][version] = {'status': 'blocked_parent_not_accepted' if ready else 'blocked_data_readiness'}
    write(output / 'index.json', index)
    write(output / 'manifest.json', {'scope': index['scope'], 'index_sha256': sha(output / 'index.json')})
    write(output / 'retention_protocol.json', {
        'schema_version': 'retained-policy-protocol/1.0', 'declared_at': '2026-10-27T20:00:00+00:00',
        'declared_before_terminal_V2': True, 'weight_source': 'latest_accepted_checkpoint',
        'logical_context': 'latest_completed_attempt', 'failed_attempt_remains_unaccepted': True,
        'budget_per_fit': 131072, 'eval_interval': 8192, 'min_improvement': 0,
        'max_new_drop': 0, 'max_old_drop': 0, 'accept_non_regression': True,
        'test_opened': False, 'new_feedback_fabricated': False})
    return output, suites, copy.deepcopy(index)


@pytest.mark.parametrize('continuation_decision', ['accepted', 'rejected'])
def test_retention_runs_only_missing_terms_and_preserves_base_and_controls(tmp_path, monkeypatch, continuation_decision):
    m = module()
    output, suites, old = base_fixture(tmp_path)
    original_index = (output / 'index.json').read_bytes()
    original_manifest = (output / 'manifest.json').read_bytes()
    calls, retentions = [], []
    monkeypatch.setattr(m, 'verify_round', lambda p: json.loads((Path(p) / 'report.json').read_text()))
    monkeypatch.setattr(m, 'decode_problem', lambda value: value)

    def retain(accepted, attempted, target):
        retentions.append((Path(accepted), Path(attempted), Path(target)))
        write(Path(target), {'accepted': str(accepted), 'attempted': str(attempted)})
        return {'selection': 'retain_accepted_weights', 'accepted_training_claim': False}

    def fit(train, validation, contract, spec, target, **kwargs):
        calls.append((spec, kwargs))
        assert Path(kwargs['parent']).name == 'V2.json'
        assert set(kwargs['historical_validation']) == {'V1', 'V2'}
        report = {'decision': continuation_decision, 'algorithm': 'dqn', 'semester_id': '2025.1',
            'steps_before': 131072, 'steps_added': 131072, 'steps_after': 262144,
            'start_weights_equal_parent': True, 'checkpoint_sha256': 'V3-weights'}
        write(Path(target) / 'input.json', {'train': train, 'validation': validation, 'contract': contract, 'round': spec})
        write(Path(target) / 'report.json', report)
        write(Path(target) / 'manifest.json', {'fixture': True})
        return report

    monkeypatch.setattr(m, 'create_retention', retain)
    monkeypatch.setattr(m, 'run_round', fit)
    result = m.continue_research(output, suites, jobs=1)
    assert len(calls) == 1
    spec, options = calls[0]
    assert options['total_timesteps'] == 131072 and options['eval_interval'] == 8192
    assert spec['decision_thresholds'] == {'accept_non_regression': True, 'min_improvement': 0., 'max_new_drop': 0., 'max_old_drop': 0.}
    assert len(retentions) == (1 if continuation_decision == 'accepted' else 2)
    assert all(accepted == output / 'rounds/dqn/V1' for accepted, _, _ in retentions)
    assert result['rounds']['dqn']['V3']['decision'] == continuation_decision
    assert result['rounds']['dqn']['V4']['status'] == 'blocked_data_readiness'
    assert result['from_scratch_controls'] == old['from_scratch_controls']
    assert (output / 'index.base.json').read_bytes() == original_index
    assert (output / 'manifest.base.json').read_bytes() == original_manifest
    assert result['retention_continuation']['discarded_training_steps'] == 131072 * len(retentions)
    assert json.loads((output / 'manifest.json').read_text())['index_sha256'] == sha(output / 'index.json')
    assert result['test_evaluated'] is False
    with pytest.raises(FileExistsError):
        m.continue_research(output, suites)


def test_existing_accepted_warm_runs_are_not_refit(tmp_path, monkeypatch):
    m = module()
    output, suites, old = base_fixture(tmp_path, second='accepted')
    monkeypatch.setattr(m, 'verify_round', lambda p: json.loads((Path(p) / 'report.json').read_text()))
    monkeypatch.setattr(m, 'run_round', lambda *a, **k: pytest.fail('existing warm run must not be retrained'))
    monkeypatch.setattr(m, 'create_retention', lambda *a: pytest.fail('accepted run needs no retention'))
    result = m.continue_research(output, suites)
    assert result['rounds']['dqn']['V3']['decision'] == 'accepted'
    assert result['retention_continuation']['additional_training_steps'] == 0
    assert result['from_scratch_controls'] == old['from_scratch_controls']


def test_opened_test_or_mismatched_suite_blocks_before_any_backup(tmp_path):
    m = module()
    output, suites, _ = base_fixture(tmp_path)
    index = json.loads((output / 'index.json').read_text())
    index['test_evaluated'] = True
    write(output / 'index.json', index)
    write(output / 'manifest.json', {'index_sha256': sha(output / 'index.json')})
    with pytest.raises(ValueError, match='test_already_opened'):
        m.continue_research(output, suites)
    assert not (output / 'index.base.json').exists()
    index['test_evaluated'] = False
    index['suites']['V2']['source_manifest_sha256'] = 'mismatched'
    write(output / 'index.json', index)
    write(output / 'manifest.json', {'index_sha256': sha(output / 'index.json')})
    with pytest.raises(ValueError, match='suite_snapshot_mismatch'):
        m.continue_research(output, suites)
    assert not (output / 'index.base.json').exists()


@pytest.mark.parametrize('field,value,error', [
    ('max_old_drop', .1, 'fixed_predeclared_retention_protocol'),
    ('declared_at', '2026-10-27T20:31:00+00:00', 'protocol_must_precede_terminal_V2'),
])
def test_quality_gate_changes_or_late_declaration_are_rejected(tmp_path, field, value, error):
    m = module()
    output, suites, _ = base_fixture(tmp_path)
    protocol = json.loads((output / 'retention_protocol.json').read_text())
    protocol[field] = value
    write(output / 'retention_protocol.json', protocol)
    with pytest.raises(ValueError, match=error):
        m.continue_research(output, suites)
    assert not (output / 'index.base.json').exists()
