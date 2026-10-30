"""Static, measured learning curves for nested RL; no interpolation or test use."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np


COLORS = {'ppo': '#1767a6', 'dqn': '#8a4fa3', 'hungarian': '#177f57',
          'greedy': '#d08b16', 'random': '#89939d'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.titleweight': 'bold',
    'axes.grid': True, 'grid.alpha': .18, 'figure.facecolor': 'white', 'savefig.facecolor': 'white'})


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def load_runs(root):
    """Check axis units and end-point parity before rendering measured curves."""
    root = Path(root)
    paths = [(p, 'sequential') for p in root.glob('rounds/*/*/report.json')]
    paths += [(p, 'from_scratch') for p in root.glob('controls/from_scratch/*/*/report.json')]
    runs = []
    for path, kind in sorted(paths):
        report = _read(path)
        inputs = _read(path.parent / 'input.json')
        n = len(inputs['validation']['student_ids'])
        curve_file = path.parent / 'learning_curve.jsonl'
        rows = [json.loads(line) for line in curve_file.read_text(encoding='utf-8').splitlines() if line.strip()] if curve_file.exists() else []
        deduplicated = {}
        for row in rows:
            step = row['relative_step']
            if (type(step) is not int or step < 0 or row['cumulative_step'] != report['steps_before'] + step
                    or step > report['steps_added']):
                raise ValueError('learning_curve_step_contract_mismatch')
            deduplicated[step] = row
        rows = [deduplicated[key] for key in sorted(deduplicated)]
        if rows and (rows[-1]['relative_step'] != report['steps_added'] or not math.isclose(
                rows[-1]['validation_objective_per_student'], report['candidate_score'], abs_tol=1e-10)):
            raise ValueError('learning_curve_final_report_mismatch')
        runs.append({'report': report, 'input': inputs, 'curve': rows, 'version': path.parent.name,
                     'algorithm': report['algorithm'], 'kind': kind, 'n_validation': n,
                     'n_train': sum(len(p['student_ids']) for p in inputs.get('train', [])), 'folder': path.parent})
    return runs


def _label(run):
    algorithm = run['algorithm'].upper()
    if run['kind'] == 'from_scratch':
        return algorithm + ' from scratch control'
    if run['report'].get('improvement_attribution') == 'optimization_only_control':
        return algorithm + ' extra-step control'
    return algorithm + ' sequential'


def _versions(root, runs):
    index = _read(Path(root) / 'index.json') if (Path(root) / 'index.json').exists() else {}
    values = {run['version'] for run in runs} | set(index.get('suites', {}))
    values |= {version for values in index.get('rounds', {}).values() for version in values}
    return sorted(values, key=lambda key: int(key[1:]) if key.startswith('V') and key[1:].isdigit() else 999)


def _panels(versions, title, ylabel, xlabel):
    columns = min(2, len(versions))
    rows = math.ceil(len(versions) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(7*columns, 3.7*rows), squeeze=False)
    for axis, version in zip(axes.flat, versions):
        axis.set(title=version, xlabel=xlabel, ylabel=ylabel)
        axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value/1000:g}k' if abs(value) >= 1000 else f'{value:g}'))
    for axis in list(axes.flat)[len(versions):]:
        axis.set_visible(False)
    fig.suptitle(title, fontsize=15, fontweight='bold', y=.995)
    return fig, list(axes.flat)[:len(versions)]


def _finish(fig, output, name, title, description, metadata):
    handles, labels = [], []
    for axis in fig.axes:
        for handle, label in zip(*axis.get_legend_handles_labels()):
            if label not in labels:
                handles.append(handle)
                labels.append(label)
    if handles:
        fig.legend(handles, labels, loc='lower center', ncol=min(4, len(labels)), frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, .12 if handles else .03, 1, .95))
    png, svg = output / f'{name}.png', output / f'{name}.svg'
    fig.savefig(png, dpi=170)
    fig.savefig(svg)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
    plt.close(fig)
    metadata.append({'name': name, 'path': png.name, 'svg_path': svg.name,
                     'title': title, 'description': description})


def _lines(runs, versions, output, metadata, *, key, name, title, ylabel, cumulative=False, baselines=False):
    fig, axes = _panels(versions, title, ylabel, 'Cumulative lineage steps' if cumulative else 'Steps added in this fit')
    for axis, version in zip(axes, versions):
        selected = [run for run in runs if run['version'] == version]
        measured = False
        for run in selected:
            rows = [row for row in run['curve'] if row.get(key) is not None]
            if not rows:
                continue
            measured = True
            xkey = 'cumulative_step' if cumulative else 'relative_step'
            values = [row[key] for row in rows]
            if key == 'train_mean_episode_reward':
                count = run['n_train']
                if not count:
                    continue
                values = [value/count for value in values]
            axis.plot([row[xkey] for row in rows], values, label=_label(run), color=COLORS[run['algorithm']],
                      linestyle='--' if run['kind'] == 'from_scratch' else '-', linewidth=1.8, marker='.', markersize=3)
            if baselines:
                parent = rows[-1].get('parent_objective_per_student')
                if parent is not None and run['kind'] != 'from_scratch':
                    axis.hlines(parent, rows[0][xkey], rows[-1][xkey], label=run['algorithm'].upper()+' frozen parent',
                                color=COLORS[run['algorithm']], linestyle=':', alpha=.75)
                for baseline in ('hungarian', 'greedy', 'random'):
                    value = rows[-1].get(baseline+'_objective_per_student')
                    if value is not None:
                        axis.hlines(value, rows[0][xkey], rows[-1][xkey], label=baseline.title(),
                                    color=COLORS[baseline], linestyle='-.', linewidth=1.15, alpha=.85)
        if not measured:
            axis.text(.5, .5, 'No completed measured fit\n(blocked / unavailable)', ha='center', va='center', transform=axis.transAxes, color='#66717c')
        if key == 'hungarian_regret_per_student':
            axis.axhline(0, color=COLORS['hungarian'], linewidth=.8)
    _finish(fig, output, name, title,
            'Measured validation checkpoints; no interpolation, smoothing, confidence interval or final-test evaluation. Missing fits stay blank.', metadata)


def _loss_data(run):
    training = run['report'].get('training', {})
    losses = training.get('losses', [])
    if losses and isinstance(losses[0], dict):
        rows = [(row.get('timesteps', row.get('cumulative_step')), row.get('loss')) for row in losses]
    elif losses:
        rows = list(zip(training.get('loss_steps', []), losses))
    else:
        rows = [(row['cumulative_step'], row.get('train_loss')) for row in run['curve']]
    rows = [(step, value) for step, value in rows if step is not None and value is not None]
    if len(rows) > 2000:
        rows = [rows[index] for index in np.unique(np.linspace(0, len(rows)-1, 2000).astype(int))]
    return rows


def _final_test_plot(root, output, metadata):
    """Read the one-time post-selection evaluation; never load or select a model."""
    path = Path(root) / 'final_test.json'
    if not path.exists():
        return
    result = _read(path)
    if result.get('status') != 'completed' or result.get('selection_changed') is not False:
        raise ValueError('final_test_selection_must_be_frozen')
    versions = sorted(result.get('baselines', {}), key=lambda value: int(value[1:]))
    if not versions:
        return
    selected = [row for terms in result.get('selected_frozen_models', {}).values() for row in terms.values()
                if row.get('objective_per_student') is not None]
    models = [row for row in result.get('models', []) if row.get('objective_per_student') is not None]
    fig, axes = plt.subplots(2, len(versions), figsize=(max(12, 6*len(versions)), 9), squeeze=False)
    kinds = ('selected_frozen', 'warm_candidate', 'from_scratch')
    aliases = {'selected_frozen': 'selected', 'warm_candidate': 'candidate', 'from_scratch': 'scratch'}
    hatches = {'selected_frozen': None, 'warm_candidate': '//', 'from_scratch': 'xx'}
    for column, version in enumerate(versions):
        baseline = result['baselines'][version]
        n_test = baseline['hungarian']['n_test']
        best = baseline['hungarian']['objective_per_student']
        rows = [row for row in [*selected, *models] if row['version'] == version]
        rows.sort(key=lambda row: (('ppo', 'dqn').index(row['algorithm']), kinds.index(row['kind'])))
        labels, values, gaps, colors, patterns = [], [], [], [], []
        for row in rows:
            score, gap = row['objective_per_student'], row['regret_per_student']
            if row['n_test'] != n_test or not math.isclose(best-score, gap, abs_tol=1e-10):
                raise ValueError('final_test_metric_context_mismatch')
            label = row['algorithm'].upper()+'\n'+aliases[row['kind']]
            if row['kind'] == 'selected_frozen' and row.get('selection', '').startswith('retained_'):
                label += '\n'+row['selection'].replace('_', ' ')
            labels.append(label)
            values.append(score)
            gaps.append(gap)
            colors.append(COLORS[row['algorithm']])
            patterns.append(hatches[row['kind']])
        for name in ('hungarian', 'greedy', 'random'):
            row = baseline[name]
            if row['n_test'] != n_test:
                raise ValueError('final_test_metric_context_mismatch')
            labels.append(name.title())
            values.append(row['objective_per_student'])
            gaps.append(best-row['objective_per_student'])
            colors.append(COLORS[name])
            patterns.append(None)
        for axis, measured, ylabel in zip(axes[:, column], (values, gaps),
                                         ('Final-test objective / student', 'Hungarian minus model / student')):
            bars = axis.bar(range(len(measured)), measured, color=colors, width=.76)
            for bar, pattern in zip(bars, patterns):
                if pattern:
                    bar.set_hatch(pattern)
                    bar.set_edgecolor('white')
            axis.set_xticks(range(len(labels)), labels, rotation=32, ha='right', fontsize=8)
            axis.set_ylabel(ylabel)
            axis.axhline(0, color='#697785', linewidth=.6)
        axes[0, column].set_title(f'{version}: held-out n={n_test}')
        axes[0, column].tick_params(labelbottom=False)
    fig.suptitle('Final test opened once after validation selection — one seed, small cohorts', fontsize=15, fontweight='bold')
    _finish(fig, output, 'final_test_comparison', 'One-time final-test comparison after frozen selection',
            'Selected/retained, final warm candidates and from-scratch controls were fixed before the final test was opened. '
            'Duplicate checkpoints can appear under different roles but reuse cached evaluation; bars are not independent samples. '
            'Final test is absent from training curves and model selection. One seed and small n; no confidence interval or academic-effectiveness claim.', metadata)


def generate_plots(root, output, reference=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    runs = load_runs(root)
    if not runs:
        raise ValueError('completed_training_reports_required')
    for version in {run['version'] for run in runs}:
        contexts = {json.dumps(run['input']['validation'], sort_keys=True) for run in runs if run['version'] == version}
        if len(contexts) != 1:
            raise ValueError('same_version_validation_context_mismatch')
    output.mkdir(parents=True, exist_ok=True)
    versions = _versions(root, runs)
    runs.sort(key=lambda run: (versions.index(run['version']), ('ppo', 'dqn').index(run['algorithm']), run['kind'] != 'sequential'))
    metadata = []
    _lines(runs, versions, output, metadata, key='validation_objective_per_student', name='validation_steps',
           title='Validation objective across training steps', ylabel='Objective / student', baselines=True)
    _lines(runs, versions, output, metadata, key='validation_objective_per_student', name='validation_cumulative_steps',
           title='Validation objective across inherited lineage steps', ylabel='Objective / student', cumulative=True, baselines=True)
    _lines(runs, versions, output, metadata, key='hungarian_regret_per_student', name='hungarian_regret',
           title='Gap to Hungarian on the same validation cohort', ylabel='Hungarian minus model / student')
    if any(row.get('train_mean_episode_reward') is not None for run in runs for row in run['curve']):
        _lines(runs, versions, output, metadata, key='train_mean_episode_reward', name='training_return',
               title='Training episode return per student — rolling last 100 completed episodes', ylabel='Rolling mean episode return / student')
        metadata[-1]['description'] = 'Mean of the latest 100 completed training episodes (all completed if fewer), normalized by train cohort size. Reward includes completion bonus and shaping; it is not the validation objective or a causal cross-cohort comparison.'
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))
    for axis, algorithm in zip(axes, ('ppo', 'dqn')):
        for run in runs:
            if run['algorithm'] != algorithm:
                continue
            rows = _loss_data(run)
            if rows:
                axis.plot([step-run['report']['steps_before'] for step, _ in rows], [value for _, value in rows],
                          linewidth=.8, alpha=.8, linestyle='--' if run['kind'] == 'from_scratch' else '-',
                          color=plt.get_cmap('tab10')(versions.index(run['version']) % 10),
                          label=run['version']+' '+_label(run))
        axis.set(title=algorithm.upper()+' loss (own scale)', xlabel='Steps added in this fit', ylabel='Logged training loss')
        axis.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x/1000:g}k'))
    fig.suptitle('Training loss — raw logged points, display sampled to at most 2,000 per fit', fontsize=13, fontweight='bold')
    _finish(fig, output, 'training_loss', 'Training loss by learner and fit',
            'Raw loss values with deterministic display subsampling for dense logs; no smoothing. PPO and DQN losses use separate axes and are not directly comparable.', metadata)
    fig, axes = _panels(versions, 'Final validation comparison on each semester cohort', 'Objective / student', '')
    for axis, version in zip(axes, versions):
        selected = [run for run in runs if run['version'] == version]
        labels, values, colors = [], [], []
        for run in selected:
            labels.append(_label(run)+'\n'+run['report']['decision'])
            values.append(run['report']['candidate_score'])
            colors.append(COLORS[run['algorithm']])
        if selected:
            baseline = selected[0]
            for name in ('hungarian', 'greedy', 'random'):
                labels.append(name.title())
                values.append(baseline['report']['baselines'][name]['metrics']['objective']/baseline['n_validation'])
                colors.append(COLORS[name])
            bars = axis.bar(range(len(values)), values, color=colors, width=.7)
            for bar, run in zip(bars, selected):
                if run['kind'] == 'from_scratch':
                    bar.set_hatch('//')
                    bar.set_edgecolor('white')
            axis.set_xticks(range(len(values)), labels, rotation=28, ha='right', fontsize=8)
            axis.xaxis.set_major_formatter(matplotlib.ticker.FixedFormatter(labels))
        else:
            axis.text(.5, .5, 'No completed fit', transform=axis.transAxes, ha='center')
    _finish(fig, output, 'final_comparison', 'Final validation comparison',
            'Candidate point estimates and classical baselines on the same cohort; accepted is a research gate, not superiority to Hungarian. No cross-semester raw-score ranking.', metadata)
    if any(run['report'].get('forgetting') for run in runs):
        fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
        shared_limit = max(.001, max(abs(row['signed_drop']) for run in runs
                          if run['kind'] == 'sequential' for row in run['report'].get('forgetting', {}).values()))
        for axis, algorithm in zip(axes, ('ppo', 'dqn')):
            selected = [run for run in runs if run['algorithm'] == algorithm and run['kind'] == 'sequential' and run['report'].get('forgetting')]
            old = sorted({key for run in selected for key in run['report']['forgetting']})
            if not selected or not old:
                axis.text(.5, .5, 'No measured inherited holdout', ha='center', transform=axis.transAxes)
                axis.set_axis_off()
                continue
            values = np.full((len(old), len(selected)), np.nan)
            for column, run in enumerate(selected):
                for row, term in enumerate(old):
                    if term in run['report']['forgetting']:
                        values[row, column] = run['report']['forgetting'][term]['signed_drop']
            img = axis.imshow(np.ma.masked_invalid(values), cmap='RdBu_r', vmin=-shared_limit, vmax=shared_limit, aspect='auto')
            for (row, column), value in np.ndenumerate(values):
                if np.isfinite(value):
                    axis.text(column, row, f'{value:+.4f}', ha='center', va='center', fontsize=10,
                              color='white' if abs(value) > .55*shared_limit else 'black')
            axis.set_xticks(range(len(selected)), [run['version'] for run in selected])
            axis.set_yticks(range(len(old)), old)
            axis.set(title=algorithm.upper()+' old-holdout change', xlabel='New training version', ylabel='Frozen historical cohort')
            axis.grid(False)
            fig.colorbar(img, ax=axis, label='Parent minus candidate / student')
        fig.suptitle('Forgetting: positive values mean the old goal became worse', fontsize=14, fontweight='bold')
        _finish(fig, output, 'forgetting_heatmap', 'Frozen historical holdout forgetting',
                'Signed objective drop on exact frozen prior validation cohorts. Red positive is degradation; blue negative is improvement. Missing observations remain masked.', metadata)
    labels = [run['version']+' '+_label(run) for run in runs]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    wall = [run['curve'][-1].get('elapsed_seconds', np.nan) if run['curve'] else np.nan for run in runs]
    coverage = [run['report']['candidate']['metrics']['coverage']*100 for run in runs]
    violations = [run['report']['candidate']['metrics']['constraint_violations'] for run in runs]
    for axis, values, title, ylabel in zip(axes, (wall, coverage, violations),
            ('Measured elapsed time', 'Validation allocation coverage', 'Validation constraint violations'), ('Seconds', 'Percent', 'Count')):
        axis.bar(range(len(runs)), values, color=[COLORS[run['algorithm']] for run in runs])
        axis.set_xticks(range(len(runs)), labels, rotation=45, ha='right', fontsize=7)
        axis.set(title=title, ylabel=ylabel)
        if ylabel == 'Count':
            axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        if ylabel == 'Percent':
            axis.set_ylim(0, 105)
    _finish(fig, output, 'runtime_constraints', 'Runtime and feasibility',
            'Elapsed time is measured wall time from the run; coverage and constraint counts are final validation quantities, not academic quality.', metadata)
    if reference:
        reference_runs = {(run['algorithm'], run['version']): run for run in load_runs(reference) if run['kind'] == 'sequential'}
        pairs = [(run, reference_runs[(run['algorithm'], run['version'])]) for run in runs
                 if (run['kind'] == 'sequential' and (run['algorithm'], run['version']) in reference_runs
                     and run['input']['validation'] == reference_runs[(run['algorithm'], run['version'])]['input']['validation'])]
        if pairs:
            fig, axis = plt.subplots(figsize=(max(8, len(pairs)*1.6), 4.7))
            x = np.arange(len(pairs))
            axis.bar(x-.18, [old['report']['candidate_score'] for _, old in pairs], .36, label='Earlier smoke budget', color='#a5b3c0')
            axis.bar(x+.18, [new['report']['candidate_score'] for new, _ in pairs], .36, label='Current long budget', color='#1767a6')
            axis.set_xticks(x, [new['version']+' '+new['algorithm'].upper() for new, _ in pairs])
            axis.set(ylabel='Validation objective / student', title='Earlier smoke versus longer training: point estimates')
            _finish(fig, output, 'smoke_vs_long', 'Smoke and long-budget validation results',
                    'Budget comparison also changes inherited parent trajectory; it is not an isolated causal effect of extra steps. One seed, no confidence interval.', metadata)
    _final_test_plot(root, output, metadata)
    (output / 'plot_index.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    args = parser.parse_args()
    print(json.dumps(generate_plots(args.run, args.output, reference=args.reference), ensure_ascii=False, indent=2))
