"""Versioned starter assessment for the UniMatch thesis portal."""
ASSESSMENT_VERSION = 'starter-v1'

# Each question stores its prompt, choices and the zero-based answer index.
ASSESSMENT = {
    'machine_learning': ('Học máy', (
        ('Tập nào dùng để đánh giá cuối sau khi chốt mô hình?',
         ('Tập huấn luyện', 'Tập kiểm thử độc lập', 'Tập dùng để chọn siêu tham số'), 1),
        ('Đưa nhãn của tập kiểm thử vào bước tạo đặc trưng gây ra gì?',
         ('Giảm overfitting', 'Tăng kích thước mẫu', 'Rò rỉ dữ liệu'), 2),
    )),
    'backend_development': ('Phát triển backend', (
        ('Mã HTTP nào biểu thị tài nguyên đã được tạo thành công?',
         ('201', '204', '409'), 0),
        ('Cơ sở dữ liệu nên dùng gì để nhiều yêu cầu đồng thời không tạo trùng khóa?',
         ('Ẩn nút gửi', 'Ràng buộc UNIQUE', 'Đợi vài giây rồi thử lại'), 1),
    )),
    'frontend_development': ('Phát triển frontend', (
        ('Phần tử HTML phù hợp cho thao tác gửi biểu mẫu là gì?',
         ('div', 'span', 'button'), 2),
        ('Thuộc tính nào của label liên kết nó với id của input?',
         ('for', 'role', 'name'), 0),
    )),
    'nlp': ('Xử lý ngôn ngữ tự nhiên', (
        ('TF-IDF ưu tiên từ nào trong một văn bản?',
         ('Từ xuất hiện ở mọi văn bản', 'Từ hay gặp ở văn bản đó nhưng hiếm trong tập', 'Từ dài nhất'), 1),
        ('Một tokenizer làm gì trước khi văn bản được đưa vào mô hình?',
         ('Dịch toàn bộ sang tiếng Anh', 'Kiểm chứng thông tin', 'Tách văn bản thành các token'), 2),
    )),
}


def public_assessment():
    return [{'id': tag, 'label': label,
             'questions': [{'prompt': prompt, 'options': options} for prompt, options, _ in questions]}
            for tag, (label, questions) in ASSESSMENT.items()]


def assess(payload):
    survey, answers = payload.get('survey'), payload.get('answers')
    if any(not isinstance(values, dict) or values.keys() != ASSESSMENT.keys() for values in (survey, answers)):
        raise ValueError('assessment_incomplete')
    skills = []
    for tag, (label, questions) in ASSESSMENT.items():
        level, selected = survey[tag], answers[tag]
        if (type(level) is not int or not 0 <= level <= 3 or not isinstance(selected, list)
                or len(selected) != len(questions) or any(type(i) is not int or not 0 <= i < len(q[1])
                                                         for i, q in zip(selected, questions))):
            raise ValueError('assessment_incomplete')
        correct = sum(i == q[2] for i, q in zip(selected, questions))
        status = ('strong' if level >= 2 and correct == len(questions) else
                  'demonstrated' if correct else 'self_reported' if level else 'unassessed')
        skills.append(dict(id=tag, label=label, level=level, correct=correct, total=len(questions), status=status))
    return dict(version=ASSESSMENT_VERSION, survey=survey, answers=answers, skills=skills)


def scoring_row(user_id, profile):
    tags = [skill['id'] for skill in profile['skills'] if skill['status'] != 'unassessed']
    return {'student_id': user_id, 'thesis_title': '', 'topic_tags': ';'.join(tags),
            'thesis_keywords': ';'.join(skill['label'] for skill in profile['skills'] if skill['id'] in tags)}
