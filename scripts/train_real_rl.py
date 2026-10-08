"""Train all curated TRAIN students against all advisors; never train on holdout."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_benchmark import run as benchmark
from src.evaluation.benchmark import load_split
from src.rl.checkpoints import (
    save_checkpoint,
    validate_resume_manifest,
    verified_checkpoint,
)
from src.rl.cli import _algorithm_class
from src.rl.training import (
    TrainingConfig,
    build_environment,
    count_invalid_proposals,
    run_manifest,
)
from src.serving import MatchingService
from src.serving.model_registry import ModelRegistry

ALGORITHMS = {
    'MaskablePPO': ('ppo', 'train_maskable_ppo'), 'DQN': ('dqn', 'train_dqn'),
    'QRDQN': ('qrdqn', 'train_qrdqn'), 'TRPO': ('trpo', 'train_trpo'),
    'ARS': ('ars', 'train_ars'), 'RecurrentPPO': ('recurrent_ppo', 'train_recurrent_ppo'),
}


def preflight(root: Path = ROOT) -> dict:
    service = MatchingService(root)
    all_indices = []
    for name in ('train', 'validation', 'test', 'future'):
        indices = service.split['indices'][name]
        if any(type(index) is not int for index in indices):
            raise ValueError('split indices must be integers')
        all_indices.extend(indices)
        if [service.theses[i]['student_id'] for i in indices] != service.split['student_ids'][name]:
            raise ValueError(f'{name} student mapping mismatch')
    if sorted(all_indices) != list(range(len(service.theses))):
        raise ValueError('splits must be disjoint and cover every student exactly once')
    for rows, field in ((service.theses, 'student_id'), (service.advisors, 'advisor_id')):
        ids = [row[field] for row in rows]
        if any(not value for value in ids) or len(ids) != len(set(ids)):
            raise ValueError(f'duplicate or empty {field}')
    if not np.isfinite(service.matrix).all() or np.any((service.matrix < 0) | (service.matrix > 1)):
        raise ValueError('compatibility scores must be finite and in [0, 1]')
    scores, capacities, provenance = load_split(root, 'train')
    return {'students': len(scores), 'advisors': len(capacities),
            'observation_shape': [3 * len(capacities)], 'action_count': len(capacities),
            'smoke': False, 'training_scope': 'curated-train', 'provenance': provenance,
            'capacity_policy': 'uniform-ceiling-experimental-v1',
            'warnings': ['official quotas are unavailable; research only',
                         'preprocessing is the frozen snapshot; excluded original train texts remain in vocabulary']}


def select_resume(output: Path, config: TrainingConfig) -> tuple[Path | None, list[dict]]:
    candidates, rejected = [], []
    advisor_count = preflight()['advisors']
    for path in sorted(output.glob(f'{config.algorithm.lower()}-seed{config.seed}-*.json')):
        try:
            manifest = json.loads(path.read_text(encoding='utf-8'))
            validate_resume_manifest(manifest, config)
            checkpoint = verified_checkpoint(path, manifest)
            shape, actions, steps = ModelRegistry._spaces(checkpoint)
            if steps != manifest.get('completed_timesteps') or shape != [3 * advisor_count] or actions != advisor_count:
                raise ValueError('checkpoint space or completed steps mismatch')
            if steps < config.timesteps:
                candidates.append((steps, path))
        except (OSError, KeyError, ValueError, TypeError) as exc:
            rejected.append({'manifest': path.name, 'reason': str(exc)})
    return (max(candidates, default=(0, None), key=lambda item: item[0])[1], rejected)


def train(args: argparse.Namespace) -> dict:
    import torch

    torch.set_num_threads(args.threads)
    info = preflight()
    output = args.output_dir.resolve()
    if output != ROOT / 'outputs/research-current':
        print('Custom output: web registry only scans its configured research directories.', flush=True)
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for algorithm in args.algorithms:
        module, function = ALGORITHMS[algorithm]
        trainer = getattr(importlib.import_module('src.rl.' + module), function)
        for seed in args.seeds:
            config = TrainingConfig(algorithm, args.timesteps, seed, output)
            stem = output / f'{algorithm.lower()}-seed{seed}-steps{args.timesteps}-{config.dataset_hash[:12]}'
            manifest_path = stem.with_suffix('.json')
            start = time.monotonic()
            if manifest_path.exists():
                verify_target(manifest_path, config, info['advisors'])
            else:
                env = build_environment(config)
                try:
                    resume, rejected = select_resume(output, config) if args.resume else (None, [])
                    for rejection in rejected:
                        print(json.dumps({'resume_rejected': rejection}), flush=True)
                    previous = 0
                    if resume:
                        prior = json.loads(resume.read_text(encoding='utf-8'))
                        checkpoint = verified_checkpoint(resume, prior)
                        model = _algorithm_class(algorithm).load(checkpoint, env=env, device='cpu')
                        previous = int(model.num_timesteps)
                        model.learn(args.timesteps - previous, reset_num_timesteps=False)
                    else:
                        print(f'Train {algorithm} seed={seed}: {info["students"]} students x {info["advisors"]} advisors', flush=True)
                        model = trainer(env, total_timesteps=args.timesteps, seed=seed)
                    metadata = run_manifest(config, completed_timesteps=int(model.num_timesteps), status='completed')
                    metadata.update(prior_completed_timesteps=previous,
                                    training_students=info['students'], training_advisors=info['advisors'],
                                    elapsed_seconds=time.monotonic() - start,
                                    invalid_proposals=count_invalid_proposals(model, env, masked=algorithm == 'MaskablePPO',
                                                                            recurrent=algorithm == 'RecurrentPPO'))
                    # Reject a changed bundle during a long training job before publishing it.
                    if preflight()['provenance'] != info['provenance']:
                        raise ValueError('data changed during training; checkpoint was not published')
                    save_checkpoint(model, stem, algorithm=algorithm, seed=seed, run_manifest=metadata)
                finally:
                    env.close()
            report = benchmark(ROOT / 'outputs/benchmarks/current-validation.json', output)
            target = verify_target(manifest_path, config, info['advisors'])
            if not any(row['checkpoint_hash'] == target['sha256'] for row in report['evaluated_checkpoints']):
                raise ValueError('target checkpoint was rejected by validation; inspect benchmark report')
            print(json.dumps({'completed': manifest_path.name, 'selected_engine': report['selected_engine']}), flush=True)
    return report


def verify_target(path: Path, config: TrainingConfig, advisor_count: int) -> dict:
    manifest = json.loads(path.read_text(encoding='utf-8'))
    validate_resume_manifest(manifest, config)
    checkpoint = verified_checkpoint(path, manifest)
    shape, actions, steps = ModelRegistry._spaces(checkpoint)
    if steps != manifest.get('completed_timesteps') or steps < config.timesteps:
        raise ValueError('checkpoint native steps do not match completed manifest/budget')
    if shape != [3 * advisor_count] or actions != advisor_count:
        raise ValueError('checkpoint spaces do not match all advisors')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--timesteps', type=int, default=2_000_000)
    parser.add_argument('--seeds', type=int, nargs='+', default=[42])
    parser.add_argument('--algorithms', choices=list(ALGORITHMS), nargs='+', default=list(ALGORITHMS))
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/research-current')
    parser.add_argument('--resume', action='store_true', help='Resume compatible completed checkpoints only')
    parser.add_argument('--threads', type=int, default=1)
    args = parser.parse_args(argv)
    if args.timesteps <= 0 or args.threads <= 0 or any(seed < 0 or seed > 2_147_483_647 for seed in args.seeds):
        parser.error('positive budget/threads and valid nonnegative seeds required')
    if args.preflight:
        print(json.dumps(preflight(), indent=2))
    else:
        train(args)


if __name__ == '__main__':
    main()
