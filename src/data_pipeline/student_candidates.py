"""Conservative thesis candidates. Evidence-backed candidates are never review approvals."""
from __future__ import annotations

import hashlib
import re
import unicodedata

PARSER_VERSION = 'student-candidates/1.0'


def clean(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', value).split()).strip(' :：')


def _join(blocks):
    text, spans = '', []
    for block in blocks:
        start = len(text)
        text += block['text'] + '\n'
        spans.append((start, len(text) - 1, block))
    return text, spans


def _field(value, start, end, spans, evidence_type='observed'):
    evidence = []
    for left, right, block in spans:
        if start >= right or end <= left:
            continue
        snippet = block['text'][max(0, start-left):min(right, end)-left]
        if not snippet.strip():
            continue
        reference = {key: block[key] for key in ('source_id', 'source_file', 'source_sha256',
                     'block_id', 'locator', 'page', 'extraction_method', 'parser_version', 'archive_chain') if key in block}
        reference['snippet'] = snippet
        evidence.append(reference)
    return {'value': clean(value), 'evidence_type': evidence_type, 'confidence': None, 'evidence': evidence}


def extract_candidates(blocks: list[dict]) -> list[dict]:
    blocks = [b for b in blocks if b.get('kind', 'block') == 'block' and b.get('text', '').strip()]
    if not blocks:
        return []
    front = [b for b in blocks if b.get('page', 1) <= 3][:160]
    text, spans = _join(front)
    all_text, all_spans = _join(blocks)
    ids = {}
    id_pattern = r'(?:mã\s*(?:số\s*)?sinh\s*viên|mssv|msv)\s*[:：]?\s*(\d{8})(?!\d)'
    for match in re.finditer(id_pattern, all_text, re.I):
        ids.setdefault(match[1], _field(match[1], *match.span(1), all_spans))
    # Unlabelled cover IDs are candidates, never evidence of verified identity.
    if not ids:
        for match in re.finditer(r'(?<!\d)\d{8}(?!\d)', text):
            ids.setdefault(match[0], _field(match[0], *match.span(), spans, evidence_type='observed_cover_number'))
    fields = {}
    name = re.search(r'(?:tên\s+sinh\s+viên|họ\s+và\s+tên|sinh\s+viên\s+thực\s+hiện|họ\s+tên)\s*[:：]?\s*([^\n:：]+)', text, re.I)
    if name and not re.search(r'(mã sinh viên|giảng viên|mssv)', name[1], re.I):
        fields['student_name'] = _field(name[1], *name.span(1), spans)
    title = re.search(r'(?:tên\s+đề\s+tài|đề\s+tài)\s*[:：]\s*(.+?)(?=\n\s*(?:tên\s+sinh\s+viên|họ\s+và\s+tên|mã\s+sinh\s+viên|mssv|giảng\s+viên|lớp|ngành)\b|\n\s*\n|\Z)', text, re.I | re.S)
    if not title:
        title = re.search(r'(?:khóa|khoá)\s+luận\s+tốt\s+nghiệp\s*\n+(.*?)\n\s*(?:tên\s+sinh\s+viên|họ\s+và\s+tên|sinh\s+viên\s+thực\s+hiện)', text, re.I | re.S)
    if title and 8 <= len(clean(title[1])) <= 800:
        fields['thesis_title'] = _field(title[1], *title.span(1), spans)
    abstract = re.search(r'(?:^|\n)\s*(?:tóm\s+tắt|abstract)\s*[:：]?\s*\n(.{40,4000}?)(?=\n\s*(?:từ\s+khóa|từ\s+khoá|keywords|chương\s+\d)|\Z)', all_text, re.I | re.S)
    if abstract:
        fields['thesis_abstract'] = _field(abstract[1], *abstract.span(1), all_spans)
    keywords = re.search(r'(?:từ\s+khóa|từ\s+khoá|keywords)\s*[:：]\s*([^\n]{3,500})', all_text, re.I)
    if keywords:
        fields['thesis_keywords'] = _field(keywords[1], *keywords.span(1), all_spans)
    technology_mentions = []
    for term in ('Python', 'Java', 'JavaScript', 'TypeScript', 'PostgreSQL', 'MySQL', 'MongoDB',
                 'PyTorch', 'TensorFlow', 'React', 'Docker', 'FastAPI', 'Spring Boot'):
        match = re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', all_text, re.I)
        if match:
            technology_mentions.append(_field(match[0], *match.span(), all_spans, evidence_type='inferred_from_thesis'))
    result = []
    for student_id, id_field in (ids.items() if ids else [(None, None)]):
        candidate_fields = dict(fields)
        if id_field:
            candidate_fields['student_id'] = id_field
        reasons = []
        for name in ('student_id', 'student_name', 'thesis_title'):
            if name not in candidate_fields:
                reasons.append(f'missing_{name}')
        if len(ids) > 1:
            reasons.append('multiple_student_ids')
            # Shared document-level name/title cannot be attributed to each person.
            candidate_fields = {'student_id': id_field}
        if id_field and id_field['evidence_type'] == 'observed_cover_number':
            reasons.append('unverified_student_id')
        source = blocks[0]
        key = f"{source.get('source_id', source['source_sha256'])}:{student_id or 'unknown'}"
        result.append({'candidate_id': hashlib.sha256(key.encode()).hexdigest(),
                       'source_id': source.get('source_id', source['source_sha256']),
                       'source_file': source['source_file'], 'source_sha256': source['source_sha256'],
                       'archive_chain': source.get('archive_chain', []), 'parser_version': PARSER_VERSION,
                       'fields': candidate_fields, 'technology_mentions': technology_mentions,
                       'skills_tags': [], 'skill_proficiency': None,
                       'review_status': 'needs_review', 'review_reasons': reasons or ['human_review_required'],
                       'status': 'quarantined' if reasons else 'extracted'})
    return result


def validate_evidence(candidates: list[dict], blocks: list[dict]) -> list[dict]:
    index = {}
    errors = []
    for block in blocks:
        if 'block_id' not in block:
            continue
        previous = index.get(block['block_id'])
        if previous is not None and previous != block:
            errors.append({'field': 'block_id', 'reason': 'conflicting_block_identity'})
        index[block['block_id']] = block
    for candidate in candidates:
        values = list(candidate['fields'].items()) + [('technology_mention', f) for f in candidate.get('technology_mentions', [])]
        for field_name, field in values:
            references = field.get('evidence', [])
            valid = bool(references)
            snippets = []
            for ev in references:
                block = index.get(ev.get('block_id'))
                valid = valid and bool(block) and ev.get('snippet', '') in block['text'] if block else False
                if block:
                    valid = valid and all(ev.get(key) == block.get(key) for key in
                                          ('source_id', 'source_file', 'source_sha256', 'locator', 'page',
                                           'archive_chain', 'extraction_method', 'parser_version'))
                    valid = valid and all(candidate.get(key) == block.get(key) for key in
                                          ('source_id', 'source_file', 'source_sha256', 'archive_chain'))
                snippets.append(ev.get('snippet', ''))
            if not valid or clean(str(field['value'])) not in clean(' '.join(snippets)):
                errors.append({'candidate_id': candidate['candidate_id'], 'field': field_name, 'reason': 'invalid_source_evidence'})
    return errors
