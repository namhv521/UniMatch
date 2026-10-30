# Triển khai RL hai cấp từ nguồn mới — 28/10/2026

Đặc tả chi phối: [RL hai cấp](rl_hai_cap_va_corpus_giang_vien_20261027.md), với các điều chỉnh tháng mới nhất của người dùng. Đây là pipeline nghiên cứu chạy được trên nguồn mới; chưa phải model được duyệt để phân công thực tế.

## Sao lưu và phạm vi dữ liệu

- Remote `backup`: `242fbea5351daafd682f7842cedc9ac2ff6b2c25`, đã kiểm tra bằng `git ls-remote`.
- Nhánh triển khai: `susois/nested-rl-20261028`.
- Run riêng: `data_rebuild/nested_rl_20261028/20261027T190955Z/`. Timestamp là UTC; thời gian địa phương đã sang 28/10.
- Kiểm tra sau chạy: **225 file nguồn/gold/release cũ không đổi size/mtime**; SHA-256 của hai CSV gold cũ khớp trước chạy.
- Dữ liệu cá nhân, raw, feature và checkpoint mới tiếp tục nằm trong `data_rebuild/` bị Git ignore. Commit code/docs/tests không đưa chúng lên GitHub.

Giảng viên được lấy HTTP mới từ FIT NEU, qua sitemap công khai vì danh bạ render bằng JavaScript. Sinh viên được sao chép bytes gốc và trích xuất lại toàn văn từ bộ PDF/DOCX được cung cấp trong `data/1.pdfs`; **không phải tải lại sinh viên từ Internet**, cũng không đọc lại gold/bronze/features cũ. Chưa có URL tải nguồn sinh viên để thực hiện một đợt tải mạng độc lập.

## Quy tắc phân kỳ hiện hành

Ngày có bằng chứng trên trang **1–2** quyết định học kỳ học vụ:

| Tháng của năm Y | Học kỳ học vụ |
|---|---|
| 1–5 | `(Y−1).2` |
| 6–8 | `(Y−1).3` — hè |
| 9–12 | `Y.1` |

Học kỳ học vụ khác phiên bản training. V1 gom lịch sử đến hết 2024; V2 nhận sinh viên tháng 1–5/2025; V3 nhận tháng 6–12/2025, gồm hè `2024.3` và kỳ chính `2025.1`; V4 nhận tháng 1–5/2026. Hè `2025.3` đã có nhãn học vụ nhưng chưa ánh xạ phiên bản training mới. Không suy một tài liệu thuộc `2026.1` từ ngày hiện tại.

Cutoff snapshot faculty/model đã chốt vẫn là 31/12/2024, 30/06/2025, 31/12/2025, 30/06/2026. Đây là mốc chốt phiên bản, không thay thế cửa sổ học kỳ của sinh viên hoặc thời điểm quyết định trong kỳ. Vòng V3 tháng 6 không được kế thừa model V2 chỉ hoàn tất cuối tháng 6 trước khi checkpoint đó thực sự có sẵn.

Chỉ có năm ≤2024: biết pool lịch sử V1 nhưng chưa biết học kỳ học vụ. Chỉ có năm 2025: chưa phân biệt V2/V3. Ngày bìa mâu thuẫn giữ pending. DOCX không có trang render thật chưa được coi các đoạn đầu là “trang 1–2”.

## Nguồn mới và độ đầy đủ

| Hạng mục | Kết quả |
|---|---:|
| Hồ sơ FIT NEU lấy mới | 38 |
| Mục công bố gắn với từng hồ sơ | 413 |
| Lỗi tải hồ sơ FIT | 0 |
| File sinh viên đầu vào | 219 |
| Nội dung sinh viên duy nhất sau khử trùng bytes | 218 |
| Block văn bản toàn văn | 322.007 |

413 là **mục công bố theo hồ sơ**, có thể trùng bài giữa đồng tác giả. Đã giữ trích dẫn, liên kết bài/DOI nếu có và bằng chứng năm; chưa tải toàn văn từng bài liên kết. Ngày dạng số tập/tạp chí không được suy thành tháng công bố.

Đã thử ba tài khoản có URL xác định: hai Scholar bị robots chặn; ResearchGate trả HTTP 403. Không có GitHub trong seed/hồ sơ vừa lấy. Các lần thử có HTTP receipt; không vượt chặn, không thêm bài suy diễn, dùng FIT làm nguồn dự phòng.

`students/` giữ lần trích xuất đầu; `students_dates/` ghi lần điều chỉnh lịch; **`students_reviewed/` là derivative hiện hành** sau sửa Unicode tổ hợp và khôi phục một tiêu đề có header ngoặc kép. Raw và hai snapshot trước giữ nguyên, mỗi derivative có manifest trỏ về nguồn gốc.

| Nhóm sau rà soát trích xuất | Số hồ sơ |
|---|---:|
| V1 | 32 |
| V2 | 80 |
| V3 | 63 |
| V4 | 1 |
| Học kỳ đã biết, training chưa ánh xạ | 19 |
| Thiếu ngày hợp lệ | 11 |
| Ngày chưa phân kỳ được / mâu thuẫn | 12 |

11 thiếu ngày gồm 9 DOCX chưa có trang render, một PDF bìa scan và một PDF không có ngày ở trang 1–2. OCR tiếng Việt/Anh hiện chưa có runtime/model cấu hình. 12 chưa phân kỳ gồm năm 2025 đơn lẻ hoặc bằng chứng bìa mâu thuẫn. Tất cả field vẫn là ứng viên trích xuất, không phải phê duyệt học vụ.

## Feature và split đã thực thi

- Baseline TF-IDF ký tự fit **chỉ trên train V1**; encoder đóng băng cho các kỳ sau, có hash và danh sách ID fit.
- Sinh viên dùng tiêu đề khóa luận làm **proxy tài liệu hồi cứu**, không diễn giải công nghệ cuối khóa luận thành năng lực đầu kỳ.
- Giảng viên dùng trích dẫn công bố có khoảng thời gian kết thúc trước cutoff; công bố thiếu thời gian giữ ngoài feature. V1/V2 dùng 331 mục; V3/V4 dùng 341 mục.
- Registry cố định 38 giảng viên, 23 người có văn bản đủ điều kiện trong baseline này; không đồng nghĩa chỉ 23 người đủ năng lực hướng dẫn.
- State 343 chiều, không tạo vector năng lực cá nhân khi chưa có bằng chứng.
- Split hash theo MSSV cố định qua kỳ, tránh một người chuyển từ holdout sang train. Test độc lập được lưu nhưng chưa đánh giá.
- Quota chia đều và eligibility trong suite này là giả định mô phỏng nghiên cứu; chưa phải chính sách học vụ xác nhận. Quota được dựng lại theo từng split, nên điểm validation không đại diện nguyên cohort vận hành.

| Suite | Train | Validation | Test | Trạng thái |
|---|---:|---:|---:|---|
| V1 | 24 | 4 | 4 | Đủ chạy kỹ thuật |
| V2 | 56 | 9 | 14 | Đủ chạy kỹ thuật; một hồ sơ thiếu field |
| V3 | 43 | 7 | 11 | Đủ chạy kỹ thuật; hai hồ sơ thiếu field |
| V4 | — | — | — | Chỉ một hồ sơ, không đủ chia split |

Ngày công bố/khóa luận và ngày thu thập được lưu riêng. Nguồn chụp năm 2026 không chứng minh feature có sẵn vào 2024. Vì vậy chạy hiện tại bắt buộc `retrospective_document_proxy`, `prediction_time_verified=false`.

## Vòng RL đã triển khai

`src/rl/nested_learning.py` thực hiện bootstrap V1, rồi kế thừa checkpoint được chấp nhận của kỳ liền trước. Trong cùng kỳ giữ cohort và số vòng liên tiếp. Vòng sau mang policy, optimizer, counter từ parent; PPO thu rollout mới, DQN giữ trọng số nhưng loại replay cũ khi ngữ nghĩa tín hiệu/reward/mask đổi. Vòng mới không ghi đè parent.

Mỗi vòng lưu input, snapshot/signal hash, quyết định, checkpoint training và bản inference; kiểm tra reload/inference cho cùng trace. Các vòng tương lai còn ghi hash mã engine/native learner/environment tại đầu chạy; đợt smoke đầu này được chạy trước khi thêm trường hash mã đó, nên manifest cũ không có trường bổ sung và được giữ nguyên.

Phản hồi người thật phải có JSON có kiểu, ví dụ **minh họa schema, không phải dữ liệu thật**:

```json
{
  "signal_id": "confirmed-preference-event",
  "changes": [
    {"student_id": "<train_student_id>", "advisor_id": "<advisor_id>", "field": "preferences", "old": 0.0, "new": 0.8},
    {"student_id": "<train_student_id>", "advisor_id": "<advisor_id>", "field": "preference_known", "old": false, "new": true}
  ]
}
```

Signal có `source_path`, `source_sha256`, `available_at`, trạng thái `verified`; snapshot phải bind `applied_signal_source_sha256` và hash problem train/validation. Engine đối chiếu toàn bộ thay đổi thực tế với khai báo `old/new`, chặn target holdout, feedback không tác dụng hoặc thay đổi không có nguồn. Preference cập nhật preference/mask; phản hồi giảng viên cập nhật eligibility/present/capacity; điều phối có thể sửa score/availability có bằng chứng. Outcome/reward adapter chưa hỗ trợ phải bị chặn, không được gán điểm giả.

Thêm bước mà không có tín hiệu mới chỉ chạy như control `extra_steps_no_new_signal`, không tuyên bố tác dụng tín hiệu. Chuyển kỳ bắt buộc holdout cũ đóng băng để đo quên. Candidate giảm quá ngưỡng bị từ chối; không khởi tạo lại để lách kết quả. Hiện chưa có phản hồi thật nên vòng 2–4 trong kỳ là `unavailable`.

## Kết quả chạy thử hiện tại

Seed 42, **1.024 bước/vòng**, metric `objective_per_student` trên validation. Ngưỡng tăng >0, không cho giảm mục tiêu mới/cũ. Chấp nhận bootstrap chỉ chứng minh chạy và ràng buộc hợp lệ, không yêu cầu vượt baseline.

| Learner / kỳ | Parent trên bối cảnh mới | Candidate | Hungarian | Quyết định |
|---|---:|---:|---:|---|
| PPO V1 | — | 0,071804 | 0,119531 | accepted bootstrap |
| PPO V2 | 0,078284 | 0,081187 | 0,133791 | accepted nghiên cứu |
| PPO V3 | 0,112315 | 0,093582 | 0,146125 | rejected, giữ V2 |
| DQN V1 | — | 0,118531 | 0,119531 | accepted bootstrap |
| DQN V2 | 0,104525 | 0,090103 | 0,133791 | rejected, giữ V1 |

Tất cả warm start đã chạy có `start_weights_equal_parent=true`; reload và inference parity đạt. PPO V2 giữ điểm V1 không giảm; DQN V2 giảm cả mục tiêu mới và holdout V1. Không chạy tiếp lineage đã bị chặn. Các số trên thuộc những bối cảnh validation khác nhau; không trừ điểm V1 ở hàng trước với V2 để đo tiến bộ.

RL hiện vẫn thấp hơn Hungarian trong smoke. Không kết luận hội tụ, quan hệ nhân quả của feedback, hiệu quả giáo dục hoặc tổng quát hóa từ một seed và validation ít mẫu. Final test chưa mở; model phục vụ hiện tại chưa được thay.

## Chạy lại

Kiểm chứng: 75 tests của pipeline/vòng RL mới đạt; 55 tests native matching, benchmark, PPO và DQN đạt trong đợt kiểm tra tương thích. Đã kiểm tra thêm đường V2 dùng encoder V1 có manifest. `git diff --check` đạt; cảnh báo còn lại là deprecation có sẵn của Gym wrapper. Không kiểm thử lại frontend/backend vì không đổi runtime đó.

Chạy headless bằng Python, không cần Chrome hoặc desktop Windows/Linux. Dùng môi trường dependency hiện có; nếu OCR thì cần cấu hình model ngôn ngữ riêng.

```powershell
# Luôn dùng thư mục run mới; các lệnh từ chối ghi đè output.
$FreshRun = 'data_rebuild/nested_rl_20261028/<new-run-id>'
python -X utf8 scripts/collect_fresh_faculty.py --output "$FreshRun/faculty" --seed-csv data_rebuild/advisor_urls/giang_vien_urls.csv
python -X utf8 scripts/collect_fresh_faculty.py --output "$FreshRun/faculty_dates" --reparse-from "$FreshRun/faculty"
python -X utf8 scripts/collect_fresh_faculty.py --output "$FreshRun/faculty_external" --external-from "$FreshRun/faculty"
python -X utf8 scripts/collect_fresh_students.py --source data/1.pdfs --output "$FreshRun/students" --ocr off
python -X utf8 scripts/collect_fresh_students.py --rederive-temporal "$FreshRun/students" --output "$FreshRun/students_reviewed"
python -X utf8 scripts/run_fresh_research.py --run $FreshRun --output "$FreshRun/research" --student-collection "$FreshRun/students_reviewed" --mode retrospective_document_proxy --timesteps 1024
```

Kiểm tra một bundle đã tạo:

```powershell
python -X utf8 scripts/train_nested_rl.py --verify 'data_rebuild/nested_rl_20261028/20261027T190955Z/research/rounds/ppo/V2'
```

Artifact kết quả chính: `research/index.json`; mỗi round có `report.json`, `decision.json`, `manifest.json`; `preservation_after.json` xác nhận dữ liệu cũ. Các suite sơ bộ trong `suites/` không được dùng cho đợt train này; đợt train dùng `research/suites/` từ `students_reviewed`.

Các bước còn phụ thuộc nguồn thật: bổ sung ngày cho tài liệu thiếu/mâu thuẫn, PDF render cho DOCX/bìa scan, nguyện vọng và phản hồi có timestamp, quota/eligibility được xác nhận, dữ liệu đầu kỳ và outcome. Cần các nguồn đó để chạy đúng vòng feedback và đánh giá hiệu quả học vụ, thay vì tăng số bước rồi gọi là một vòng cải tiến mới.
