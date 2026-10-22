from src.data_pipeline.semester_evidence import term_evidence


def test_explicit_term_code_is_candidate_with_exact_span():
    text='BÁO CÁO KLTN\nHọc kỳ 2025.1\nHà Nội, 2025'
    result=term_evidence(text)
    assert result['candidate_terms']==['2025.1']
    assert all(text[r['start']:r['end']]==r['quote'] for r in result['evidence'])
    assert result['review_status']=='pending'


def test_year_date_and_citation_never_become_semester():
    for text in ('Hà Nội, ngày 20 tháng 8 năm 2026','References: 2025.1 in software version',
                 'Niên khóa 2020-2024','2026','08.2025.1'):
        assert term_evidence(text)['candidate_terms']==[]


def test_conflicting_term_candidates_remain_ambiguous():
    result=term_evidence('Học kỳ 2025.1\nHọc kỳ 2025.2')
    assert result['status']=='ambiguous' and result['approved_semester_id'] is None
