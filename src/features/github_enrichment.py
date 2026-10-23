"""Add owner-bound GitHub evidence without rewriting accepted P3/P4 artifacts."""
import copy
import csv
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.data_pipeline.csv_contracts import HEADERS, validate_row
from src.data_pipeline.normalization import load_taxonomy, normalize_mentions, taxonomy_ids
from src.data_pipeline.reconcile import ROOT, _digest, _read_bound_phase
from src.data_pipeline.review_decisions import record_hash
from src.features.rebuild_acceptance import _verified_manifest, load_approved_features
from src.features.rebuild_experiments import _load_snapshot
from src.features.rebuild_features import FeaturePipeline


TARGETS = {'fit_992239a385b6475451e8': 'nhthang9x', 'fit_5a04416402925947eef7': 'vietnh1009'}
SCHEMA = 'github-advisor-training-bundle/1.0'


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8'))


def merge_advisors(base, supplements, evidence, review, *, taxonomy,
                   github_manifest_sha256, quality_review_sha256):
    if (review.get('status') != 'verified' or review.get('source_manifest_sha256') != github_manifest_sha256
            or len(supplements) != 2 or {row['advisor_id'] for row in supplements} != set(TARGETS)):
        raise ValueError('github_review_or_target_binding_mismatch')
    by_id = {row['evidence_id']: row for row in evidence}
    if len(by_id) != len(evidence):
        raise ValueError('duplicate_github_evidence_id')
    result = copy.deepcopy(base)
    if len({row['advisor_id'] for row in result}) != len(result) or not set(TARGETS) <= {r['advisor_id'] for r in result}:
        raise ValueError('github_advisor_registry_mismatch')
    units = review.get('approved_units', [])
    for supplement in supplements:
        key = supplement['advisor_id']
        if (supplement.get('github_username') != TARGETS[key]
                or supplement.get('identity_mapping') != 'owner_confirmed'
                or supplement.get('personal_proficiency') is not None):
            raise ValueError('github_identity_or_proficiency_not_authorized')
        candidate_units = {(group, tag) for group, tags in supplement['tags'].items() for tag in tags}
        accepted, refs, descriptions = set(), [], []
        for unit in (row for row in units if row['advisor_id'] == key):
            pair = (unit['group'], unit['tag'])
            if (pair in accepted or pair not in candidate_units
                    or unit.get('checks') != {'source': 'pass', 'span': 'pass', 'semantic': 'pass'}
                    or pair[1] not in taxonomy['groups'].get(pair[0], {})):
                raise ValueError('github_tag_review_not_passed')
            chosen = None
            for identifier in unit.get('evidence_ids', []):
                occurrence = by_id.get(identifier)
                if (occurrence is None or occurrence['advisor_id'] != key
                        or (occurrence['group'], occurrence['tag']) != pair
                        or identifier not in supplement['evidence_refs']):
                    raise ValueError('github_tag_evidence_binding_mismatch')
                if chosen is None:
                    chosen = occurrence
            if chosen is None:
                raise ValueError('github_tag_evidence_required')
            accepted.add(pair)
            refs.append(copy.deepcopy(chosen))
            descriptions.append(chosen['excerpt'])
        if not accepted or not candidate_units:
            raise ValueError('github_no_reviewed_feature_evidence')
        row = next(row for row in result if row['advisor_id'] == key)
        parts = [row.get('research_description') or '', *descriptions]
        row['research_description'] = '\n'.join(dict.fromkeys(part for part in parts if part))
        for group, tag in sorted(accepted):
            column = 'expertise_topic_tags' if group == 'topic_tags' else group
            current = set(str(row.get(column) or '').split(';')) - {''}
            row[column] = ';'.join(sorted(current | {tag}))
        row['expertise_evidence_type'] = 'verified_web'
        row['expertise_confidence'] = str(len(accepted)/len(candidate_units))
        row['expertise_evidence_refs'] = json.dumps({
            'schema_version': 'github-field-evidence/1.0', 'source_manifest_sha256': github_manifest_sha256,
            'quality_review_sha256': quality_review_sha256, 'identity_mapping': 'owner_confirmed',
            'confidence_semantics': 'Valid source/span/semantic units divided by candidate units; not proficiency.',
            'refs': refs}, ensure_ascii=False)
        row['source_type'] = 'official_web_and_owner_bound_github'
        row['reviewer_notes'] = json.dumps({
            'parent_review': row.get('reviewer_notes'), 'github_source_manifest_sha256': github_manifest_sha256,
            'github_quality_review_sha256': quality_review_sha256, 'approved_units': len(accepted),
            'candidate_units': len(candidate_units), 'identity_mapping': 'owner_confirmed',
            'primary_source_policy': 'Official URL/SHA remain the identity anchor. New fields use GitHub evidence refs.',
            'claim_scope': 'Public project technology/topic evidence only; not proficiency, capacity or outcomes.'}, ensure_ascii=False)
    return result


def source_text(run, occurrence, sources):
    source = sources[occurrence['source_id']]
    if (source['sha256'] != occurrence['source_sha256'] or source['url'] != occurrence['source_url']):
        raise ValueError('github_evidence_source_mismatch')
    body = (Path(run)/'raw'/(source['sha256']+'.bin')).read_bytes()
    if source['kind'] == 'repository_listing':
        match = re.fullmatch(r'repositories\[id=(\d+)\]\.(name|description|language)', occurrence['locator'])
        if match is None:
            raise ValueError('github_metadata_locator_required')
        rows = [row for row in json.loads(body) if str(row['id']) == match[1]
                and row['full_name'] == occurrence['repository']]
        if len(rows) != 1 or not isinstance(rows[0].get(match[2]), str):
            raise ValueError('github_metadata_field_missing')
        return rows[0][match[2]]
    return body.decode('utf-8-sig')


def verify_reviewed_evidence(run, evidence, review, taxonomy):
    from src.data_pipeline.github_advisors import verify_run
    manifest = verify_run(run)
    if (not manifest['quality']['enumeration_complete'] or not manifest['quality']['source_bytes_complete']
            or review.get('source_manifest_sha256') != _digest(Path(run)/'manifest.json')):
        raise ValueError('github_source_quality_not_verified')
    sources = {r['source_id']: r for r in _lines(Path(run)/'sources.jsonl')}
    repositories = {r['full_name']: r for r in _lines(Path(run)/'repositories.jsonl')}
    by_id = {r['evidence_id']: r for r in evidence}
    for unit in review['approved_units']:
        for identifier in unit['evidence_ids']:
            occurrence = by_id[identifier]
            repository = repositories[occurrence['repository']]
            if repository['fork'] or repository.get('is_template'):
                raise ValueError('github_fork_evidence_not_attributable')
            text = source_text(run, occurrence, sources)
            if (text[occurrence['start']:occurrence['end']] != occurrence['matched_text']
                    or text[occurrence['excerpt_start']:occurrence['excerpt_end']] != occurrence['excerpt']
                    or not any(all(mention[k] == occurrence[k] for k in ('group', 'tag', 'start', 'end'))
                               for mention in normalize_mentions(text, taxonomy))):
                raise ValueError('github_literal_evidence_span_mismatch')
    return manifest


def _lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def load_training_bundle(path):
    path = Path(path).resolve()
    manifest = _verified_manifest(path.parent)
    if manifest.get('gate', {}).get('status') != 'verified':
        raise ValueError('github_training_bundle_not_verified')
    if not any(entry['path'] == path.name for entry in manifest['artifacts']):
        raise ValueError('github_training_bundle_not_bound')
    bundle = _read(path)
    if bundle.get('schema_version') != SCHEMA:
        raise ValueError('github_training_bundle_schema_mismatch')
    for artifact in bundle['source_artifacts']:
        source = Path(artifact['path'])
        if not source.is_absolute() or source.is_symlink() or _digest(source) != artifact['sha256']:
            raise ValueError('github_training_source_artifact_changed')
    if bundle.get('serving', {}).get('github_source_run'):
        from src.data_pipeline.github_advisors import verify_run
        verify_run(bundle['serving']['github_source_run'])
    return bundle


def prepare_bundle(output, github_run, quality_review, *, destination=None):
    from src.data_pipeline.rebuild_cohorts import assemble_research_suite
    from src.environment.rebuild_env import MatchingEnv
    from src.evaluation.rebuild_benchmark import problem_payload
    from src.domain.rebuild_matching import feasible
    output, github_run, quality_review = map(lambda p: Path(p).resolve(), (output, github_run, quality_review))
    taxonomy = load_taxonomy()
    review = _read(quality_review)
    evidence = _lines(github_run/'evidence.jsonl')
    github_manifest = verify_reviewed_evidence(github_run, evidence, review, taxonomy)
    students, original_advisors, snapshot = _load_snapshot(output)
    parent = load_approved_features(output)
    advisors = merge_advisors(original_advisors, _read(github_run/'supplements.json')['advisors'], evidence, review,
                              taxonomy=taxonomy, github_manifest_sha256=_digest(github_run/'manifest.json'),
                              quality_review_sha256=_digest(quality_review))
    groups = {key: set(tags) for key, tags in taxonomy['groups'].items()}
    for row in advisors:
        errors = validate_row({key: row.get(key, '') for key in HEADERS['advisors']}, 'advisors', mode='gold',
                              taxonomy_ids=taxonomy_ids(taxonomy), taxonomy_groups=groups)
        if errors:
            raise ValueError('enriched_advisor_csv_invalid:'+str(errors[:2]))
    parent_run = Path(parent['gate']['run_dir'])
    identities = sorted({str(row[key]) for row in students+advisors
                         for key in ('student_id', 'student_name', 'advisor_id', 'advisor_name') if row.get(key)})
    pipeline = FeaturePipeline.load(parent_run/'transformer', known_identities=identities)
    transformed = pipeline.transform_score(students, advisors)
    scores, available = transformed['scores']['E4'], transformed['available']['E4']
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    run = Path(destination or output.parents[0]/'github_rebuild').resolve()/run_id
    run.mkdir(parents=True, exist_ok=False)
    shutil.copytree(parent_run/'transformer', run/'transformer')
    shutil.copyfile(parent_run/'splits.json', run/'splits.json')
    _write(run/'students.json', students)
    _write(run/'advisors.json', advisors)
    _, silver = _read_bound_phase(output, 3, 'silver/review_records.jsonl')
    wanted = {row['advisor_id'] for row in advisors}
    profiles = [row for row in _lines(silver) if row.get('entity_type') == 'advisors' and row['advisor_id'] in wanted]
    _write(run/'source_profiles.json', profiles)
    for entity, rows in (('students', students), ('advisors', advisors)):
        path = run/'gold'/f'{entity}.csv'
        path.parent.mkdir(exist_ok=True)
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=HEADERS[entity], extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
    (run/'features').mkdir()
    np.save(run/'features/scores.npy', scores, allow_pickle=False)
    np.save(run/'features/available.npy', available, allow_pickle=False)
    index = {'student_ids': [r['student_id'] for r in students], 'advisor_ids': [r['advisor_id'] for r in advisors],
             'shape': list(scores.shape), 'dtype': str(scores.dtype)}
    _write(run/'features/index.json', index)
    encoder = {key: _digest(run/'transformer'/name) for key, name in
               (('transformer_json_sha256', 'transformer.json'), ('transformer_idf_sha256', 'idf.npz'))}
    contract = {'schema_version': 'github-advisor-feature-contract/1.0', 'scope': 'local_research_source_enriched',
                'parent_phase4_run_id': parent['gate']['run_id'],
                'parent_feature_contract_sha256': parent['gate']['feature_contract_sha256'],
                'parent_snapshot_sha256': snapshot['snapshot_sha256'],
                'github_manifest_sha256': _digest(github_run/'manifest.json'),
                'quality_review_sha256': _digest(quality_review),
                'owner_receipt_sha256': _digest(github_run/'owner_receipt.json'),
                'hybrid_weights': pipeline.weights, 'frozen_encoder': encoder,
                'student_split_sha256': _digest(run/'splits.json'),
                'index_sha256': _digest(run/'features/index.json'),
                'matrix_sha256': _digest(run/'features/scores.npy'),
                'availability_sha256': _digest(run/'features/available.npy'),
                'taxonomy_sha256': _digest(ROOT/'configs/data/taxonomy_v1.yaml'),
                'identity_policy': 'owner_confirmed',
                'test_policy': {'used_for_selection': False, 'old_test_previously_seen': True}}
    _write(run/'feature_contract.json', contract)
    features = {'scores': scores, 'available': available, 'index': index,
                'gate': {'run_id': run_id, 'feature_contract_sha256': _digest(run/'feature_contract.json')}}
    suite = assemble_research_suite(features, students, _read(run/'splits.json'), taxonomy)
    if not all(feasible(problem) for problem in [*suite['train'], suite['validation'], suite['test']]):
        raise ValueError('enriched_research_suite_infeasible')
    if not set(TARGETS) <= set(suite['metadata']['selected_advisor_ids']):
        raise ValueError('github_advisors_not_fully_scorable_in_training; inspect source and OOV report')
    env = MatchingEnv(suite['train'], shuffle_students=True)
    native = {'scope': 'local_research_source_enriched', 'feature_contract_sha256': _digest(run/'feature_contract.json'),
              'phase4_run_id': run_id, 'state_contract': env.state_contract,
              'taxonomy_feature_order_sha256': suite['metadata']['taxonomy_feature_order_sha256'],
              'quota_policy_version': 'equal-division-canonical/1.0', 'reward_weights': env.reward_weights,
              'training_student_ids': sorted(s for p in suite['train'] for s in p.student_ids),
              'training_problem_sha256': [record_hash(problem_payload(p)) for p in suite['train']]}
    feature_report = {'status': 'verified', 'source_only_change': 'Exactly two owner-linked advisor profiles',
                      'students_unchanged': students == _load_snapshot(output)[0],
                      'advisor_registry_unchanged': index['advisor_ids'] == parent['index']['advisor_ids'],
                      'shape': index['shape'], 'training_sizes': [len(p.student_ids) for p in suite['train']],
                      'selected_advisors': len(suite['metadata']['selected_advisor_ids']),
                      'target_available_pairs': {key: int(available[:, index['advisor_ids'].index(key)].sum()) for key in TARGETS},
                      'old_target_available_pairs': {key: int(parent['available'][:, index['advisor_ids'].index(key)].sum()) for key in TARGETS},
                      'frozen_encoder_files_identical': all(_digest(run/'transformer'/name) == _digest(parent_run/'transformer'/name)
                                                            for name in ('transformer.json', 'idf.npz')),
                      'test_evaluated': False, 'claim_scope': 'Source integrity and score availability, not academic accuracy.'}
    _write(run/'reports/feature_quality.json', feature_report)
    serving = {key: str(path) for key, path in {
        'students_path': run/'students.json', 'advisors_path': run/'advisors.json',
        'source_profiles_path': run/'source_profiles.json', 'transformer_dir': run/'transformer',
        'taxonomy_path': ROOT/'configs/data/taxonomy_v1.yaml', 'splits_path': run/'splits.json',
        'github_source_run': github_run, 'github_quality_review_path': quality_review,
        'feature_contract_path': run/'feature_contract.json', 'index_path': run/'features/index.json',
        'scores_path': run/'features/scores.npy', 'available_path': run/'features/available.npy'}.items()}
    serving.update(github_manifest_sha256=_digest(github_run/'manifest.json'), github_quality_review_sha256=_digest(quality_review))
    sources = [p for p in run.rglob('*') if p.is_file()]
    sources += [github_run/'manifest.json', quality_review, ROOT/'configs/data/taxonomy_v1.yaml',
                ROOT/'configs/data/feature_allowlist.yaml', output/'reports/phase3_gate.json',
                Path(snapshot['run_dir'])/'manifest.json' if 'run_dir' in snapshot else silver.parents[1]/'manifest.json',
                parent_run/'manifest.json', Path(__file__)]
    bundle = {'schema_version': SCHEMA, 'bundle_run_id': run_id,
              'training_problems': [problem_payload(p) for p in suite['train']],
              'evaluation_problems': {key: problem_payload(suite[key]) for key in ('validation', 'test')},
              'model_contract': native,
              'frozen_encoder': {**encoder, 'artifacts': [{'path': str(run/'transformer'/name), 'sha256': _digest(run/'transformer'/name)}
                                                        for name in ('transformer.json', 'idf.npz')]},
              'source_artifacts': [{'path': str(path.resolve()), 'sha256': _digest(path)} for path in sorted(set(sources))],
              'student_split_sha256': _digest(run/'splits.json'), 'serving': serving,
              'comparators': {'previous_run_id': '20261022T185701Z-ba772936',
                              'interpretation': 'Old/new dataset effects confounded; step effects compare within this enriched suite.'}}
    _write(run/'training_bundle.json', bundle)
    artifacts = [{'path': path.relative_to(run).as_posix(), 'sha256': _digest(path)}
                 for path in sorted(run.rglob('*')) if path.is_file()]
    _write(run/'manifest.json', {'schema_version': 'github-advisor-bundle/1.0', 'gate': {'status': 'verified'}, 'artifacts': artifacts})
    load_training_bundle(run/'training_bundle.json')
    return run/'training_bundle.json'
