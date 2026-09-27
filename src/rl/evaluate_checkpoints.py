"""Five-seed validation benchmark; missing or invalid checkpoints never get substitute scores."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from src.baselines.classical import allocate
from src.environment.gym_matching_env import GymMatchingEnv
from src.models.data_contract import validate_matching_data
from src.rl.benchmark import evaluate_assignment

SEEDS = (42, 123, 456, 789, 1024)
RL_ALGORITHMS = ('ppo', 'dqn', 'qrdqn', 'a2c')
CLASSICAL_ALGORITHMS = ('random', 'greedy', 'spa', 'exact')


def verify_checkpoint(path, expected_configuration, steps, partial):
    """Check locally produced metadata and bytes before SB3 deserialization.

    Hashes prove consistency, not authenticity: only use trusted local artifacts.
    """
    path = Path(path)
    metadata = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if metadata.get('configuration') != expected_configuration:
        raise ValueError('Checkpoint configuration/dataset mismatch')
    if metadata.get('partial_data_smoke_only') is not partial:
        raise ValueError('Checkpoint partial-data flag mismatch')
    actual = metadata.get('actual_timesteps')
    if (metadata.get('requested_timesteps') != steps or type(actual) is not int
            or actual < steps):
        raise ValueError('Checkpoint milestone mismatch or undertrained artifact')
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata.get('model_sha256'):
        raise ValueError('Checkpoint integrity mismatch')
    return metadata


def load_policy(path, algorithm, metadata):
    import torch
    from sb3_contrib import QRDQN, MaskablePPO
    from stable_baselines3 import A2C, DQN
    torch.set_num_threads(1)
    classes = {'ppo': MaskablePPO, 'dqn': DQN, 'qrdqn': QRDQN, 'a2c': A2C}
    model = classes[algorithm].load(path, device='cpu')
    config = metadata['configuration']
    if (model.num_timesteps != metadata['actual_timesteps'] or model.seed != config['seed']
            or model.gamma != config['gamma'] or model.learning_rate != config['learning_rate']):
        raise ValueError('Loaded model differs from checkpoint configuration')
    return model


def rollout_policy(model, algorithm, scores, quotas, *, seed, fairness_weight=.15,
                   historical=None):
    if algorithm not in RL_ALGORITHMS:
        raise ValueError('Unknown RL algorithm')
    env = GymMatchingEnv(scores, quotas, fairness_weight=fairness_weight)
    obs, _ = env.reset(seed=seed)
    started = perf_counter()
    try:
        while True:
            kwargs = {'deterministic': True}
            if algorithm == 'ppo':
                kwargs['action_masks'] = env.action_masks()
            action, _ = model.predict(obs, **kwargs)
            action = np.asarray(action)
            if action.size != 1 or not np.issubdtype(action.dtype, np.integer):
                raise ValueError('Policy must return a single integer action')
            obs, _, terminated, truncated, info = env.step(int(action.item()))
            if terminated or truncated:
                break
        result = {'complete': bool(terminated and not truncated),
                  'terminated': terminated, 'truncated': truncated,
                  'assigned_count': info['assigned_count'], 'proposals': env.proposals,
                  'assignments': info['assignments'], 'quota_violations': info['quota_violations'],
                  'invalid_proposals': info['invalid_proposals'],
                  'rollout_seconds': perf_counter() - started,
                  'mean_compatibility': None, 'load_variance': None,
                  'historical_top1_accuracy': None, 'optimality_ratio': None}
        if result['complete']:
            result.update(evaluate_assignment(scores, quotas, env.assignments, historical,
                                              invalid_proposals=env.invalid_proposals))
        return result
    finally:
        env.close()


def benchmark_checkpoints(scores, quotas, *, dataset_sha256, partial, model_dir,
                          steps=200000, split='val', allow_partial=False,
                          learning_rate=.0003, fairness_weight=.15, historical=None):
    split = 'val' if split == 'validation' else split
    if split != 'val':
        raise ValueError('Only validation is allowed; final holdout requires frozen selection')
    if partial and not allow_partial:
        raise ValueError('Partial data requires explicit allow_partial')
    if (type(steps) is not int or steps <= 0 or not np.isfinite(learning_rate)
            or learning_rate <= 0 or not np.isfinite(fairness_weight) or fairness_weight < 0):
        raise ValueError('Invalid milestone or configuration')
    # Solver slot expansion may clamp quotas to N; policy load ratios must keep
    # the original capacity used by GymMatchingEnv during training.
    scores, _ = validate_matching_data(scores, quotas)
    results = []
    smoke = bool(partial or allow_partial)
    for seed in SEEDS:
        common = {'seed': seed, 'split': split, 'dataset_sha256': dataset_sha256,
                  'partial_data': bool(partial), 'smoke_only': smoke}
        for strategy in CLASSICAL_ALGORITHMS:
            started = perf_counter()
            assignments = allocate(scores, quotas, strategy, seed)
            elapsed = perf_counter() - started
            results.append({**common, 'strategy': strategy, 'status': 'complete',
                            'complete': True, 'assigned_count': len(scores),
                            'assignments': assignments.tolist(), 'rollout_seconds': elapsed,
                            **evaluate_assignment(scores, quotas, assignments, historical)})
        for algorithm in RL_ALGORITHMS:
            path = Path(model_dir) / f'{algorithm}_seed{seed}_steps{steps}.zip'
            row = {**common, 'strategy': algorithm, 'complete': False,
                   'checkpoint': str(path), 'requested_timesteps': steps}
            if not path.is_file() or not path.with_suffix('.json').is_file():
                results.append({**row, 'status': 'missing_checkpoint'})
                continue
            configuration = {'algorithm': algorithm, 'seed': seed,
                             'dataset_sha256': dataset_sha256, 'learning_rate': learning_rate,
                             'fairness_weight': fairness_weight, 'gamma': .99}
            try:
                metadata = verify_checkpoint(path, configuration, steps, partial)
                model = load_policy(path, algorithm, metadata)
                if (model.observation_space.shape != (3 * scores.shape[1],)
                        or model.action_space.n != scores.shape[1]):
                    raise ValueError('Checkpoint observation/action space mismatch')
                result = rollout_policy(model, algorithm, scores, quotas, seed=seed,
                                        fairness_weight=fairness_weight, historical=historical)
                row.update(result, model_sha256=metadata['model_sha256'],
                           actual_timesteps=metadata['actual_timesteps'],
                           configuration=configuration,
                           status='complete' if result['complete'] else 'incomplete_episode')
            except Exception as exc:  # noqa: BLE001 - failed policies remain explicit failure rows, never fallback scores
                # Retain an explicit failure row; never replace it with a baseline.
                row.update(status='checkpoint_error', error=f'{type(exc).__name__}: {exc}')
            results.append(row)
    evaluation_complete = all(row['complete'] for row in results)
    return {'complete': evaluation_complete and not smoke,
            'evaluation_complete': evaluation_complete, 'smoke_only': smoke,
            'split': split, 'dataset_sha256': dataset_sha256, 'requested_timesteps': steps,
            'expected_rl_rows': 20, 'expected_classical_rows': 20,
            'completed_rows': sum(row['complete'] for row in results), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['val', 'validation', 'test'], default='validation')
    parser.add_argument('--steps', type=int, default=200000)
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--learning-rate', type=float, default=.0003)
    parser.add_argument('--fairness-weight', type=float, default=.15)
    args = parser.parse_args()
    if args.split == 'test':
        parser.error('Final holdout is blocked until candidate selection is frozen')
    from src.data_pipeline.dataset import cohort, load_dataset
    dataset = load_dataset(allow_partial=args.allow_partial)
    scores, quotas, indices = cohort(dataset, 'val')
    lookup = {row['advisor_id']: i for i, row in enumerate(dataset['advisors'])}
    labels = [lookup.get(dataset['students'][i].get('advisor_id'), -1) for i in indices]
    model_dir = Path('outputs/smoke_models' if dataset['partial'] else 'outputs/models')
    report = benchmark_checkpoints(scores, quotas, dataset_sha256=dataset['sha256'],
                                   partial=dataset['partial'], model_dir=model_dir,
                                   steps=args.steps, split=args.split, historical=labels,
                                   allow_partial=args.allow_partial,
                                   learning_rate=args.learning_rate,
                                   fairness_weight=args.fairness_weight)
    output = Path('outputs/smoke_results' if report['smoke_only'] else 'outputs/results')
    output.mkdir(parents=True, exist_ok=True)
    path = output / f'checkpoint_benchmark_val_steps{args.steps}.json'
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'report': str(path), 'complete': report['complete'],
                      'completed_rows': report['completed_rows'], 'expected_rows': 40,
                      'smoke_only': report['smoke_only']}))
    return 0 if report['evaluation_complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
