"""Resumable cumulative-milestone RL training; final experiments require complete curation."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--algorithm', choices=['ppo', 'dqn', 'qrdqn', 'a2c'], default='ppo')
    parser.add_argument('--timesteps', type=int, default=20000)
    parser.add_argument('--milestones', type=int, nargs='+')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--learning-rate', type=float, default=.0003)
    parser.add_argument('--fairness-weight', type=float, default=.15)
    args = parser.parse_args()
    targets = args.milestones or [args.timesteps]
    if targets != sorted(set(targets)) or min(targets) <= 0:
        parser.error('Milestones must be positive, unique and increasing')
    import torch
    torch.set_num_threads(1)
    from sb3_contrib import QRDQN, MaskablePPO
    from stable_baselines3 import A2C, DQN
    from stable_baselines3.common.monitor import Monitor

    from src.data_pipeline.dataset import cohort, load_dataset
    from src.environment.gym_matching_env import GymMatchingEnv
    dataset = load_dataset(allow_partial=args.allow_partial)
    scores, quotas, _ = cohort(dataset, 'train')
    output = Path('outputs/smoke_models' if dataset['partial'] else 'outputs/models')
    output.mkdir(parents=True, exist_ok=True)
    log = output / f'{args.algorithm}_seed{args.seed}.monitor.csv'
    env = Monitor(GymMatchingEnv(scores, quotas, fairness_weight=args.fairness_weight), str(log))
    classes = {'ppo': MaskablePPO, 'dqn': DQN, 'qrdqn': QRDQN, 'a2c': A2C}
    model_class = classes[args.algorithm]
    configuration = {'algorithm': args.algorithm, 'seed': args.seed,
                     'dataset_sha256': dataset['sha256'], 'learning_rate': args.learning_rate,
                     'fairness_weight': args.fairness_weight, 'gamma': .99}
    if args.resume:
        metadata = json.loads(args.resume.with_suffix('.json').read_text(encoding='utf-8'))
        if metadata['configuration'] != configuration:
            raise ValueError('Resume configuration/dataset differs from checkpoint')
        if hashlib.sha256(args.resume.read_bytes()).hexdigest() != metadata['model_sha256']:
            raise ValueError('Checkpoint integrity mismatch')
        model = model_class.load(args.resume, env=env, device='cpu')
        if args.algorithm in ('dqn', 'qrdqn'):
            model.load_replay_buffer(args.resume.with_suffix('.replay.pkl'))
    else:
        kwargs = {'learning_rate': args.learning_rate, 'gamma': .99, 'seed': args.seed,
                  'device': 'cpu', 'verbose': 0}
        if args.algorithm == 'ppo':
            kwargs.update(n_steps=256, batch_size=64)
        elif args.algorithm in ('dqn', 'qrdqn'):
            kwargs.update(buffer_size=50000, learning_starts=500, batch_size=64)
        model = model_class('MlpPolicy', env, **kwargs)
    for target in targets:
        if target <= model.num_timesteps:
            continue
        model.learn(total_timesteps=target - model.num_timesteps, reset_num_timesteps=False)
        path = output / f'{args.algorithm}_seed{args.seed}_steps{target}.zip'
        model.save(path)
        if args.algorithm in ('dqn', 'qrdqn'):
            model.save_replay_buffer(path.with_suffix('.replay.pkl'))
        metadata = {'configuration': configuration, 'requested_timesteps': target,
                    'actual_timesteps': model.num_timesteps, 'partial_data_smoke_only': dataset['partial'],
                    'model_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'created_at': datetime.now(timezone.utc).isoformat()}
        path.with_suffix('.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        print(json.dumps({'checkpoint': str(path), 'actual_timesteps': model.num_timesteps,
                          'smoke_only': dataset['partial']}), flush=True)
    env.close()


if __name__ == '__main__':
    main()
