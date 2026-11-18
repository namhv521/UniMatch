"""Versioned assessments for the UniMatch thesis portal."""
from .thesis_tracks import TRACKS

ASSESSMENT_VERSION = 'roles-v2'
ORIENTATIONS = ('exploring', 'idea', 'defined')
MAJORS = ('it', 'cs', 'other')

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
    return [{'id': key, 'label': track['label'], 'tools': track['tools'],
             'questions': [{'prompt': prompt, 'options': options} for prompt, options, _ in track['questions']]}
            for key, track in TRACKS.items()]


def assess(payload):
    survey, answers = payload.get('survey'), payload.get('answers')
    version = payload.get('version', 'starter-v1')
    if version == 'starter-v1':
        return score(survey, answers, ASSESSMENT, version, max_level=3)
    selected = payload.get('roles')
    orientation, major = payload.get('orientation'), payload.get('major', '')
    tools = payload.get('tools')
    if (version != ASSESSMENT_VERSION or orientation not in ORIENTATIONS or major not in (*MAJORS, '')
            or not isinstance(selected, list) or not 1 <= len(selected) <= len(TRACKS)
            or any(not isinstance(key, str) or key not in TRACKS for key in selected)
            or len(set(selected)) != len(selected) or not isinstance(tools, dict) or tools.keys() != set(selected)):
        raise ValueError('assessment_incomplete')
    for key, values in tools.items():
        allowed = TRACKS[key]['tools']
        if (not isinstance(values, list) or len(values) > len(allowed)
                or any(not isinstance(value, str) or value not in allowed for value in values)
                or len(set(values)) != len(values)):
            raise ValueError('assessment_incomplete')
    bank = {key: (TRACKS[key]['label'], TRACKS[key]['questions']) for key in selected}
    profile = score(survey, answers, bank, version, max_level=4)
    return {**profile, 'roles': selected, 'orientation': orientation, 'major': major, 'tools': tools}


def score(survey, answers, bank, version, *, max_level):
    if any(not isinstance(values, dict) or values.keys() != bank.keys() for values in (survey, answers)):
        raise ValueError('assessment_incomplete')
    skills = []
    for tag, (label, questions) in bank.items():
        level, selected = survey[tag], answers[tag]
        if (type(level) is not int or not 0 <= level <= max_level or not isinstance(selected, list)
                or len(selected) != len(questions) or any(type(i) is not int or not 0 <= i < len(q[1])
                                                         for i, q in zip(selected, questions))):
            raise ValueError('assessment_incomplete')
        correct = sum(i == q[2] for i, q in zip(selected, questions))
        strong = (level >= 3 and correct >= 4) if version == ASSESSMENT_VERSION else (level >= 2 and correct == len(questions))
        status = ('strong' if strong else
                  'demonstrated' if correct else 'self_reported' if level else 'unassessed')
        skills.append(dict(id=tag, label=label, level=level, correct=correct, total=len(questions), status=status))
    return dict(version=version, survey=survey, answers=answers, skills=skills)


def scoring_row(user_id, profile, dossier=None):
    base_title = ''
    extra_tags = []
    extra_keywords = []
    if isinstance(dossier, dict):
        base_title = ' '.join(filter(None, [dossier.get('formal_title', ''), dossier.get('formal_summary', '')])).strip()
        tax_tags = dossier.get('taxonomy_tags') or {}
        if isinstance(tax_tags, dict):
            extra_tags = list(tax_tags.get('topic_tags', [])) + list(tax_tags.get('research_domain_tags', []))
            for values in tax_tags.values():
                if isinstance(values, list):
                    extra_keywords.extend(v.replace('_', ' ') for v in values)
        for item in dossier.get('normalized_skills') or []:
            if isinstance(item, dict) and item.get('label'):
                extra_keywords.append(item['label'])

    if profile.get('version') == ASSESSMENT_VERSION:
        roles = list(dict.fromkeys(list(profile['roles']) + extra_tags))
        strengths = [skill['id'] for skill in profile['skills'] if skill['status'] in ('strong', 'demonstrated')]
        terms = [term for key in profile['roles'] if key in TRACKS for term in TRACKS[key]['keywords']]
        terms += [term for key in strengths for term in profile['tools'].get(key, [])]
        terms += extra_keywords
        return {'student_id': user_id, 'thesis_title': base_title, 'topic_tags': ';'.join(roles),
                'thesis_keywords': ';'.join(dict.fromkeys(terms))}
    tags = [skill['id'] for skill in profile['skills'] if skill['status'] != 'unassessed']
    merged_tags = list(dict.fromkeys(tags + extra_tags))
    kw = [skill['label'] for skill in profile['skills'] if skill['id'] in tags] + extra_keywords
    return {'student_id': user_id, 'thesis_title': base_title, 'topic_tags': ';'.join(merged_tags),
            'thesis_keywords': ';'.join(dict.fromkeys(kw))}
