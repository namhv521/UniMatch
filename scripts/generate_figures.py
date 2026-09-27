"""Export 300-DPI figures from measured artifacts; missing runs remain visibly missing."""
import argparse
import csv
import json
from itertools import pairwise
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=Path('outputs/results/checkpoint_benchmark_val_steps2000000.json'))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    root = Path('outputs/figures')
    root.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'savefig.dpi': 300, 'font.family': 'DejaVu Sans'})
    artifacts = []

    def save(fig, name):
        path = root / (name + '.png')
        fig.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
        fig.savefig(path.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
        plt.close(fig)
        artifacts.append(str(path))

    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    for path in sorted(Path('outputs/models').glob('*.monitor.csv')):
        with path.open(encoding='utf-8') as stream:
            rows = list(csv.DictReader(line for line in stream if not line.startswith('#')))
        if not rows:
            continue
        rewards = np.array([float(row['r']) for row in rows])
        steps = np.cumsum([int(row['l']) for row in rows])
        window = min(50, len(rows))
        ax.plot(steps[window - 1:], np.convolve(rewards, np.ones(window) / window, mode='valid'),
                label=path.stem.replace('.monitor', ''), linewidth=1)
    ax.set(xlabel='Environment steps', ylabel='Episode return (rolling mean, up to 50)',
           title='Observed training curves — available runs only')
    if ax.lines:
        ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=.2)
    save(fig, 'learning_curves')

    groups = {}
    for row in report['results']:
        if row.get('complete'):
            groups.setdefault(row['strategy'], []).append(row)
    names = list(groups)
    labels = [f'{name}\nn={len(groups[name])}' for name in names]
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    means = [np.mean([row['mean_compatibility'] for row in groups[name]]) for name in names]
    deviations = [np.std([row['mean_compatibility'] for row in groups[name]], ddof=1)
                  if len(groups[name]) > 1 else 0 for name in names]
    ax.bar(labels, means, yerr=deviations, capsize=4, color='#32644c')
    ax.set(ylabel='Mean TF-IDF compatibility (± sample SD)', ylim=(0, 1),
           title='Validation compatibility — successful runs only')
    missing = sorted({row['strategy'] for row in report['results'] if not row.get('complete')})
    fig.text(.12, .01, 'Incomplete algorithms: ' + (', '.join(missing) or 'none'), fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, 1))
    save(fig, 'algorithm_comparison')

    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    quota = [max(row['quota_violations'] for row in groups[name]) for name in names]
    invalid = [max(row['invalid_proposals'] for row in groups[name]) for name in names]
    x = np.arange(len(names))
    ax.bar(x - .18, quota, width=.36, label='Quota violations', color='#32644c')
    ax.bar(x + .18, invalid, width=.36, label='Invalid proposals', color='#9d6638')
    ax.set_xticks(x, labels)
    ax.set(ylabel='Maximum count across available successful runs',
           title='Constraint audit — incomplete runs excluded', ylim=(0, max([1, *quota, *invalid]) * 1.1))
    ax.legend()
    save(fig, 'constraint_violations')

    for name, title, boxes in [
        ('system_architecture', 'Implemented system architecture', [
            'PDF / DOCX\nOfficial FIT profiles', 'Grounded extraction\nEvidence + audit',
            'Temporal student split\nTrain-only TF-IDF', 'Matching environment\nBaselines / RL',
            'Validation + gate\nLocked holdout', 'Local FastAPI\nReact dashboard']),
        ('mdp_flow', 'Sequential matching transition', [
            'Current student i\nCompatibility scores', 'Observe [scores, rem, load]\n3M dimensions',
            'Feasible action mask\nLoad < quota', 'Policy proposes advisor j',
            'Valid: assign + update load\nInvalid: penalty, retain i', 'Reward + next student\nStop at N or proposal limit'])]:
        fig, ax = plt.subplots(figsize=(9, 3.5))
        ax.set(xlim=(0, 3), ylim=(0, 2), title=title)
        ax.axis('off')
        positions = [(0.5, 1.5), (1.5, 1.5), (2.5, 1.5), (2.5, .5), (1.5, .5), (.5, .5)]
        for text, (x, y) in zip(boxes, positions):
            ax.text(x, y, text, ha='center', va='center', fontsize=9,
                    bbox={'boxstyle': 'round,pad=.7', 'facecolor': '#eff4ef', 'edgecolor': '#32644c'})
        for (x1, y1), (x2, y2) in pairwise(positions):
            dx, dy = x2 - x1, y2 - y1
            ax.annotate('', xy=(x2 - .40 * dx, y2 - .27 * dy),
                        xytext=(x1 + .40 * dx, y1 + .27 * dy),
                        arrowprops={'arrowstyle': '->', 'color': '#32644c'})
        save(fig, name)
    (root / 'manifest.json').write_text(json.dumps({
        'source_report': str(args.report), 'dataset_sha256': report['dataset_sha256'],
        'full_benchmark_complete': report['complete'], 'dpi': 300, 'artifacts': artifacts,
        'caveat': 'Current advisor snapshot is not a historical faculty backtest; regenerate after remaining runs.'
    }, indent=2), encoding='utf-8')
    print(json.dumps({'figures': len(artifacts), 'full_benchmark_complete': report['complete']}))


if __name__ == '__main__':
    main()
