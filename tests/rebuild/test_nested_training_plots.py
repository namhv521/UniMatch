"""Scientific plots use measured steps/metrics and show absent training explicitly."""
import importlib
import json
import shutil

import pytest


def fixture(root):
    folder = root / 'rounds/ppo/V1'
    folder.mkdir(parents=True)
    metrics = {'objective': .8, 'coverage': 1., 'constraint_violations': 0}
    report = {'algorithm': 'ppo', 'semester_id': '2024.1', 'round_id': 'V1-r1',
              'steps_before': 0, 'steps_added': 16, 'steps_after': 16,
              'candidate_score': .4, 'parent_score': None, 'decision': 'accepted',
              'candidate': {'metrics': metrics},
              'baselines': {name: {'metrics': {'objective': value}} for name, value in
                            [('hungarian', 1.), ('greedy', .9), ('random', .5)]},
              'training': {'losses': [{'timesteps': 8, 'loss': .8}, {'timesteps': 16, 'loss': .3}]},
              'forgetting': {}, 'improvement_attribution': 'causality_not_established'}
    (folder / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    (folder / 'input.json').write_text(json.dumps({'validation': {'student_ids': ['a', 'b']}}))
    points = [{'relative_step': step, 'cumulative_step': step, 'phase': phase,
               'validation_objective_per_student': score, 'hungarian_objective_per_student': .5,
               'greedy_objective_per_student': .45, 'random_objective_per_student': .25,
               'hungarian_regret_per_student': .5-score,
               'validation_coverage': 1., 'validation_constraint_violations': 0,
               'elapsed_seconds': step / 4, 'train_mean_episode_reward': step / 10,
               'historical_validation': {}} for step, phase, score in [(0, 'initial', .2), (8, 'interval', .3), (16, 'final', .4)]]
    (folder / 'learning_curve.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in points))
    (root / 'index.json').write_text(json.dumps({'rounds': {'ppo': {'V1': {'decision': 'accepted'}, 'V2': {'status': 'blocked_data_readiness'}}}}))
    return folder


def test_generate_measured_plots_and_assets(tmp_path):
    module = importlib.import_module('scripts.plot_nested_training')
    folder = fixture(tmp_path)
    control = tmp_path / 'controls/from_scratch/ppo/V1'
    shutil.copytree(folder, control)
    output = tmp_path / 'figures'
    result = module.generate_plots(tmp_path, output)
    assert {'validation_steps', 'validation_cumulative_steps', 'training_loss', 'training_return',
            'hungarian_regret', 'final_comparison', 'runtime_constraints'} <= {row['name'] for row in result}
    for row in result:
        assert (output / row['path']).read_bytes().startswith(b'\x89PNG')
        assert '<svg' in (output / row['svg_path']).read_text(encoding='utf-8')
        assert (output / row['path']).stat().st_size > 1000
    runs = module.load_runs(tmp_path)
    assert [row['relative_step'] for row in runs[0]['curve']] == [0, 8, 16]
    assert {run['kind'] for run in runs} == {'sequential', 'from_scratch'}


def test_step_axis_or_final_metric_mismatch_is_rejected(tmp_path):
    module = importlib.import_module('scripts.plot_nested_training')
    folder = fixture(tmp_path)
    curve = [json.loads(line) for line in (folder / 'learning_curve.jsonl').read_text().splitlines()]
    curve[-1]['cumulative_step'] = 999
    (folder / 'learning_curve.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in curve))
    with pytest.raises(ValueError, match='step_contract'):
        module.load_runs(tmp_path)


def test_forgetting_heatmap_and_reference_require_matching_validation_context(tmp_path):
    module = importlib.import_module('scripts.plot_nested_training')
    root = tmp_path / 'current'
    folder = fixture(root)
    report = json.loads((folder / 'report.json').read_text())
    report['forgetting'] = {'old': {'signed_drop': -.01}}
    (folder / 'report.json').write_text(json.dumps(report))
    reference = tmp_path / 'reference'
    fixture(reference)
    output = root / 'figures'
    plots = module.generate_plots(root, output, reference=reference)
    assert {'forgetting_heatmap', 'smoke_vs_long'} <= {row['name'] for row in plots}


def test_optional_final_test_figure_uses_frozen_roles_and_measured_gap(tmp_path):
    module = importlib.import_module('scripts.plot_nested_training')
    fixture(tmp_path)
    row = {'algorithm': 'ppo', 'version': 'V1', 'kind': 'warm_candidate', 'n_test': 2,
           'objective_per_student': .4, 'regret_per_student': .1, 'decision': 'accepted', 'status': 'feasible'}
    payload = {'status': 'completed', 'selection_changed': False, 'models': [row],
               'selected_frozen_models': {'ppo': {'V1': {**row, 'kind': 'selected_frozen', 'selection': 'accepted_candidate'}}},
               'baselines': {'V1': {name: {'n_test': 2, 'objective_per_student': value} for name, value in
                                     [('hungarian', .5), ('greedy', .45), ('random', .25)]}}}
    (tmp_path / 'final_test.json').write_text(json.dumps(payload))
    result = module.generate_plots(tmp_path, tmp_path / 'figures')
    assert 'final_test_comparison' in {row['name'] for row in result}
    payload['selection_changed'] = True
    (tmp_path / 'final_test.json').write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='final_test_selection'):
        module._final_test_plot(tmp_path, tmp_path / 'figures', [])
