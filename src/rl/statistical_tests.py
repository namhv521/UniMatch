"""Paired five-seed comparisons with explicit small-sample/degeneracy reporting."""
import argparse
import json
from pathlib import Path

import numpy as np
import scipy
from scipy import stats

from .evaluate_checkpoints import CLASSICAL_ALGORITHMS, RL_ALGORITHMS, SEEDS


def paired_statistics(candidate, reference):
    a, b = np.asarray(candidate, dtype=float), np.asarray(reference, dtype=float)
    if a.shape != (5,) or b.shape != (5,) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Exactly five finite paired observations required')
    differences = a - b
    result = {'differences': differences.tolist(), 'mean_difference': float(differences.mean()),
              'df': 4, 't_statistic': None, 't_p': None, 'mean_difference_ci95': None,
              'wilcoxon_p': None, 'status': 'ok',
              'wilcoxon_method': 'exhaustive paired sign permutations, two-sided',
              'warning': 'With five pairs, exact two-sided Wilcoxon cannot attain p<0.05. Seeds are not independent datasets.'}
    if np.all(differences == 0):
        result['status'] = 'identical_observations'
        return result
    if np.std(differences, ddof=1) == 0:
        result['status'] = 'constant_nonzero_differences_t_undefined'
    else:
        t = stats.ttest_rel(a, b)
        ci = t.confidence_interval()
        result.update(t_statistic=float(t.statistic), t_p=float(t.pvalue),
                      mean_difference_ci95=[float(ci.low), float(ci.high)])
    w = stats.wilcoxon(differences, alternative='two-sided',
                       method=stats.PermutationMethod(n_resamples=np.inf))
    result['wilcoxon_p'] = float(w.pvalue)
    return result


def holm_adjust(values):
    p = np.asarray(values, dtype=float)
    if p.ndim != 1 or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Invalid p-values')
    order = np.argsort(p)
    adjusted = np.empty_like(p)
    adjusted[order] = np.minimum(1, np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1)))
    return adjusted.tolist()


def compare_report(report):
    if report.get('split') != 'val' or report.get('smoke_only') or not report.get('dataset_sha256'):
        raise ValueError('Full-data validation evidence required')
    comparisons, excluded = {}, {}
    groups = {}
    for algorithm in (*CLASSICAL_ALGORITHMS, *RL_ALGORITHMS):
        rows = [row for row in report['results'] if row['strategy'] == algorithm]
        if (len(rows) != 5 or {row['seed'] for row in rows} != set(SEEDS)
                or any(not row.get('complete') or row.get('partial_data') is not False
                       or row.get('dataset_sha256') != report['dataset_sha256'] for row in rows)):
            excluded[algorithm] = 'Missing, failed or incompatible paired runs; no imputed scores'
        else:
            groups[algorithm] = {row['seed']: row['mean_compatibility'] for row in rows}
    if 'greedy' not in groups:
        raise ValueError('Five matched Greedy observations required')
    for algorithm, mapping in groups.items():
        if algorithm != 'greedy':
            comparisons[algorithm] = paired_statistics([mapping[s] for s in SEEDS],
                                                         [groups['greedy'][s] for s in SEEDS])
    for field in ('t_p', 'wilcoxon_p'):
        names = [name for name, row in comparisons.items() if row[field] is not None]
        for name, adjusted in zip(names, holm_adjust([comparisons[name][field] for name in names])):
            comparisons[name][field + '_holm'] = adjusted
    return {'dataset_sha256': report['dataset_sha256'], 'split': 'val', 'scipy_version': scipy.__version__,
            'seeds': list(SEEDS), 'complete_eight_algorithm_comparison': not excluded,
            'comparisons_vs_greedy': comparisons, 'excluded_algorithms': excluded,
            'assumptions': 'Independent paired runs; t-test normal differences, signed-rank symmetric differences. Nonsignificance is not equivalence.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    result = compare_report(json.loads(args.report.read_text(encoding='utf-8')))
    path = args.report.with_name(args.report.stem + '_statistics.json')
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'output': str(path), 'complete': result['complete_eight_algorithm_comparison']}))


if __name__ == '__main__':
    main()
