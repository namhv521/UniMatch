"""Prepare the requested 215-record snapshot; evaluate or train all real algorithms."""
import argparse
import csv
import hashlib
import importlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation.benchmark import evaluate_baselines, evaluate_checkpoint, load_split
from src.evaluation.promotion import DEFAULT_SEEDS

ALGORITHMS = {'DQN': ('dqn', 'train_dqn'), 'MaskablePPO': ('ppo', 'train_maskable_ppo'),
              'QRDQN': ('qrdqn', 'train_qrdqn'), 'TRPO': ('trpo', 'train_trpo'),
              'ARS': ('ars', 'train_ars'), 'RecurrentPPO': ('recurrent_ppo', 'train_recurrent_ppo')}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def ordered(values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def prepare(root=ROOT, failures=None):
    failures = failures or root / 'outputs/data_quality/v2026-09-28/failure_report.json'
    report_path = root / 'data/excluded/requested-five/manifest.json'
    if report_path.exists():
        verify_transfer(root, root / 'outputs/snapshot-220-before-exclusion')
        return read(report_path)
    load_split(root)
    curated, features = root / 'data/curated', root / 'data/features'
    rows, advisors = read(curated / 'theses.json'), read(curated / 'advisors.json')
    sources = {f['source'].split('-')[0] for f in read(failures)}
    excluded = [r for r in rows if r['source_sha256'] in sources]
    if len(rows) != 220 or len(excluded) != 5 or len(sources) != 5:
        raise ValueError('expected original 220 records and exactly five matching sources')
    archive = root / 'outputs/snapshot-220-before-exclusion'
    if archive.exists():
        raise ValueError('archive already exists without completion manifest; inspect before retry')
    for name in ('curated', 'features'):
        shutil.copytree(root / 'data' / name, archive / 'data' / name)
    target = report_path.parent
    write(target / 'theses.json', excluded)
    write(target / 'failure_report_original.json', read(failures))
    # Keep original PDFs/evidence intact; move only the five raw LLM artifacts.
    moves = []
    for failure in read(failures):
        source = root / 'data/extracted/llm' / failure['source']
        if source.is_file():
            dest = target / 'llm' / source.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            moves.append({'from':source.relative_to(root).as_posix(), 'to':dest.relative_to(root).as_posix(), 'sha256':sha(source)})
            shutil.move(str(source), str(dest))
    keep = [i for i, row in enumerate(rows) if row['source_sha256'] not in sources]
    retained = [rows[i] for i in keep]
    excluded_ids = {r['student_id'] for r in excluded}
    write(curated / 'theses.json', retained)
    csv_path = curated / 'theses.csv'
    if csv_path.exists():
        with csv_path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream); fields = reader.fieldnames; csv_rows = list(reader)
        with csv_path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
            writer.writerows(r for r in csv_rows if r['student_id'] not in excluded_ids)
    source_rows = curated / 'thesis_source_records.jsonl'
    if source_rows.exists():
        original = source_rows.read_text(encoding='utf-8').splitlines()
        source_rows.write_text(''.join(line+'\n' for line in original if json.loads(line).get('source_sha256') not in sources), encoding='utf-8')
    split = read(curated / 'split_indices.json')
    mapping = {old:new for new, old in enumerate(keep)}
    split['indices'] = {name:[mapping[i] for i in ids if i in mapping] for name, ids in split['indices'].items()}
    split['student_ids'] = {name:[retained[i]['student_id'] for i in ids] for name, ids in split['indices'].items()}
    split.pop('legacy_indices', None)
    split['dataset_sha256'] = canonical(retained)
    write(curated / 'split_indices.json', split)
    matrix = np.load(features / 'compatibility_matrix_v2.npy', allow_pickle=False)[keep]
    np.save(features / 'compatibility_matrix_v2.npy', matrix, allow_pickle=False)
    feature = read(features / 'feature_manifest_v2.json')
    feature.update(matrix_shape=list(matrix.shape), matrix_sha256=hashlib.sha256(matrix.tobytes()).hexdigest(),
                   dataset_sha256=canonical(retained), split_sha256=sha(curated / 'split_indices.json'),
                   preprocessing_scope='frozen original train corpus; excluded train documents were used in original fit',
                   parent_feature_sha256=read(archive / 'data/features/feature_manifest_v2.json')['matrix_sha256'])
    write(features / 'feature_manifest_v2.json', feature)
    contract = {'matrix_sha256':feature['matrix_sha256'], 'dataset_sha256':feature['dataset_sha256'],
                'split_sha256':feature['split_sha256'], 'student_order_sha256':ordered([r['student_id'] for r in retained]),
                'advisor_order_sha256':ordered([r['advisor_id'] for r in advisors]),
                'split_counts':{name:len(ids) for name, ids in split['indices'].items()}}
    write(curated / 'serving_contract.json', contract)
    inputs = {p.relative_to(root).as_posix():sha(p) for p in [curated/'theses.json', curated/'advisors.json', curated/'split_indices.json', features/'feature_manifest_v2.json', features/'compatibility_matrix_v2.npy', curated/'serving_contract.json']}
    load_split(root)
    write(curated / 'quality_report_v2.json', {'ready':True, 'research_ready':True, 'operational_ready':False,
          'scope':'filtered snapshot integrity for research; experimental quotas; not semantic completeness or model promotion',
          'generated_at':datetime.now(timezone.utc).isoformat(), 'input_files':inputs,
          'counts':{'theses':len(retained), 'advisors':len(advisors)}, 'capacity_policy':'uniform-ceiling-experimental-v1',
          'warnings':['six advisor profiles have no serving text', 'official quota unavailable', 'five excluded by user request, including corrected records', feature['preprocessing_scope']]})
    write(curated / 'curation_report.json', {'curated_students':len(retained), 'excluded_documents':5,
          'scope':'user-requested filtering; original report retained in archive', 'ready_for_full_experiment':False})
    report = {'retained':len(retained), 'excluded':5, 'excluded_sources':sorted(sources), 'moves':moves,
              'archive':archive.relative_to(root).as_posix(), 'split_counts':contract['split_counts']}
    write(report_path, report)
    verify_transfer(root, archive)
    return report


def verify_transfer(root, archive):
    _, _, original = load_split(archive)
    load_split(root)
    old, new = read(archive/'data/curated/theses.json'), read(root/'data/curated/theses.json')
    excluded = set(read(root/'data/excluded/requested-five/manifest.json')['excluded_sources'])
    indices = [i for i, row in enumerate(old) if row['source_sha256'] not in excluded]
    if len(excluded) != 5 or new != [old[i] for i in indices]:
        raise ValueError('transfer requires exactly the requested subset, unchanged records')
    if sha(root/'data/curated/advisors.json') != sha(archive/'data/curated/advisors.json'):
        raise ValueError('advisor mapping/content changed')
    if not np.array_equal(np.load(root/'data/features/compatibility_matrix_v2.npy'), np.load(archive/'data/features/compatibility_matrix_v2.npy')[indices]):
        raise ValueError('transfer scores/preprocessing changed')
    old_split, new_split = read(archive/'data/curated/split_indices.json'), read(root/'data/curated/split_indices.json')
    ids = {r['student_id'] for r in new}
    for name, values in old_split['student_ids'].items():
        if new_split['student_ids'][name] != [i for i in values if i in ids]:
            raise ValueError('split reassignment could leak original training data')
    return original


def evaluate(root=ROOT):
    import torch
    torch.set_num_threads(1)
    scores, capacities, provenance = load_split(root)
    original = verify_transfer(root, root/'outputs/snapshot-220-before-exclusion')
    rows = evaluate_baselines(scores, capacities, DEFAULT_SEEDS)
    for row in rows:
        row['evaluation_scope'] = 'baseline'
    rejected = []
    for directory in ('research-real', 'research-filtered', 'training-smoke'):
        for path in sorted((root/'outputs'/directory).glob('*.json')):
            try:
                manifest = read(path)
                transfer = directory == 'research-real'
                row = evaluate_checkpoint(root, path, scores, capacities, provenance,
                                          training_provenance=original if transfer else None)
                row['evaluation_scope'] = 'filtered-subset-transfer' if transfer else 'filtered-native'
                row['training_provenance'] = {k:manifest.get(k) for k in ('dataset_hash','feature_hash','split_hash')}
                rows.append(row)
            except (ValueError, KeyError, FileNotFoundError) as exc:
                rejected.append({'manifest':path.relative_to(root).as_posix(), 'reason':str(exc)})
    summary = []
    groups = sorted({(r['algorithm'], r['evaluation_scope'], r.get('target_timesteps', 0)) for r in rows})
    for algorithm, scope, budget in groups:
        values = [r for r in rows if (r['algorithm'], r['evaluation_scope'], r.get('target_timesteps', 0)) == (algorithm, scope, budget)]
        summary.append({'algorithm':algorithm, 'scope':scope, 'target_timesteps':budget, 'runs':len(values), 'metrics':{
            key:{'mean':float(np.mean([r['metrics'][key] for r in values])), 'std':float(np.std([r['metrics'][key] for r in values]))}
            for key in ('mean_compatibility','load_variance','quota_violations','invalid_proposals','fallback_count')}})
    report = {'scope':'filtered-validation; frozen preprocessing; transfer and native runs are distinguished',
              'students':len(scores), 'advisors':len(capacities), 'provenance':provenance,
              'rows':rows, 'summary':summary, 'rejected_checkpoints':rejected, 'promoted':False,
              'limitations':['old real policies trained on 220-record snapshot', 'toy smoke is not real-data evidence',
                             'excluded training texts remain in frozen vocabulary', 'test holdout not evaluated']}
    write(root/'outputs/benchmarks/filtered-validation.json', report)
    print(json.dumps({'rows':len(rows),'rejected':len(rejected),'summary':summary}))
    return report


def train(args):
    import torch
    torch.set_num_threads(1)
    from src.rl.training import TrainingConfig, build_environment, run_manifest
    from src.rl.checkpoints import save_checkpoint, validate_resume_manifest, verified_checkpoint
    verify_transfer(ROOT, ROOT/'outputs/snapshot-220-before-exclusion')
    for algorithm in args.algorithms:
        module, function = ALGORITHMS[algorithm]
        trainer = getattr(importlib.import_module('src.rl.'+module), function)
        for seed in args.seeds:
            output = ROOT/'outputs/research-filtered'
            stem = output/f'{algorithm.lower()}-seed{seed}-steps{args.timesteps}'
            config = TrainingConfig(algorithm, args.timesteps, seed, output)
            if stem.with_suffix('.json').exists():
                manifest = read(stem.with_suffix('.json'))
                validate_resume_manifest(manifest, config)
                verified_checkpoint(stem.with_suffix('.json'), manifest)
                continue
            print(f'Training {algorithm} seed={seed} steps={args.timesteps}', flush=True)
            env = build_environment(config)
            model = trainer(env, total_timesteps=args.timesteps, seed=seed)
            metadata = run_manifest(config, completed_timesteps=int(model.num_timesteps), status='completed')
            save_checkpoint(model, stem, algorithm=algorithm, seed=seed, run_manifest=metadata)
            env.close()
            evaluate()
    evaluate()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','evaluate','train'])
    parser.add_argument('--timesteps', type=int, default=2_000_000)
    parser.add_argument('--seeds', nargs='+', type=int, default=DEFAULT_SEEDS)
    parser.add_argument('--algorithms', nargs='+', choices=list(ALGORITHMS), default=list(ALGORITHMS))
    args = parser.parse_args()
    if args.action == 'prepare': print(json.dumps(prepare()))
    elif args.action == 'evaluate': evaluate()
    else: train(args)
