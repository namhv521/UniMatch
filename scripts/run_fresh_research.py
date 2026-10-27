"""Build fresh retrospective suites and execute an adjacent accepted-parent chain.

This bounded diagnostic run never fills absent feedback, evaluates final test,
claims convergence, or changes the serving release.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features.fresh_suite import MODE, prepare_suite, write_json, digest, verify_source
from src.rl.nested_learning import decode_problem, run_round


VERSIONS = ('V1', 'V2', 'V3', 'V4')


def _run_algorithm(settings):
    output = Path(settings['output'])
    algorithm = settings['algorithm']
    payloads = settings['payloads']
    rounds, controls = {}, {}
    parent, history, halted = None, {}, False
    ledger = output / 'rounds' / algorithm / 'progress.json'

    def fit(version, *, control=False):
        data = copy.deepcopy(payloads[version])
        data['round']['algorithm'] = algorithm
        data['round']['seed'] = settings['seed']
        data['round']['round_id'] += '-' + algorithm + ('-scratch' if control else '-long')
        if settings['accept_non_regression'] is not None:
            data['round'].setdefault('decision_thresholds', {})['accept_non_regression'] = settings['accept_non_regression']
        if control:
            data['round']['control'] = 'from_scratch'
        folder = output / ('controls/from_scratch' if control else 'rounds') / algorithm / version
        print(json.dumps({'event': 'training_start', 'algorithm': algorithm, 'version': version,
                          'control': control, 'requested_steps': settings['timesteps']}), flush=True)
        extra = {'eval_interval': settings['eval_interval']} if settings['eval_interval'] is not None else {}
        result = run_round([decode_problem(p) for p in data['train']], decode_problem(data['validation']),
            data['contract'], data['round'], folder, parent=None if control else parent,
            total_timesteps=settings['timesteps'],
            historical_validation={} if control else {name: decode_problem(p) for name, p in history.items()}, **extra)
        summary = {key: result.get(key) for key in
            ('decision', 'steps_before', 'steps_added', 'steps_after', 'candidate_score', 'parent_score', 'delta',
             'start_weights_equal_parent', 'replay_policy', 'forgetting_status', 'reload_parity', 'inference_parity',
             'training_elapsed_seconds')}
        elapsed = result.get('training_elapsed_seconds')
        summary['steps_per_second'] = result.get('steps_added', 0) / elapsed if elapsed else None
        summary['artifact'] = folder.relative_to(output).as_posix()
        print(json.dumps({'event': 'training_end', 'algorithm': algorithm, 'version': version,
                          'control': control, 'decision': result['decision'], 'score': result.get('candidate_score')}), flush=True)
        return folder, data, summary

    for version in VERSIONS:
        if version not in payloads:
            rounds[version] = {'status': 'blocked_data_readiness'}
            halted = True
        elif halted:
            rounds[version] = {'status': 'blocked_parent_not_accepted'}
        else:
            folder, data, summary = fit(version)
            rounds[version] = summary
            if summary['decision'] == 'accepted':
                parent = folder
                history[version] = data['validation']
            else:
                halted = True
        write_json(ledger, {'rounds': rounds, 'from_scratch_controls': controls})
    if settings['from_scratch_controls']:
        controls['V1'] = {'status': 'shared_bootstrap', **rounds['V1']}
        for version in VERSIONS[1:]:
            if version not in payloads:
                controls[version] = {'status': 'blocked_data_readiness'}
            else:
                _, _, controls[version] = fit(version, control=True)
            write_json(ledger, {'rounds': rounds, 'from_scratch_controls': controls})
    return algorithm, rounds, controls


def run_research(root, output, *, mode, student_collection=None, algorithms=('ppo', 'dqn'), timesteps=1024, seed=42,
                 reuse_suites=None, eval_interval=None, accept_non_regression=None, from_scratch_controls=False, jobs=1):
    root, output = Path(root).resolve(), Path(output).resolve()
    if mode != MODE or not output.is_relative_to(root):
        raise ValueError('explicit_fresh_retrospective_run_required')
    if root.parent.name != 'nested_rl_20261028' or root.parent.parent.name != 'data_rebuild' or output.parent != root:
        raise ValueError('new_research_must_be_fresh_run_child')
    if output.exists():
        raise FileExistsError('new_research_output_required')
    if not algorithms or len(set(algorithms)) != len(algorithms) or set(algorithms) - {'ppo', 'dqn'}:
        raise ValueError('unique_supported_algorithms_required')
    if jobs not in (1, 2):
        raise ValueError('one_or_two_independent_processes_required')
    if student_collection and Path(student_collection).resolve().parent != root:
        raise ValueError('student_collection_must_be_fresh_run_child')
    if reuse_suites:
        reuse_suites = Path(reuse_suites).resolve()
        if not reuse_suites.is_relative_to(root):
            raise ValueError('reused_suites_must_belong_to_fresh_run')
        verify_source(Path(student_collection).resolve() if student_collection else root / 'students_dates')
        verify_source(root / 'faculty')
        verify_source(root / 'faculty_dates')
    output.mkdir(parents=True)
    report = {'scope': mode, 'seed': seed, 'requested_timesteps_per_round': timesteps, 'suites': {}, 'rounds': {},
              'from_scratch_controls': {}, 'eval_interval': eval_interval, 'accept_non_regression': accept_non_regression,
              'checkpoint_selection': 'final_only', 'independent_processes': jobs,
              'test_protocol': 'open_once_after_all_training_and_selection_frozen_no_retuning',
              'inner_feedback_rounds': {'status': 'unavailable', 'reason': 'No verified student/faculty/coordinator feedback was supplied; do not manufacture rounds 2-4.'},
              'prediction_time_verified': False, 'test_evaluated': False, 'production_promoted': False,
              'convergence_established': False}
    payloads = {}
    for version in VERSIONS:
        folder = output / 'suites' / version
        if reuse_suites:
            source = reuse_suites / version
            verify_source(source)
            report['suites'][version] = json.loads((source / 'readiness.json').read_text(encoding='utf-8'))
            report['suites'][version]['source_manifest_sha256'] = digest(source / 'manifest.json')
            if report['suites'][version]['status'] == 'ready_research_only':
                payloads[version] = json.loads((source / 'suite.json').read_text(encoding='utf-8'))
            continue
        if version != 'V1' and not (output / 'suites/V1/encoder.json').is_file():
            report['suites'][version] = {'status': 'blocked_bootstrap_unavailable'}
            continue
        report['suites'][version] = prepare_suite(root, folder, version=version, mode=mode, seed=seed,
            student_collection=student_collection, frozen_encoder=output / 'suites/V1/encoder.json' if version != 'V1' else None)
        if report['suites'][version]['status'] == 'ready_research_only':
            payloads[version] = json.loads((folder / 'suite.json').read_text(encoding='utf-8'))
    write_json(output / 'index.json', report)
    settings = [{'output': str(output), 'algorithm': algorithm, 'payloads': payloads,
                 'timesteps': timesteps, 'eval_interval': eval_interval, 'accept_non_regression': accept_non_regression,
                 'from_scratch_controls': from_scratch_controls, 'seed': seed} for algorithm in algorithms]
    if jobs == 1:
        results = map(_run_algorithm, settings)
        for algorithm, rounds, controls in results:
            report['rounds'][algorithm] = rounds
            report['from_scratch_controls'][algorithm] = controls
            write_json(output / 'index.json', report)
    else:
        with ProcessPoolExecutor(max_workers=jobs) as executor:
            for algorithm, rounds, controls in executor.map(_run_algorithm, settings):
                report['rounds'][algorithm] = rounds
                report['from_scratch_controls'][algorithm] = controls
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
    parser.add_argument('--reuse-suites', type=Path)
    parser.add_argument('--eval-interval', type=int)
    parser.add_argument('--accept-non-regression', action='store_const', const=True, default=None)
    parser.add_argument('--from-scratch-controls', action='store_true')
    parser.add_argument('--jobs', type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    result = run_research(args.run, args.output, mode=args.mode, student_collection=args.student_collection,
                          algorithms=args.algorithms, timesteps=args.timesteps, seed=args.seed, reuse_suites=args.reuse_suites,
                          eval_interval=args.eval_interval, accept_non_regression=args.accept_non_regression,
                          from_scratch_controls=args.from_scratch_controls, jobs=args.jobs)
    print(json.dumps(result, ensure_ascii=True, indent=2))
