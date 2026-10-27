"""Fresh-source, explicitly retrospective text baseline for nested RL research.

Final thesis titles are document proxies, not verified pre-allocation forms.
Nothing here approves academic data, invents feedback, or promotes serving models.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src.data_pipeline.review_decisions import record_hash
from src.data_pipeline.semester_versions import SEMESTER_BY_VERSION
from src.domain.rebuild_matching import AllocationProblem, equal_quotas, feasible
from src.environment.rebuild_env import MatchingEnv
from src.evaluation.rebuild_benchmark import problem_payload, evaluate_problem
from src.features.rebuild_features import preprocess_text


END = {'V1': '2024-12-31', 'V2': '2025-06-30', 'V3': '2025-12-31', 'V4': '2026-06-30'}
MODE = 'retrospective_document_proxy'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def write_jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


def verify_source(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if not manifest.get('artifacts'):
        raise ValueError('source_manifest_required')
    for name, sha in manifest['artifacts'].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder) or not path.is_file() or digest(path) != sha:
            raise ValueError('source_artifact_hash_mismatch')
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and p != folder / 'manifest.json'}
    if actual != set(manifest['artifacts']):
        raise ValueError('source_artifact_inventory_mismatch')
    if manifest.get('source_collection'):
        source = Path(manifest['source_collection']).resolve()
        if source.parent != folder.parent or source == folder:
            raise ValueError('derivative_source_must_be_fresh_sibling')
        if verify_source(source) != manifest['source_collection_manifest_sha256']:
            raise ValueError('derivative_source_binding_mismatch')
    return digest(folder / 'manifest.json')


def select_publications(rows, version):
    """Use only dates whose entire precision interval ends before cutoff."""
    end = END[version]
    used, withheld = [], []
    for row in rows:
        year = row.get('publication_year')
        value, precision = row.get('publication_date'), row.get('date_precision')
        status = row.get('date_status')
        valid = False
        if status not in ('ambiguous', 'invalid'):
            if value and precision in ('day', 'month'):
                try:
                    if precision == 'day':
                        parsed = date.fromisoformat(value)
                    else:
                        if len(value) != 7:
                            raise ValueError('month_precision_required')
                        year_value, month = map(int, value.split('-'))
                        parsed = date(year_value, month, monthrange(year_value, month)[1])
                    valid = parsed.isoformat() <= end and (year is None or year == parsed.year)
                except (ValueError, TypeError):
                    valid = False
            elif isinstance(year, int) and not isinstance(year, bool):
                valid = year < int(end[:4]) or (year == int(end[:4]) and end.endswith('12-31'))
        (used if valid else withheld).append(row)
    return used, withheld


def fit_encoder(texts):
    vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), max_features=10000,
                                 lowercase=True, norm='l2', dtype=np.float64)
    vectorizer.fit(texts)
    return vectorizer, {'schema_version': 'fresh-char-tfidf/1.0', 'analyzer': 'char_wb',
                        'ngram_range': [3, 5], 'vocabulary': {key: int(value) for key, value in vectorizer.vocabulary_.items()},
                        'idf': vectorizer.idf_.tolist(), 'fit_scope': 'bootstrap_train_only'}


def restore_encoder(frozen):
    if frozen.get('schema_version') != 'fresh-char-tfidf/1.0':
        raise ValueError('unsupported_frozen_encoder')
    vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5),
                                 vocabulary=frozen['vocabulary'], lowercase=True, norm='l2', dtype=np.float64)
    vectorizer.idf_ = np.asarray(frozen['idf'], dtype=np.float64)
    return vectorizer


def _value(row, field):
    return str(row.get('fields', {}).get(field, {}).get('value') or '').strip()


def student_split(student_id, seed):
    """Keep identities in the same holdout across every semester."""
    bucket = int(hashlib.sha256(f'{seed}:{student_id}'.encode()).hexdigest()[:8], 16) % 100
    return 'validation' if bucket < 15 else ('test' if bucket < 30 else 'train')


def seal_suite(output):
    output = Path(output)
    artifacts = {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob('*'))
                 if p.is_file() and p != output / 'manifest.json'}
    write_json(output / 'manifest.json', {'schema_version': 'fresh-suite/1.0', 'artifacts': artifacts,
               'builder_sha256': digest(Path(__file__)), 'scope': MODE})


def event_upper_bound(temporal):
    """Return an evidence interval end, never a claimed exact publication day."""
    value = temporal.get('event_interval_upper_bound') or temporal.get('event_date') or temporal.get('publication_date')
    if value:
        parts = str(value)[:10].split('-')
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 12
        day = int(parts[2]) if len(parts) > 2 else monthrange(year, month)[1]
    else:
        year = temporal.get('event_year') or temporal.get('publication_year')
        month = temporal.get('event_month') or temporal.get('publication_month') or 12
        if not isinstance(year, int):
            raise ValueError('source_event_interval_required')
        day = monthrange(year, month)[1]
    return f'{year:04d}-{month:02d}-{day:02d}T23:59:59+07:00'


def prepare_suite(root, output, *, version, mode, seed=42, frozen_encoder=None, student_collection=None):
    if mode != MODE:
        raise ValueError('explicit_retrospective_proxy_mode_required')
    if version not in END:
        raise ValueError('unknown_version')
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError('new_suite_output_required')
    if not (root.parent.name == 'nested_rl_20261028' and root.parent.parent.name == 'data_rebuild'):
        raise ValueError('fresh_namespace_required')
    if not output.is_relative_to(root):
        raise ValueError('suite_must_stay_in_fresh_run')
    student_folder = Path(student_collection).resolve() if student_collection else root / ('students_dates' if (root / 'students_dates/manifest.json').exists() else 'students')
    if student_folder.parent != root:
        raise ValueError('student_collection_must_be_fresh_run_child')
    sources = [root / name for name in ('students', 'students_dates', 'students_reviewed', 'faculty', 'faculty_dates', 'faculty_external')]
    if any(output.is_relative_to(folder) for folder in [student_folder, *sources]):
        raise ValueError('immutable_source_output_forbidden')
    student_sha = verify_source(student_folder)
    faculty_sha = verify_source(root / 'faculty')
    publication_folder = root / ('faculty_dates' if (root / 'faculty_dates/manifest.json').exists() else 'faculty')
    publication_sha = verify_source(publication_folder)
    students = read_jsonl(student_folder / 'students.jsonl')
    advisors = sorted(read_jsonl(root / 'faculty/faculty.jsonl'), key=lambda row: row['advisor_id'])
    publications = read_jsonl(publication_folder / 'publications.jsonl')
    used, withheld = select_publications(publications, version)
    by_id, quarantine = {}, []
    for row in students:
        if row.get('temporal', {}).get('version') != version or not _value(row, 'thesis_title') or row.get('provenance_validation') != 'passed':
            continue
        sid = _value(row, 'student_id')
        if not sid:
            quarantine.append({'candidate_id': row.get('candidate_id'), 'reason': 'missing_student_id'})
            continue
        if sid in by_id and (by_id[sid]['source_sha256'] != row['source_sha256']
                             or _value(by_id[sid], 'thesis_title') != _value(row, 'thesis_title')):
            quarantine.append({'student_id': sid, 'reason': 'multiple_source_identity_requires_review'})
        else:
            by_id[sid] = row
    for item in quarantine:
        by_id.pop(item.get('student_id'), None)
    chosen = sorted(by_id.items())
    output.mkdir(parents=True)
    write_jsonl(output / 'publications_used.jsonl', used)
    write_jsonl(output / 'publications_withheld.jsonl', withheld)
    write_jsonl(output / 'identity_review.jsonl', quarantine)
    report = {'schema_version': 'fresh-suite/1.0', 'version': version, 'semester_id': SEMESTER_BY_VERSION[version],
              'scope': mode, 'student_collection': student_folder.name, 'student_candidates': len(chosen), 'faculty_registry': len(advisors),
              'publications_used': len(used), 'publications_withheld': len(withheld),
              'student_temporal_counts': dict(Counter(row.get('temporal', {}).get('version') or row.get('temporal', {}).get('status') for row in students)),
              'prediction_time_verified': False, 'operational_allocation_authorized': False,
              'limitations': ['Final-thesis title is a retrospective document proxy, not a verified initial form.',
                             'Publication event-time eligibility assumes retrospective availability, not point-in-time evidence.',
                             'Equal quotas and universal eligibility are research simulation, not confirmed semester policy.',
                             'Human preferences, acceptance feedback and grades remain unknown.',
                             'No academic accuracy, model convergence or production promotion is inferred.']}
    if len(chosen) < 6 or not advisors or not used:
        report.update(status='blocked_data_insufficient', reason='At least six distinct dated title candidates and dated faculty text required for research split.')
        write_json(output / 'readiness.json', report)
        seal_suite(output)
        return report
    split = {name: [i for i, (sid, _) in enumerate(chosen) if student_split(sid, seed) == name]
             for name in ('train', 'validation', 'test')}
    if any(not indices for indices in split.values()):
        report.update(status='blocked_identity_holdout_coverage', reason='Stable identity split has an empty cohort; do not move identities between holdouts.')
        write_json(output / 'readiness.json', report)
        seal_suite(output)
        return report
    identities = [name for _, row in chosen for name in (_value(row, 'student_name'), _value(row, 'student_id')) if name]
    identities += [row.get('advisor_name') or '' for row in advisors]
    identities = sorted(set(identities) - {''})
    texts = [preprocess_text(_value(row, 'thesis_title'), identities)[0] for _, row in chosen]
    if frozen_encoder:
        encoder_path = Path(frozen_encoder).resolve()
        if not encoder_path.is_relative_to(root) or encoder_path.name != 'encoder.json':
            raise ValueError('fresh_bootstrap_encoder_required')
        verify_source(encoder_path.parent)
        encoder_report = json.loads((encoder_path.parent / 'readiness.json').read_text(encoding='utf-8'))
        frozen = json.loads(encoder_path.read_text(encoding='utf-8'))
        if (encoder_report.get('version') != 'V1' or encoder_report.get('status') != 'ready_research_only'
                or frozen.get('fit_scope') != 'bootstrap_train_only' or not frozen.get('fit_student_ids')
                or record_hash(frozen) != encoder_report.get('encoder_sha256')):
            raise ValueError('verified_bootstrap_encoder_required')
        vectorizer = restore_encoder(frozen)
    elif version == 'V1':
        vectorizer, frozen = fit_encoder([texts[i] for i in split['train']])
        frozen['fit_student_ids'] = [chosen[i][0] for i in split['train']]
    else:
        raise ValueError('bootstrap_frozen_encoder_required_for_later_versions')
    write_json(output / 'encoder.json', frozen)
    advisor_texts = defaultdict(list)
    for row in used:
        advisor_texts[row['advisor_id']].append(row.get('title_text') or row.get('text') or '')
    registry = tuple(row['advisor_id'] for row in advisors)
    right = vectorizer.transform([preprocess_text('\n'.join(advisor_texts[aid]), identities)[0] for aid in registry])
    left = vectorizer.transform(texts)
    present = np.asarray(right.getnnz(axis=1) > 0, dtype=bool)
    known = np.outer(left.getnnz(axis=1) > 0, present)
    scores = np.clip((left @ right.T).toarray(), 0, 1)
    if not present.any() or not known.any(axis=1).all():
        report.update(status='blocked_feature_coverage', reason='Some text proxies have no observable frozen-encoder features.')
        write_json(output / 'readiness.json', report)
        seal_suite(output)
        return report
    feature_sha = record_hash(frozen)
    taxonomy_sha = record_hash({'schema': 'text-only-no-personal-skill-vector/1.0', 'dimension': 0})
    selected = [aid for aid, active in zip(registry, present) if active]
    problems = {}
    for name, indices in split.items():
        ids = tuple(chosen[i][0] for i in indices)
        problems[name] = AllocationProblem(scores=scores[indices], available=known[indices], student_ids=ids,
            advisor_ids=registry, capacities=equal_quotas(len(ids), registry, selected),
            eligible=np.ones((len(ids), len(registry)), dtype=bool), present=present,
            metadata={'split': name, 'scope': mode, 'semester_id': SEMESTER_BY_VERSION[version],
                      'feature_contract_sha256': feature_sha, 'taxonomy_feature_order_sha256': taxonomy_sha,
                      'policy_version': 'research-equal-quota/1.0'})
        if not feasible(problems[name]):
            raise ValueError('research_split_infeasible')
    env = MatchingEnv([problems['train']])
    contract = {'scope': mode, 'state_contract': env.state_contract, 'feature_contract_sha256': feature_sha,
                'taxonomy_feature_order_sha256': taxonomy_sha, 'quota_policy_version': 'research-equal-quota/1.0',
                'reward_weights': env.reward_weights, 'training_student_ids': list(problems['train'].student_ids),
                'training_semester_ids': [SEMESTER_BY_VERSION[version]], 'dataset_snapshot_sha256': student_sha}
    signal_id = 'initial-source-' + record_hash({'student': student_sha, 'faculty': faculty_sha, 'publications': publication_sha, 'version': version})[:20]
    train_payload = [problem_payload(problems['train'])]
    val_payload = problem_payload(problems['validation'])
    source_upper = max([event_upper_bound(row['temporal']) for _, row in chosen] +
                       [event_upper_bound(row) for row in used])
    snapshot = {'scope': mode, 'version': version, 'signal_ids': [signal_id],
                'initial_source_event_upper_bound': source_upper,
                'training_problem_sha256': [record_hash(p) for p in train_payload],
                'validation_problem_sha256': record_hash(val_payload),
                'student_manifest_sha256': student_sha, 'faculty_manifest_sha256': faculty_sha,
                'publication_manifest_sha256': publication_sha, 'prediction_time_verified': False}
    write_json(output / 'snapshot.json', snapshot)
    captured = max([str(row.get('captured_at') or '') for _, row in chosen] +
                   [str(row.get('retrieved_at') or '') for row in used]) or datetime.now(timezone.utc).isoformat()
    round_spec = {'semester_id': SEMESTER_BY_VERSION[version], 'round_id': version + '-r1', 'round_index': 1,
        'algorithm': 'ppo', 'seed': seed, 'snapshot_path': str((output / 'snapshot.json').resolve()),
        'snapshot_sha256': digest(output / 'snapshot.json'), 'cutoff_timestamp': END[version] + 'T23:59:59+07:00',
        'reward_version': 'native-score-preference-fairness/1.0', 'constraint_version': 'research-equal-quota/1.0',
        'signal_state_sha256': record_hash([signal_id]), 'availability_assumption': 'retrospective_event_time_proxy',
        'signals': [{'signal_id': signal_id, 'type': 'initial_source', 'source_path': str((output / 'snapshot.json').resolve()),
                     'source_sha256': digest(output / 'snapshot.json'), 'available_at': captured,
                     'event_upper_bound': source_upper, 'event_date_status': 'retrospective_interval_upper_bound',
                     'review_status': 'source_verified'}],
        'decision_thresholds': {'min_improvement': 0., 'max_new_drop': 0., 'max_old_drop': 0.,
                                'accept_non_regression': False}}
    suite = {'schema_version': 'fresh-nested-suite/1.0', 'scope': mode, 'train': train_payload,
             'validation': val_payload, 'test': problem_payload(problems['test']), 'contract': contract, 'round': round_spec}
    write_json(output / 'suite.json', suite)
    baseline = {name: {algorithm: {k: v for k, v in evaluate_problem(problem, algorithm, seed=seed).items() if k not in ('trace', 'assignments')}
                      for algorithm in ('hungarian', 'greedy', 'random')} for name, problem in problems.items() if name != 'test'}
    write_json(output / 'baselines.json', baseline)
    report.update(status='ready_research_only', train=len(split['train']), validation=len(split['validation']), test=len(split['test']),
                  split_policy='sha256-student-identity/1.0',
                  selected_research_advisors=len(selected), state_dimension=env.observation_space.shape[0],
                  encoder_sha256=feature_sha, test_evaluated=False)
    write_json(output / 'readiness.json', report)
    seal_suite(output)
    return report
