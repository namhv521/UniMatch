import hashlib
import importlib.util
import stat
import zipfile
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[2] / 'src/data_pipeline/document_sources.py'
    assert path.exists(), 'Document source extraction implementation is missing'
    spec = importlib.util.spec_from_file_location('document_sources', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_docx_unicode_structure_and_source_chain(tmp_path):
    source = tmp_path / 'thesis.docx'
    xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Đề tài nghiên cứu</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Phương pháp học máy</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'''
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    blocks = module().extract_docx(source, {'source_file': 'private/thesis.docx', 'source_id': 'source-1', 'archive_chain': [{'sha256': 'parent'}]})
    assert [b['text'] for b in blocks] == ['Đề tài nghiên cứu', 'Phương pháp học máy']
    assert 'tbl[1]/tr[1]/tc[1]/p[1]' in blocks[1]['locator']
    assert all(b['source_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest() for b in blocks)
    assert all(b['source_id'] == 'source-1' and b['archive_chain'] == [{'sha256': 'parent'}] for b in blocks)
    assert len({b['block_id'] for b in blocks}) == 2
    assert all(b['kind'] == 'block' and b['confidence'] is None for b in blocks)
    assert not any('page' in b for b in blocks)
    other = module().extract_docx(source, {'source_file': 'private/copy.docx', 'source_id': 'source-2'})
    assert not {b['block_id'] for b in blocks} & {b['block_id'] for b in other}
    repeated = module().extract_docx(source, {'source_file': 'private/thesis.docx', 'source_id': 'source-1', 'archive_chain': [{'sha256': 'parent'}]})
    assert repeated == blocks


def test_archive_manifest_supported_unsupported_and_repeat(tmp_path):
    source = tmp_path / 'source.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('tài liệu/', '')
        archive.writestr('tài liệu/thesis.pdf', b'%PDF-test')
        archive.writestr('tài liệu/code.js', b'console.log(1)')
        archive.writestr('nested.zip', b'PK-placeholder')
    helper = module()
    rows = helper.expand_archive(source, tmp_path / 'expanded')
    by_name = {r['member_path']: r for r in rows}
    assert by_name['tài liệu/']['status'] == 'directory'
    assert by_name['tài liệu/thesis.pdf']['status'] == 'extracted'
    assert Path(by_name['tài liệu/thesis.pdf']['extracted_path']).read_bytes() == b'%PDF-test'
    assert by_name['tài liệu/code.js']['status'] == 'quarantined'
    assert by_name['tài liệu/code.js']['reason'] == 'unsupported_format'
    assert by_name['nested.zip']['status'] == 'extracted'
    assert helper.expand_archive(source, tmp_path / 'expanded') == rows


@pytest.mark.parametrize('name', ['../escape.pdf', '/absolute.pdf', 'C:/drive.pdf', r'\\host\share\file.pdf', 'folder/../../escape.pdf', 'file.pdf:payload', 'CON.pdf'])
def test_archive_rejects_unsafe_paths(tmp_path, name):
    source = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr(name, b'unsafe')
    rows = module().expand_archive(source, tmp_path / 'expanded')
    assert rows[0]['status'] == 'quarantined'
    assert rows[0]['reason'] == 'unsafe_member_path'
    assert not (tmp_path / 'escape.pdf').exists()


def test_archive_rejects_links_and_normalized_collisions(tmp_path):
    source = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('A.pdf', b'first')
        archive.writestr('a.PDF', b'second')
        link = zipfile.ZipInfo('link.pdf')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, '../elsewhere')
    rows = module().expand_archive(source, tmp_path / 'expanded')
    assert rows[0]['status'] == rows[1]['status'] == 'quarantined'
    assert rows[0]['reason'] == rows[1]['reason'] == 'normalized_path_collision'
    assert rows[2]['reason'] == 'link_not_allowed'


def test_archive_unicode_collision_and_whole_archive_budgets(tmp_path):
    source = tmp_path / 'unicode.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('đề.pdf', b'first')
        archive.writestr('đề.pdf', b'second')
    helper = module()
    rows = helper.expand_archive(source, tmp_path / 'unicode')
    assert all(r['reason'] == 'normalized_path_collision' for r in rows)
    source = tmp_path / 'budget.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('one.pdf', b'1234')
        archive.writestr('two.pdf', b'5678')
    rows = helper.expand_archive(source, tmp_path / 'count', max_members=1)
    assert all(r['reason'] == 'archive_member_count_limit' for r in rows)
    rows = helper.expand_archive(source, tmp_path / 'bytes', max_total_bytes=7)
    assert all(r['reason'] == 'archive_total_size_limit' for r in rows)


def test_archive_byte_budget_and_existing_file_protection(tmp_path):
    source = tmp_path / 'safe.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('thesis.pdf', b'123456')
    helper = module()
    rows = helper.expand_archive(source, tmp_path / 'limited', max_member_bytes=5)
    assert rows[0]['reason'] == 'member_size_limit'
    dest = tmp_path / 'existing'
    dest.mkdir()
    (dest / 'thesis.pdf').write_bytes(b'existing')
    rows = helper.expand_archive(source, dest)
    assert rows[0]['reason'] == 'existing_file_conflict'
    assert (dest / 'thesis.pdf').read_bytes() == b'existing'


def test_docx_rejects_oversized_xml_and_entities(tmp_path):
    source = tmp_path / 'bad.docx'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('word/document.xml', '<!DOCTYPE x [<!ENTITY test "unsafe">]><x>&test;</x>')
    helper = module()
    with pytest.raises(ValueError, match='xml_entities_not_allowed'):
        helper.extract_docx(source, {})
    with pytest.raises(ValueError, match='document_xml_size_limit'):
        helper.extract_docx(source, {}, max_xml_bytes=4)
