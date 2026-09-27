"""Comparable baseline metrics with explicit partial-data and holdout gates."""
import argparse
import json
from pathlib import Path

import numpy as np

from src.baselines.classical import allocate
from src.models.data_contract import validate_matching_data


def evaluate_assignment(scores, quotas, assignment, historical=None, invalid_proposals=0):
    scores, quotas = validate_matching_data(scores, quotas)
    assignment = np.asarray(assignment)
    n, m = scores.shape
    if (assignment.shape != (n,) or not np.issubdtype(assignment.dtype, np.integer)
            or np.any(assignment < 0) or np.any(assignment >= m)):
        raise ValueError('Every student must have one valid advisor index')
    loads = np.bincount(assignment, minlength=m)
    score = float(scores[np.arange(n), assignment].sum())
    exact = allocate(scores, quotas, 'exact')
    optimal = float(scores[np.arange(n), exact].sum())
    accuracy = None
    if historical is not None:
        labels = np.asarray(historical)
        if labels.shape != (n,):
            raise ValueError('Historical labels must align with cohort')
        valid = (labels >= 0) & (labels < m)
        accuracy = float(np.mean(assignment[valid] == labels[valid])) if valid.any() else None
    return {'mean_compatibility': score / n, 'quota_violations': int(np.maximum(loads - quotas, 0).sum()),
            'invalid_proposals': int(invalid_proposals), 'load_variance': float(np.var(loads)),
            'historical_top1_accuracy': accuracy, 'optimality_ratio': score / optimal if optimal > 0 else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strategy', choices=['all', 'random', 'greedy', 'spa', 'exact'], default='all')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--split', choices=['train', 'val', 'test'], default='val')
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    if args.split == 'test':
        parser.error('Final holdout requires frozen candidate selection; use dedicated final-evaluation workflow')
    from src.data_pipeline.dataset import cohort, load_dataset
    dataset = load_dataset(allow_partial=args.allow_partial)
    scores, quotas, indices = cohort(dataset, args.split)
    lookup = {row['advisor_id']: index for index, row in enumerate(dataset['advisors'])}
    labels = [lookup.get(dataset['students'][i]['advisor_id'], -1) for i in indices]
    results = []
    for strategy in (['random', 'greedy', 'spa', 'exact'] if args.strategy == 'all' else [args.strategy]):
        assignments = allocate(scores, quotas, strategy, args.seed)
        results.append({'strategy': strategy, 'seed': args.seed, 'split': args.split,
                        'dataset_sha256': dataset['sha256'], 'partial_data': dataset['partial'],
                        'complete': True, **evaluate_assignment(scores, quotas, assignments, labels)})
    output = Path('outputs/smoke_results' if dataset['partial'] else 'outputs/results')
    output.mkdir(parents=True, exist_ok=True)
    path = output / f'baseline_{args.split}_seed{args.seed}.json'
    path.write_text(json.dumps(results, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
