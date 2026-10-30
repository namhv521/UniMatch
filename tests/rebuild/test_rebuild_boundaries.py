"""Integration boundaries: accepted source identity, archive budgets and run integrity."""
import csv
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from src.data_pipeline import source_rebuild as pipeline


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def docx_bytes():
    import io
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Technical extraction fixture without identity.</w:t></w:r></w:p></w:body></w:document>')
    return stream.getvalue()


def accepted(root, files):
    source = root / 'source'
    source.mkdir()
    for name, content in files.items():
        (source / name).write_bytes(content)
    output = root / 'output'
    (output / 'reports').mkdir(parents=True)
    rows = [{'relative_path': name, 'format': Path(name).suffix[1:], 'sha256': sha(source / name)} for name in files]
    write_inventory(output, rows)
    return source, output


def write_inventory(output, rows, *, declared_count=None):
    inventory = output / 'reports/input_inventory.csv'
    with inventory.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['relative_path', 'format', 'sha256'])
        writer.writeheader()
        writer.writerows(rows)
    gate = {'status': 'verified', 'can_start_phase1': True, 'inventory_sha256': sha(inventory),
            'actual_source_files': len(rows) if declared_count is None else declared_count}
    (output / 'reports/phase0_gate.json').write_text(json.dumps(gate), encoding='utf-8')


def zip_bytes(entries):
    import io
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return stream.getvalue()


def read_csv(run, name):
    with (Path(run) / 'reports' / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def test_duplicate_original_inventory_cannot_create_multiple_identities(tmp_path):
    source, output = accepted(tmp_path, {'technical.docx': docx_bytes()})
    row = {'relative_path': 'technical.docx', 'format': 'docx', 'sha256': sha(source / 'technical.docx')}
    write_inventory(output, [row, row])
    with pytest.raises(ValueError, match='phase0_inventory_count_or_identity_mismatch'):
        pipeline.rebuild(source, output, ocr_mode='off')
    assert not (output / 'phase1_runs').exists()


def test_inventory_declared_count_and_path_boundary_are_enforced(tmp_path):
    source, output = accepted(tmp_path, {'technical.docx': docx_bytes()})
    row = {'relative_path': 'technical.docx', 'format': 'docx', 'sha256': sha(source / 'technical.docx')}
    write_inventory(output, [row], declared_count=2)
    with pytest.raises(ValueError, match='phase0_inventory_count_or_identity_mismatch'):
        pipeline.rebuild(source, output, ocr_mode='off')
    outside = tmp_path / 'outside.docx'
    outside.write_bytes(docx_bytes())
    write_inventory(output, [{'relative_path': '../outside.docx', 'format': 'docx', 'sha256': sha(outside)}])
    with pytest.raises(ValueError, match='unsafe_source_path'):
        pipeline.rebuild(source, output, ocr_mode='off')
    assert not (output / 'phase1_runs').exists()


def test_remaining_archive_bytes_are_not_reset_between_originals(tmp_path, monkeypatch):
    document = docx_bytes()
    source, output = accepted(tmp_path, {'first.zip': zip_bytes({'one.docx': document}),
                                         'second.zip': zip_bytes({'two.docx': document})})
    real_expand = pipeline.expand_archive
    calls = []

    def expand(path, dest, **limits):
        calls.append(limits)
        rows = real_expand(path, dest, **limits)
        if len(calls) == 1:
            # Simulate a near-full previous extraction without allocating 2 GiB.
            rows[0]['size_bytes'] = 2 * 1024**3 - 1
        return rows

    monkeypatch.setattr(pipeline, 'expand_archive', expand)
    result = pipeline.rebuild(source, output, ocr_mode='off')
    assert len(calls) == 2 and calls[1]['max_total_bytes'] == 1
    members = read_csv(result['run_dir'], 'archive_member_manifest.csv')
    second = next(row for row in members if row['member_path'] == 'two.docx')
    assert second['status'] == 'quarantined'
    assert second['reason'] == 'archive_total_size_limit'
    sources = read_csv(result['run_dir'], 'source_extraction_quality.csv')
    assert not any(row['source_file'] == 'second.zip!two.docx' for row in sources)


def test_remaining_member_budget_quarantines_later_archive(tmp_path, monkeypatch):
    document = docx_bytes()
    source, output = accepted(tmp_path, {'first.zip': zip_bytes({'placeholder/': b''}),
                                         'second.zip': zip_bytes({'one.docx': document, 'two.docx': document})})
    real_expand = pipeline.expand_archive
    calls = []

    def expand(path, dest, **limits):
        calls.append(limits)
        if len(calls) == 1:
            # A manifest can consume the member budget without any document bytes.
            return [{'member_path': f'folder-{i}/', 'status': 'directory', 'reason': '',
                     'member_sha256': None, 'size_bytes': 0, 'parser': 'fixture', 'parser_version': '1'}
                    for i in range(9999)]
        return real_expand(path, dest, **limits)

    monkeypatch.setattr(pipeline, 'expand_archive', expand)
    result = pipeline.rebuild(source, output, ocr_mode='off')
    assert calls[1]['max_members'] == 1
    members = read_csv(result['run_dir'], 'archive_member_manifest.csv')
    second = [row for row in members if row['member_path'].endswith('.docx')]
    assert len(second) == 2
    assert all(row['status'] == 'quarantined' and row['reason'] == 'archive_member_count_limit' for row in second)


def test_code_changed_during_extraction_cannot_pass_gate(tmp_path, monkeypatch):
    source, output = accepted(tmp_path, {'technical.docx': docx_bytes()})
    original_extract, original_digest = pipeline.extract_docx, pipeline.digest
    changed = False

    def extract(path, ref):
        nonlocal changed
        blocks = original_extract(path, ref)
        changed = True
        return blocks

    def digest(path):
        # Simulate a code file mutation; do not edit frozen source files on disk.
        if changed and Path(path).resolve() == Path(pipeline.__file__).resolve():
            return '0' * 64
        return original_digest(path)

    monkeypatch.setattr(pipeline, 'extract_docx', extract)
    monkeypatch.setattr(pipeline, 'digest', digest)
    result = pipeline.rebuild(source, output, ocr_mode='off')
    assert result['code_unchanged_during_run'] is False
    assert result['status'] == 'blocked' and result['can_start_phase2'] is False


def test_source_record_budget_reserves_space_for_later_originals(tmp_path, monkeypatch):
    source, output = accepted(tmp_path, {'first.zip': zip_bytes({'placeholder/': b''}),
                                         'last.docx': docx_bytes()})
    document = tmp_path / 'derived.docx'
    document.write_bytes(docx_bytes())

    def expand(path, dest, **limits):
        return [{'member_path': f'{i}.docx', 'status': 'extracted', 'reason': '',
                 'member_sha256': sha(document), 'size_bytes': document.stat().st_size,
                 'extracted_path': document.as_posix(), 'parser': 'fixture', 'parser_version': '1'}
                for i in range(2000)]

    monkeypatch.setattr(pipeline, 'expand_archive', expand)
    monkeypatch.setattr(pipeline, 'extract_docx', lambda path, ref: [])
    result = pipeline.rebuild(source, output, ocr_mode='off')
    assert result['original_sources_accounted'] == 2
    assert result['source_records_including_derived'] <= 2000
    members = read_csv(result['run_dir'], 'archive_member_manifest.csv')
    assert any(row['reason'] == 'whole_run_source_count_limit' for row in members)
