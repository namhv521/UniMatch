def test_publication_skills_keep_evidence_and_do_not_invent_frameworks():
    from src.data_pipeline.crawl_advisors import parse_profile
    record = {'id': 1, 'slug': 'test', 'displayName': 'TS Test', 'introduction': '',
              'additionalInfo': '<h3>GIẢNG DẠY</h3><p>Lập trình Python</p>'
              '<h3>LĨNH VỰC NGHIÊN CỨU</h3><p>Học sâu</p>'
              '<h3>CÁC BÀI BÁO KHOA HỌC</h3><p>Deep learning for text (2023)</p>'}
    profile, evidence, publications = parse_profile(record)
    assert profile['publication_evidence_count'] == 1
    assert 'Python' in profile['skill_text']
    assert 'PyTorch' not in profile['skill_text']
    assert any(row['skill_name'] == 'Deep Learning' for row in evidence)
    assert publications[0]['year'] == 2023
    assert all(row['source_url'].startswith('https://fit.neu.edu.vn/') for row in evidence)


def test_blank_profile_is_not_filled_with_guesses():
    from src.data_pipeline.crawl_advisors import parse_profile
    profile, evidence, publications = parse_profile({'id': 2, 'displayName': 'Name', 'slug': 'name'})
    assert profile['skill_count'] == 0
    assert evidence == publications == []
    assert profile['needs_review']
