"""Nested-round controls; all data here are explicitly synthetic test fixtures."""
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from src.domain.rebuild_matching import AllocationProblem
from src.environment.rebuild_env import MatchingEnv
from src.evaluation.rebuild_benchmark import problem_payload
from src.data_pipeline.review_decisions import record_hash


def module():
    assert importlib.util.find_spec('src.rl.nested_learning'), 'nested round controller is missing'
    return importlib.import_module('src.rl.nested_learning')


def fixture(tmp_path, *, algorithm='dqn', term='2024.1', index=1, prefix='one', signals=None):
    feature = 'f' * 64
    taxonomy = 'a' * 64
    def problem(ids, split):
        return AllocationProblem(
            scores=np.array([[.9, .8], [.7, .1]], float), available=np.ones((2, 2), bool),
            student_ids=tuple(ids), advisor_ids=('a', 'b'), capacities=np.array([1, 1]),
            eligible=np.ones((2, 2), bool), present=np.ones(2, bool),
            student_features=np.array([[.5], [.8]], np.float32), student_feature_known=np.ones((2, 1), bool),
            metadata={'split': split, 'scope': 'synthetic_test_only', 'feature_contract_sha256': feature,
                      'taxonomy_feature_order_sha256': taxonomy, 'policy_version': 'equal/1'})
    train = [problem([prefix + '-train-a', prefix + '-train-b'], 'train')]
    validation = problem([prefix + '-val-a', prefix + '-val-b'], 'validation')
    env = MatchingEnv(train)
    contract = {'scope': 'synthetic_test_only', 'state_contract': env.state_contract,
                'feature_contract_sha256': feature, 'taxonomy_feature_order_sha256': taxonomy,
                'quota_policy_version': 'equal/1', 'reward_weights': env.reward_weights,
                'training_student_ids': list(train[0].student_ids)}
    if index > 1:
        changed = problem_payload(train[0])
        changed['preferences'][0][0] = .8
        changed['preference_known'][0][0] = True
        train = [module().decode_problem(changed)]
    if signals is None:
        source = tmp_path / f'signal-{prefix}-{index}.json'
        source.write_text(json.dumps({'scope': 'synthetic_test_only', 'signal_id': f'{prefix}-{index}',
            'changes': ([{'student_id': prefix + '-train-a', 'advisor_id': 'a', 'field': 'preferences', 'old': 0., 'new': .8},
                         {'student_id': prefix + '-train-a', 'advisor_id': 'a', 'field': 'preference_known', 'old': False, 'new': True}] if index > 1 else [])}), encoding='utf-8')
        signals = [{'signal_id': f'{prefix}-{index}', 'type': 'initial_source' if index == 1 else 'student_preference',
                    'source_path': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'available_at': '2024-12-01T00:00:00+07:00', 'review_status': 'verified'}]
    snapshot = tmp_path / f'snapshot-{prefix}-{index}.json'
    snapshot.write_text(json.dumps({'training_problem_sha256': [record_hash(problem_payload(p)) for p in train],
                                  'validation_problem_sha256': record_hash(problem_payload(validation)),
                                  'signal_ids': [s['signal_id'] for s in signals],
                                  'applied_signal_source_sha256': {s['signal_id']: s['source_sha256'] for s in signals if s['type'] != 'initial_source'}}), encoding='utf-8')
    spec = {'semester_id': term, 'round_id': f'{term}-r{index}-{prefix}', 'round_index': index,
            'algorithm': algorithm, 'seed': 42, 'snapshot_path': str(snapshot),
            'snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            'cutoff_timestamp': '2024-12-31T23:59:59+07:00' if term == '2024.1' else '2025-06-30T23:59:59+07:00',
            'signals': signals, 'signal_state_sha256': record_hash([s['signal_id'] for s in signals]),
            'reward_version': 'reward/1', 'constraint_version': 'equal/1',
            'decision_thresholds': {'min_improvement': 0., 'max_new_drop': 1., 'max_old_drop': 1.,
                                    'accept_non_regression': True}}
    return train, validation, contract, spec


def test_round_validation_binds_actual_matrices_and_source(tmp_path):
    train, val, contract, spec = fixture(tmp_path)
    report = module().validate_round(train, val, contract, spec)
    assert report['ready'] and report['training_student_count'] == 2
    changed = copy.deepcopy(spec)
    Path(changed['snapshot_path']).write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='snapshot'):
        module().validate_round(train, val, contract, changed)


def test_future_unverified_and_duplicate_signals_rejected(tmp_path):
    train, val, contract, spec = fixture(tmp_path)
    for key, value, match in [('available_at', '2025-01-01T00:00:00+07:00', 'future_signal'),
                              ('review_status', 'pending', 'unverified_signal')]:
        changed = copy.deepcopy(spec)
        changed['signals'][0][key] = value
        with pytest.raises(ValueError, match=match):
            module().validate_round(train, val, contract, changed)
    changed = copy.deepcopy(spec)
    changed['signals'] *= 2
    with pytest.raises(ValueError, match='signal_id'):
        module().validate_round(train, val, contract, changed)


def test_holdout_overlap_and_second_round_without_parent_rejected(tmp_path):
    train, val, contract, spec = fixture(tmp_path)
    with pytest.raises(ValueError, match='holdout_overlap'):
        module().validate_round(train, train[0], contract, spec)
    spec['round_index'] = 2
    with pytest.raises(ValueError, match='parent_required'):
        module().validate_round(train, val, contract, spec)


def test_changed_signal_discards_stale_replay_but_keeps_weights(tmp_path):
    train, val, contract, spec = fixture(tmp_path)
    first = tmp_path / 'first'
    config = dict(hidden_sizes=[8], batch_size=2, learning_starts=2, train_frequency=1,
                  target_update_interval=4, buffer_size=64)
    a = module().run_round(train, val, contract, spec, first, total_timesteps=16, model_config=config)
    assert a['decision'] == 'accepted' and a['production_promoted'] is False
    train2, val2, contract2, spec2 = fixture(tmp_path, index=2)
    second = tmp_path / 'second'
    b = module().run_round(train2, val2, contract2, spec2, second, parent=first, total_timesteps=16)
    assert b['parent_checkpoint_sha256'] == a['checkpoint_sha256']
    assert b['start_weights_equal_parent'] is True
    assert b['replay_policy'] == 'discard_stale_keep_weights'
    assert b['steps_before'] == a['steps_after']
    assert b['steps_after'] == b['steps_before'] + 16
    assert b['reload_parity'] and b['inference_parity']
    assert b['training']['training_unique_student_count'] == 2
    module().verify_round(second)
    manifest = json.loads((second / 'manifest.json').read_text(encoding='utf-8'))
    assert set(manifest['code_sha256']) == {'src/rl/nested_learning.py', 'src/rl/rebuild_ppo.py',
        'src/rl/rebuild_dqn.py', 'src/environment/rebuild_env.py'}
    assert all(len(value) == 64 for value in manifest['code_sha256'].values())


def test_unapplied_and_unattributed_human_feedback_rejected(tmp_path):
    m = module()
    train, val, contract, spec = fixture(tmp_path)
    parent = tmp_path / 'parent'
    m.run_round(train, val, contract, spec, parent, total_timesteps=4,
        model_config=dict(hidden_sizes=[8], batch_size=2, learning_starts=2, train_frequency=1))
    revised, val2, contract2, spec2 = fixture(tmp_path, index=2)
    snapshot = Path(spec2['snapshot_path'])
    content = json.loads(snapshot.read_text(encoding='utf-8'))
    # A new real file and valid hashes are insufficient if the preferences did
    # not actually change in the matrices being trained.
    content['training_problem_sha256'] = [record_hash(problem_payload(p)) for p in train]
    snapshot.write_text(json.dumps(content), encoding='utf-8')
    spec2['snapshot_sha256'] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='change_not_applied'):
        m.validate_round(train, val2, contract2, spec2, parent=parent)
    content['training_problem_sha256'] = [record_hash(problem_payload(p)) for p in revised]
    content.pop('applied_signal_source_sha256')
    snapshot.write_text(json.dumps(content), encoding='utf-8')
    spec2['snapshot_sha256'] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='source_binding_required'):
        m.validate_round(revised, val2, contract2, spec2, parent=parent)
    content['applied_signal_source_sha256'] = {s['signal_id']: s['source_sha256'] for s in spec2['signals']}
    extra = problem_payload(revised[0])
    extra['scores'][0][1] = .6
    extra = [m.decode_problem(extra)]
    content['training_problem_sha256'] = [record_hash(problem_payload(p)) for p in extra]
    snapshot.write_text(json.dumps(content), encoding='utf-8')
    spec2['snapshot_sha256'] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='unattributed_training'):
        m.validate_round(extra, val2, contract2, spec2, parent=parent)
    content['training_problem_sha256'] = [record_hash(problem_payload(p)) for p in revised]
    snapshot.write_text(json.dumps(content), encoding='utf-8')
    spec2['snapshot_sha256'] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    spec2['signals'][0]['type'] = 'verified_outcome'
    with pytest.raises(ValueError, match='unsupported_feedback_signal_type'):
        m.validate_round(revised, val2, contract2, spec2, parent=parent)
    spec2['signals'][0]['type'] = 'initial_source'
    with pytest.raises(ValueError, match='same_semester_typed_feedback_required'):
        m.validate_round(revised, val2, contract2, spec2, parent=parent)


def test_dqn_cross_term_then_same_term_chain_keeps_complete_native_bundle(tmp_path):
    m = module()
    train, val, contract, spec = fixture(tmp_path)
    a = tmp_path / 'a'
    m.run_round(train, val, contract, spec, a, total_timesteps=8,
                model_config=dict(hidden_sizes=[8], batch_size=2, learning_starts=2,
                                  train_frequency=1, buffer_size=32))
    train2, val2, contract2, spec2 = fixture(tmp_path, term='2024.2', prefix='two')
    b = tmp_path / 'b'
    with pytest.raises(ValueError, match='historical_validation_required'):
        m.run_round(train2, val2, contract2, spec2, b, parent=a, total_timesteps=8)
    skipped = copy.deepcopy(spec2)
    skipped.update(semester_id='2025.1', round_id='2025.1-r1-skipped',
                   cutoff_timestamp='2025-12-31T23:59:59+07:00')
    with pytest.raises(ValueError, match='adjacent_semester'):
        m.validate_round(train2, val2, contract2, skipped, parent=a)
    report = m.run_round(train2, val2, contract2, spec2, b, parent=a, total_timesteps=8, historical_validation={'V1': val})
    assert report['cross_semester'] is True and report['start_weights_equal_parent']
    assert report['forgetting_status'] == 'measured'
    train3, val3, contract3, spec3 = fixture(tmp_path, term='2024.2', index=2, prefix='two')
    c = tmp_path / 'c'
    report3 = m.run_round(train3, val3, contract3, spec3, c, parent=b, total_timesteps=8)
    assert report3['steps_before'] == 16 and report3['steps_after'] == 24
    assert (c / 'checkpoint/replay.npz').exists()
    assert m.verify_round(c)['round_id'] == spec3['round_id']


def test_same_term_membership_and_parent_seed_cannot_silently_change(tmp_path):
    m = module()
    train, val, contract, spec = fixture(tmp_path)
    a = tmp_path / 'a'
    m.run_round(train, val, contract, spec, a, total_timesteps=4,
                model_config=dict(hidden_sizes=[8], batch_size=2, learning_starts=2, train_frequency=1))
    t2, v2, c2, s2 = fixture(tmp_path, index=2, prefix='changed')
    with pytest.raises(ValueError, match='same_semester_cohort'):
        m.validate_round(t2, v2, c2, s2, parent=a)
    t2, v2, c2, s2 = fixture(tmp_path, index=2)
    s2['seed'] = 43
    with pytest.raises(ValueError, match='parent_algorithm_seed'):
        m.validate_round(t2, v2, c2, s2, parent=a)


def test_ppo_bootstrap_and_feedback_round_use_fresh_rollouts(tmp_path):
    m = module()
    train, val, contract, spec = fixture(tmp_path, algorithm='ppo')
    a = tmp_path / 'a'
    report = m.run_round(train, val, contract, spec, a, total_timesteps=16,
                         model_config=dict(n_steps=8, batch_size=4, n_epochs=1, hidden_sizes=[8]))
    train2, val2, contract2, spec2 = fixture(tmp_path, algorithm='ppo', index=2)
    report2 = m.run_round(train2, val2, contract2, spec2, tmp_path / 'b', parent=a, total_timesteps=16)
    assert report['reload_parity'] and report2['reload_parity']
    assert report2['replay_policy'] == 'fresh_on_policy_rollouts'
    assert report2['start_weights_equal_parent']
    assert report2['training']['epochs_completed'] > report['training']['epochs_completed']


def test_tampering_and_existing_output_rejected(tmp_path):
    m = module()
    train, val, contract, spec = fixture(tmp_path)
    a = tmp_path / 'a'
    m.run_round(train, val, contract, spec, a, total_timesteps=4,
                model_config=dict(hidden_sizes=[8], batch_size=2, learning_starts=2, train_frequency=1))
    with pytest.raises(FileExistsError):
        m.run_round(train, val, contract, spec, a, total_timesteps=4)
    (a / 'checkpoint/weights.pt').write_bytes(b'changed')
    with pytest.raises(ValueError, match='artifact_hash'):
        m.verify_round(a)


def test_retrospective_proxy_never_waives_human_signal_time(tmp_path):
    train, val, contract, spec = fixture(tmp_path)
    contract['scope'] = 'retrospective_document_proxy'
    spec['availability_assumption'] = 'retrospective_event_time_proxy'
    spec['signals'][0].update(available_at='2026-10-28T00:00:00+07:00', event_year=2024)
    assert module().validate_round(train, val, contract, spec)['prediction_time_verified'] is False
    spec['signals'][0]['type'] = 'student_preference'
    with pytest.raises(ValueError, match='future_signal'):
        module().validate_round(train, val, contract, spec)


def test_half_year_proxy_requires_snapshot_bound_event_interval(tmp_path):
    train, val, contract, spec = fixture(tmp_path, term='2024.2')
    spec['control'] = 'from_scratch'
    contract['scope'] = 'retrospective_document_proxy'
    spec['availability_assumption'] = 'retrospective_event_time_proxy'
    spec['signals'][0].update(available_at='2026-10-28T00:00:00+07:00', event_year=2025)
    with pytest.raises(ValueError, match='ambiguous_event_year'):
        module().validate_round(train, val, contract, spec)
    bound = '2025-06-30T23:59:59+07:00'
    spec['signals'][0]['event_upper_bound'] = bound
    with pytest.raises(ValueError, match='event_upper_bound_binding'):
        module().validate_round(train, val, contract, spec)
    snapshot = Path(spec['snapshot_path'])
    content = json.loads(snapshot.read_text(encoding='utf-8'))
    content['initial_source_event_upper_bound'] = bound
    snapshot.write_text(json.dumps(content), encoding='utf-8')
    spec['snapshot_sha256'] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert module().validate_round(train, val, contract, spec)['prediction_time_verified'] is False
    spec['signals'][0]['type'] = 'advisor_feedback'
    with pytest.raises(ValueError, match='future_signal'):
        module().validate_round(train, val, contract, spec)
    spec['signals'][0]['type'] = 'initial_source'
    spec['signals'][0]['event_upper_bound'] = '2025-07-31T23:59:59+07:00'
    with pytest.raises(ValueError, match='ambiguous_event_year|event_upper_bound_binding'):
        module().validate_round(train, val, contract, spec)


def test_unchanged_semantics_control_retains_bounded_replay(tmp_path):
    m = module()
    train, val, contract, spec = fixture(tmp_path)
    a = tmp_path / 'a'
    m.run_round(train, val, contract, spec, a, total_timesteps=8,
                model_config=dict(hidden_sizes=[8], batch_size=2, learning_starts=2,
                                  train_frequency=1, buffer_size=12))
    spec2 = copy.deepcopy(spec)
    spec2.update(round_id='2024.1-r2-control', round_index=2, control='extra_steps_no_new_signal')
    b = tmp_path / 'b'
    report = m.run_round(train, val, contract, spec2, b, parent=a, total_timesteps=8)
    assert report['replay_policy'] == 'retain_compatible_bounded_replay'
    assert report['improvement_demonstrated'] is False
    assert report['improvement_attribution'] == 'optimization_only_control'
    loaded = m.MaskedDQN.load(b / 'checkpoint', expected_contract=contract)
    assert loaded.replay.capacity == 12 and len(loaded.replay) == 12
    # An unversioned correction to stored reward inputs must still discard old
    # transitions; "same semantics" cannot be asserted just by version labels.
    revised = problem_payload(train[0])
    revised['scores'][0][0] = .4
    train = [m.decode_problem(revised)]
    snapshot = Path(spec['snapshot_path'])
    content = json.loads(snapshot.read_text(encoding='utf-8'))
    content['training_problem_sha256'] = [record_hash(problem_payload(p)) for p in train]
    snapshot.write_text(json.dumps(content), encoding='utf-8')
    spec2.update(round_id='2024.1-r3-control', round_index=3,
                 snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match='control_requires_identical_inputs'):
        m.run_round(train, val, contract, spec2, tmp_path / 'c', parent=b, total_timesteps=8)
