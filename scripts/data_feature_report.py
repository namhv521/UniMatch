"""Generate Week 2 feature-quality report from the frozen training cohort only."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.dataset import load_dataset


def report_field(value):
    text = (value or '').casefold()
    for name, terms in [
        ('AI / dữ liệu', ('ai', 'trí tuệ', 'học máy', 'deep learning', 'machine learning', 'dữ liệu', 'data science')),
        ('Di động', ('mobile', 'di động', 'android', 'ios')),
        ('IoT', ('iot', 'vạn vật', 'nhúng')),
        ('An toàn thông tin', ('bảo mật', 'an toàn', 'security', 'an ninh')),
        ('Web', ('web', 'thương mại điện tử', 'website')),
        ('Game', ('game', 'trò chơi')),
        ('Hệ thống thông tin / phần mềm', ('hệ thống thông tin', 'phần mềm', 'information system')),
    ]:
        if any(term in text for term in terms):
            return name
    return 'Khác / chưa phân nhóm'


if __name__ == '__main__':
    data = load_dataset()
    groups = defaultdict(list)
    for index in data['split']['train']:
        field = report_field(data['students'][index].get('field_category'))
        groups[field].append(index)
    rows = []
    for field, indices in sorted(groups.items()):
        values = data['scores'][indices]
        rows.append(f"| {field.replace('|', '/')} | {len(indices)} | {values.mean():.6f} | {values.max(axis=1).mean():.6f} |")
    curation = json.loads(Path('data/curated/curation_report.json').read_text(encoding='utf-8'))
    text = '\n'.join([
        '# Báo cáo dữ liệu và đặc trưng — Tuần 2', '',
        f"Snapshot SHA256: `{data['sha256']}`.", '',
        (f"Đã trích xuất {curation['llm_extracted_documents']}/{curation['unique_source_documents']} tài liệu; "
        f"{len(data['students'])} sinh viên và {len(data['advisors'])} giảng viên."),
        (f"Train/validation/test: {len(data['split']['train'])}/{len(data['split']['val'])}/{len(data['split']['test'])}. "
        f"Ngoài giao thức do năm2026: {len(data['future_indices'])} hồ sơ."), '',
        '## Tương thích theo lĩnh vực trên train', '',
        ('Nhóm thống kê dùng từ khóa trong field_category; ưu tiên AI/dữ liệu → Di động → IoT → '
        'An toàn thông tin → Web → Game → Hệ thống thông tin/phần mềm → Khác. '
        'Đây là phép gộp phục vụ báo cáo, không thay đổi nhãn nguồn hay snapshot huấn luyện. '
        'Mean all pairs là trung bình với toàn bộ giảng viên; mean best advisor là trung bình điểm cao nhất '
        'từng sinh viên, chưa xét quota. Đây là độ tương đồng văn bản, không phải xác suất phù hợp hoặc accuracy.'), '',
        '| Lĩnh vực nguồn | Số SV train | Mean all pairs | Mean best advisor |',
        '|---|---:|---:|---:|', *rows, '',
        '## Kiểm soát chất lượng', '',
        '- TF-IDF fit chỉ trên158 hồ sơ train; giữ nguyên vocabulary khi transform validation/test.',
        '- Dữ liệu test không dùng trong thống kê tương thích của báo cáo này.',
        '- Nguồn trùng được ghi manifest; metadata sửa có quote/page trong metadata_adjudications.json.',
        '- Kỹ năng không được bằng chứng hỗ trợ bị giữ ngoài profile; không biến missing thành kỹ năng tự suy đoán.',
        '- MPNet có ma trận220×768 và38×768; TF-IDF220×38. Nhánh dense chưa dùng để thay baseline đã khóa.',
        '- Snapshot giảng viên2026 và nguồn không rõ ngày giới hạn diễn giải backtest lịch sử.',
        '- Lĩnh vực/role và kỹ năng giảng viên suy luận vẫn cần chuyên gia đánh giá, dù mọi dòng có provenance.',
        '', f"Giá trị ma trận train hữu hạn: {bool(np.isfinite(data['scores'][data['split']['train']]).all())}.",
    ])
    Path('docs/week2_data_feature_report.md').write_text(text + '\n', encoding='utf-8')
    print(json.dumps({'training_groups': len(groups), 'output': 'docs/week2_data_feature_report.md'}))
