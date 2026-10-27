import hashlib
import importlib.util
from pathlib import Path

import pymupdf
import pytest


def audit_module():
    path = Path(__file__).resolve().parents[2] / 'scripts/audit_rebuild_phase0.py'
    assert path.exists(), 'Phase 0 inventory implementation is missing'
    spec = importlib.util.spec_from_file_location('phase0', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pdf(path, *, encrypted=False, blank=False):
    with pymupdf.open() as doc:
        page = doc.new_page()
        if not blank:
            page.insert_text((30, 30), 'Inventory test fixture, not a student record. ' * 3)
        kwargs = dict(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='secret') if encrypted else {}
        doc.save(path, **kwargs)


def test_inventory_accounts_for_entries_and_duplicates(tmp_path):
    module = audit_module()
    (tmp_path / '.nested').mkdir()
    pdf(tmp_path / 'a.PDF')
    data = (tmp_path / 'a.PDF').read_bytes()
    (tmp_path / '.nested/copy.pdf').write_bytes(data)
    (tmp_path / 'desktop.ini').write_text('system metadata')
    rows, entries = module.inventory(tmp_path)
    assert len(rows) == 2
    assert len(entries) == 4
    assert {r['sha256'] for r in rows} == {hashlib.sha256(data).hexdigest()}
    assert all(r['page_count'] == 1 and r['text_length'] > 100 for r in rows)
    assert any(e['hidden'] for e in entries)
    result = module.quality(rows, expected=220)
    assert result['status'] == 'blocked'
    assert result['count_delta'] == -218
    assert len(result['duplicate_hash_groups']) == 1
    assert module.quality(rows, expected=2)['status'] == 'verified'


def test_invalid_encrypted_and_low_text_are_distinct(tmp_path):
    module = audit_module()
    (tmp_path / 'broken.pdf').write_bytes(b'not a PDF')
    pdf(tmp_path / 'locked.pdf', encrypted=True)
    pdf(tmp_path / 'blank.pdf', blank=True)
    rows, _ = module.inventory(tmp_path)
    by_name = {r['relative_path']: r for r in rows}
    assert by_name['broken.pdf']['status'] == 'failed'
    assert by_name['locked.pdf']['encrypted']
    assert by_name['locked.pdf']['status'] == 'encrypted'
    assert by_name['blank.pdf']['low_text_pages'] == 1
    assert by_name['blank.pdf']['scan_candidate']
    assert module.quality(rows, expected=3)['status'] == 'blocked'


def test_missing_root_is_not_empty_success(tmp_path):
    with pytest.raises(FileNotFoundError):
        audit_module().inventory(tmp_path / 'absent')


def test_cli_writes_private_reports_and_blocks_count_mismatch(tmp_path, monkeypatch):
    import sys
    import json
    import csv
    module = audit_module()
    source = tmp_path / 'source'
    source.mkdir()
    pdf(source / 'sample.pdf')
    output = tmp_path / 'output'
    monkeypatch.setattr(sys, 'argv', ['audit', '--source', str(source), '--output', str(output)])
    assert module.main() == 2
    report = json.loads((output / 'reports/input_quality.json').read_text(encoding='utf-8'))
    assert report['actual_count'] == 1
    with (output / 'reports/input_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
        assert len(list(csv.DictReader(stream))) == 1
    assert report['inventory_sha256'] == module.sha256(output / 'reports/input_inventory.csv')
    monkeypatch.setattr(sys, 'argv', ['audit', '--source', str(source), '--output', str(source / 'bad')])
    with pytest.raises(SystemExit):
        module.main()
    assert not (source / 'bad').exists()


def test_source_count_includes_word_archives_and_excludes_system_files(tmp_path):
    module = audit_module()
    pdf(tmp_path / 'a.PDF')
    (tmp_path / 'b.DOCX').write_bytes(b'Word source: extraction belongs to Phase 1')
    (tmp_path / 'c.RAR').write_bytes(b'Archive source: expansion belongs to Phase 1')
    (tmp_path / 'desktop.ini').write_text('system metadata')
    rows, entries = module.inventory(tmp_path)
    assert len(rows) == 3
    assert {r['format'] for r in rows} == {'pdf', 'docx', 'rar'}
    assert all(len(r['sha256']) == 64 for r in rows)
    excluded = [e for e in entries if e.get('exclusion_reason')]
    assert len(excluded) == 1 and excluded[0]['relative_path'] == 'desktop.ini'
    assert module.quality(rows, expected=3)['status'] == 'verified'
    assert module.quality(rows, expected=3)['format_counts'] == {'pdf': 1, 'docx': 1, 'rar': 1}


def test_valid_pdf_cache_requires_matching_hash(tmp_path):
    module = audit_module()
    pdf(tmp_path / 'a.pdf')
    rows, _ = module.inventory(tmp_path)
    cached, _ = module.inventory(tmp_path, cached_pdf_rows=rows)
    assert cached[0]['pdf_inspection'] == 'cached_sha256_verified'
    rows[0]['parser_version'] = 'stale-parser'
    refreshed, _ = module.inventory(tmp_path, cached_pdf_rows=rows)
    assert refreshed[0]['pdf_inspection'] == 'PyMuPDF_embedded_text'
    (tmp_path / 'a.pdf').write_bytes(b'invalid replacement')
    changed, _ = module.inventory(tmp_path, cached_pdf_rows=rows)
    assert changed[0]['status'] == 'failed'


def test_unrecognized_source_format_blocks_gate(tmp_path):
    module = audit_module()
    (tmp_path / 'source.bin').write_bytes(b'Unknown source')
    rows, _ = module.inventory(tmp_path)
    assert rows[0]['status'] == 'unsupported'
    assert module.quality(rows, expected=1)['status'] == 'blocked'
