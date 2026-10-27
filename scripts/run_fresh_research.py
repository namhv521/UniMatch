"""Build fresh retrospective suites and execute an adjacent accepted-parent chain.

This bounded diagnostic run never fills absent feedback, evaluates final test,
claims convergence, or changes the serving release.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features.fresh_suite import MODE, prepare_suite, write_json, digest
from src.rl.nested_learning import decode_problem, run_round


def run_research(root, output, *, mode, student_collection=None, algorithms=('ppo', 'dqn'), timesteps=1024, seed=42):
    root, output = Path(root).resolve(), Path(output).resolve()
    if mode != MODE or not output.is_relative_to(root):
        raise ValueError('explicit_fresh_retrospective_run_required')
    if root.parent.name != 'nested_rl_20261028' or root.parent.parent.name != 'data_rebuild' or output.parent != root:
        raise ValueError('new_research_must_be_fresh_run_child')
    if output.exists():
        raise FileExistsError('new_research_output_required')
    if not algorithms or len(set(algorithms)) != len(algorithms) or set(algorithms) - {'ppo', 'dqn'}:
        raise ValueError('unique_supported_algorithms_required')
    output.mkdir(parents=True)
    report = {'scope': mode, 'seed': seed, 'requested_timesteps_per_round': timesteps, 'suites': {}, 'rounds': {},
              'inner_feedback_rounds': {'status': 'unavailable', 'reason': 'No verified student/faculty/coordinator feedback was supplied; do not manufacture rounds 2-4.'},
              'prediction_time_verified': False, 'test_evaluated': False, 'production_promoted': False,
              'convergence_established': False}
    versions = ('V1', 'V2', 'V3', 'V4')
    payloads = {}
    for version in versions:
        folder = output / 'suites' / version
        if version != 'V1' and not (output / 'suites/V1/encoder.json').is_file():
            report['suites'][version] = {'status': 'blocked_bootstrap_unavailable'}
            continue
        report['suites'][version] = prepare_suite(root, folder, version=version, mode=mode, seed=seed,
            student_collection=student_collection, frozen_encoder=output / 'suites/V1/encoder.json' if version != 'V1' else None)
        if report['suites'][version]['status'] == 'ready_research_only':
            payloads[version] = json.loads((folder / 'suite.json').read_text(encoding='utf-8'))
    write_json(output / 'index.json', report)
    for algorithm in algorithms:
        parent, history, halted = None, {}, False
        report['rounds'][algorithm] = {}
        for version in versions:
            if halted:
                report['rounds'][algorithm][version] = {'status': 'blocked_parent_not_accepted'}
                continue
            if version not in payloads:
                report['rounds'][algorithm][version] = {'status': 'blocked_data_readiness'}
                halted = True
                continue
            data = copy.deepcopy(payloads[version])
            data['round']['algorithm'] = algorithm
            data['round']['round_id'] += '-' + algorithm
            folder = output / 'rounds' / algorithm / version
            result = run_round([decode_problem(p) for p in data['train']], decode_problem(data['validation']),
                data['contract'], data['round'], folder, parent=parent, total_timesteps=timesteps,
                historical_validation={name: decode_problem(p) for name, p in history.items()})
            report['rounds'][algorithm][version] = {key: result.get(key) for key in
                ('decision', 'steps_before', 'steps_added', 'steps_after', 'candidate_score', 'parent_score', 'delta',
                 'start_weights_equal_parent', 'replay_policy', 'forgetting_status', 'reload_parity', 'inference_parity')}
            report['rounds'][algorithm][version]['artifact'] = str(folder.relative_to(output))
            if result['decision'] == 'accepted':
                parent = folder
                history[version] = data['validation']
            else:
                halted = True
            write_json(output / 'index.json', report)
        write_json(output / 'index.json', report)
    write_json(output / 'manifest.json', {'scope': mode, 'index_sha256': digest(output / 'index.json'),
                'runner_sha256': digest(Path(__file__)), 'production_promoted': False})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--student-collection', type=Path)
    parser.add_argument('--mode', choices=[MODE], required=True)
    parser.add_argument('--algorithms', choices=['ppo', 'dqn'], nargs='+', default=['ppo', 'dqn'])
    parser.add_argument('--timesteps', type=int, default=1024)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    result = run_research(args.run, args.output, mode=args.mode, student_collection=args.student_collection,
                          algorithms=args.algorithms, timesteps=args.timesteps, seed=args.seed)
    print(json.dumps(result, ensure_ascii=True, indent=2))
