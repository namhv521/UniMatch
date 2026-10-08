"""Train on curated TRAIN only and evaluate on validation; defaults to full budget."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_benchmark import run as benchmark

from src.evaluation.promotion import DEFAULT_SEEDS
from src.rl.checkpoints import (
    save_checkpoint,
    validate_resume_manifest,
    verified_checkpoint,
)
from src.rl.cli import _algorithm_class
from src.rl.dqn import train_dqn
from src.rl.ppo import train_maskable_ppo
from src.rl.training import (
    TrainingConfig,
    build_environment,
    count_invalid_proposals,
    run_manifest,
)


def main():
    import torch
    torch.set_num_threads(1)
    parser = argparse.ArgumentParser()
    parser.add_argument('--timesteps', type=int, default=2_000_000)
    parser.add_argument('--seeds', nargs='+', type=int, default=DEFAULT_SEEDS)
    parser.add_argument('--algorithms', nargs='+', choices=['MaskablePPO','DQN'], default=['MaskablePPO','DQN'])
    args = parser.parse_args()
    output = ROOT / 'outputs/research-real'
    output.mkdir(parents=True, exist_ok=True)
    for algorithm in args.algorithms:
        for seed in args.seeds:
            stem = output / f'{algorithm.lower()}-seed{seed}-steps{args.timesteps}'
            config = TrainingConfig(algorithm, args.timesteps, seed, output)
            if stem.with_suffix('.json').exists():
                metadata = json.loads(stem.with_suffix('.json').read_text())
                validate_resume_manifest(metadata, config)
                verified_checkpoint(stem.with_suffix('.json'), metadata)
                print(json.dumps({'already_completed':stem.name}), flush=True)
                continue
            env = build_environment(config)
            prior = []
            for candidate in output.glob(f'{algorithm.lower()}-seed{seed}-steps*.json'):
                metadata = json.loads(candidate.read_text())
                if metadata.get('completed_timesteps',0) < args.timesteps:
                    prior.append((metadata['completed_timesteps'], candidate, metadata))
            start = time.monotonic()
            previous_steps = 0
            if prior:
                previous_steps, candidate, metadata = max(prior, key=lambda item:item[0])
                validate_resume_manifest(metadata, config)
                checkpoint = verified_checkpoint(candidate, metadata)
                model = _algorithm_class(algorithm).load(checkpoint, env=env, device='cpu')
                model.learn(args.timesteps-previous_steps, reset_num_timesteps=False)
            else:
                trainer = train_maskable_ppo if algorithm=='MaskablePPO' else train_dqn
                model = trainer(env, total_timesteps=args.timesteps, seed=seed)
            metadata = run_manifest(config, completed_timesteps=int(model.num_timesteps), status='completed')
            metadata.update({'prior_completed_timesteps':previous_steps,
                             'invalid_proposals':count_invalid_proposals(model,env,masked=algorithm=='MaskablePPO'),
                             'elapsed_seconds':time.monotonic()-start})
            save_checkpoint(model, stem, algorithm=algorithm, seed=seed, run_manifest=metadata)
            print(json.dumps({'algorithm':algorithm,'seed':seed,'timesteps':int(model.num_timesteps),
                              'elapsed_seconds':metadata['elapsed_seconds']}),flush=True)
            benchmark(ROOT/'outputs/benchmarks/validation-2026-10-07.json', output)


if __name__=='__main__':
    main()
