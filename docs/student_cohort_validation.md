# Kiểm chứng nhập sinh viên theo kỳ — mẫu v1, 15/10/2026

Bản ghi lịch sử cho mẫu 17 cột trước khi bổ sung khảo sát đầu kỳ. Workbook hiện tại đã chuyển sang mẫu v2 KhaoSat; xem hướng dẫn mới tại [student_cohort_upload.md](student_cohort_upload.md). Hash và số cột ở bản ghi này chỉ áp dụng artifact v1 tại thời điểm kiểm chứng.

## Phạm vi

Trang `#/students`, workbook thu thập kỹ năng, bốn API nhập/phân bổ và persistence trên SQLite local. Dữ liệu test 38 sinh viên là **dữ liệu tổng hợp**, không phải danh sách đã thu thập từ sinh viên thật. Danh sách giảng viên và danh mục kỹ năng được lấy từ dữ liệu hiện có.

## Kết quả đã kiểm chứng

Full Python suite: **180 passed, 1 skipped, 1 warning trong 73,09 giây**. Skip là PostgreSQL integration tùy chọn chưa cấu hình; warning Gymnasium hiện có không làm test thất bại.

- Điền 38 dòng vào bản sao của **chính workbook được bàn giao**, upload qua HTTP có đăng nhập và chọn bốn GV, gồm TS PHẠM MINH HOÀN.
- Nhận đủ 38 assignment; chỉ bốn GV đã chọn nhận SV; quota và tải thực tế bằng nhau: **10/10/9/9**.
- Kết quả, dữ liệu cohort và provenance được lưu trong `simulation_runs`; dữ liệu tồn tại sau restart backend. SQLite integrity check trả `ok`; tập gốc vẫn có 215 SV và 38 GV.
- 30 hash dữ liệu/model đóng băng khớp manifest trước khi thêm luồng upload; không thay đổi corpus nghiên cứu hoặc checkpoint.
- Browser QA trang mới đạt trên desktop 1440 px và mobile 390 px: tải mẫu, preview, tìm GV không dấu, chọn/bỏ checkbox, quota, kết quả, lỗi file hỏng, xóa kết quả khi thay đổi input và không tràn ngang trang.
- Browser QA luồng ghép cặp/kết quả cũ đạt desktop/mobile. Frontend syntax, 13 unit tests và build năm asset đạt.
- Ruff cho các file Python của thay đổi, compileall, `git diff --check` đạt. `check_publish.py` không phát hiện private file trong Git index.

## Các trường hợp lỗi có regression

Thiếu/trùng ID, thiếu tên/kỹ năng, header sai, file hỏng/công thức, XML worksheet hỏng, worksheet khai báo quá nhiều dòng, file vượt giới hạn kể cả stream không có Content-Length tin cậy, GV lạ/trùng/không chọn, đảo thứ tự query GV và số SV ít hơn số GV. Matching giữ được C++, C#, R; kết quả ghi token pattern để truy xuất cấu hình.

## Workbook

- `assets/student-skills-template.xlsx`: ba sheet, 17 cột, 1.000 dòng nhập trống, 13 nhóm kỹ năng/vai trò và 2.119 giá trị danh mục lấy từ 215 hồ sơ.
- SHA256: `5a692295b6fab68777dfaf635616511295ac2c59d2440959df12258c3542445d`.
- Đã render và đọc lại cả ba sheet; sheet nhập không chứa sinh viên mẫu/công thức, mã sinh viên giữ định dạng Text.

## Evidence

- `outputs/final_validation/pytest-student-upload-2026-10-15.xml`: kết quả full Python suite.
- `outputs/final_validation/cohort-live-smoke-2026-10-15.json`: readback HTTP/SQLite.
- `outputs/final_validation/release-manifest-student-upload-2026-10-15.json`: hash 115 source/assets và năm asset frontend.
- `outputs/final_validation/verification-student-upload-2026-10-15.json`: tổng hợp kiểm chứng và hash evidence.
- `outputs/student-template/readback-validation.json` và `previews/`: kiểm chứng workbook.
- `frontend/qa-artifacts/cohorts-desktop.png`, `cohorts-mobile.png`: bằng chứng UI.

## Giới hạn

Đã xác nhận runtime local SQLite. Docker, PostgreSQL và triển khai Vercel/Render chưa được kiểm chứng trong thay đổi này. Chính sách quota là chia đều theo số SV và GV được người điều phối chọn; không thay thế quyết định giao nhiệm vụ chính thức của đơn vị. Chất lượng matching phụ thuộc kỹ năng tự khai và hồ sơ GV hiện có.
