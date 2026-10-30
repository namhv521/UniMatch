"""Final test is immutable, post-selection only and isolated from training IDs."""
import hashlib
import importlib
import json

import numpy as np
import pytest


def module():
    return importlib.import_module('scripts.evaluate_nested_final')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_final_evaluation_rejects_incomplete_training_before_opening_test(tmp_path):
    root = tmp_path / 'long'
    root.mkdir()
    with pytest.raises(ValueError, match='completed_training_manifest_required'):
        module().evaluate_final(root, tmp_path / 'suites', root / 'final_test.json')
    assert not (root / 'final_test.json').exists()


def test_final_evaluation_rejects_tampered_selection_index(tmp_path):
    root = tmp_path / 'long'
    write(root / 'index.json', {'rounds': {}})
    write(root / 'manifest.json', {'index_sha256': '0' * 64})
    with pytest.raises(ValueError, match='frozen_training_index_hash_mismatch'):
        module().evaluate_final(root, tmp_path / 'suites', root / 'final_test.json')


def test_pending_retention_continuation_cannot_open_final_holdout(tmp_path, monkeypatch):
    root = tmp_path / 'long'
    write(root / 'index.json', {'retention_continuation': {'status': 'pending'}})
    write(root / 'manifest.json', {'index_sha256': sha(root / 'index.json')})
    write(root / 'retention_protocol.json', {'continuation': 'predeclared'})
    m = module()
    def forbidden(*args, **kwargs):
        pytest.fail('Pending continuation must not inspect suites or predict final holdouts.')
    monkeypatch.setattr(m, 'verify_source', forbidden)
    monkeypatch.setattr(m, 'evaluate_problem', forbidden)
    with pytest.raises(ValueError, match='retention_continuation_must_complete_before_final_test'):
        m.evaluate_final(root, tmp_path / 'suites', root / 'final_test.json')
    assert not (root / 'final_test.json').exists()


def make_frozen_fixture(tmp_path, *, overlap=False):
    from src.data_pipeline.review_decisions import record_hash
    from src.domain.rebuild_matching import AllocationProblem
    from src.environment.rebuild_env import MatchingEnv
    from src.evaluation.rebuild_benchmark import problem_payload
    from src.rl.nested_learning import run_round
    root, suites = tmp_path / 'long', tmp_path / 'suites'
    root.mkdir()
    def problem(ids, split):
        return AllocationProblem(scores=np.array([[.9, .8], [.7, .1]]), available=np.ones((2, 2), bool),
            student_ids=tuple(ids), advisor_ids=('a', 'b'), capacities=np.array([1, 1]),
            eligible=np.ones((2, 2), bool), present=np.ones(2, bool),
            metadata={'split': split, 'feature_contract_sha256': 'f' * 64,
                      'taxonomy_feature_order_sha256': 'a' * 64, 'policy_version': 'quota/1'})
    train, val = problem(('train-a', 'train-b'), 'train'), problem(('val-a', 'val-b'), 'validation')
    test = problem(('train-a', 'test-b') if overlap else ('test-a', 'test-b'), 'test')
    env = MatchingEnv([train])
    contract = {'scope': 'synthetic_test_only', 'state_contract': env.state_contract,
                'feature_contract_sha256': 'f' * 64, 'taxonomy_feature_order_sha256': 'a' * 64,
                'quota_policy_version': 'quota/1', 'reward_weights': env.reward_weights,
                'training_student_ids': list(train.student_ids)}
    source = tmp_path / 'signal.json'
    write(source, {'fixture': 'initial_source'})
    snapshot = tmp_path / 'snapshot.json'
    write(snapshot, {'training_problem_sha256': [record_hash(problem_payload(train))],
                     'validation_problem_sha256': record_hash(problem_payload(val)), 'signal_ids': ['source']})
    spec = {'algorithm': 'dqn', 'seed': 42, 'semester_id': '2024.1', 'round_index': 1, 'round_id': 'fixture-r1',
            'snapshot_path': str(snapshot), 'snapshot_sha256': sha(snapshot),
            'cutoff_timestamp': '2024-12-31T23:59:59+07:00', 'reward_version': 'r1', 'constraint_version': 'c1',
            'signal_state_sha256': record_hash(['source']),
            'signals': [{'signal_id': 'source', 'type': 'initial_source', 'source_path': str(source),
                         'source_sha256': sha(source), 'available_at': '2024-12-01T00:00:00+07:00', 'review_status': 'verified'}],
            'decision_thresholds': {'min_improvement': 0., 'max_new_drop': 0., 'max_old_drop': 0., 'accept_non_regression': True}}
    artifact = root / 'rounds/dqn/V1'
    run_round([train], val, contract, spec, artifact, total_timesteps=8,
              model_config={'hidden_sizes': [8], 'batch_size': 2, 'learning_starts': 2, 'buffer_size': 16})
    write(suites / 'V1/suite.json', {'train': [problem_payload(train)], 'validation': problem_payload(val),
                                   'test': problem_payload(test), 'contract': contract})
    write(suites / 'V1/readiness.json', {'status': 'ready_research_only'})
    write(suites / 'V1/manifest.json', {'artifacts': {name: sha(suites / 'V1' / name) for name in ('suite.json', 'readiness.json')}})
    ready = {'status': 'ready_research_only', 'source_manifest_sha256': sha(suites / 'V1/manifest.json')}
    index = {'test_protocol': 'open_once_after_all_training_and_selection_frozen_no_retuning',
             'checkpoint_selection': 'final_only', 'test_evaluated': False,
             'suites': {'V1': ready, **{v: {'status': 'blocked_data_insufficient'} for v in ('V2', 'V3', 'V4')}},
             'rounds': {'dqn': {'V1': {'decision': 'accepted', 'artifact': 'rounds/dqn/V1'},
                               **{v: {'status': 'blocked_data_readiness'} for v in ('V2', 'V3', 'V4')}}},
             'from_scratch_controls': {}}
    write(root / 'index.json', index)
    write(root / 'manifest.json', {'index_sha256': sha(root / 'index.json')})
    return root, suites


def test_frozen_final_metrics_and_open_once_guard(tmp_path):
    root, suites = make_frozen_fixture(tmp_path)
    before = (root / 'index.json').read_bytes()
    report = module().evaluate_final(root, suites, root / 'final_test.json')
    assert report['status'] == 'completed' and report['selection_changed'] is False
    assert report['models'][0]['n_test'] == 2
    assert report['models'][0]['metrics']['coverage'] == 1.
    assert (root / 'index.json').read_bytes() == before
    output_text = (root / 'final_test.json').read_text()
    assert 'train-a' not in output_text and 'test-a' not in output_text
    with pytest.raises(FileExistsError):
        module().evaluate_final(root, suites, root / 'final_test.json')


def test_final_test_cannot_contain_lineage_training_identity(tmp_path):
    root, suites = make_frozen_fixture(tmp_path, overlap=True)
    with pytest.raises(ValueError, match='final_holdout_training_overlap'):
        module().evaluate_final(root, suites, root / 'final_test.json')


def test_final_evaluation_rejects_changed_frozen_test_bytes(tmp_path):
    root, suites = make_frozen_fixture(tmp_path)
    path = suites / 'V1/suite.json'
    payload = json.loads(path.read_text())
    payload['test']['scores'][0][0] = .01
    write(path, payload)
    with pytest.raises(ValueError, match='source_artifact_hash_mismatch'):
        module().evaluate_final(root, suites, root / 'final_test.json')
    assert not (root / 'final_test.json').exists()
