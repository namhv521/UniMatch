"""Page/block PDF extraction with conservative, traceable Vietnamese OCR.

No student inference occurs here. Empty, damaged, or unavailable OCR content is
represented by explicit page outcomes rather than silently dropped.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterator

import pymupdf


PARSER_VERSION = pymupdf.VersionBind
OCR_LANGUAGE = 'vie+eng'
OCR_DPI = 180
LOW_TEXT_CHAR_THRESHOLD = 50
OCR_MIN_IMAGE_COVERAGE = 0.30
REVIEW_MIN_IMAGE_COVERAGE = 0.10


def _digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _ocr_configuration(tessdata: str | Path | None) -> dict:
    location = tessdata or os.environ.get('TESSDATA_PREFIX')
    if location is None:
        try:
            location = pymupdf.get_tessdata()
        except Exception:
            location = None
    directory = Path(location) if location else None
    models = {lang: directory / f'{lang}.traineddata' for lang in ('vie', 'eng')} if directory else {}
    available = bool(models) and all(path.is_file() for path in models.values())
    return {'available': available, 'tessdata': str(directory) if directory else None,
            'language': OCR_LANGUAGE, 'dpi': OCR_DPI,
            'version': f'PyMuPDF/{PARSER_VERSION} MuPDF-integrated-Tesseract',
            'model_sha256': {lang: _digest(path) for lang, path in models.items()} if available else {}}


def _image_coverage(page: pymupdf.Page) -> float:
    area = page.rect.get_area()
    if not area:
        return 0.0
    rectangles = [pymupdf.Rect(info['bbox']) & page.rect for info in page.get_image_info()]
    rectangles = [rect for rect in rectangles if not rect.is_empty]
    # Union area avoids repeated logos/layers incorrectly classifying a scan.
    edges = sorted({x for rect in rectangles for x in (rect.x0, rect.x1)})
    covered_area = 0.0
    for left, right in zip(edges, edges[1:]):
        intervals = sorted((rect.y0, rect.y1) for rect in rectangles if rect.x0 < right and rect.x1 > left)
        covered_height, end = 0.0, float('-inf')
        for top, bottom in intervals:
            covered_height += max(0.0, bottom - max(top, end))
            end = max(end, bottom)
        covered_area += (right - left) * covered_height
    return min(1.0, covered_area / area)


def iter_pdf_blocks(path: Path, source_ref: dict, ocr_mode: str = 'auto',
                    tessdata: str | Path | None = None) -> Iterator[dict]:
    """Yield text blocks followed by exactly one outcome per readable PDF page.

    Document-open/encryption/hash failures produce one page=None outcome when
    page-level access is impossible. Source references, including archive chains,
    pass through unchanged. OCR confidence is unknown, never fabricated.
    """
    if ocr_mode not in {'auto', 'off'}:
        raise ValueError('ocr_mode must be auto or off')
    path = Path(path)
    base = {**source_ref, 'parser_version': PARSER_VERSION, 'confidence': None}
    document_failure = {**base, 'kind': 'page_outcome', 'page': None, 'status': 'failed',
                        'reason': '', 'text_length': 0, 'ocr_candidate': False,
                        'ocr_attempted': False, 'ocr_available': False,
                        'extraction_method': None, 'ocr_method': None, 'ocr_version': None}
    try:
        actual_hash = _digest(path)
    except OSError as exc:
        yield {**document_failure, 'reason': 'source_unreadable', 'error_class': type(exc).__name__}
        return
    if source_ref.get('source_sha256') != actual_hash:
        yield {**document_failure, 'reason': 'source_hash_mismatch'}
        return
    source_key = source_ref.get('source_id') or hashlib.sha256(
        f'{source_ref.get("source_file", path.name)}:{actual_hash}'.encode('utf-8')).hexdigest()
    try:
        document = pymupdf.open(path)
        if not document.is_pdf:
            document.close()
            raise ValueError('not_pdf_content')
    except Exception as exc:
        yield {**document_failure, 'reason': 'pdf_open_failed', 'error_class': type(exc).__name__}
        return
    with document:
        if document.needs_pass:
            yield {**document_failure, 'status': 'quarantined', 'reason': 'password_required'}
            return
        if not document.page_count:
            yield {**document_failure, 'reason': 'zero_pages'}
            return
        ocr = _ocr_configuration(tessdata) if ocr_mode == 'auto' else {'available': False}
        for number in range(document.page_count):
            page_number = number + 1
            outcome = {**base, 'kind': 'page_outcome', 'page': page_number,
                       'locator': f'page:{page_number}', 'status': 'failed', 'reason': '',
                       'text_length': 0, 'ocr_candidate': False, 'ocr_attempted': False,
                       'ocr_available': ocr['available'], 'ocr_method': None, 'ocr_version': None,
                       'extraction_method': 'pymupdf_embedded_text'}
            try:
                page = document.load_page(number)
                text = page.get_text().strip()
                coverage = _image_coverage(page)
                low_text = len(text) < LOW_TEXT_CHAR_THRESHOLD
                ocr_candidate = low_text and coverage >= OCR_MIN_IMAGE_COVERAGE
                outcome.update(ocr_candidate=ocr_candidate, image_coverage=round(coverage, 6),
                               embedded_text_length=len(text))
                method = 'pymupdf_embedded_text'
                textpage = None
                if ocr_candidate:
                    if ocr_mode == 'off' or not ocr['available']:
                        outcome.update(status='quarantined', reason='ocr_disabled' if ocr_mode == 'off' else 'ocr_unavailable')
                    else:
                        outcome.update(ocr_attempted=True, ocr_method='pymupdf_tesseract',
                                       ocr_version=ocr['version'], ocr_language=ocr['language'],
                                       ocr_dpi=ocr['dpi'], ocr_model_sha256=ocr['model_sha256'])
                        try:
                            textpage = page.get_textpage_ocr(language=OCR_LANGUAGE, dpi=OCR_DPI,
                                                             full=True, tessdata=ocr['tessdata'])
                            method = 'pymupdf_tesseract'
                            outcome['extraction_method'] = method
                        except Exception as exc:
                            outcome.update(status='quarantined', reason='ocr_failed', error_class=type(exc).__name__)
                elif low_text and coverage >= REVIEW_MIN_IMAGE_COVERAGE:
                    outcome.update(status='quarantined', reason='low_text_image_requires_review')
                blocks = page.get_text('blocks', textpage=textpage, sort=True)
                text_length = 0
                block_count = 0
                for block in blocks:
                    if len(block) > 6 and block[6] != 0:
                        continue
                    block_text = block[4].strip()
                    if not block_text:
                        continue
                    locator = f'page:{page_number}/block:{block_count}'
                    block_id = f'{source_key}/{locator}'
                    yield {**base, 'kind': 'block', 'block_id': block_id, 'page': page_number,
                           'locator': locator, 'bbox': list(block[:4]), 'text': block_text,
                           'extraction_method': method}
                    text_length += len(block_text)
                    block_count += 1
                outcome.update(text_length=text_length, block_count=block_count)
                if not outcome['reason']:
                    if text_length:
                        outcome.update(status='extracted', reason='')
                    elif ocr_candidate:
                        outcome.update(status='quarantined', reason='ocr_no_text')
                    elif coverage or page.get_drawings():
                        outcome.update(status='quarantined', reason='nontext_content_requires_review')
                    else:
                        outcome.update(status='blank', reason='no_text_or_graphics')
            except Exception as exc:
                outcome.update(status='failed', reason='page_extraction_failed', error_class=type(exc).__name__)
            yield outcome
    try:
        if _digest(path) != actual_hash:
            yield {**document_failure, 'reason': 'source_changed_during_extraction'}
    except OSError as exc:
        yield {**document_failure, 'reason': 'source_unreadable_after_extraction', 'error_class': type(exc).__name__}
