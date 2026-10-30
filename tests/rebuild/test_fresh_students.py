import csv
import hashlib
from importlib import import_module, util
import json
from pathlib import Path
import zipfile

import pytest


def module():
    assert util.find_spec('src.data_pipeline.fresh_students'), 'fresh student collector missing'
    return import_module('src.data_pipeline.fresh_students')


def make_docx(path, paragraphs):
    from xml.sax.saxutils import escape
    body = ''.join(f'<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>' for text in paragraphs)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '</w:body></w:document>')


def test_fresh_full_document_copy_aliases_and_candidate_provenance(tmp_path):
    m = module()
    source = tmp_path / 'source'
    source.mkdir()
    paragraphs = ['KHÓA LUẬN TỐT NGHIỆP', 'Tên đề tài: Xây dựng hệ thống phần mềm phân công',
                  'Sinh viên thực hiện: Nguyễn Văn B', 'Mã sinh viên: 11220001',
                  'Giảng viên hướng dẫn: TS. Nguyễn Văn A', 'Hà Nội, tháng 6 năm 2025']
    paragraphs += ['Text filler'] * 130 + ['This full-document section uses PyTorch.']
    make_docx(source / 'original.docx', paragraphs)
    (source / 'alias.docx').write_bytes((source / 'original.docx').read_bytes())
    (source / 'desktop.ini').write_text('metadata')
    before = hashlib.sha256((source / 'original.docx').read_bytes()).hexdigest()
    output = tmp_path / 'new'
    report = m.collect_students(source, output, ocr='off')
    assert report['source_files'] == 2 and report['unique_content'] == 1
    assert report['duplicate_aliases'] == 1 and report['system_files_excluded'] == 1
    docs = [json.loads(x) for x in (output / 'documents.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(docs) == 1 and len(docs[0]['source_aliases']) == 2
    students = [json.loads(x) for x in (output / 'students.jsonl').read_text(encoding='utf-8').splitlines()]
    assert students[0]['fields']['student_id']['value'] == '11220001'
    assert any(x['value'].lower() == 'pytorch' for x in students[0]['technology_mentions'])
    # OOXML paragraphs have no rendered page positions; cannot assert pages1-2.
    assert students[0]['temporal']['status'] == 'unknown'
    assert students[0]['supervisor_names'][0]['value'] == 'TS. Nguyễn Văn A'
    assert students[0]['review_status'] == 'needs_review'
    assert students[0]['feature_available_at'] is None
    assert hashlib.sha256((source / 'original.docx').read_bytes()).hexdigest() == before
    raw = output / docs[0]['raw_path']
    assert raw.is_file() and hashlib.sha256(raw.read_bytes()).hexdigest() == before
    assert m.verify_collection(output)['source_files'] == 2


def test_unreadable_or_unsupported_source_is_not_lost(tmp_path):
    m = module()
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'broken.pdf').write_bytes(b'not a valid pdf')
    (source / 'source.rar').write_bytes(b'archive awaiting extraction')
    result = m.collect_students(source, tmp_path / 'out', ocr='off')
    assert result['source_files'] == 2 and result['failed_or_pending_documents'] == 2
    assert result['training_ready'] is False


def test_output_cannot_overwrite_sources_or_existing_manual_data(tmp_path):
    m = module()
    source = tmp_path / 'source'
    source.mkdir()
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'manual.csv').write_text('keep')
    with pytest.raises(FileExistsError):
        m.collect_students(source, out)
    with pytest.raises(ValueError, match='overlap'):
        m.collect_students(source, source / 'nested')


def test_cover_dates_require_context_not_citation_years():
    m = module()
    blocks = [{'kind': 'block', 'text': 'Tài liệu tham khảo Smith (2025)', 'page': 1,
               'source_id': 'a', 'source_file': 'x', 'source_sha256': 'f' * 64,
               'block_id': 'a/1', 'locator': 'page:1', 'extraction_method': 'test', 'parser_version': 'test'}]
    assert m.cover_metadata(blocks)['temporal']['status'] == 'unknown'


def cover_block(text, page=1):
    return {'kind': 'block', 'text': text, 'page': page, 'source_id': 'a',
            'source_file': 'x', 'source_sha256': 'f' * 64, 'block_id': f'a/{page}/{text}',
            'locator': f'page:{page}', 'extraction_method': 'test', 'parser_version': 'test'}


def test_month_slash_year_recognized_but_page_three_never_sets_cohort():
    m = module()
    result = m.cover_metadata([cover_block('Hà Nội, tháng 6/2025')])
    assert result['temporal']['version'] == 'V3'
    assert result['temporal']['academic_cohort'] == '2024.3'
    assert result['temporal']['event_date'] is None
    assert m.cover_metadata([cover_block('Hà Nội, tháng 6/2025', page=3)])['temporal']['status'] == 'unknown'


def test_conflicting_cover_dates_remain_pending_even_inside_same_semester():
    m = module()
    result = m.cover_metadata([cover_block('Hà Nội, ngày 1 tháng 6 năm 2025'),
                               cover_block('Hà Nội, ngày 2 tháng 6 năm 2025', page=2)])
    assert result['temporal']['status'] == 'ambiguous'
    assert result['temporal']['version'] is None
    assert result['temporal']['event_date'] is None
    assert result['temporal']['event_interval_upper_bound'] == '2025-06-02'


def test_temporal_derivative_binds_original_and_preserves_it(tmp_path):
    m = module()
    source = tmp_path / 'source'
    source.mkdir()
    make_docx(source / 'document.docx', ['Đề tài: Example project title', 'Mã sinh viên: 11220001'])
    original = tmp_path / 'students'
    m.collect_students(source, original)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in original.iterdir() if p.is_file()}
    result = m.rederive_temporal(original, tmp_path / 'students_dates')
    assert result['student_candidates'] == 1
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in original.iterdir() if p.is_file()}
    assert before == after
    derivative = tmp_path / 'students_dates'
    assert {p.name for p in derivative.iterdir()} == {'students.jsonl', 'report.json', 'manifest.json'}
    manifest = json.loads((derivative / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['source_collection_manifest_sha256'] == before['manifest.json']
    assert m.verify_collection(derivative) == result



def test_decomposed_city_date_keeps_original_evidence():
    import unicodedata
    text = unicodedata.normalize('NFD', 'Hà Nội, 5/2025')
    result = module().cover_metadata([cover_block(text)])
    assert result['temporal']['version'] == 'V2'
    assert result['date_evidence'][0]['evidence'][0]['snippet'] == text
    assert result['date_evidence'][0]['quote'] == text


def test_quoted_title_fallback_keeps_original_block_evidence():
    blocks = [cover_block('“KHÓA LUẬN TỐT NGHIỆP”'),
              cover_block('Xây dựng hệ thống bán cây cảnh'),
              cover_block('tích hợp trí tuệ nhân tạo'), cover_block('Tên sinh viên: Nguyễn Điệp Vũ')]
    result = module()._quoted_cover_title(blocks)
    assert result['value'] == 'Xây dựng hệ thống bán cây cảnh tích hợp trí tuệ nhân tạo'
    assert [e['snippet'] for e in result['evidence']] == [blocks[1]['text'], blocks[2]['text']]
