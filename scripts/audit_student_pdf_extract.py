"""Advisory audit of the assigned frozen first 73 student records; never approval."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_pipeline.review_decisions import record_hash
from src.data_pipeline.student_candidates import clean, validate_evidence

P1 = ROOT / 'data_rebuild/v1/phase1_runs/20261021T154719Z-b40d7836'
P3 = ROOT / 'data_rebuild/v1/phase3_runs/20261021T160845Z-0126fe47'
OUTPUT = ROOT / 'data_rebuild/v1/review/full_audit'


def read_jsonl(path):
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def evidence(block, snippet=None):
    return {**{key: block[key] for key in ('source_id', 'source_file', 'source_sha256',
              'block_id', 'locator', 'page', 'extraction_method', 'parser_version', 'archive_chain') if key in block},
            'snippet': block['text'] if snippet is None else snippet}


def corrected_field(value, blocks, snippets=None):
    return {'value': clean(value), 'evidence_type': 'observed', 'confidence': None,
            'evidence': [evidence(block, snippet) for block, snippet in
                         zip(blocks, snippets or [None] * len(blocks))]}


def run():
    frozen = list(read_jsonl(P3 / 'silver/review_records.jsonl'))
    records = sorted((r for r in frozen if r['entity_type'] == 'students'), key=lambda r: r['record_id'])[:73]
    assert len(records) == 73
    wanted = {r['source_id'] for r in records}
    blocks = defaultdict(list)
    for block in read_jsonl(P1 / 'bronze/document_blocks.jsonl'):
        if block['source_id'] in wanted:
            blocks[block['source_id']].append(block)
    pages = defaultdict(list)
    for page in read_jsonl(P1 / 'bronze/page_outcomes.jsonl'):
        if page['source_id'] in wanted:
            pages[page['source_id']].append(page)
    members = list(csv.DictReader((P1 / 'reports/archive_member_manifest.csv').open(encoding='utf-8-sig')))

    def block_at(index, locator):
        return next(b for b in blocks[records[index]['source_id']] if b['locator'] == locator)

    corrections = defaultdict(dict)
    # All choices below follow inspection of each assigned canonical cover excerpt.
    # Name/parser mistakes: exact labelled names remain in source blocks.
    for index, locator in [(6, 'page:1/block:5'), (14, 'page:1/block:6'),
                           (41, 'page:1/block:8'), (50, 'page:1/block:5'), (62, 'page:1/block:5')]:
        block = block_at(index, locator)
        name = re.search(r':\s*([^\n]+)', block['text']).group(1).strip()
        corrections[index]['student_name'] = corrected_field(name, [block], [name])
    # Missing or contaminated titles: take only the directly evidenced title lines.
    title_locators = {
        3: ['page:1/block:5', 'page:1/block:6'],
        19: ['page:2/block:4', 'page:2/block:5'],
        32: ['page:2/block:4', 'page:2/block:5'],
        59: ['page:2/block:3', 'page:2/block:4'],
    }
    for index, locators in title_locators.items():
        selected = [block_at(index, locator) for locator in locators]
        values = [block['text'] for block in selected]
        if index == 32:
            values[0] = values[0].split('\n', 1)[1]
        corrections[index]['thesis_title'] = corrected_field(' '.join(values), selected, values)
    # Directly labelled IDs were missed because of zero-width characters/table layout.
    for index, locator in [(6, 'page:2/block:5'), (50, 'page:3/block:5')]:
        block = block_at(index, locator)
        value = records[index]['fields']['student_id']['value']
        corrections[index]['student_id'] = corrected_field(value, [block], [value])
    table_label = block_at(65, '/document[1]/body[1]/tbl[1]/tr[2]/tc[1]/p[1]')
    table_value = block_at(65, '/document[1]/body[1]/tbl[1]/tr[2]/tc[2]/p[1]')
    corrections[65]['student_id'] = corrected_field(records[65]['fields']['student_id']['value'], [table_label, table_value])

    # Additional heading prefixes are normalization issues, not additional thesis text.
    for index in (44, 47, 62):
        field = records[index]['fields']['thesis_title']
        prefix = re.match(r'^(?:T\u00ean\s+\u0111\u1ec1\s+t\u00e0i|\u0110\u1ec0\s*T\u00c0\s*I)\s*:?\s*', field['value'], re.I)
        if prefix:
            value = field['value'][prefix.end():]
            corrections[index]['thesis_title'] = {**field, 'value': value, 'confidence': None}

    reviewed_at = datetime.now(timezone.utc).isoformat()
    audit, proposals, correction_errors = [], [], []
    for index, row in enumerate(records):
        source_blocks = blocks[row['source_id']]
        front = [b for b in source_blocks if (b.get('page') or 1) <= 3][:160]
        all_front_text = '\n'.join(b['text'] for b in front)
        front_ids = sorted(set(re.findall(r'(?<!\d)\d{8}(?!\d)', all_front_text)))
        fields = row['fields']
        candidate_id = fields.get('student_id', {}).get('value')
        findings = []
        integrity_errors = validate_evidence([row], source_blocks)
        if integrity_errors:
            findings.append({'code': 'evidence_link_error', 'severity': 'blocking', 'details': integrity_errors})
        if index in (0, 57):
            findings.append({'code': 'conflicting_student_id_lengths', 'severity': 'blocking',
                             'details': 'Eight-digit outer-cover number conflicts with nine-digit labelled inner-cover number; cannot infer a correction.',
                             'evidence': [evidence(b) for b in front if re.search(r'\d{8,9}', b['text'])]})
        if index == 10:
            findings.append({'code': 'conflicting_cover_identity', 'severity': 'blocking',
                             'details': 'Outer spine gives a different name/ID than labelled front and inner-cover student; possible reused template, requires owner confirmation.',
                             'evidence': [evidence(block_at(index, p)) for p in ('page:1/block:6', 'page:1/block:9', 'page:2/block:7')]})
        if len(front_ids) > 1 and index != 10:
            findings.append({'code': 'multiple_front_cover_numbers', 'severity': 'review',
                             'details': 'More than one eight-digit cover number; number context needs owner review.', 'observed_numbers': front_ids})
        if index in (6, 14, 41, 50, 62):
            findings.append({'code': 'incorrect_student_name_extraction', 'severity': 'blocking',
                             'details': 'Extracted value is a zero-width character or generic metadata label, not the explicitly named student.'})
        if index in (19, 59):
            findings.append({'code': 'missing_title_with_source_evidence', 'severity': 'blocking',
                             'details': 'Canonical cover blocks contain a title that the parser did not populate.'})
        if index == 32:
            findings.extend([
                {'code': 'title_includes_non_title_metadata', 'severity': 'blocking',
                 'details': 'Extracted title includes city/date and a repeated cover; proposed title is limited to actual title blocks.'},
                {'code': 'missing_id_source_seven_digits', 'severity': 'blocking',
                 'details': 'Inner cover explicitly supplies seven digits; no supported eight-digit ID can be reconstructed.',
                 'evidence': [evidence(block_at(index, 'page:2/block:7'))]},
            ])
        if index in (3, 44, 47, 62):
            findings.append({'code': 'title_contains_field_label_prefix', 'severity': 'review',
                             'details': 'Title value includes the source metadata label. Pending correction removes only that label.'})
        if index == 59:
            findings.append({'code': 'ocr_word_spacing_uncertainty', 'severity': 'review',
                             'details': 'OCR cover title is directly evidenced but merges some word spaces. Pending correction preserves raw OCR spelling; rendered original needs owner confirmation.'})
        quarantined_pages = [p['page'] for p in pages[row['source_id']] if p['status'] in {'quarantined', 'failed'}]
        if quarantined_pages:
            findings.append({'code': 'page_extraction_requires_review', 'severity': 'review',
                             'details': 'Source has explicitly quarantined/failed pages; front-matter identity checks do not establish full document completeness.',
                             'pages': quarantined_pages})
        if row.get('source_aliases'):
            findings.append({'code': 'source_aliases_retained', 'severity': 'review',
                             'details': 'P3 retains multiple source aliases; byte identity does not itself certify unique student identity.'})
        if not findings:
            findings.append({'code': 'front_fields_supported_in_agent_text_review', 'severity': 'information',
                             'details': 'Agent inspected the canonical front-matter text. Student name, labelled ID and title align with the current values; owner approval still pending.'})
        if row['archive_chain']:
            member = next((m for m in members if m['parent_source_file'] + '!' + m['member_path'] == row['source_file'] and m.get('member_sha256') == row['source_sha256']), None)
            source_path = Path(member['extracted_path']) if member else None
        else:
            source_path = ROOT / 'data/1.pdfs' / row['source_file']
        source_matches = bool(source_path and source_path.is_file() and file_hash(source_path) == row['source_sha256'])
        if not source_matches:
            findings.append({'code': 'source_file_hash_unverified', 'severity': 'blocking', 'details': 'Current private source bytes could not be matched.'})
        entry = {'record_id': row['record_id'], 'record_sha256': record_hash(row),
                 'source_sha256': row['source_sha256'], 'entity_type': 'students',
                 'reviewer': 'agent:pdf_extract', 'review_kind': 'agent_advisory', 'reviewed_at': reviewed_at,
                 'checks': {'assigned_sorted_index': index, 'frozen_p3_run': P3.name, 'canonical_p1_run': P1.name,
                            'source_file_sha256_matches': source_matches, 'canonical_source_block_count': len(source_blocks),
                            'front_blocks_examined': len(front), 'fields_semantically_examined': ['student_id', 'student_name', 'thesis_title'],
                            'all_field_and_technology_evidence_validated': not integrity_errors,
                            'evidence_error_count': len(integrity_errors), 'front_numbers': front_ids,
                            'proven_personal_skills_not_inferred': row.get('skills_tags') == [] and row.get('skill_proficiency') is None,
                            'human_accuracy_measured': False, 'full_document_visual_review': False},
                 'findings': findings, 'recommendation': 'owner_source_confirmation_required' if any(f['severity'] == 'blocking' for f in findings)
                    else 'owner_review_required_with_explicit_limitations',
                 'review_status': 'pending', 'evidence_confidence': None}
        audit.append(entry)
        if corrections[index]:
            changed = {**row, 'fields': {**fields, **corrections[index]}}
            errors = validate_evidence([changed], source_blocks)
            if errors:
                correction_errors.extend({'record_id': row['record_id'], **error} for error in errors)
            else:
                proposals.append({'record_id': row['record_id'], 'record_sha256': record_hash(row),
                                  'reviewer': 'agent:pdf_extract', 'reviewed_at': reviewed_at, 'decision': 'needs_review',
                                  'corrections': corrections[index], 'evidence_confidence': None,
                                  'notes': 'Agent advisory proposal only; direct canonical source evidence, owner approval required.'})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, values in [('pdf_extract.jsonl', audit), ('pdf_extract_proposals.jsonl', proposals)]:
        (OUTPUT / name).write_text(''.join(json.dumps(value, ensure_ascii=False) + '\n' for value in values), encoding='utf-8')
    summary = {'frozen_p3_run': P3.name, 'canonical_p1_run': P1.name, 'agent': 'agent:pdf_extract', 'records_audited': len(audit),
               'assigned_sorted_indices': [0, 72], 'source_hashes_verified': sum(r['checks']['source_file_sha256_matches'] for r in audit),
               'evidence_error_records': sum(bool(r['checks']['evidence_error_count']) for r in audit),
               'records_with_blocking_findings': sum(any(f['severity'] == 'blocking' for f in row['findings']) for row in audit),
               'finding_counts': dict(Counter(f['code'] for row in audit for f in row['findings'])),
               'proposal_records': len(proposals), 'proposed_fields': sum(len(p['corrections']) for p in proposals),
               'proposal_validation_errors': correction_errors, 'human_approved_records': 0,
               'audit_script_sha256': file_hash(Path(__file__)),
               'limitations': ['Agent semantic review of canonical cover text for all assigned records, not full-PDF visual proofreading.',
                              'All source hashes and populated field/technology evidence were checked mechanically.',
                              'Matching evidence proves traceability, not truthful authorship, institutional acceptance or proven skill.',
                              'Explicit ID conflicts and malformed seven-digit IDs remain unresolved; no digits synthesized.',
                              'No optional abstract/keyword field accuracy or OCR character accuracy score has been measured.']}
    (OUTPUT / 'pdf_extract_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k not in {'finding_counts', 'limitations', 'proposal_validation_errors'}}))
    return summary


if __name__ == '__main__':
    run()
