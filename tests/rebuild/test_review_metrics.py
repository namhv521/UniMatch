import csv

from src.data_pipeline.review_metrics import evaluate_sample


def test_metrics_require_actual_reviews_and_bind_values_to_snapshot(tmp_path):
    candidate = {'candidate_id': 'fixture', 'source_sha256': 'a'*64,
                 'fields': {'thesis_title': {'value': 'Technical fixture'}}, 'technology_mentions': []}
    path = tmp_path / 'labels.csv'
    header = ['run_id', 'candidate_id', 'source_sha256', 'field_name', 'candidate_value', 'review_status',
              'reviewer', 'reviewed_at', 'field_verdict']
    row = dict(zip(header, ['run', 'fixture', 'a'*64, 'thesis_title', 'Technical fixture', 'pending', '', '', '']))
    def write():
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=header)
            writer.writeheader()
            writer.writerow(row)
    write()
    result = evaluate_sample(path, [candidate], 'run')
    assert not result['complete'] and result['fields'] == {}
    row.update(review_status='reviewed', reviewer='fixture-reviewer', reviewed_at='2026-10-21T12:00:00+00:00', field_verdict='correct')
    write()
    result = evaluate_sample(path, [candidate], 'run')
    assert result['fields']['thesis_title']['accuracy'] == 1.0
    assert not result['complete']  # One field alone is not a complete six-field sample.
    row['candidate_value'] = 'Stale previous extraction'
    write()
    assert not evaluate_sample(path, [candidate], 'run')['complete']


def test_complete_fields_cannot_hide_an_omitted_sample_document(tmp_path):
    from src.data_pipeline.review_metrics import REVIEW_FIELDS, sample_candidates
    candidates = [{'candidate_id': key, 'source_sha256': key*64, 'fields': {},
                   'technology_mentions': [], 'source_file': key+'.pdf'} for key in ('a', 'b')]
    assert set(sample_candidates(candidates)) == {'a', 'b'}
    rows = [{'run_id': 'run', 'candidate_id': 'a', 'source_sha256': 'a'*64,
             'field_name': field, 'candidate_value': '[]' if field == 'technology_mentions' else '',
             'review_status': 'reviewed', 'reviewer': 'test-reviewer',
             'reviewed_at': '2026-10-21T12:00:00Z', 'field_verdict': 'missing_in_source'}
            for field in sorted(REVIEW_FIELDS)]
    path = tmp_path / 'subset.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = evaluate_sample(path, candidates, 'run')
    assert result['complete_field_coverage']
    assert not result['complete'] and not result['expected_package_coverage']


def test_uncertain_labels_are_reported_without_fabricated_accuracy(tmp_path):
    from src.data_pipeline.review_metrics import REVIEW_FIELDS
    candidate = {'candidate_id': 'fixture', 'source_sha256': 'a'*64, 'fields': {}, 'technology_mentions': []}
    rows = [{'run_id': 'run', 'candidate_id': 'fixture', 'source_sha256': 'a'*64,
             'field_name': field, 'candidate_value': '[]' if field == 'technology_mentions' else '',
             'review_status': 'reviewed', 'reviewer': 'test-reviewer',
             'reviewed_at': '2026-10-21T12:00:00Z', 'field_verdict': 'uncertain'} for field in REVIEW_FIELDS]
    path = tmp_path / 'uncertain.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = evaluate_sample(path, [candidate], 'run')
    assert result['complete'] and result['uncertain_labels'] == 6
    assert all(field['accuracy'] is None for field in result['fields'].values())


def test_sampling_recognizes_canonical_tesseract_method():
    from src.data_pipeline.review_metrics import sample_candidates
    candidate = {'candidate_id': 'fixture', 'fields': {
        'student_name': {'evidence': [{'extraction_method': 'pymupdf_tesseract'}]}}}
    assert 'ocr_field' in sample_candidates([candidate])['fixture']
