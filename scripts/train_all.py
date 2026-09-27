"""Resume the requested four-algorithm, five-seed milestone grid with bounded CPU jobs."""
import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.rl.evaluate_checkpoints import RL_ALGORITHMS, SEEDS


def latest_checkpoint(directory, algorithm, seed):
    candidates = []
    for path in directory.glob(f'{algorithm}_seed{seed}_steps*.json'):
        metadata = json.loads(path.read_text(encoding='utf-8'))
        model = path.with_suffix('.zip')
        if not model.exists() or hashlib.sha256(model.read_bytes()).hexdigest() != metadata['model_sha256']:
            raise ValueError(f'Checkpoint integrity failure: {path.name}')
        candidates.append((metadata['actual_timesteps'], model))
    return max(candidates, default=(0, None), key=lambda item: item[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3, 4), default=2)
    parser.add_argument('--milestones', nargs='+', type=int, default=[200000, 500000, 1000000, 2000000])
    parser.add_argument('--exclude', nargs='*', default=[], help='Currently active jobs, e.g. ppo:42')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.milestones != sorted(set(args.milestones)) or min(args.milestones) <= 0:
        parser.error('Milestones must be positive, unique and increasing')
    from src.data_pipeline.dataset import load_dataset
    dataset = load_dataset()
    logdir = ROOT / 'outputs/training'
    logdir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for algorithm in RL_ALGORITHMS:
        for seed in SEEDS:
            name = f'{algorithm}:{seed}'
            if name in args.exclude:
                continue
            steps, checkpoint = latest_checkpoint(ROOT / 'outputs/models', algorithm, seed)
            if checkpoint:
                metadata = json.loads(checkpoint.with_suffix('.json').read_text(encoding='utf-8'))
                if metadata['configuration']['dataset_sha256'] != dataset['sha256']:
                    raise ValueError('Existing checkpoint belongs to a different dataset')
            if steps >= max(args.milestones):
                continue
            command = [sys.executable, '-m', 'src.rl.train', '--algorithm', algorithm,
                       '--seed', str(seed), '--milestones', *map(str, args.milestones)]
            if checkpoint:
                command.extend(['--resume', str(checkpoint)])
            jobs.append((name, command))
    if args.dry_run:
        print(json.dumps({'pending_jobs': [name for name, _ in jobs], 'dataset_sha256': dataset['sha256']}))
        return 0

    def run(job):
        name, command = job
        log = logdir / (name.replace(':', '_') + '.log')
        with log.open('a', encoding='utf-8') as stream:
            stream.write('\nRun started ' + datetime.now(timezone.utc).isoformat() + '\n')
            stream.flush()
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False)
        return {'job': name, 'exit_code': result.returncode, 'log': str(log)}

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(run, job) for job in jobs]):
            result = future.result()
            results.append(result)
            print(json.dumps(result), flush=True)
            (logdir / 'grid_status.json').write_text(json.dumps({
                'dataset_sha256': dataset['sha256'], 'requested_jobs': len(jobs),
                'finished_jobs': results, 'excluded_running_jobs': args.exclude}, indent=2), encoding='utf-8')
    return int(any(row['exit_code'] for row in results))


if __name__ == '__main__':
    raise SystemExit(main())
