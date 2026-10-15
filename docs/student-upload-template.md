# Mẫu khảo sát năng lực sinh viên trước khóa luận

File `assets/student-skills-template.xlsx` dùng để khảo sát sinh viên khi bắt đầu chuẩn bị khóa luận. Sinh viên chưa cần có tên hoặc mô tả đề tài.

## Nội dung cần thu thập

- `Mã sinh viên` và `Họ và tên` là bắt buộc.
- Mỗi sinh viên khai ít nhất một kỹ năng hoặc framework **đã học hoặc đã dùng**.
- Lớp, chuyên ngành, mức độ tự khai, dự án, link sản phẩm, lĩnh vực quan tâm và mục tiêu học tập giúp giảng viên rà soát kết quả matching.
- `Tên đề tài` và `Mô tả đề tài` nằm cuối bảng, có thể để trống và bổ sung sau.
- Vai trò chuyên môn và phương pháp nghiên cứu cũng có thể để trống nếu sinh viên chưa xác định.

Nhiều giá trị trong một ô cách nhau bằng dấu chấm phẩy (`;`). Mức độ là tùy chọn và dùng dạng `Python|2; React|1`:

1. Đã học hoặc làm theo hướng dẫn.
2. Tự làm được một chức năng hoặc bài tập.
3. Đã dùng trong dự án và giải thích được phần việc của mình.

Thang này là thông tin tự khai để hỗ trợ phân công, không phải điểm thi hay kết luận khách quan về năng lực.

## Quan hệ với dữ liệu hiện hành

Sheet `DanhMucSkill` chứa 13 nhóm matching và các giá trị được trích từ 215 khóa luận đã có. Đây là ngôn ngữ mô tả của dữ liệu lịch sử, không phải bằng chứng rằng sinh viên hiện tại có các kỹ năng đó.

Sinh viên chỉ điền kỹ năng mình thực sự đã học hoặc đã dùng. `Lĩnh vực muốn tìm hiểu` và `Kỹ năng muốn học thêm` được lưu riêng, không được xem là kỹ năng hiện có khi matching. Hai nhóm bổ sung `Framework mobile đã dùng` và `Công cụ phát triển đã dùng` phục vụ khảo sát thực tế; các ví dụ Flutter, React Native, Git, Docker và Postman được ghi rõ là gợi ý ngoài dữ liệu nguồn.

## Quy tắc file

- Chỉ nhập dữ liệu tại sheet `KhaoSat`, bắt đầu từ dòng 2.
- Không đổi tên sheet hoặc 26 tiêu đề tiếng Việt ở dòng 1.
- Mã sinh viên được định dạng văn bản để giữ số 0 ở đầu.
- File nhận tối đa 1.000 sinh viên và không chấp nhận công thức trong vùng dữ liệu.
- Sheet `HuongDan` giải thích toàn bộ 26 trường và đưa ví dụ cách nhập.

## Tạo lại file

Builder dùng `@oai/artifact-tool` từ Codex runtime, không cài dependency vào repository:

```powershell
$codexNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
& $codexNode scripts\build_student_template.mjs
```

Trước khi chạy, tạo junction `outputs/student-template/node_modules` trỏ tới thư mục dependency runtime. Builder đọc schema v2 và dữ liệu theo đường dẫn tương đối từ repository, xuất đúng một file Excel vào `assets/`, đồng thời tạo preview và báo cáo kiểm chứng trong `outputs/student-template/`.
