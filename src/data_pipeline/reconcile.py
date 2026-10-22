"""Phase 3 staging, exact-source reconciliation and explicit review-gated gold."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import shutil
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .review_decisions import apply_decisions, record_hash

ROOT = Path(__file__).resolve().parents[2]


def _digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def _jsonl(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def canonicalize_students(candidates):
    groups, decisions = defaultdict(list), []
    for candidate in candidates:
        identifier = candidate['fields'].get('student_id', {}).get('value')
        key = (identifier, candidate['source_sha256']) if identifier else (None, candidate['candidate_id'])
        groups[key].append(candidate)
    records = []
    for group in groups.values():
        ordered = sorted(group, key=lambda c: c['candidate_id'])
        canonical = copy.deepcopy(ordered[0])
        canonical.update(record_id=canonical['candidate_id'], entity_type='students', source_aliases=[])
        for duplicate in ordered[1:]:
            alias = {k: duplicate[k] for k in ('candidate_id', 'source_id', 'source_file', 'source_sha256')}
            canonical['source_aliases'].append(alias)
            decisions.append({'source_id': duplicate['source_id'], 'canonical_record_id': canonical['record_id'],
                              'decision': 'identical_bytes_same_observed_id', 'source_sha256': duplicate['source_sha256']})
        records.append(canonical)
    identities = defaultdict(list)
    for row in records:
        identifier = row['fields'].get('student_id', {}).get('value')
        if identifier:
            identities[identifier].append(row)
    for group in identities.values():
        if len(group) > 1:
            for row in group:
                row['review_reasons'] = sorted(set(row['review_reasons'] + ['conflicting_source_versions']))
    return sorted(records, key=lambda r: r['record_id']), decisions


def _read_bound_phase(output, number, artifact):
    gate_path = output / f'reports/phase{number}_gate.json'
    gate = json.loads(gate_path.read_text(encoding='utf-8'))
    if gate.get('status') != 'verified' or not gate.get(f'can_start_phase{number+1}'):
        raise ValueError(f'phase{number}_not_verified')
    run_id = gate.get('run_id', '')
    if not run_id or Path(run_id).name != run_id:
        raise ValueError('invalid_predecessor_run_id')
    run = output / f'phase{number}_runs' / run_id
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    records = {r['path'].replace('\\', '/'): r['sha256'] for r in manifest['artifacts']}
    if (manifest['gate'] != gate or _digest(gate_path) != records[f'reports/phase{number}_gate.json']
            or _digest(run / artifact) != records[artifact]):
        raise ValueError('predecessor_artifact_hash_mismatch')
    return gate, run / artifact


def _headers(entity):
    with (ROOT / f'docs/{entity}_import.csv').open(encoding='utf-8-sig', newline='') as stream:
        return next(csv.reader(stream))


def _csv(path, rows, headers):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, '') for h in headers})


def _row(record, entity, semester_id, taxonomy, normalization_audit=None):
    from .normalization import normalize_mentions
    row = {h: '' for h in _headers(entity)}
    row.update(schema_version='1.0', semester_id=semester_id or '', review_status=record['review_status'],
               source_sha256=record['source_sha256'])
    if entity == 'students':
        for key, field in record['fields'].items():
            if key in row:
                row[key] = field['value']
        source_fields = ('thesis_title', 'thesis_abstract', 'thesis_keywords')
        segments = [(field, str(record['fields'][field]['value']), record['fields'][field]['evidence'])
                    for field in source_fields if field in record['fields']]
        # Technologies are thesis mentions, never personal skills or proficiency.
        segments += [('technology_mentions', str(m['value']), m['evidence']) for m in record.get('technology_mentions', [])]
        row.update(source_file=record['source_file'], source_type='docx' if record['source_file'].lower().endswith('.docx') else 'pdf',
                   extracted_at=record.get('extracted_at', ''), skill_evidence_type='inferred_from_thesis')
        refs = [ev for field in record['fields'].values() for ev in field.get('evidence', [])]
        refs += [ev for mention in record.get('technology_mentions', []) for ev in mention.get('evidence', [])]
        row['source_page'] = next((str(ev['page']) for ev in refs if ev.get('page')), '')
        confidence_field = 'skill_confidence'
    else:
        research = '\n'.join(record.get('research_topics', []) + record.get('teaching_topics', []))
        row.update(advisor_id=record['advisor_id'], advisor_name=record.get('advisor_name') or '',
                   profile_url=record['source_url'], research_description=research,
                   source_type='official_web', source_url=record['source_url'], crawled_at=record['retrieved_at'],
                   expertise_evidence_type='verified_web')
        segments = [(field, value, [ev for ev in record['evidence'] if ev['field'] == field and ev['snippet'] == value])
                    for field in ('research_topics', 'teaching_topics') for value in record.get(field, [])]
        confidence_field = 'expertise_confidence'
    groups = defaultdict(set)
    tag_evidence, shared_refs, ref_indexes = [], [], {}
    for field, text, source_refs in segments:
        for mention in normalize_mentions(text, taxonomy):
            column = 'expertise_topic_tags' if entity == 'advisors' and mention['group'] == 'topic_tags' else mention['group']
            if column not in row or column == 'skills_tags':
                continue
            groups[column].add(mention['tag'])
            indexes = []
            for reference in source_refs:
                compact = {key: value for key, value in reference.items() if key not in
                           {'source_id', 'source_file', 'source_sha256', 'source_url', 'archive_chain'}}
                key = record_hash(compact)
                if key not in ref_indexes:
                    ref_indexes[key] = len(shared_refs)
                    shared_refs.append(compact)
                indexes.append(ref_indexes[key])
            tag_evidence.append({**mention, 'output_column': column, 'source_field': field, 'ref_indexes': indexes})
    for group, tags in groups.items():
        row[group] = ';'.join(sorted(tags))
    envelope = {key: record[key] for key in ('source_file', 'source_url', 'source_sha256', 'archive_chain') if key in record}
    if tag_evidence:
        envelope.update(refs=shared_refs, tags=tag_evidence)
        row['skill_evidence_refs' if entity == 'students' else 'expertise_evidence_refs'] = json.dumps(envelope, ensure_ascii=False)
    if normalization_audit is not None:
        normalization_audit.append({'record_id': record['record_id'], 'entity_type': entity,
                                    'taxonomy_version': taxonomy['taxonomy_version'], 'source': envelope,
                                    'confidence_missing': record.get('review_audit', {}).get('evidence_confidence') is None})
    confidence = record.get('review_audit', {}).get('evidence_confidence')
    if confidence is not None:
        row[confidence_field] = str(confidence)
    row['reviewer_notes'] = json.dumps({'record_id': record['record_id'],
                                       'review_reasons': record.get('review_reasons', []),
                                       'review_audit': record.get('review_audit')}, ensure_ascii=False)
    return row


def validate_advisor_correction(old, changed):
    """Remove misclassified metadata; never introduce expertise absent from the bound source."""
    for field in ('research_topics', 'teaching_topics'):
        values = changed.get(field, [])
        if (not isinstance(values, list) or any(not isinstance(v, str) for v in values)
                or len(values) != len(set(values)) or not set(values) <= set(old.get(field, []))):
            return ['advisor_correction_must_be_source_subset']
    if changed.get('evidence') != old.get('evidence'):
        return ['advisor_source_evidence_modified']
    return []


def stage_sources(output: Path, *, semester_id=None, decisions_file=None, taxonomy_approval_file=None,
                  sample_reviews_file=None, proposals_file=None, owner_acceptance_file=None,
                  quality_assessments_file=None, eligibility_file=None):
    from .csv_contracts import export_json_schema, validate_csv
    from .normalization import load_taxonomy, taxonomy_ids
    output = Path(output).resolve()
    code_paths = [Path(__file__).with_name(name + '.py') for name in
                  ('reconcile', 'review_decisions', 'review_metrics', 'csv_contracts', 'normalization',
                   'acceptance', 'evidence_quality')]
    code_hashes = {path.name: _digest(path) for path in code_paths}
    input_paths = {'decisions': decisions_file, 'agent_proposals': proposals_file,
                   'sample_reviews': sample_reviews_file, 'taxonomy_approval': taxonomy_approval_file,
                   'owner_acceptance': owner_acceptance_file,
                   'quality_assessments': quality_assessments_file, 'eligibility': eligibility_file}
    review_inputs = {label: Path(path).read_bytes() for label, path in input_paths.items() if path}
    if any(len(value) > 20 * 1024**2 for value in review_inputs.values()):
        raise ValueError('review_input_size_limit')
    input_hashes = {key: hashlib.sha256(value).hexdigest() for key, value in review_inputs.items()}
    student_gate, student_path = _read_bound_phase(output, 1, 'bronze/student_candidates.jsonl')
    faculty_gate, faculty_path = _read_bound_phase(output, 2, 'silver/advisors.jsonl')
    inventory_hash = _digest(output / 'reports/input_inventory.csv')
    if student_gate['input_inventory_sha256'] != inventory_hash:
        raise ValueError('source_inventory_binding_mismatch')
    original_candidates = _jsonl(student_path)
    students, dedupe = canonicalize_students(original_candidates)
    advisors = [{**row, 'record_id': row['advisor_id'], 'entity_type': 'advisors'} for row in _jsonl(faculty_path)]
    for row in students:
        row['extracted_at'] = student_gate['created_at']
    decisions = [json.loads(s) for s in review_inputs.get('decisions', b'').decode('utf-8-sig').splitlines() if s.strip()]
    proposals = [json.loads(s) for s in review_inputs.get('agent_proposals', b'').decode('utf-8-sig').splitlines() if s.strip()]
    if any(p.get('decision') != 'needs_review' or p.get('evidence_confidence') is not None for p in proposals):
        raise ValueError('agent_proposals_cannot_approve_or_invent_confidence')
    corrected_ids = {d['record_id'] for d in proposals+decisions if d.get('corrections') or d.get('remove_fields')}
    wanted_sources = {r['source_id'] for r in students if r['record_id'] in corrected_ids}
    correction_blocks = defaultdict(list)
    if wanted_sources:
        path = output / 'phase1_runs' / student_gate['run_id'] / 'bronze/document_blocks.jsonl'
        manifest = json.loads((path.parents[1] / 'manifest.json').read_text(encoding='utf-8'))
        expected = next(r['sha256'] for r in manifest['artifacts'] if r['path'].replace('\\', '/') == 'bronze/document_blocks.jsonl')
        if _digest(path) != expected:
            raise ValueError('correction_evidence_artifact_modified')
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                block = json.loads(line)
                if block['source_id'] in wanted_sources:
                    correction_blocks[block['source_id']].append(block)
    def validate_correction(old, changed):
        if old['entity_type'] == 'advisors':
            return validate_advisor_correction(old, changed)
        from .student_candidates import validate_evidence
        try:
            return validate_evidence([changed], correction_blocks[old['source_id']])
        except (KeyError, TypeError):
            return ['invalid_correction_schema']
    base_records, proposal_errors = apply_decisions(students+advisors, proposals, correction_validator=validate_correction)
    records, review_errors = apply_decisions(base_records, decisions, correction_validator=validate_correction)
    review_errors = proposal_errors + review_errors
    taxonomy = load_taxonomy()
    taxonomy_groups = {group: set(values) for group, values in taxonomy['groups'].items()}
    taxonomy_path = ROOT / 'configs/data/taxonomy_v1.yaml'
    taxonomy_hash = _digest(taxonomy_path)
    config_hashes = {name: _digest(ROOT / 'configs/data' / name) for name in
                     ('taxonomy_v1.yaml', 'feature_allowlist.yaml', 'feature_excluded.yaml')}
    config_hash = record_hash(config_hashes)
    taxonomy_approved = False
    taxonomy_review_error = False
    if taxonomy_approval_file:
        try:
            approval = json.loads(review_inputs['taxonomy_approval'].decode('utf-8-sig'))
            timestamp = datetime.fromisoformat(approval.get('reviewed_at', '').replace('Z', '+00:00'))
            taxonomy_approved = (approval.get('taxonomy_sha256') == taxonomy_hash and approval.get('config_sha256') == config_hash
                                 and approval.get('decision') == 'approve'
                                 and bool(approval.get('reviewer')) and timestamp.tzinfo is not None)
        except (ValueError, TypeError, AttributeError):
            taxonomy_review_error = True
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    run = output / 'phase3_runs' / run_id
    for name in ('silver', 'gold', 'reports', 'review'):
        (run / name).mkdir(parents=True, exist_ok=False)
    with (run / 'silver/review_records.jsonl').open('w', encoding='utf-8') as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    template = []
    for record in base_records:
        template.append({'record_id': record['record_id'], 'record_sha256': record_hash(record),
                         'entity_type': record['entity_type'], 'source_sha256': record['source_sha256'],
                         'decision': '', 'reviewer': '', 'reviewed_at': '', 'evidence_confidence': '', 'notes': ''})
    _csv(run / 'review/decisions_template.csv', template, list(template[0]) if template else ['record_id'])
    _json(run / 'review/taxonomy_approval_template.json', {
        'taxonomy_sha256': taxonomy_hash, 'config_sha256': config_hash, 'config_files': config_hashes,
        'decision': '', 'reviewer': '', 'reviewed_at': '',
    })
    # Preserve the exact review inputs; later edits must never rewrite this run's authority trail.
    for label, content in review_inputs.items():
        (run / 'review' / (label + Path(input_paths[label]).suffix)).write_bytes(content)
    validations, counts, missingness, normalization_audit = {}, {}, {}, []
    for entity in ('students', 'advisors'):
        selected = [r for r in records if r['entity_type'] == entity]
        rows = [_row(record, entity, semester_id, taxonomy, normalization_audit) for record in selected]
        _csv(run / f'silver/{entity}_staging.csv', rows, _headers(entity))
        validations[entity] = validate_csv(run / f'silver/{entity}_staging.csv', entity,
                                           mode='staging', taxonomy_ids=taxonomy_ids(taxonomy), taxonomy_groups=taxonomy_groups)
        approved = [row for row in rows if row['review_status'] == 'approved']
        _csv(run / f'gold/{entity}.csv', approved, _headers(entity))
        _csv(run / f'silver/{entity}_quarantine.csv',
             [row for row in rows if row['review_status'] != 'approved'], _headers(entity))
        validations[entity+'_gold'] = validate_csv(run / f'gold/{entity}.csv', entity,
                                                  mode='gold', taxonomy_ids=taxonomy_ids(taxonomy), taxonomy_groups=taxonomy_groups)
        counts[entity] = {'source_records': len(selected), 'approved': len(approved)}
        missingness[entity] = {key: sum(row.get(key, '') == '' for row in rows) for key in _headers(entity)}
        _json(run / f'reports/{entity}_schema.json', export_json_schema(entity))
    _json(run / 'reports/import_validation.json', validations)
    _json(run / 'reports/field_missingness.json', missingness)
    _json(run / 'reports/review_errors.json', review_errors)
    _json(run / 'reports/reconciliation_decisions.json', dedupe)
    _json(run / 'reports/normalization_evidence.json', normalization_audit)
    if sample_reviews_file:
        from .review_metrics import evaluate_sample
        sample_metrics = evaluate_sample(run / 'review' / ('sample_reviews' + Path(sample_reviews_file).suffix),
                                         original_candidates, student_gate['run_id'])
    else:
        sample_metrics = {'complete': False, 'reviewed_rows': 0, 'fields': {}, 'errors': []}
    _json(run / 'reports/human_sample_metrics.json', sample_metrics)
    blockers = []
    code_unchanged = all(_digest(path) == code_hashes[path.name] for path in code_paths)
    if not code_unchanged:
        blockers.append('PIPELINE_CODE_CHANGED_DURING_RUN')
    if not semester_id:
        blockers.append('SEMESTER_ID_REQUIRED_BEFORE_GOLD_IMPORT')
    if not taxonomy_approved:
        blockers.append('TAXONOMY_OWNER_REVIEW_REQUIRED')
    if taxonomy_review_error:
        blockers.append('INVALID_TAXONOMY_APPROVAL')
    if not all(v['approved'] for v in counts.values()):
        blockers.append('HUMAN_RECORD_REVIEW_REQUIRED')
    if review_errors:
        blockers.append('INVALID_REVIEW_DECISIONS')
    if any(not validations[entity+'_gold'].get('valid', False) for entity in ('students', 'advisors')):
        blockers.append('GOLD_CSV_VALIDATION_FAILED')
    if not sample_metrics['complete']:
        blockers.append('HUMAN_GOLDEN_SAMPLE_METRICS_REQUIRED')
    elif any(not sample_metrics['fields'].get(field, {}).get('known_labels')
             for field in ('student_id', 'student_name', 'thesis_title')):
        blockers.append('CORE_FIELD_ACCURACY_LABELS_REQUIRED')
    ratified_sample = bool(sample_metrics.get('review_kind_counts', {}).get('owner_ratified_agent_report'))
    if ratified_sample and not owner_acceptance_file:
        blockers.append('OWNER_SAMPLE_RATIFICATION_RECEIPT_REQUIRED')
    elif ratified_sample and sample_metrics.get('ratification_receipt_sha256s') != [input_hashes['owner_acceptance']]:
        blockers.append('OWNER_SAMPLE_RATIFICATION_RECEIPT_MISMATCH')
    if sample_metrics.get('review_kind_counts', {}).get('agent_advisory'):
        blockers.append('AGENT_ONLY_SAMPLE_IS_NOT_OWNER_APPROVAL')
    if ratified_sample and owner_acceptance_file:
        from .acceptance import build_owner_decisions, validate_quality_binding, verify_owner_package
        try:
            receipt, package = verify_owner_package(json.loads(review_inputs['owner_acceptance'].decode('utf-8-sig')))
            with (package / 'staging_review/decisions_template.csv').open(encoding='utf-8-sig', newline='') as stream:
                template_rows = list(csv.DictReader(stream))
            bound_records = {r['record_id']: r['record_sha256'] for r in template_rows}
            if (len(bound_records) != len(template_rows)
                    or bound_records != {r['record_id']: record_hash(r) for r in base_records}):
                raise ValueError('owner_package_records_mismatch')
            eligibility = [json.loads(line) for line in review_inputs['eligibility'].decode('utf-8-sig').splitlines() if line.strip()]
            quality = [json.loads(line) for line in review_inputs['quality_assessments'].decode('utf-8-sig').splitlines() if line.strip()]
            validate_quality_binding(base_records, normalization_audit, quality)
            expected_decisions = build_owner_decisions(base_records, eligibility, quality, receipt,
                                                       receipt_sha256=input_hashes['owner_acceptance'])
            if ({r['record_id']: r for r in expected_decisions} != {r['record_id']: r for r in decisions}
                    or len(decisions) != len(expected_decisions)):
                raise ValueError('owner_decisions_differ_from_bound_assessments')
        except (ValueError, KeyError, TypeError, OSError, IndexError):
            blockers.append('OWNER_RATIFICATION_VALIDATION_FAILED')
    approved_ids = {r['record_id'] for r in records if r['review_status'] == 'approved'}
    approved_records = {r['record_id']: r for r in records if r['review_status'] == 'approved'}
    canonical_id = {alias['candidate_id']: r['record_id'] for r in students for alias in r.get('source_aliases', [])}
    originals_by_id = {r['candidate_id']: r for r in original_candidates}
    def unresolved_sample_error(item):
        key = canonical_id.get(item['candidate_id'], item['candidate_id'])
        if key not in approved_ids:
            return False
        record = approved_records[key]
        field = item['field']
        if field not in record.get('review_audit', {}).get('corrected_fields', []):
            return True
        original = originals_by_id[item['candidate_id']]
        return original['fields'].get(field, {}).get('value') == record['fields'].get(field, {}).get('value')
    if any(unresolved_sample_error(item) for item in sample_metrics.get('incorrect_fields', [])):
        blockers.append('HUMAN_SAMPLE_ERRORS_IN_APPROVED_RECORDS')
    if any(item['field'] in {'student_id', 'student_name', 'thesis_title'}
           and (key := canonical_id.get(item['candidate_id'], item['candidate_id'])) in approved_ids
           and item['field'] not in approved_records[key].get('review_audit', {}).get('corrected_fields', [])
           for item in sample_metrics.get('uncertain_fields', [])):
        blockers.append('HUMAN_SAMPLE_CORE_UNCERTAINTY_IN_APPROVED_RECORDS')
    gate = {'phase': 3, 'status': 'blocked' if blockers else 'verified', 'can_start_phase4': not blockers,
            'run_id': run_id, 'run_dir': str(run), 'blocking_reasons': blockers, 'counts': counts,
            'exact_byte_source_aliases_resolved': len(dedupe), 'semester_id': semester_id,
            'taxonomy_sha256': taxonomy_hash, 'config_sha256': config_hash, 'taxonomy_approved': taxonomy_approved,
            'student_source_run_id': student_gate['run_id'], 'faculty_source_run_id': faculty_gate['run_id'],
            'human_golden_sample_accuracy': (sample_metrics['fields'] or None) if not ratified_sample else None,
            'owner_ratified_sample_accuracy': (sample_metrics['fields'] or None) if ratified_sample else None,
            'semester_status': 'draft', 'semester_dates': None,
            'quota_policy': 'balanced-divmod-selected-advisors-v1',
            'code_sha256': code_hashes, 'code_unchanged_during_run': code_unchanged,
            'created_at': datetime.now(timezone.utc).isoformat()}
    _json(run / 'reports/phase3_gate.json', gate)
    reconciliation_report = ['# Phase 3 reconciliation',
        f"Run: {run_id}. Status: {gate['status']}. Semester remains a draft.",
        '| Entity | Source records | Approved | Quarantined/not approved |', '|---|---:|---:|---:|']
    reconciliation_report += [f"| {entity} | {value['source_records']} | {value['approved']} | "
                              f"{value['source_records']-value['approved']} |" for entity, value in counts.items()]
    reconciliation_report += ['', f'Exact-byte source aliases retained: {len(dedupe)}.',
        'All source records remain in review_records.jsonl and staging CSVs. Gold contains approved rows only.',
        'Evidence score measures source/span/semantic checks, not proficiency or a calibrated probability.',
        'Faculty profile approval does not establish semester participation, eligibility or capacity.',
        'Owner-ratified agent-report labels are reported separately from direct manual human labels.',
        'See field_missingness.json, normalization_evidence.json, human_sample_metrics.json and immutable review inputs.']
    (run / 'silver/reconciliation_report.md').write_text('\n'.join(reconciliation_report), encoding='utf-8')
    _json(run / 'gold/snapshot_manifest.json', {'snapshot_id': run_id, 'status': 'approved' if not blockers else 'draft_not_approved', 'gate': gate,
          'inputs': {'student_candidates_sha256': _digest(student_path), 'faculty_profiles_sha256': _digest(faculty_path),
                     'inventory_sha256': inventory_hash, 'taxonomy_sha256': taxonomy_hash, 'config_files': config_hashes,
                     'decisions_sha256': input_hashes.get('decisions'),
                     'sample_reviews_sha256': input_hashes.get('sample_reviews'),
                     'taxonomy_approval_sha256': input_hashes.get('taxonomy_approval'),
                     'owner_acceptance_sha256': input_hashes.get('owner_acceptance'),
                     'quality_assessments_sha256': input_hashes.get('quality_assessments'),
                     'eligibility_sha256': input_hashes.get('eligibility'),
                     'agent_proposals_sha256': input_hashes.get('agent_proposals')},
          'outputs': {f'{entity}.csv': _digest(run / f'gold/{entity}.csv') for entity in ('students', 'advisors')}})
    _json(run / 'manifest.json', {'gate': gate, 'artifacts': [
        {'path': path.relative_to(run).as_posix(), 'sha256': _digest(path)} for parent in ('silver', 'gold', 'reports', 'review')
        for path in sorted((run / parent).iterdir()) if path.is_file()]})
    for parent in ('silver', 'gold', 'reports', 'review'):
        (output / parent).mkdir(exist_ok=True)
        for path in (run / parent).iterdir():
            shutil.copy2(path, output / parent / path.name)
    return gate
