def test_missing_curated_is_reported_not_fabricated(tmp_path):
    from src.data_pipeline.clean_processed_data import audit_curated
    report = audit_curated(tmp_path)
    assert report['ready'] is False
    assert set(report['missing_files']) == {'theses.csv', 'advisors.csv'}


def test_audit_rejects_duplicate_ids_and_missing_skill_text(tmp_path):
    from src.data_pipeline.clean_processed_data import audit_curated
    (tmp_path / 'theses.csv').write_text(
        'thesis_id,student_id,submission_year,thesis_title\nt1,s1,2025,Topic\nt1,s1,2025,Topic\n', encoding='utf-8')
    (tmp_path / 'advisors.csv').write_text(
        'advisor_id,advisor_name,quota,skill_text\na1,Advisor,3,\n', encoding='utf-8')
    report = audit_curated(tmp_path)
    assert not report['ready']
    assert report['tables']['theses.csv']['duplicate_ids'] == 1
    assert report['tables']['advisors.csv']['null_rates']['skill_text'] == 1
