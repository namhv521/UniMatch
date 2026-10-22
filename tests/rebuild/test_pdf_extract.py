import hashlib
import importlib.util
from pathlib import Path

import pymupdf
import pytest


ROOT = Path(__file__).resolve().parents[2]


def extractor():
    path = ROOT / 'src/data_pipeline/pdf_extract.py'
    assert path.exists(), 'PDF extraction implementation is missing'
    spec = importlib.util.spec_from_file_location('pdf_extract', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference(path):
    return {'source_file': path.name, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'source_id': 'fixture-source', 'archive_chain': [{'member': path.name, 'archive_sha256': 'a' * 64}]}


def create_pdf(path, *, scanned=False, blank=False, encrypted=False):
    with pymupdf.open() as original:
        page = original.new_page(width=600, height=800)
        if not blank:
            page.insert_font(fontname='Fixture', fontfile=str(ROOT / 'frontend/assets/manrope-regular.ttf'))
            page.insert_text((40, 80), 'Tiếng Việt: đề tài nghiên cứu, công nghệ và dữ liệu.', fontname='Fixture', fontsize=14)
        if scanned:
            image = page.get_pixmap().tobytes('png')
            with pymupdf.open() as raster:
                raster.new_page(width=600, height=800).insert_image(pymupdf.Rect(0, 0, 600, 800), stream=image)
                raster.save(path)
        else:
            options = dict(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='secret') if encrypted else {}
            original.save(path, **options)


def test_unicode_blocks_have_source_and_page_provenance(tmp_path):
    path = tmp_path / 'unicode.pdf'
    create_pdf(path)
    ref = reference(path)
    records = list(extractor().iter_pdf_blocks(path, ref, ocr_mode='off'))
    blocks = [r for r in records if r['kind'] == 'block']
    outcomes = [r for r in records if r['kind'] == 'page_outcome']
    assert 'Tiếng Việt' in ''.join(r['text'] for r in blocks)
    assert outcomes[0]['status'] == 'extracted'
    for block in blocks:
        assert block['source_sha256'] == ref['source_sha256']
        assert block['archive_chain'] == ref['archive_chain']
        assert block['source_id'] == 'fixture-source'
        assert block['page'] == 1 and block['locator'].startswith('page:1/block:')
        assert len(block['bbox']) == 4
        assert block['confidence'] is None
        assert block['extraction_method'] == 'pymupdf_embedded_text'


@pytest.mark.parametrize('mode,reason', [('off', 'ocr_disabled'), ('auto', 'ocr_unavailable')])
def test_scan_without_ocr_has_explicit_quarantine(tmp_path, mode, reason):
    path = tmp_path / 'scan.pdf'
    create_pdf(path, scanned=True)
    records = list(extractor().iter_pdf_blocks(path, reference(path), ocr_mode=mode, tessdata=tmp_path / 'missing'))
    outcome = [r for r in records if r['kind'] == 'page_outcome'][0]
    assert outcome['status'] == 'quarantined'
    assert outcome['reason'] == reason
    assert outcome['ocr_candidate']
    assert outcome['text_length'] == 0


def test_blank_page_is_accounted_without_attempting_ocr(tmp_path):
    path = tmp_path / 'blank.pdf'
    create_pdf(path, blank=True)
    records = list(extractor().iter_pdf_blocks(path, reference(path), tessdata=tmp_path / 'missing'))
    assert len(records) == 1
    assert records[0]['status'] == 'blank'
    assert records[0]['page'] == 1
    assert not records[0]['ocr_candidate']
    assert not records[0]['ocr_attempted']


def test_corrupt_encrypted_and_wrong_hash_fail_explicitly(tmp_path):
    module = extractor()
    corrupt = tmp_path / 'corrupt.pdf'
    corrupt.write_bytes(b'not a PDF')
    encrypted = tmp_path / 'encrypted.pdf'
    create_pdf(encrypted, encrypted=True)
    for path, reason in [(corrupt, 'pdf_open_failed'), (encrypted, 'password_required')]:
        outcomes = list(module.iter_pdf_blocks(path, reference(path)))
        assert len(outcomes) == 1
        assert outcomes[0]['status'] in {'failed', 'quarantined'}
        assert outcomes[0]['reason'] == reason
    wrong_ref = reference(encrypted)
    wrong_ref['source_sha256'] = '0' * 64
    result = list(module.iter_pdf_blocks(encrypted, wrong_ref))[0]
    assert result['reason'] == 'source_hash_mismatch'


def test_all_pages_have_exactly_one_outcome(tmp_path):
    path = tmp_path / 'three.pdf'
    with pymupdf.open() as doc:
        for _ in range(3):
            doc.new_page()
        doc.save(path)
    outcomes = [r for r in extractor().iter_pdf_blocks(path, reference(path)) if r['kind'] == 'page_outcome']
    assert [r['page'] for r in outcomes] == [1, 2, 3]
    assert all(r['status'] == 'blank' for r in outcomes)


def test_block_ids_are_distinct_across_sources(tmp_path):
    module = extractor()
    first = tmp_path / 'first.pdf'
    second = tmp_path / 'second.pdf'
    create_pdf(first)
    second.write_bytes(first.read_bytes())
    first_ref, second_ref = reference(first), reference(second)
    first_ref['source_id'], second_ref['source_id'] = 'first-source', 'second-source'
    first_blocks = [r for r in module.iter_pdf_blocks(first, first_ref) if r['kind'] == 'block']
    second_blocks = [r for r in module.iter_pdf_blocks(second, second_ref) if r['kind'] == 'block']
    assert first_blocks[0]['locator'] == second_blocks[0]['locator']
    assert first_blocks[0]['block_id'] != second_blocks[0]['block_id']


def test_source_change_during_stream_is_reported(tmp_path):
    path = tmp_path / 'changing.pdf'
    create_pdf(path)
    stream = extractor().iter_pdf_blocks(path, reference(path))
    assert next(stream)['kind'] == 'block'
    with path.open('ab') as output:
        output.write(b'\n% changed during extraction\n')
    records = list(stream)
    assert records[-1]['status'] == 'failed'
    assert records[-1]['reason'] == 'source_changed_during_extraction'


def test_overlapping_small_images_do_not_trigger_full_page_ocr(tmp_path):
    path = tmp_path / 'overlap.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=800)
        with pymupdf.open() as image_doc:
            image_doc.new_page(width=300, height=400)
            image = image_doc[0].get_pixmap().tobytes('png')
        for _ in range(3):
            page.insert_image(pymupdf.Rect(0, 0, 300, 400), stream=image)
        doc.save(path)
    outcome = list(extractor().iter_pdf_blocks(path, reference(path), ocr_mode='off'))[-1]
    assert outcome['image_coverage'] == 0.25
    assert not outcome['ocr_candidate']


def test_integrated_vietnamese_ocr_when_local_models_available(tmp_path):
    tessdata = ROOT / 'data_rebuild/v1/tools/tessdata'
    if not all((tessdata / f'{language}.traineddata').is_file() for language in ('vie', 'eng')):
        pytest.skip('Private local OCR language models not installed')
    path = tmp_path / 'vietnamese-scan.pdf'
    create_pdf(path, scanned=True)
    records = list(extractor().iter_pdf_blocks(path, reference(path), tessdata=tessdata))
    text = ' '.join(r['text'] for r in records if r['kind'] == 'block')
    outcome = [r for r in records if r['kind'] == 'page_outcome'][0]
    assert 'Tiếng' in text and 'Việt' in text
    assert outcome['status'] == 'extracted'
    assert outcome['ocr_attempted'] and outcome['ocr_language'] == 'vie+eng'
    assert set(outcome['ocr_model_sha256']) == {'vie', 'eng'}
    assert all(r['confidence'] is None for r in records)


def test_cropped_page_scan_at_46_percent_is_an_ocr_candidate(tmp_path):
    path = tmp_path / 'cropped-scan.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=800)
        with pymupdf.open() as image_doc:
            image_doc.new_page(width=300, height=400)
            image = image_doc[0].get_pixmap().tobytes('png')
        page.insert_image(pymupdf.Rect(0, 0, 400, 552), stream=image, keep_proportion=False)
        page.insert_text((550, 780), '5')
        doc.save(path)
    outcome = list(extractor().iter_pdf_blocks(path, reference(path), ocr_mode='off'))[-1]
    assert outcome['image_coverage'] == 0.46
    assert outcome['ocr_candidate']
    assert outcome['status'] == 'quarantined'
    assert outcome['reason'] == 'ocr_disabled'


def test_substantial_image_below_ocr_threshold_with_footer_needs_review(tmp_path):
    path = tmp_path / 'subthreshold.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=800)
        with pymupdf.open() as image_doc:
            image_doc.new_page(width=300, height=400)
            image = image_doc[0].get_pixmap().tobytes('png')
        page.insert_image(pymupdf.Rect(0, 0, 300, 400), stream=image)
        page.insert_text((550, 780), '12')
        doc.save(path)
    outcome = list(extractor().iter_pdf_blocks(path, reference(path), ocr_mode='off'))[-1]
    assert not outcome['ocr_candidate']
    assert outcome['status'] == 'quarantined'
    assert outcome['reason'] == 'low_text_image_requires_review'
