from src.data_pipeline.student_candidates import extract_candidates, validate_evidence


def block(text, page=1, number=0):
    return {'kind': 'block', 'block_id': f'source:p{page}:b{number}', 'source_id': 'source',
            'source_file': 'fixture.pdf', 'source_sha256': 'a' * 64, 'page': page,
            'locator': f'page:{page}/block:{number}', 'text': text,
            'extraction_method': 'embedded_text', 'parser_version': 'test', 'archive_chain': []}


def test_vietnamese_fields_are_evidence_backed_and_not_skills():
    blocks = [block('ĐẠI HỌC KINH TẾ QUỐC DÂN\nKHÓA LUẬN TỐT NGHIỆP\n'
                    'Xây dựng hệ thống phân tích dữ liệu\nTên sinh viên\n: Nguyễn Văn Ví Dụ\n'
                    'Mã sinh viên\n: 11223344\nLớp: Khoa học máy tính K63\n'
                    'Giảng viên hướng dẫn: TS. Ví Dụ\nHà Nội, 05/2025'),
              block('TÓM TẮT\nNghiên cứu dùng Python và PostgreSQL để xây dựng hệ thống thử nghiệm.\n'
                    'Từ khóa: phân tích dữ liệu; hệ thống thông tin', 3)]
    candidates = extract_candidates(blocks)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate['fields']['student_id']['value'] == '11223344'
    assert candidate['fields']['student_name']['value'] == 'Nguyễn Văn Ví Dụ'
    assert candidate['fields']['thesis_title']['value'] == 'Xây dựng hệ thống phân tích dữ liệu'
    assert candidate['skills_tags'] == []
    assert candidate['skill_proficiency'] is None
    assert candidate['review_status'] == 'needs_review'
    assert validate_evidence(candidates, blocks) == []
    candidate['fields']['student_id']['value'] = '99999999'
    assert validate_evidence(candidates, blocks)


def test_conflicting_ids_never_silently_collapse():
    blocks = [block('Tên sinh viên: Nguyễn Ví Dụ\nMã sinh viên: 11223344\n'
                    'Mã sinh viên: 11223345\n')]
    result = extract_candidates(blocks)
    assert len(result) == 2
    assert all('multiple_student_ids' in row['review_reasons'] for row in result)
    assert all(row['status'] == 'quarantined' for row in result)


def test_missing_identity_and_title_remain_missing():
    candidates = extract_candidates([block('Nội dung chưa xác định tác giả hoặc đề tài.')])
    assert len(candidates) == 1
    assert candidates[0]['fields'] == {}
    assert candidates[0]['status'] == 'quarantined'
    assert set(candidates[0]['review_reasons']) >= {'missing_student_id', 'missing_thesis_title'}


def test_word_structure_can_span_blocks_without_inventing_pages():
    blocks = [block('KHÓA LUẬN TỐT NGHIỆP'), block('Đề tài: Phân tích dữ liệu kinh tế', number=1),
              block('Tên sinh viên: Nguyễn Ví Dụ', number=2), block('MSSV: 11223344', number=3)]
    for row in blocks:
        row.pop('page')
        row['source_file'] = 'fixture.docx'
        row['locator'] = f'paragraph:{row["block_id"]}'
    candidates = extract_candidates(blocks)
    assert candidates[0]['fields']['thesis_title']['value'] == 'Phân tích dữ liệu kinh tế'
    assert validate_evidence(candidates, blocks) == []
    assert all('page' not in ev for field in candidates[0]['fields'].values() for ev in field['evidence'])


def test_provenance_tampering_and_late_second_thesis_are_quarantined():
    blocks = [block('KHÓA LUẬN TỐT NGHIỆP\nĐề tài: Thử nghiệm dữ liệu\nTên sinh viên: Nguyễn Ví Dụ\nMSSV: 11223344'),
              block('KHÓA LUẬN TỐT NGHIỆP\nTên sinh viên: Người Thứ Hai\nMSSV: 11223345', 10)]
    candidates = extract_candidates(blocks)
    assert len(candidates) == 2
    assert all(c['status'] == 'quarantined' for c in candidates)
    assert all('thesis_title' not in c['fields'] for c in candidates)
    candidates[0]['fields']['student_id']['evidence'][0]['archive_chain'] = [{'invented': 'archive'}]
    assert validate_evidence(candidates, blocks)


def test_unlabelled_number_is_not_verified_identity_and_multiline_title_survives():
    blocks = [block('KHÓA LUẬN TỐT NGHIỆP\nĐề tài: Xây dựng hệ thống\nphân tích dữ liệu kinh tế\n'
                    'Tên sinh viên: Nguyễn Ví Dụ\nLiên hệ: 12345678')]
    candidate = extract_candidates(blocks)[0]
    assert candidate['fields']['thesis_title']['value'] == 'Xây dựng hệ thống phân tích dữ liệu kinh tế'
    assert 'unverified_student_id' in candidate['review_reasons']
    assert candidate['status'] == 'quarantined'
