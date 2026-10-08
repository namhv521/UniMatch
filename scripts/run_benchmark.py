"""Run repeatable holdout evaluation; missing candidates become explicit blockers."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation.benchmark import evaluate_baselines, evaluate_checkpoint, load_split
from src.evaluation.promotion import DEFAULT_SEEDS, promotion_decision


def run(output, checkpoint_dir, split='validation'):
    output, checkpoint_dir = Path(output).resolve(), Path(checkpoint_dir).resolve()
    import torch
    torch.set_num_threads(1)
    scores, capacities, provenance = load_split(ROOT, split)
    rows = evaluate_baselines(scores, capacities, DEFAULT_SEEDS)
    rejected = []
    for path in sorted(checkpoint_dir.glob('*.json')):
        try:
            rows.append(evaluate_checkpoint(ROOT, path, scores, capacities, provenance))
        except (ValueError, KeyError, FileNotFoundError) as exc:
            rejected.append({'manifest':path.name, 'reason':str(exc)})
    evaluated = [{key: row[key] for key in ('algorithm', 'seed', 'checkpoint_hash', 'training_timesteps')}
                 for row in rows if 'checkpoint_hash' in row]
    # Select latest budget per algorithm/seed, never choose by validation score.
    selected = {}
    for row in rows:
        key = (row['algorithm'], row['seed'])
        if key not in selected or row.get('training_timesteps',0) > selected[key].get('training_timesteps',0):
            selected[key] = row
    rows = list(selected.values())
    promotion = {}
    for algorithm in ('MaskablePPO', 'DQN', 'QRDQN', 'TRPO', 'ARS', 'RecurrentPPO'):
        candidates = [row for row in rows if row['algorithm'] == algorithm]
        promotion[algorithm] = promotion_decision(candidates)
    summary = []
    for algorithm in sorted({row['algorithm'] for row in rows}):
        values = [row for row in rows if row['algorithm'] == algorithm]
        summary.append({'algorithm':algorithm, 'seed_count':len(values),
                        'metrics': {name:{'mean':float(np.mean([r['metrics'][name] for r in values])),
                                         'std':float(np.std([r['metrics'][name] for r in values]))}
                                    for name in ('mean_compatibility','load_variance','quota_violations','invalid_proposals','fallback_count')}})
    approved = [item for item in summary if promotion.get(item['algorithm'], {}).get('promoted')]
    engine = max(approved, key=lambda item:item['metrics']['mean_compatibility']['mean'])['algorithm'] if approved else 'Hungarian'
    report = {'schema_version':'1.0', 'created_at':datetime.now(timezone.utc).isoformat(),
              'scope':'holdout-research', 'split':split, 'students':len(scores), 'advisors':len(capacities),
              'seeds':DEFAULT_SEEDS, 'provenance':provenance, 'rows':rows,
              'summary':summary, 'rejected_checkpoints':rejected, 'promotion':promotion,
              'evaluated_checkpoints':evaluated,
              'selected_engine':engine, 'selection_reason':'Verified validation promotion gates passed' if approved else 'No approved full-budget multi-seed RL evidence',
              'limitations':['quota is an experimental uniform capacity, not official advisor quota',
                             'same fixed holdout order; no generalization claim beyond this split']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'output':str(output), 'rows':len(rows), 'rejected':len(rejected),
                      'selected_engine':report['selected_engine']}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', choices=['validation','test'], default='validation')
    parser.add_argument('--checkpoint-dir', type=Path, default=ROOT / 'outputs/research-real')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/benchmarks/validation-2026-10-07.json')
    args = parser.parse_args()
    run(args.output, args.checkpoint_dir, args.split)
