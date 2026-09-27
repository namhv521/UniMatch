import pytest


def test_evidence_must_occur_on_claimed_page():
    from src.data_pipeline.extract_documents import validate_evidence
    pages = [{'page': 1, 'text': 'Ứng dụng React và FastAPI.'}]
    assert validate_evidence([{'page': 1, 'quote': 'React và FastAPI'}], pages)
    with pytest.raises(ValueError):
        validate_evidence([{'page': 1, 'quote': 'TensorFlow'}], pages)
    with pytest.raises(ValueError):
        validate_evidence([{'page': 2, 'quote': 'React'}], pages)


def test_pdf_text_keeps_page_provenance(tmp_path):
    import fitz

    from src.data_pipeline.extract_documents import extract_pages
    path = tmp_path / 'source.pdf'
    document = fitz.open()
    document.new_page().insert_text((72, 72), 'React FastAPI 2025')
    document.save(path)
    document.close()
    pages = extract_pages(path)
    assert pages[0]['page'] == 1
    assert 'FastAPI' in pages[0]['text']


def test_llm_schema_does_not_accept_invented_fields():
    from src.data_pipeline.extraction_schema import ThesisExtraction
    with pytest.raises(ValueError):
        ThesisExtraction.model_validate({'invented_feature': 'value'})


def test_docx_text_does_not_depend_on_optional_relationships(tmp_path):
    from zipfile import ZipFile

    from src.data_pipeline.extract_documents import extract_pages
    path = tmp_path / 'minimal.docx'
    with ZipFile(path, 'w') as target:
        target.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>FastAPI</w:t></w:r></w:p></w:body></w:document>')
    assert extract_pages(path)[0]['text'] == 'FastAPI'
