def test_unverifiable_features_are_withheld():
    from src.data_pipeline.extraction_schema import ThesisExtraction
    from src.data_pipeline.llm_extract import ground_profile
    values = {key: ([] if field.annotation == list[str] else None)
              for key, field in ThesisExtraction.model_fields.items() if key != 'evidence'}
    values.update(evidence=[{'field': 'backend_frameworks', 'value': 'FastAPI', 'page': 1,
                             'quote': 'We use FastAPI', 'kind': 'direct'}],
                  backend_frameworks=['FastAPI', 'Django'], thesis_title='Invented title')
    profile, _rejected = ground_profile(values, [{'page': 1, 'text': 'We use FastAPI'}])
    assert profile['backend_frameworks'] == ['FastAPI']
    assert profile['thesis_title'] is None


def test_unrelated_quote_cannot_support_identity_or_technology():
    from src.data_pipeline.extraction_schema import ThesisExtraction
    from src.data_pipeline.llm_extract import ground_profile
    values = {key: ([] if field.annotation == list[str] else None)
              for key, field in ThesisExtraction.model_fields.items() if key != 'evidence'}
    values.update(student_id='12345678', backend_frameworks=['FastAPI'], evidence=[
        {'field': 'student_id', 'value': '87654321', 'page': 1, 'quote': '87654321 uses Django', 'kind': 'direct'},
        {'field': 'backend_frameworks', 'value': 'FastAPI', 'page': 1, 'quote': '87654321 uses Django', 'kind': 'direct'}])
    profile, rejected = ground_profile(values, [{'page': 1, 'text': '87654321 uses Django'}])
    assert profile['student_id'] is None
    assert profile['backend_frameworks'] == []
    assert rejected


def test_json_envelope_accepts_only_json_or_single_fence():
    import pytest

    from src.data_pipeline.llm_extract import parse_json_response
    assert parse_json_response('```json\n{"ok": true}\n```') == {'ok': True}
    with pytest.raises(ValueError):
        parse_json_response('Here is JSON: {"ok": true}')


def test_pdf_spacing_repair_retains_actual_source_quote():
    from src.data_pipeline.llm_extract import locate_quote
    pages = [{'page': 2, 'text': 'Mã sinh viên\u200b : 11220052\nPhân tích dữliệu'}]
    assert locate_quote('Mã sinh viên : 11220052', pages) == (2, 'Mã sinh viên\u200b : 11220052')
    assert locate_quote('Phân tích dữ liệu', pages) == (2, 'Phân tích dữliệu')
    assert locate_quote('Phân tích tất cả dữ liệu', pages) is None
