"""Apply an existing explicit owner acceptance; never invent an owner approval."""
import argparse
import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.acceptance import build_owner_decisions, validate_quality_binding, verify_owner_package
from src.data_pipeline.reconcile import stage_sources


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def write_jsonl(path, values):
    path.write_text(''.join(json.dumps(v, ensure_ascii=False)+'\n' for v in values), encoding='utf-8')


def finalize(output, authority, eligibility_path, quality_path, advisory_path=None):
    output = Path(output).resolve()
    receipt, package = verify_owner_package(authority)
    run = output / 'phase3_runs' / receipt['approved_staging_run_id']
    package_manifest = json.loads((package / 'package_manifest.json').read_text(encoding='utf-8'))
    if digest(run / 'manifest.json') != package_manifest['input_manifest_sha256']:
        raise ValueError('approved_staging_manifest_modified')
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    for artifact in manifest['artifacts']:
        if digest(run / artifact['path']) != artifact['sha256']:
            raise ValueError('approved_staging_artifact_modified')
    records = jsonl(run / 'silver/review_records.jsonl')
    eligibility, quality = jsonl(eligibility_path), jsonl(quality_path)
    index = {r['record_id']: r for r in records}
    canonical = {alias['candidate_id']: r['record_id'] for r in records for alias in r.get('source_aliases', [])}
    eligible = {r['record_id']: r for r in eligibility}
    normalization = json.loads((run / 'reports/normalization_evidence.json').read_text(encoding='utf-8'))
    validate_quality_binding(records, normalization, quality)
    # Additional advisory findings can only hold records; an old approval cannot
    # silently ratify a new finding or supply a new correction.
    if advisory_path:
        for finding in jsonl(advisory_path):
            field = finding.get('field_name')
            if field not in {'thesis_abstract', 'thesis_keywords'} or finding.get('proposed_verdict') != 'incorrect':
                continue
            key = canonical.get(finding.get('candidate_id'), finding.get('candidate_id'))
            if key not in index:
                continue
            if finding.get('source_sha256') != index[key]['source_sha256']:
                raise ValueError('supplemental_finding_source_mismatch')
            current = index[key]['fields'].get(field, {}).get('value', '')
            original = finding.get('candidate_value', '')
            if current and current == original:
                eligible[key]['eligible_core'] = False
                eligible[key]['blocking_codes'] = sorted(set(eligible[key]['blocking_codes'] + ['unresolved_optional_field_misclassification']))
                eligible[key]['supplemental_finding'] = finding
    decisions = build_owner_decisions(records, eligibility, quality, receipt, receipt_sha256=digest(authority))
    folder = output / 'review' / ('accepted-inputs-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    folder.mkdir()
    decisions_path = folder / 'owner_decisions.jsonl'
    merged_eligibility = folder / 'eligibility.jsonl'
    write_jsonl(decisions_path, decisions)
    write_jsonl(merged_eligibility, eligibility)
    taxonomy = json.loads((package / 'staging_review/taxonomy_approval_template.json').read_text(encoding='utf-8'))
    taxonomy.update(decision='approve', reviewer=receipt['reviewer'], reviewed_at=receipt['recorded_at'],
                    authority_receipt_sha256=digest(authority), review_kind='owner_ratified_agent_report')
    taxonomy_path = folder / 'taxonomy_approval.json'
    write_json(taxonomy_path, taxonomy)
    with (package / 'sample/sample.csv').open(encoding='utf-8-sig', newline='') as stream:
        sample = list(csv.DictReader(stream))
    labels = []
    for original in sample:
        label = dict(original)
        key = canonical.get(label['candidate_id'], label['candidate_id'])
        record, field = index[key], label['field_name']
        verdict = 'uncertain'
        if field in {'student_id', 'student_name', 'thesis_title'}:
            value = str(record['fields'].get(field, {}).get('value', ''))
            if value != label['candidate_value'] and field in record.get('review_audit', {}).get('corrected_fields', []):
                verdict = 'incorrect' if label['candidate_value'] else 'not_extracted'
            elif value and eligible[key]['eligible_core']:
                verdict = 'correct'
        label.update(review_status='reviewed', reviewer=receipt['reviewer'], reviewed_at=receipt['recorded_at'],
                     field_verdict=verdict, review_kind='owner_ratified_agent_report',
                     authority_receipt_sha256=digest(authority),
                     reviewer_notes='Derived conservatively from owner-ratified original agent core-field report and approved corrections. '
                     'Unassessed optional fields remain uncertain. No direct manual human labels are claimed.')
        labels.append(label)
    labels_path = folder / 'owner_ratified_sample.csv'
    with labels_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(labels[0]))
        writer.writeheader()
        writer.writerows(labels)
    report = stage_sources(output, semester_id=manifest['gate']['semester_id'], decisions_file=decisions_path,
                           taxonomy_approval_file=taxonomy_path, sample_reviews_file=labels_path,
                           proposals_file=package / 'combined_proposals.jsonl', owner_acceptance_file=authority,
                           quality_assessments_file=quality_path, eligibility_file=merged_eligibility)
    write_json(folder / 'execution_manifest.json', {'gate': report, 'authority_receipt_sha256': digest(authority),
               'input_eligibility_sha256': digest(eligibility_path), 'input_quality_sha256': digest(quality_path),
               'supplemental_advisory_sha256': digest(advisory_path) if advisory_path else None,
               'generator_sha256': digest(__file__)})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    parser.add_argument('--authority', type=Path, required=True)
    parser.add_argument('--eligibility', type=Path, required=True)
    parser.add_argument('--quality', type=Path, required=True)
    parser.add_argument('--sample-advisory', type=Path)
    args = parser.parse_args()
    report = finalize(args.output, args.authority, args.eligibility, args.quality, args.sample_advisory)
    print(json.dumps(report, ensure_ascii=True))
    raise SystemExit(0 if report['status'] == 'verified' else 2)
