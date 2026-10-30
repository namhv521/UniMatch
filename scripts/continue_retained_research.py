"""Complete a preregistered retained-policy chain before opening final test.

Existing warm fits and scratch controls stay immutable. Unaccepted candidates
remain unaccepted; only the latest accepted native weights can seed a new fit.
"""
from __future__ import annotations

import argparse
import copy
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features.fresh_suite import MODE, digest, verify_source, write_json
from src.data_pipeline.review_decisions import record_hash
from src.rl.nested_learning import decode_problem, run_round, verify_round


VERSIONS = ('V1', 'V2', 'V3', 'V4')
SUMMARY_KEYS = ('decision', 'steps_before', 'steps_added', 'steps_after', 'candidate_score', 'parent_score', 'delta',
    'start_weights_equal_parent', 'replay_policy', 'forgetting_status', 'reload_parity', 'inference_parity',
    'training_elapsed_seconds')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def create_retention(*args):
    # Deferred until execution: the standalone ledger module can be added while
    # predeclared base training is still running without changing that process.
    from src.rl.model_retention import create_retention as create
    return create(*args)


def _time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone_timestamp_required')
    return parsed


def _spec(payload, algorithm, seed, accept_non_regression):
    result = copy.deepcopy(payload['round'])
    result.update(algorithm=algorithm, seed=seed)
    result['round_id'] += '-' + algorithm + '-long'
    if accept_non_regression is not None:
        result.setdefault('decision_thresholds', {})['accept_non_regression'] = accept_non_regression
    return result


def _existing(output, algorithm, version, summary, payload, settings):
    folder = (output / summary['artifact']).resolve()
    if not folder.is_relative_to(output / 'rounds' / algorithm):
        raise ValueError('warm_artifact_must_stay_in_algorithm_namespace')
    result = verify_round(folder)
    data = _read(folder / 'input.json')
    if (result.get('decision') != summary.get('decision') or result.get('algorithm') != algorithm
            or result.get('semester_id') != payload['round']['semester_id']
            or result.get('steps_added') != settings['timesteps']):
        raise ValueError('base_warm_summary_mismatch')
    if any(record_hash(data[name]) != record_hash(payload[name]) for name in ('train', 'validation', 'contract')):
        raise ValueError('base_warm_suite_input_mismatch')
    expected = _spec(payload, algorithm, settings['seed'], settings['accept_non_regression'])
    if record_hash(data['round']) != record_hash(expected):
        raise ValueError('base_warm_protocol_mismatch')
    return folder, result


def _continue_algorithm(settings):
    output = Path(settings['output'])
    algorithm, payloads = settings['algorithm'], settings['payloads']
    rounds = copy.deepcopy(settings['rounds'])
    accepted, accepted_result, parent, history = None, None, None, {}
    retentions, added_steps, discarded_steps = {}, 0, 0
    for version in VERSIONS:
        if version not in payloads:
            rounds[version] = {'status': 'blocked_data_readiness', 'retained_parent_available': parent is not None}
            continue
        payload = payloads[version]
        old = rounds.get(version, {})
        if old.get('artifact'):
            folder, result = _existing(output, algorithm, version, old, payload, settings)
        elif parent is not None:
            spec = _spec(payload, algorithm, settings['seed'], settings['accept_non_regression'])
            folder = output / 'rounds' / algorithm / version
            print(json.dumps({'event': 'retained_training_start', 'algorithm': algorithm, 'version': version,
                              'parent': str(parent), 'requested_steps': settings['timesteps']}), flush=True)
            result = run_round([decode_problem(p) for p in payload['train']], decode_problem(payload['validation']),
                payload['contract'], spec, folder, parent=parent, total_timesteps=settings['timesteps'],
                historical_validation={name: decode_problem(p) for name, p in history.items()},
                eval_interval=settings['eval_interval'])
            added_steps += result['steps_added']
            rounds[version] = {key: result.get(key) for key in SUMMARY_KEYS}
            elapsed = result.get('training_elapsed_seconds')
            rounds[version]['steps_per_second'] = result['steps_added'] / elapsed if elapsed else None
            rounds[version]['artifact'] = folder.relative_to(output).as_posix()
            print(json.dumps({'event': 'retained_training_end', 'algorithm': algorithm, 'version': version,
                              'decision': result['decision'], 'score': result.get('candidate_score')}), flush=True)
        else:
            rounds[version] = {'status': 'blocked_no_accepted_checkpoint'}
            continue
        history[version] = payload['validation']
        if result['decision'] == 'accepted':
            accepted, accepted_result, parent = folder, result, folder
        elif result['decision'] in ('rejected', 'inconclusive'):
            discarded_steps += result['steps_added']
            if accepted is None:
                rounds[version]['retention_status'] = 'unavailable_no_accepted_checkpoint'
                continue
            ledger = output / 'retention' / algorithm / (version + '.json')
            ledger.parent.mkdir(parents=True, exist_ok=True)
            retained = create_retention(accepted, folder, ledger)
            retentions[version] = {'artifact': ledger.relative_to(output).as_posix(),
                                  'sha256': digest(ledger), 'summary': retained}
            rounds[version]['retained_policy'] = retentions[version]
            parent = ledger
        else:
            raise ValueError('known_candidate_decision_required')
        if accepted is not None:
            rounds[version]['effective_weight_source'] = accepted.relative_to(output).as_posix()
            rounds[version]['effective_model_steps_after'] = accepted_result['steps_after']
        write_json(output / 'continuation' / (algorithm + '.json'), {'rounds': rounds, 'retentions': retentions,
            'additional_training_steps': added_steps, 'discarded_training_steps': discarded_steps})
    return algorithm, rounds, retentions, added_steps, discarded_steps


def continue_research(output, suites, *, jobs=1):
    output, suites = Path(output).resolve(), Path(suites).resolve()
    if output.parent.parent.name != 'nested_rl_20261028' or output.parent.parent.parent.name != 'data_rebuild':
        raise ValueError('fresh_research_namespace_required')
    if not suites.is_relative_to(output.parent) or jobs not in (1, 2):
        raise ValueError('fresh_suites_and_one_or_two_workers_required')
    index_path, manifest_path = output / 'index.json', output / 'manifest.json'
    report, base_manifest = _read(index_path), _read(manifest_path)
    if report.get('test_evaluated') or any((output / p).exists() for p in ('final_test.json', 'test_results.json')):
        raise ValueError('test_already_opened')
    if report.get('scope') != MODE or base_manifest.get('index_sha256') != digest(index_path):
        raise ValueError('complete_verified_base_phase_required')
    base_copies = (output / 'index.base.json', output / 'manifest.base.json')
    if any(path.exists() for path in base_copies) or report.get('retention_continuation'):
        raise FileExistsError('retention_phase_already_started')
    protocol_path = output / 'retention_protocol.json'
    protocol = _read(protocol_path)
    fixed = {'schema_version': 'retained-policy-protocol/1.0', 'declared_before_terminal_V2': True,
        'weight_source': 'latest_accepted_checkpoint', 'logical_context': 'latest_completed_attempt',
        'failed_attempt_remains_unaccepted': True, 'budget_per_fit': 131072, 'eval_interval': 8192,
        'max_new_drop': 0, 'max_old_drop': 0, 'min_improvement': 0, 'accept_non_regression': True,
        'test_opened': False, 'new_feedback_fabricated': False}
    if any(protocol.get(key) != value for key, value in fixed.items()):
        raise ValueError('fixed_predeclared_retention_protocol_required')
    declared_at = _time(protocol['declared_at'])
    if (report.get('requested_timesteps_per_round') != protocol['budget_per_fit']
            or report.get('eval_interval') != protocol['eval_interval'] or report.get('accept_non_regression') is not True
            or report.get('checkpoint_selection') != 'final_only'):
        raise ValueError('base_budget_and_selection_must_match_protocol')
    payloads = {}
    for version in VERSIONS:
        folder = suites / version
        verify_source(folder)
        source_sha = digest(folder / 'manifest.json')
        if report['suites'][version].get('source_manifest_sha256') != source_sha:
            raise ValueError('suite_snapshot_mismatch: ' + version)
        readiness = _read(folder / 'readiness.json')
        if readiness['status'] != report['suites'][version]['status']:
            raise ValueError('suite_readiness_mismatch')
        if readiness['status'] == 'ready_research_only':
            payloads[version] = _read(folder / 'suite.json')
            thresholds = payloads[version]['round']['decision_thresholds']
            if any(thresholds.get(key) != protocol[key] for key in ('min_improvement', 'max_new_drop', 'max_old_drop')):
                raise ValueError('suite_quality_gates_must_remain_unchanged')
    for algorithm, rounds in report['rounds'].items():
        terminal = rounds.get('V2', {})
        if terminal.get('artifact'):
            folder = (output / terminal['artifact']).resolve()
            if not folder.is_relative_to(output / 'rounds' / algorithm):
                raise ValueError('warm_artifact_must_stay_in_algorithm_namespace')
            if declared_at >= _time(_read(folder / 'manifest.json')['created_at']):
                raise ValueError('protocol_must_precede_terminal_V2')
    # Preserve the exact completed base aggregate before any new fitting.
    for source, target in zip((index_path, manifest_path), base_copies):
        with target.open('xb') as stream:
            stream.write(source.read_bytes())
    settings = [{'output': str(output), 'algorithm': algorithm, 'payloads': payloads,
        'rounds': copy.deepcopy(rounds), 'timesteps': protocol['budget_per_fit'],
        'eval_interval': protocol['eval_interval'], 'accept_non_regression': protocol['accept_non_regression'],
        'seed': report['seed']} for algorithm, rounds in report['rounds'].items()]
    phase = {'protocol': 'retain-latest-accepted-with-unchanged-quality-gates',
        'protocol_sha256': digest(protocol_path), 'base_index_sha256': digest(base_copies[0]),
        'base_manifest_sha256': digest(base_copies[1]), 'started_at': datetime.now(timezone.utc).isoformat(),
        'retentions': {}, 'additional_training_steps': 0, 'discarded_training_steps': 0,
        'test_opened': False, 'accepted_training_fabricated': False}
    write_json(output / 'continuation/protocol.json', phase)
    if jobs == 1:
        results = list(map(_continue_algorithm, settings))
    else:
        with ProcessPoolExecutor(max_workers=jobs) as executor:
            results = list(executor.map(_continue_algorithm, settings))
    for algorithm, rounds, retentions, added, discarded in results:
        report['rounds'][algorithm] = rounds
        phase['retentions'][algorithm] = retentions
        phase['additional_training_steps'] += added
        phase['discarded_training_steps'] += discarded
    phase.update(status='complete', finished_at=datetime.now(timezone.utc).isoformat())
    report['retention_continuation'] = phase
    write_json(index_path, report)
    write_json(manifest_path, {**base_manifest, 'index_sha256': digest(index_path),
        'base_index_sha256': phase['base_index_sha256'], 'base_manifest_sha256': phase['base_manifest_sha256'],
        'retention_protocol_sha256': phase['protocol_sha256'], 'continuation_script_sha256': digest(Path(__file__)),
        'production_promoted': False})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suites', type=Path, required=True)
    parser.add_argument('--jobs', type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    result = continue_research(args.output, args.suites, jobs=args.jobs)
    print(json.dumps(result['retention_continuation'], ensure_ascii=True, indent=2))
