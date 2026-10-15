# Kiểm chứng khảo sát sinh viên đầu kỳ — v2

## Đầu vào thực tế

Workbook `assets/student-skills-template.xlsx` chuyển sang sheet `KhaoSat`, 26 tiêu đề tiếng Việt. Sinh viên chỉ bắt buộc có mã, tên và ít nhất một kỹ năng đã học/dùng. Đề tài và mô tả có thể để trống hoàn toàn. Các nhóm công nghệ không áp dụng để trống; không cần tự khai phương pháp nghiên cứu hoặc vai trò chưa có.

Hồ sơ giữ 13 nhóm dữ liệu cũ và thêm kỹ năng mobile/công cụ phát triển một cách tường minh. Mức tự đánh giá, thông tin lớp/ngành, phần việc trong dự án, minh chứng, sở thích và mục tiêu học tập được lưu riêng trong `survey`, bao gồm câu trả lời gốc. Điểm matching chưa dùng mức tự đánh giá; không coi công nghệ muốn học là năng lực hiện có.

## Kiểm tra hồi quy

- Chấp nhận khảo sát không có tên/mô tả đề tài.
- Lưu nguyên các trường khảo sát và mức độ; ngữ cảnh không tham gia feature text.
- Kiểm mức 1–3, kỹ năng phải được khai trong nhóm công nghệ, từ chối mức trùng/sai định dạng.
- Giữ framework mobile và công cụ phát triển riêng, vẫn đưa kỹ năng khai báo vào matching.
- Ghi schema v2 và sheet nguồn vào provenance; mẫu cũ SinhVien vẫn được nhận.
- Từ chối file có cả hai sheet nhập liệu để tránh chọn nhầm danh sách.
- Giữ nguyên giới hạn file, công thức, số sinh viên và kiểm tra XML/ZIP đã có.

Các kiểm thử cohort gồm **34 trường hợp đạt**. Frontend có **13 unit tests đạt**, syntax và build đạt. UI hiển thị khảo sát trong phần mở rộng từng SV, escape toàn bộ nội dung nhập.

## Evidence cuối

Kết quả tổng hợp ở `outputs/final_validation/verification-survey-2026-10-15.json`; JUnit ở `pytest-survey-2026-10-15.xml`, HTTP/SQLite readback ở `survey-live-smoke-2026-10-15.json` cùng thư mục. Workbook được render và đọc lại trong `outputs/student-template/`. Bản mẫu v1 được giữ local tại `outputs/student-template/archive/student-skills-template-v1.xlsx`.

Input live/browser dùng 38 sinh viên **tổng hợp để kiểm thử**, không phải khảo sát thật. Việc khảo sát thực tế và xác nhận năng lực chưa diễn ra. Hướng dẫn thu thập, chuẩn hóa và giới hạn áp dụng nằm trong [student_cohort_upload.md](student_cohort_upload.md).

## Kết quả cuối

Full Python suite: **190 passed, 1 skipped, 1 warning trong 175,98 giây**; skip là PostgreSQL tùy chọn chưa cấu hình. HTTP/SQLite và browser dùng bản sao của chính workbook v2, 38 hồ sơ không đề tài/mô tả, có điểm matching dương và tải đúng 10/10/9/9 cho bốn GV. Nguyện vọng không vào feature text. Cả luồng UI mới và ghép cặp cũ đạt desktop/mobile. 30 hash dữ liệu/model gốc giữ nguyên.

SHA256 workbook: `eeddc40db67098773faf738d57d0c47b24c8579438c45a7dbe9832cf7a887461`. Lượt tạo đã xuất workbook và log cuối; wrapper trả mã 1 trong bước tự sinh inspect phụ của runtime. Không coi mã này là build thành công: file bàn giao được kiểm chứng độc lập bằng render, readback và upload qua API thật.
