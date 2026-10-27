"""Open frozen final holdouts once after all training/selection has completed.

Writes aggregate metrics only. Never trains, selects models or edits the frozen
research index. An existing result (including an interrupted attempt) blocks
another opening under this protocol.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch

from src.environment.rebuild_env import MatchingEnv
from src.data_pipeline.review_decisions import record_hash
from src.data_pipeline.semester_versions import SEMESTER_BY_VERSION
from src.evaluation.rebuild_benchmark import evaluate_problem
from src.features.fresh_suite import digest, verify_source, write_json
from src.rl.nested_learning import _load_parent, decode_problem, verify_round


VERSIONS = ('V1', 'V2', 'V3', 'V4')
PROTOCOL = 'open_once_after_all_training_and_selection_frozen_no_retuning'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _frozen_inputs(root, suites):
    if not (root / 'manifest.json').is_file() or not (root / 'index.json').is_file():
        raise ValueError('completed_training_manifest_required')
    manifest, index = read(root / 'manifest.json'), read(root / 'index.json')
    if digest(root / 'index.json') != manifest.get('index_sha256'):
        raise ValueError('frozen_training_index_hash_mismatch')
    if (root / 'retention_protocol.json').is_file() and index.get('retention_continuation', {}).get('status') != 'complete':
        raise ValueError('retention_continuation_must_complete_before_final_test')
    if index.get('test_protocol') != PROTOCOL or index.get('checkpoint_selection') != 'final_only':
        raise ValueError('predeclared_final_test_protocol_required')
    if index.get('test_evaluated') is not False:
        raise ValueError('final_holdout_already_opened')
    versions = set(VERSIONS)
    if set(index.get('suites', {})) != versions or not index.get('rounds'):
        raise ValueError('complete_frozen_training_index_required')
    if set(index['rounds']) - {'ppo', 'dqn'} or set(index.get('from_scratch_controls', {})) - set(index['rounds']):
        raise ValueError('supported_frozen_algorithm_inventory_required')
    for table in [*index['rounds'].values(), *index.get('from_scratch_controls', {}).values()]:
        if set(table) != versions:
            raise ValueError('complete_frozen_training_index_required')
    payloads, source_hashes = {}, {}
    for version, entry in index['suites'].items():
        expected = entry.get('source_manifest_sha256')
        if expected:
            actual = verify_source(suites / version)
            if actual != expected:
                raise ValueError('frozen_suite_manifest_hash_mismatch')
            source_hashes[version] = actual
        elif entry.get('status') == 'ready_research_only':
            raise ValueError('frozen_suite_manifest_binding_required')
        if entry.get('status') == 'ready_research_only':
            payloads[version] = read(suites / version / 'suite.json')
    return index, source_hashes, payloads


def _checked_artifact(root, entry, algorithm):
    artifact = (root / entry['artifact']).resolve()
    if not artifact.is_relative_to(root):
        raise ValueError('model_artifact_outside_frozen_run')
    report = verify_round(artifact)
    inputs = read(artifact / 'input.json')
    if (report.get('algorithm') != algorithm or inputs.get('round', {}).get('algorithm') != algorithm
            or report.get('decision') != entry.get('decision')):
        raise ValueError('frozen_model_selection_mismatch')
    return artifact, report, inputs


def _validate_holdout(problem, report, inputs):
    ids = set(problem.student_ids)
    learned = set(report.get('lineage_training_student_ids', []))
    learned.update(s for p in inputs['train'] for s in p['student_ids'])
    if ids & learned:
        raise ValueError('final_holdout_training_overlap')
    contract = inputs['contract']
    if (problem.metadata.get('split') != 'test' or contract['state_contract'] != MatchingEnv([problem]).state_contract
            or tuple(problem.advisor_ids) != tuple(contract['state_contract']['advisor_ids'])):
        raise ValueError('final_holdout_state_contract_mismatch')
    for key in ('feature_contract_sha256', 'taxonomy_feature_order_sha256'):
        if problem.metadata.get(key) != contract.get(key):
            raise ValueError('final_holdout_feature_contract_mismatch')
    if problem.metadata.get('policy_version') != contract.get('quota_policy_version'):
        raise ValueError('final_holdout_quota_policy_mismatch')


def _metrics(result, n):
    return {'n_test': n, 'objective_per_student': result['metrics']['objective'] / n,
            'metrics': result['metrics'], 'invalid_action_count': result['invalid_action_count'],
            'elapsed_seconds': result['elapsed_seconds'], 'status': result['status']}


def evaluate_final(root, suites, output):
    root, suites, output = Path(root).resolve(), Path(suites).resolve(), Path(output).resolve()
    if output != root / 'final_test.json':
        raise ValueError('one_fixed_final_test_output_required')
    if output.exists():
        raise FileExistsError('final_test_was_already_opened')
    index, suite_hashes, payloads = _frozen_inputs(root, suites)
    problems = {version: decode_problem(data['test']) for version, data in payloads.items()}
    checked = {}
    for kind, tables in [('warm_candidate', index['rounds']), ('from_scratch', index.get('from_scratch_controls', {}))]:
        for algorithm, table in tables.items():
            for version, entry in table.items():
                if version not in problems or not entry.get('artifact'):
                    continue
                artifact, model_report, inputs = _checked_artifact(root, entry, algorithm)
                if (model_report.get('semester_id') != SEMESTER_BY_VERSION[version]
                        or model_report.get('seed') != index.get('seed', 42)
                        or record_hash(inputs['train']) != record_hash(payloads[version]['train'])
                        or record_hash(inputs['validation']) != record_hash(payloads[version]['validation'])):
                    raise ValueError('model_inputs_do_not_match_frozen_version_suite')
                _validate_holdout(problems[version], model_report, inputs)
                checked[(kind, algorithm, version)] = (entry, artifact, model_report, inputs)
    for algorithm in index['rounds']:
        selected = None
        for version in VERSIONS:
            candidate = checked.get(('warm_candidate', algorithm, version))
            if candidate and candidate[2]['decision'] == 'accepted':
                selected = candidate
            if version in problems and selected:
                _validate_holdout(problems[version], selected[2], selected[3])
    # Reserve before any prediction: failed/interrupted attempts cannot silently
    # reopen test via a second process or a different output filename.
    frozen_index_sha = digest(root / 'index.json')
    with output.open('x', encoding='utf-8') as stream:
        json.dump({'status': 'evaluating', 'protocol': PROTOCOL, 'training_index_sha256': frozen_index_sha}, stream)
    torch.set_num_threads(1)
    started = time.perf_counter()
    baselines = {version: {name: _metrics(evaluate_problem(problem, name, seed=index.get('seed', 42)), len(problem.student_ids))
                          for name in ('hungarian', 'greedy', 'random')}
                 for version, problem in problems.items()}
    report = {'schema_version': 'nested-rl-final-test/1.0', 'status': 'evaluating', 'protocol': PROTOCOL,
              'scope': index.get('scope', 'research_only'), 'prediction_time_verified': index.get('prediction_time_verified', False),
              'evaluation_target': 'frozen_document_proxy_holdout_not_academic_outcome',
              'training_index_sha256': frozen_index_sha, 'training_manifest_sha256': digest(root / 'manifest.json'),
              'suite_manifest_sha256': suite_hashes, 'evaluator_sha256': digest(Path(__file__)),
              'selection_changed': False, 'learning_performed': False, 'production_promoted': False,
              'baselines': baselines, 'models': [], 'selected_frozen_models': {}}
    cache = {}
    def evaluate(algorithm, version, value, kind):
        entry, artifact, model_report, inputs = value
        key = (str(artifact), version)
        if key not in cache:
            problem = problems[version]
            _validate_holdout(problem, model_report, inputs)
            model = _load_parent({'path': artifact, 'report': model_report, 'input': inputs})
            result = evaluate_problem(problem, algorithm, model=model, seed=index.get('seed', 42))
            cache[key] = _metrics(result, len(problem.student_ids))
        metrics = cache[key]
        return {'algorithm': algorithm, 'version': version, 'kind': kind,
                'decision': model_report['decision'], 'artifact': artifact.relative_to(root).as_posix(),
                'model_semester_id': model_report['semester_id'],
                'steps_added': model_report.get('steps_added'), 'steps_after': model_report.get('steps_after'),
                'model_manifest_sha256': digest(artifact / 'manifest.json'),
                **metrics, 'regret_per_student': baselines[version]['hungarian']['objective_per_student']-metrics['objective_per_student']}
    for (kind, algorithm, version), value in checked.items():
        report['models'].append(evaluate(algorithm, version, value, kind))
    for algorithm, table in index['rounds'].items():
        selected, selected_version = None, None
        report['selected_frozen_models'][algorithm] = {}
        for version in VERSIONS:
            candidate = checked.get(('warm_candidate', algorithm, version))
            if candidate and candidate[2]['decision'] == 'accepted':
                selected, selected_version = candidate, version
            if version not in problems:
                report['selected_frozen_models'][algorithm][version] = {'status': 'unavailable_test_data'}
            elif selected is None:
                report['selected_frozen_models'][algorithm][version] = {'status': 'no_accepted_checkpoint'}
            else:
                row = evaluate(algorithm, version, selected, 'selected_frozen')
                row.update(selected_from_version=selected_version, selection='accepted_candidate' if selected_version == version else 'retained_'+selected_version)
                report['selected_frozen_models'][algorithm][version] = row
    if digest(root / 'index.json') != frozen_index_sha:
        raise RuntimeError('training_index_changed_during_final_evaluation')
    report.update(status='completed', elapsed_seconds=time.perf_counter()-started,
                  unique_model_holdout_evaluations=len(cache), retuning_allowed=False)
    write_json(output, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--suites', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_final(args.root, args.suites, args.output)
    print(json.dumps({'status': result['status'], 'model_rows': len(result['models']),
                      'unique_model_holdout_evaluations': result['unique_model_holdout_evaluations'],
                      'selection_changed': False, 'elapsed_seconds': result['elapsed_seconds']}))
