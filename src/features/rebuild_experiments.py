"""Immutable Phase 4 experiments, with validation review and an untouched test split."""
import csv
import hashlib
import json
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.data_pipeline.normalization import load_taxonomy, normalize_mentions
from src.data_pipeline.reconcile import ROOT, _digest, _read_bound_phase
from src.data_pipeline.review_decisions import record_hash
from src.evaluation.rebuild_diagnostics import diagnostic_hungarian, rank_matrix, summarize_matrix
from src.evaluation.rebuild_ranking import calibrate_e4, ranking_metrics, validate_pair_labels
from src.evaluation.rebuild_review import map_advisory_labels
from .rebuild_features import TECH_COLUMNS, FeaturePipeline, preprocess_text
from .rebuild_splits import make_grouped_split


VARIANTS = ('E0', 'E1', 'E2', 'E3', 'E4')


def _json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def _load_snapshot(output):
    gate, student_path = _read_bound_phase(output, 3, 'gold/students.csv')
    advisor_gate, advisor_path = _read_bound_phase(output, 3, 'gold/advisors.csv')
    if gate != advisor_gate:
        raise ValueError('mixed_phase3_snapshots')
    run = student_path.parents[1]
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    for artifact in manifest['artifacts']:
        if _digest(run / artifact['path']) != artifact['sha256']:
            raise ValueError('phase3_artifact_hash_mismatch')
    snapshot_path = run / 'gold/snapshot_manifest.json'
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    if snapshot.get('status') != 'approved' or snapshot.get('gate') != gate:
        raise ValueError('phase3_snapshot_not_approved')
    for name, sha in snapshot['inputs']['config_files'].items():
        if _digest(ROOT / 'configs/data' / name) != sha:
            raise ValueError('approved_feature_config_hash_mismatch')
    def read(path, key):
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        if (not rows or any(r['review_status'] != 'approved' for r in rows)
                or len({r[key] for r in rows}) != len(rows)):
            raise ValueError('invalid_gold_identity_or_review')
        return sorted(rows, key=lambda row: row[key])
    students, advisors = read(student_path, 'student_id'), read(advisor_path, 'advisor_id')
    records = _jsonl(run / 'silver/review_records.jsonl')
    aliases = {r['fields']['student_id']['value']: r.get('source_aliases', []) for r in records
               if r.get('entity_type') == 'students' and 'student_id' in r['fields']}
    for row in students:
        row['source_aliases'] = aliases.get(row['student_id'], [])
    profiles = {r['advisor_id']: r for r in records if r.get('entity_type') == 'advisors'}
    for row in advisors:
        profile = profiles.get(row['advisor_id'], {})
        # Attribution context for the reviewer packet only; the transformer
        # consumes the approved research_description field, never these extras.
        row['reviewed_research_topics'] = profile.get('research_topics', [])
        row['reviewed_teaching_topics'] = profile.get('teaching_topics', [])
    return students, advisors, {'run_id': gate['run_id'], 'snapshot_sha256': _digest(snapshot_path),
            'manifest_sha256': _digest(run / 'manifest.json'), 'students_sha256': _digest(student_path),
            'advisors_sha256': _digest(advisor_path), 'config_sha256': snapshot['inputs']['config_files']}


def _weight_grid():
    # Policy frozen before judgments: E4 keeps a text backbone; tag-only ablations
    # remain E2/E3 and cannot quietly drop most missing-tag validation students.
    return [{'E1': a/4, 'E2': b/4, 'E3': (4-a-b)/4}
            for a in range(1, 5) for b in range(5-a)]


def _hybrid(result, weights):
    numerator = np.zeros_like(result['scores']['E1'])
    denominator = np.zeros_like(numerator)
    for name, weight in weights.items():
        effective = weight * result['available'][name]
        numerator += effective * result['scores'][name]
        denominator += effective
    scores = np.zeros_like(numerator)
    available = denominator > 0
    np.divide(numerator, denominator, out=scores, where=available)
    return scores, available


def _packet(run, students, advisors, result, snapshot, splits, identities):
    student_ids, advisor_ids = [r['student_id'] for r in students], [r['advisor_id'] for r in advisors]
    candidates = {key: set() for key in student_ids}
    for variant in VARIANTS:
        for key, values in rank_matrix(result['scores'][variant], result['available'][variant], student_ids, advisor_ids).items():
            candidates[key].update(values[:5])
    for weights in _weight_grid():
        scores, available = _hybrid(result, weights)
        for key, values in rank_matrix(scores, available, student_ids, advisor_ids).items():
            candidates[key].update(values[:5])
    advisor_index = {r['advisor_id']: r for r in advisors}
    pairs, review_rows = {}, []
    for student in students:
        key = student['student_id']
        for advisor_id in sorted(candidates[key]):
            advisor = advisor_index[advisor_id]
            binding = {'student_id': key, 'advisor_id': advisor_id,
                       'student_record_sha256': record_hash(student), 'advisor_record_sha256': record_hash(advisor),
                       'snapshot_sha256': snapshot['snapshot_sha256']}
            pair_id = record_hash(binding)
            pairs[pair_id] = binding
            review_rows.append({'pair_id': pair_id,
                'student_title': preprocess_text(student['thesis_title'], identities)[0],
                'student_abstract': preprocess_text(student.get('thesis_abstract'), identities)[0],
                'advisor_profile': preprocess_text(advisor.get('research_description'), identities)[0],
                'advisor_profile_sections': {name: [preprocess_text(value, identities)[0] for value in advisor.get(field, [])]
                    for name, field in [('research', 'reviewed_research_topics'), ('teaching', 'reviewed_teaching_topics')]},
                'student_source_sha256': student['source_sha256'], 'advisor_source_sha256': advisor['source_sha256'],
                'advisor_source_url': advisor['source_url'],
                'scope': 'Reviewed teaching/research profile and thesis topic; no mastery or supervision/outcome claim.'})
    review_rows.sort(key=lambda r: r['pair_id'])
    (run / 'review/blinded_pairs.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in review_rows), encoding='utf-8')
    _json(run / 'review/pair_bindings.json', pairs)
    packet = {'snapshot': snapshot, 'student_ids': student_ids, 'pair_count': len(pairs),
              'split': 'validation', 'scores_exposed_to_reviewer': False,
              'student_splits': {key: splits['assignments'][key] for key in student_ids},
              'blinded_pairs_sha256': _digest(run / 'review/blinded_pairs.jsonl'),
              'pair_bindings_sha256': _digest(run / 'review/pair_bindings.json'),
              'candidate_policy': 'Union top5 E0-E4 and all 10 predeclared E4 grid candidates; unknown signals masked.',
              'rubric': {'3': 'Direct specific topic/method relevance evidenced in profile',
                         '2': 'Clear domain or method relevance', '1': 'Broad or general teaching relevance',
                         '0': 'Evidence supports a different topic; not absence of profile information',
                         'uncertain': 'Insufficient/ambiguous evidence; never treated as grade zero'},
              'label_authority': 'Agent proposals only until owner reviews the evidence report.'}
    _json(run / 'review/packet_manifest.json', packet)
    return packet


def _alias_diagnostics():
    taxonomy = load_taxonomy()
    cases = []
    for group, entries in taxonomy['groups'].items():
        for tag, definition in entries.items():
            for alias in definition.get('aliases', []) + definition.get('case_sensitive_aliases', []):
                found = normalize_mentions(alias, taxonomy)
                cases.append({'group': group, 'tag': tag, 'alias': alias,
                              'matched': any(m['group'] == group and m['tag'] == tag for m in found)})
    return {'cases': len(cases), 'passed': sum(c['matched'] for c in cases),
            'failed': [c for c in cases if not c['matched']],
            'scope': 'Defined taxonomy aliases only; not a claim of general semantic robustness.'}


def run_experiments(output, *, seed=42, labels_file=None, review_packet=None):
    output = Path(output).resolve()
    label_bytes = Path(labels_file).read_bytes() if labels_file else None
    if label_bytes is not None and len(label_bytes) > 20 * 1024**2:
        raise ValueError('review_input_size_limit')
    students, advisors, snapshot = _load_snapshot(output)
    code_paths = [Path(__file__), Path(__file__).with_name('rebuild_features.py'),
                  Path(__file__).with_name('rebuild_splits.py'),
                  ROOT / 'src/evaluation/rebuild_diagnostics.py', ROOT / 'src/evaluation/rebuild_ranking.py',
                  ROOT / 'src/evaluation/rebuild_review.py', ROOT / 'src/data_pipeline/normalization.py']
    code_hashes = {str(p.relative_to(ROOT)): _digest(p) for p in code_paths}
    splits = make_grouped_split(students, seed=seed)
    train = [r for r in students if splits['assignments'][r['student_id']] == 'train']
    validation = [r for r in students if splits['assignments'][r['student_id']] == 'validation']
    identities = sorted({str(r[k]) for r in students+advisors
                         for k in ('student_id','student_name','advisor_id','advisor_name') if r.get(k)})
    pipeline = FeaturePipeline({'known_identities': identities}).fit(train, advisors)
    started = time.perf_counter()
    result = pipeline.transform_score(validation, advisors)
    elapsed = time.perf_counter()-started
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    run = output / 'phase4_runs' / run_id
    for folder in ('reports','review','transformer','validation_scores'):
        (run / folder).mkdir(parents=True, exist_ok=False)
    _json(run / 'splits.json', splits)
    _json(run / 'snapshot_binding.json', snapshot)
    pipeline.save(run / 'transformer')
    reloaded = FeaturePipeline.load(run / 'transformer', known_identities=pipeline.identities)
    replay = reloaded.transform_score(validation, advisors)
    parity = all(np.array_equal(result['scores'][v], replay['scores'][v])
                 and np.array_equal(result['available'][v], replay['available'][v]) for v in VARIANTS)
    student_ids, advisor_ids = [r['student_id'] for r in validation], [r['advisor_id'] for r in advisors]
    diagnostics, rankings = {}, {}
    common_columns = np.logical_and.reduce([result['available'][v].any(axis=0) for v in ('E0', 'E1', 'E4')])
    common_advisors = [advisor for j, advisor in enumerate(advisor_ids) if common_columns[j]]
    for variant in VARIANTS:
        scores, available = result['scores'][variant], result['available'][variant]
        np.save(run / f'validation_scores/{variant}.npy', scores, allow_pickle=False)
        np.save(run / f'validation_scores/{variant}_available.npy', available, allow_pickle=False)
        rankings[variant] = rank_matrix(scores, available, student_ids, advisor_ids)
        diagnostics[variant] = {'matrix': summarize_matrix(scores, available),
                               'hungarian_diagnostic': diagnostic_hungarian(scores, available, student_ids, advisor_ids)}
        diagnostics[variant]['common_scorable_catalog'] = {'advisor_ids': common_advisors,
            'scope': 'Diagnostic intersection with observed E0/E1/E4 profile signals; not supervisory eligibility.'}
        if common_advisors:
            diagnostics[variant]['hungarian_common_catalog'] = diagnostic_hungarian(
                scores[:, common_columns], available[:, common_columns], student_ids, common_advisors)
    packet = _packet(run, validation, advisors, result, snapshot, splits, identities)
    _json(run / 'validation_scores/index.json', {'student_ids': student_ids, 'advisor_ids': advisor_ids,
                                               'split': 'validation', 'dtype': 'float64'})
    labels, calibration, metrics = [], None, None
    if labels_file:
        if not review_packet:
            raise ValueError('labels_require_frozen_review_packet')
        previous = Path(review_packet)
        previous_manifest = json.loads((previous / 'packet_manifest.json').read_text(encoding='utf-8'))
        if (previous_manifest['snapshot'] != snapshot or previous_manifest['student_ids'] != student_ids
                or previous_manifest['blinded_pairs_sha256'] != _digest(previous / 'blinded_pairs.jsonl')
                or previous_manifest['pair_bindings_sha256'] != _digest(previous / 'pair_bindings.json')):
            raise ValueError('stale_or_modified_review_packet')
        proposals = [json.loads(line) for line in label_bytes.decode('utf-8-sig').splitlines() if line.strip()]
        mapped = map_advisory_labels(previous, proposals)
        labels = validate_pair_labels(mapped,
                   student_hashes={r['student_id']: record_hash(r) for r in students},
                   advisor_hashes={r['advisor_id']: record_hash(r) for r in advisors},
                   snapshot_sha256=snapshot['snapshot_sha256'])
        if any(splits['assignments'][r['student_id']] != 'validation' for r in labels):
            raise ValueError('test_or_train_labels_not_allowed_for_selection')
        allowed = {(r['student_id'],r['advisor_id']) for r in json.loads((previous/'pair_bindings.json').read_text()).values()}
        if {(r['student_id'],r['advisor_id']) for r in labels} != allowed:
            raise ValueError('review_pair_coverage_mismatch')
        (run / 'review/agent_proposals.jsonl').write_bytes(label_bytes)
        (run / 'review/labels.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in labels), encoding='utf-8')
        components = {v: {student: {advisor: float(result['scores'][v][i,j]) if result['available'][v][i,j] else None
                        for j, advisor in enumerate(advisor_ids)} for i, student in enumerate(student_ids)} for v in ('E1','E2','E3')}
        calibration = calibrate_e4(components, labels, splits['assignments'], min_text_weight=.25)
        if calibration['weights']:
            scores, available = _hybrid(result, calibration['weights'])
            name = 'E4_calibrated_proposal'
            rankings[name] = rank_matrix(scores, available, student_ids, advisor_ids)
            np.save(run / f'validation_scores/{name}.npy', scores, allow_pickle=False)
            np.save(run / f'validation_scores/{name}_available.npy', available, allow_pickle=False)
            diagnostics[name] = {'matrix': summarize_matrix(scores, available),
                'hungarian_diagnostic': diagnostic_hungarian(scores, available, student_ids, advisor_ids),
                'common_scorable_catalog': diagnostics['E4']['common_scorable_catalog']}
            if common_advisors:
                diagnostics[name]['hungarian_common_catalog'] = diagnostic_hungarian(
                    scores[:, common_columns], available[:, common_columns], student_ids, common_advisors)
            calibrated_pipe = FeaturePipeline.load(run / 'transformer', known_identities=pipeline.identities)
            calibrated_pipe.weights = dict(calibration['weights'])
            calibrated_pipe.config['hybrid_weights'] = dict(calibration['weights'])
            calibrated_pipe.save(run / 'transformer_calibrated_proposal')
            calibrated_replay = FeaturePipeline.load(run / 'transformer_calibrated_proposal', known_identities=pipeline.identities).transform_score(validation, advisors)
            parity = parity and np.array_equal(scores, calibrated_replay['scores']['E4']) and np.array_equal(available, calibrated_replay['available']['E4'])
        metrics = {name: ranking_metrics(ranking, labels) for name, ranking in rankings.items()}
    _json(run / 'reports/experiment_diagnostics.json', diagnostics)
    _json(run / 'reports/ranking_metrics.json', {'status': 'agent_advisory_only' if labels else 'no_labels', 'metrics': metrics})
    _json(run / 'reports/hybrid_calibration.json', calibration)
    _json(run / 'reports/alias_robustness.json', _alias_diagnostics())
    _json(run / 'feature_manifest.json', {
        'status': 'experimental_pending_owner_selection', 'snapshot': snapshot,
        'variants': {'E0': ['thesis_title', 'research_description'],
                     'E1': ['thesis_title', 'thesis_abstract', 'research_description'],
                     'E2': ['research_domain_tags', 'topic_tags', 'expertise_topic_tags'],
                     'E3': ['TECH_COLUMNS', 'skill_confidence', 'expertise_confidence'],
                     'E4': ['E1', 'E2', 'E3', 'explicitly_confirmed_preferences_only']},
        'technology_columns': list(TECH_COLUMNS),
        'prohibited_inputs': ['identities', 'contacts', 'protected_demographics', 'gpa', 'source_filenames'],
        'identity_policy': 'Join/redaction only; identity registry is not serialized or learned.',
        'fit_population': {'split': 'train', 'student_count': len(train), 'assignments': 'splits.json'},
        'missing_policy': 'Mask unavailable signals; zero without a true mask is not an observed score.',
        'quality_policy': 'Evidence-validity ratio only; no mastery/proficiency inference.',
        'publication_summaries': 'Unavailable; unapproved raw publications excluded.',
        'baseline_e4_weights': pipeline.weights, 'calibrated_proposal': calibration['weights'] if calibration else None,
        'transformer_sha256': _digest(run / 'transformer/transformer.json'),
        'review_packet_sha256': _digest(Path(review_packet)/'packet_manifest.json') if review_packet else None})
    _json(run / 'reports/feature_audit.json', {'transform_parity': parity, 'redaction_counts': result['redaction_counts'],
        'learned_from': 'train_student_text_only', 'train_count': len(train), 'validation_count': len(validation),
        'test_count': splits['metadata']['student_counts']['test'], 'test_scores_generated': False,
        'publications_used': False, 'proficiency_used': False, 'confirmed_preferences_count': 0,
        'transform_seconds': elapsed, 'full_matrix_status': 'pending_owner_feature_selection'})
    unchanged = all(_digest(p) == code_hashes[str(p.relative_to(ROOT))] for p in code_paths)
    try:
        source_unchanged = _load_snapshot(output)[2] == snapshot
    except (ValueError, OSError):
        source_unchanged = False
    blockers = ['OWNER_RANKING_REVIEW_REQUIRED', 'SELECTED_FEATURE_CONTRACT_NOT_APPROVED']
    if not parity: blockers.append('TRANSFORMER_ROUNDTRIP_MISMATCH')
    if not unchanged: blockers.append('CODE_CHANGED_DURING_EXPERIMENT')
    if not source_unchanged: blockers.append('APPROVED_INPUTS_CHANGED_DURING_EXPERIMENT')
    gate = {'phase': 4, 'status': 'blocked', 'can_start_phase5': False, 'run_id': run_id, 'run_dir': str(run),
            'blocking_reasons': blockers, 'phase3_snapshot': snapshot, 'split_counts': splits['metadata']['student_counts'],
            'experiments': list(VARIANTS), 'validation_shape': [len(validation),len(advisors)],
            'review_pairs': packet['pair_count'], 'owner_validated_ranking_metrics': None,
            'full_matrix_status': 'pending_owner_feature_selection', 'code_sha256': code_hashes,
            'code_unchanged_during_run': unchanged, 'inputs_unchanged_during_run': source_unchanged,
            'created_at': datetime.now(timezone.utc).isoformat()}
    _json(run / 'reports/phase4_gate.json', gate)
    _json(run / 'manifest.json', {'gate': gate, 'agent_proposals_sha256': hashlib.sha256(label_bytes).hexdigest() if label_bytes else None,
          'artifacts': [{'path': p.relative_to(run).as_posix(), 'sha256': _digest(p)}
                        for p in sorted(run.rglob('*')) if p.is_file()]})
    _json(output / 'reports/phase4_gate.json', gate)
    return gate
