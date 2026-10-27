"""Technical-only review workflow, isolated from every real source and approval."""
import csv
import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.data_pipeline import normalization, reconcile
from src.data_pipeline.csv_contracts import HEADERS
from src.data_pipeline.review_decisions import record_hash


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


def seal_phase(output, number, artifact, records, **metadata):
    run_id = f'phase{number}-technical-fixture'
    run = output / f'phase{number}_runs' / run_id
    write_jsonl(run / artifact, records)
    gate = {'phase': number, 'status': 'verified', f'can_start_phase{number+1}': True,
            'run_id': run_id, 'created_at': '2026-10-21T12:00:00+00:00', **metadata}
    gate_name = f'reports/phase{number}_gate.json'
    write_json(run / gate_name, gate)
    write_json(output / gate_name, gate)
    write_json(run / 'manifest.json', {'gate': gate, 'artifacts': [
        {'path': name, 'sha256': digest(run / name)} for name in (artifact, gate_name)]})
    return gate


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    project = tmp_path / 'technical-project'
    for entity, headers in HEADERS.items():
        path = project / f'docs/{entity}_import.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            csv.writer(stream).writerow(headers)
    configs = project / 'configs/data'
    configs.mkdir(parents=True)
    taxonomy_path = configs / 'taxonomy_v1.yaml'
    taxonomy_path.write_text("schema_version: '1.0'\ntaxonomy_version: '1.0'\ngroups:\n  programming_languages:\n    python:\n      aliases: [Python]\n", encoding='utf-8')
    for name in ('feature_allowlist.yaml', 'feature_excluded.yaml'):
        (configs / name).write_text('technical_fixture: true\n', encoding='utf-8')
    load_taxonomy = normalization.load_taxonomy
    monkeypatch.setattr(normalization, 'load_taxonomy', lambda: load_taxonomy(taxonomy_path))
    monkeypatch.setattr(reconcile, 'ROOT', project)
    output = tmp_path / 'technical-output'
    (output / 'reports').mkdir(parents=True)
    inventory = output / 'reports/input_inventory.csv'
    inventory.write_text('technical-fixture-inventory\n', encoding='utf-8')
    source = {'source_id': 'technical-source', 'source_file': 'technical-fixture.pdf',
              'source_sha256': 'a' * 64, 'archive_chain': []}
    def field(value):
        return {'value': value, 'evidence_type': 'observed', 'confidence': None, 'evidence': [
            {**source, 'locator': 'page:1/block:0', 'page': 1, 'block_id': 'technical-block',
             'snippet': value, 'extraction_method': 'technical_fixture', 'parser_version': 'technical/1'}]}
    student = {**source, 'candidate_id': 'technical-candidate', 'review_status': 'needs_review',
               'review_reasons': ['human_review_required'], 'status': 'extracted', 'technology_mentions': [],
               'fields': {'student_id': field('STUDENT-TECH-001'), 'student_name': field('Technical Learner'),
                          'thesis_title': field('Python technical study')}}
    student_gate = seal_phase(output, 1, 'bronze/student_candidates.jsonl', [student], input_inventory_sha256=digest(inventory))
    advisor = {'advisor_id': 'ADVISOR-TECH-001', 'advisor_name': 'Technical Advisor',
               'source_sha256': 'b' * 64, 'source_url': 'https://example.test/lecturer/technical',
               'retrieved_at': '2026-10-21T12:00:00+00:00', 'research_topics': ['Python technical research'],
               'teaching_topics': [], 'review_status': 'needs_review', 'evidence': [
                   {'field': 'research_topics', 'source_url': 'https://example.test/lecturer/technical',
                    'snippet': 'Python technical research'}]}
    seal_phase(output, 2, 'silver/advisors.jsonl', [advisor])
    return {'output': output, 'student': student, 'student_gate': student_gate, 'temporary_root': tmp_path}


def write_reviews(workflow, first_gate):
    """Human-like labels are explicit test inputs for known technical fixtures only."""
    output = workflow['output']
    run = Path(first_gate['run_dir'])
    records = [json.loads(line) for line in (run / 'silver/review_records.jsonl').read_text(encoding='utf-8').splitlines()]
    decisions = [{'record_id': r['record_id'], 'record_sha256': record_hash(r), 'decision': 'approve',
                  'reviewer': 'technical-fixture-reviewer', 'reviewed_at': '2026-10-21T13:00:00+00:00',
                  'evidence_confidence': 0.8, 'notes': 'Synthetic technical input; no real approval.'} for r in records]
    decisions_path = output / 'technical-decisions.jsonl'
    write_jsonl(decisions_path, decisions)
    approval = json.loads((run / 'review/taxonomy_approval_template.json').read_text(encoding='utf-8'))
    approval.update(decision='approve', reviewer='technical-fixture-reviewer', reviewed_at='2026-10-21T13:00:00+00:00')
    approval_path = output / 'technical-taxonomy-review.json'
    write_json(approval_path, approval)
    labels = []
    candidate = workflow['student']
    for name in ('student_id', 'student_name', 'thesis_title', 'thesis_abstract', 'thesis_keywords', 'technology_mentions'):
        value = '[]' if name == 'technology_mentions' else candidate['fields'].get(name, {}).get('value', '')
        labels.append({'run_id': workflow['student_gate']['run_id'], 'candidate_id': candidate['candidate_id'],
                       'source_sha256': candidate['source_sha256'], 'field_name': name, 'candidate_value': value,
                       'review_status': 'reviewed', 'reviewer': 'technical-fixture-reviewer',
                       'reviewed_at': '2026-10-21T13:00:00+00:00',
                       'field_verdict': 'missing_in_source' if value in {'', '[]'} else 'correct'})
    labels_path = output / 'technical-labels.csv'
    with labels_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(labels[0]))
        writer.writeheader()
        writer.writerows(labels)
    return dict(decisions_file=decisions_path, taxonomy_approval_file=approval_path, sample_reviews_file=labels_path)


def test_bound_workflow_blocks_without_reviews_then_can_accept_technical_approvals(workflow):
    output = workflow['output']
    first = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM')
    assert first['status'] == 'blocked'
    assert not first['can_start_phase4']
    assert 'HUMAN_RECORD_REVIEW_REQUIRED' in first['blocking_reasons']
    assert all(c['approved'] == 0 for c in first['counts'].values())
    inputs = write_reviews(workflow, first)
    authority_path = output / 'technical-owner-receipt.json'
    write_json(authority_path, {'scope': 'Isolated technical-fixture owner receipt; no real authority.'})
    accepted = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM', owner_acceptance_file=authority_path, **inputs)
    assert accepted['status'] == 'verified', accepted['blocking_reasons']
    assert accepted['can_start_phase4']
    assert accepted['counts'] == {'students': {'source_records': 1, 'approved': 1},
                                  'advisors': {'source_records': 1, 'approved': 1}}
    run = Path(accepted['run_dir'])
    assert workflow['temporary_root'] in run.parents
    for entity in ('students', 'advisors'):
        with (run / f'gold/{entity}.csv').open(encoding='utf-8-sig', newline='') as stream:
            records = list(csv.DictReader(stream))
        assert len(records) == 1 and records[0]['review_status'] == 'approved'
        proficiency = records[0]['skill_proficiency_json' if entity == 'students' else 'expertise_proficiency_json']
        assert proficiency == ''
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    assert all(digest(run / item['path']) == item['sha256'] for item in manifest['artifacts'])
    snapshot = json.loads((run / 'gold/snapshot_manifest.json').read_text(encoding='utf-8'))
    assert snapshot['status'] == 'approved'
    assert snapshot['inputs']['decisions_sha256'] == digest(inputs['decisions_file'])
    assert snapshot['inputs']['owner_acceptance_sha256'] == digest(authority_path)
    assert (run / 'review/owner_acceptance.json').read_bytes() == authority_path.read_bytes()


def test_predecessor_candidate_tampering_fails_before_a_new_phase3_run(workflow):
    output = workflow['output']
    path = output / 'phase1_runs' / workflow['student_gate']['run_id'] / 'bronze/student_candidates.jsonl'
    with path.open('a', encoding='utf-8') as stream:
        stream.write('{}\n')
    with pytest.raises(ValueError, match='predecessor_artifact_hash_mismatch'):
        reconcile.stage_sources(output, semester_id='TECHNICAL-TERM')
    assert not (output / 'phase3_runs').exists()


def test_approved_record_with_uncertain_sampled_core_field_cannot_release_gold(workflow):
    """A known label for another student must not hide an unresolved approved ID."""
    output = workflow['output']
    second = copy.deepcopy(workflow['student'])
    second.update(candidate_id='technical-second-candidate', source_id='technical-second-source',
                  source_file='technical-second.pdf', source_sha256='c' * 64)
    second['fields']['student_id']['value'] = 'STUDENT-TECH-002'
    for field in second['fields'].values():
        for reference in field['evidence']:
            reference.update(source_id=second['source_id'], source_file=second['source_file'],
                             source_sha256=second['source_sha256'], block_id='technical-second-block',
                             snippet=field['value'])
    seal_phase(output, 1, 'bronze/student_candidates.jsonl', [workflow['student'], second],
               input_inventory_sha256=digest(output / 'reports/input_inventory.csv'))
    first = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM')
    inputs = write_reviews(workflow, first)
    labels_path = inputs['sample_reviews_file']
    with labels_path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames
        labels = list(reader)
    second_labels = copy.deepcopy(labels)
    for label in second_labels:
        label.update(candidate_id=second['candidate_id'], source_sha256=second['source_sha256'])
        if label['field_name'] == 'student_id':
            label.update(candidate_value='STUDENT-TECH-002', field_verdict='uncertain')
    with labels_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(labels + second_labels)
    result = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM', **inputs)
    metrics = json.loads((Path(result['run_dir']) / 'reports/human_sample_metrics.json').read_text(encoding='utf-8'))
    assert metrics['complete'] and metrics['uncertain_labels'] == 1
    assert metrics['fields']['student_id']['known_labels'] == 1
    assert result['status'] == 'blocked'
    assert not result['can_start_phase4']
    assert any('UNCERTAIN' in reason and 'CORE' in reason for reason in result['blocking_reasons'])
    snapshot = json.loads((Path(result['run_dir']) / 'gold/snapshot_manifest.json').read_text(encoding='utf-8'))
    assert snapshot['status'] == 'draft_not_approved'


def test_arbitrary_owner_receipt_cannot_ratify_labels_or_release_gold(workflow):
    output = workflow['output']
    first = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM')
    inputs = write_reviews(workflow, first)
    receipt = output / 'technical-ratification.json'
    write_json(receipt, {'scope': 'Technical test fixture; no human data or approval.'})
    path = inputs['sample_reviews_file']
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row.update(review_kind='owner_ratified_agent_report', authority_receipt_sha256=digest(receipt))
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    blocked = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM', **inputs)
    assert 'OWNER_SAMPLE_RATIFICATION_RECEIPT_REQUIRED' in blocked['blocking_reasons']
    accepted = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM', owner_acceptance_file=receipt, **inputs)
    assert accepted['status'] == 'blocked'
    assert 'OWNER_RATIFICATION_VALIDATION_FAILED' in accepted['blocking_reasons']
    assert accepted['human_golden_sample_accuracy'] is None
    assert accepted['owner_ratified_sample_accuracy']['student_id']['known_labels'] == 1
    write_json(receipt, {'scope': 'A different technical receipt'})
    stale = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM', owner_acceptance_file=receipt, **inputs)
    assert 'OWNER_SAMPLE_RATIFICATION_RECEIPT_MISMATCH' in stale['blocking_reasons']


def test_bound_owner_ratification_accepts_valid_inputs_and_blocks_rehashed_tampering(workflow):
    """No real approvals: a sealed technical package exercises the central authority gate."""
    from collections import defaultdict
    from src.data_pipeline.acceptance import build_owner_decisions
    from src.data_pipeline.evidence_quality import evaluate_tag_checks

    output = workflow['output']
    first = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM')
    run = Path(first['run_dir'])
    inputs = write_reviews(workflow, first)
    records = [json.loads(line) for line in (run / 'silver/review_records.jsonl').read_text(encoding='utf-8').splitlines()]
    index = {record['record_id']: record for record in records}
    normalization_rows = json.loads((run / 'reports/normalization_evidence.json').read_text(encoding='utf-8'))
    eligibility = [{'record_id': r['record_id'], 'record_sha256': record_hash(r),
                    'eligible_core': True, 'blocking_codes': []} for r in records]
    quality = []
    for normalized in normalization_rows:
        key, source = normalized['record_id'], normalized['source']
        record = index[key]
        units = defaultdict(list)
        for mention in source['tags']:
            field = mention['source_field']
            text = (record['fields'][field]['value'] if record['entity_type'] == 'students'
                    else next(value for value in record[field]
                              if value[mention['start']:mention['end']] == mention['matched_text']))
            units[(mention['output_column'], mention['tag'])].append({
                **mention, 'source_text': text,
                'refs': [source['refs'][i] for i in mention['ref_indexes']],
                'checks': dict.fromkeys(('source', 'span', 'semantic'), 'pass')})
        tags = [{'tag': tag, 'output_column': column, 'group': occurrences[0]['group'],
                 'source_sha256': record['source_sha256'], 'evidence_sha256': record_hash(occurrences),
                 'occurrences': occurrences, 'checks': dict.fromkeys(('source', 'span', 'semantic'), 'pass')}
                for (column, tag), occurrences in units.items()]
        quality.append(evaluate_tag_checks(key, record_hash(record), tags))

    package = output / 'technical-approved-package'
    template = package / 'staging_review/decisions_template.csv'
    template.parent.mkdir(parents=True)
    template.write_bytes((run / 'review/decisions_template.csv').read_bytes())
    package_manifest = package / 'package_manifest.json'
    write_json(package_manifest, {'phase3_run_id': first['run_id'], 'artifacts': [
        {'path': 'staging_review/decisions_template.csv', 'sha256': digest(template)}]})
    receipt = {'authority_type': 'explicit_owner_messages_in_current_conversation',
               'package_path': str(package), 'package_manifest_sha256': digest(package_manifest),
               'approved_staging_run_id': first['run_id'],
               'owner_quote': 'Technical fixture only; no actual owner acceptance.',
               'reviewer': 'owner:technical-fixture', 'recorded_at': '2026-10-21T13:00:00Z',
               'rubric_version': 'source-span-semantic-v1'}
    receipt_path = output / 'technical-valid-owner.json'
    write_json(receipt_path, receipt)
    decisions = build_owner_decisions(records, eligibility, quality, receipt, receipt_sha256=digest(receipt_path))
    write_jsonl(inputs['decisions_file'], decisions)
    eligibility_path, quality_path = output / 'technical-eligibility.jsonl', output / 'technical-quality.jsonl'
    write_jsonl(eligibility_path, eligibility)
    write_jsonl(quality_path, quality)
    path = inputs['sample_reviews_file']
    with path.open(encoding='utf-8-sig', newline='') as stream:
        labels = list(csv.DictReader(stream))
    for row in labels:
        row.update(review_kind='owner_ratified_agent_report', authority_receipt_sha256=digest(receipt_path))
        if row['field_name'] not in {'student_id', 'student_name', 'thesis_title'}:
            row['field_verdict'] = 'uncertain'
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(labels[0]))
        writer.writeheader()
        writer.writerows(labels)
    bound_inputs = {**inputs, 'owner_acceptance_file': receipt_path,
                    'quality_assessments_file': quality_path, 'eligibility_file': eligibility_path}
    valid = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM', **bound_inputs)
    assert valid['status'] == 'verified', valid['blocking_reasons']
    assert valid['counts']['students']['approved'] == valid['counts']['advisors']['approved'] == 1
    assert valid['human_golden_sample_accuracy'] is None
    assert valid['owner_ratified_sample_accuracy']['student_id']['accuracy'] == 1

    # A newly computed assessment hash cannot legitimize a different source.
    forged = copy.deepcopy(quality)
    forged[0]['tags'][0]['source_sha256'] = 'f' * 64
    forged[0] = evaluate_tag_checks(forged[0]['record_id'], forged[0]['record_sha256'], forged[0]['tags'])
    write_jsonl(quality_path, forged)
    forged_decisions = build_owner_decisions(records, eligibility, forged, receipt,
                                            receipt_sha256=digest(receipt_path))
    write_jsonl(inputs['decisions_file'], forged_decisions)
    source_tamper = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM', **bound_inputs)
    assert source_tamper['status'] == 'blocked'
    assert 'OWNER_RATIFICATION_VALIDATION_FAILED' in source_tamper['blocking_reasons']

    # Even otherwise valid approve decisions cannot override a bound HOLD assessment.
    write_jsonl(quality_path, quality)
    write_jsonl(inputs['decisions_file'], decisions)
    eligibility[0].update(eligible_core=False, blocking_codes=['technical_identity_conflict'])
    write_jsonl(eligibility_path, eligibility)
    held = reconcile.stage_sources(output, semester_id='TECHNICAL-TERM', **bound_inputs)
    assert held['status'] == 'blocked'
    assert 'OWNER_RATIFICATION_VALIDATION_FAILED' in held['blocking_reasons']
