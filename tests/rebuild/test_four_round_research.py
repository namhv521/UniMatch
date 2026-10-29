import copy
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('four_round', Path(__file__).parents[2] / 'scripts/run_four_round_research.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_missing_feedback_never_trains_or_creates_output(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'run_round', lambda *a, **k: pytest.fail('must not train'))
    out = tmp_path / 'new'
    with pytest.raises(ValueError, match='missing_real_feedback'):
        m.run(tmp_path / 'suites', tmp_path / 'feedback', out)
    assert not out.exists()
    report = m.readiness(tmp_path / 'suites', tmp_path / 'feedback')
    assert len(report['rounds']) == 12 and not report['ready']


def test_four_round_order_inheritance_and_r4_unchanged(tmp_path, monkeypatch):
    suites, feedback = tmp_path / 'suites', tmp_path / 'feedback'
    for version, term in zip(m.VERSIONS, m.TERMS):
        for index, kind in enumerate(('initial_source', 'student_preference', 'advisor_feedback'), 1):
            data = {'train': [{'round_data': index}], 'validation': {'version': version},
                    'contract': {}, 'round': {'semester_id': term, 'signals': [{'type': kind}]}}
            m.write(suites / version / 'suite.json' if index == 1 else feedback / version / f'R{index}.json', data)
    calls = []
    monkeypatch.setattr(m, 'decode_problem', copy.deepcopy)

    def fit(train, validation, contract, round_spec, folder, **kwargs):
        calls.append((copy.deepcopy(train), round_spec, folder, kwargs))
        return {'decision': 'accepted', 'steps_added': 16}

    monkeypatch.setattr(m, 'run_round', fit)
    output = tmp_path / 'out'
    result = m.run(suites, feedback, output, algorithms=('dqn',), timesteps=16, eval_interval=8)
    assert result['status'] == 'completed' and len(calls) == 12
    for i, (train, round_spec, folder, kwargs) in enumerate(calls):
        assert kwargs['parent'] == (calls[i-1][2] if i else None)
        assert round_spec['round_index'] == i % 4 + 1
        assert len(kwargs['historical_validation']) == i // 4
        assert folder == output / m.VERSIONS[i // 4] / f'R{i % 4 + 1}' / 'dqn'
        if i % 4 == 3:
            assert train == calls[i-1][0]
            assert round_spec['control'] == 'extra_steps_no_new_signal'
            assert round_spec['signals'] == calls[i-1][1]['signals']
    with pytest.raises(FileExistsError):
        m.run(suites, feedback, output)


def test_feedback_type_cannot_be_replaced_by_initial_source():
    data = {'round': {'semester_id': '2024.1', 'signals': [{'type': 'initial_source'}]}}
    with pytest.raises(ValueError, match='required_round_feedback_missing'):
        m.prepare(data, 'V1', 2, 'ppo', 42)


def test_mock_export_rejects_real_scope_and_false_completion(tmp_path):
    from scripts.export_four_round_results import export
    root = tmp_path / 'results'
    protocol = {'feedback_scope': 'source_bound_feedback', 'timesteps_per_fit': 32768, 'seed': 42}
    m.write(root / 'ppo/comparison.json', {'protocol': protocol, 'status': 'completed', 'results': []})
    with pytest.raises(ValueError, match='this_mock_publication_requires'):
        export(root, tmp_path / 'public')
    protocol['feedback_scope'] = 'simulated_feedback_not_human'
    for algorithm in ('ppo', 'dqn'):
        m.write(root / algorithm / 'comparison.json', {'protocol': protocol, 'status': 'completed', 'results': []})
    with pytest.raises(ValueError, match='unique_complete_24'):
        export(root, tmp_path / 'public')
    assert not (tmp_path / 'public/results.json').exists()
