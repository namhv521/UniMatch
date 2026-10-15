# Nhập sinh viên bằng Excel và chọn giảng viên hướng dẫn

Trang local: `http://127.0.0.1:8000/#/students`. Dùng tài khoản hiện tại của dashboard.

## Quy trình

1. Mở **Nhập sinh viên** và tải Excel mẫu.
2. Điền sheet **KhaoSat** của mẫu mới, mỗi dòng là một sinh viên, từ dòng 2. Giữ nguyên tên cột dòng 1. File mẫu cũ có sheet **SinhVien** vẫn được chấp nhận.
3. Điền **mã sinh viên**, **họ tên** và ít nhất một kỹ năng/vai trò. Các nhóm kỹ năng không áp dụng có thể để trống.
4. Upload `.xlsx`, xem trước danh sách và thông báo lỗi nếu có.
5. Tích tên các GV tham gia hướng dẫn đợt này, ví dụ **TS PHẠM MINH HOÀN** và ba GV khác.
6. Kiểm tra số SV/GV và phân bổ dự kiến, rồi chạy phân bổ.
7. Xem tải từng GV và kết quả SV → GV kèm điểm tương thích.

File tối đa 5 MiB và 1.000 sinh viên. Dòng trống không được tính là sinh viên. Mã không được trùng; thiếu tên/kỹ năng phải bổ sung trước khi phân bổ. Công thức trong dữ liệu upload bị từ chối: nếu dữ liệu ban đầu được tính bằng Excel, copy và **Paste Values** vào file nhập.

## Điền kỹ năng đúng cấu trúc dữ liệu

| Cột Excel | Nội dung |
|---|---|
| `student_id` | Mã sinh viên, giữ dạng Text để không mất số 0 đầu |
| `student_name` | Họ và tên |
| `thesis_title` | Tên hoặc hướng đề tài dự kiến, nếu đã có |
| `abstract` | Mô tả ngắn đề tài/nguyện vọng, nếu đã có |
| `web_languages` | Ngôn ngữ web |
| `app_languages` | Ngôn ngữ ứng dụng |
| `frontend_frameworks` | Framework frontend |
| `backend_frameworks` | Framework backend |
| `ai_frameworks` | Framework AI |
| `database_cache` | Cơ sở dữ liệu/cache |
| `app_db_backend` | Công nghệ backend/database ứng dụng |
| `ai_problems` | Bài toán AI đã học/thực hiện |
| `data_tools` | Công cụ xử lý dữ liệu |
| `data_models` | Mô hình dữ liệu |
| `research_methods` | Phương pháp nghiên cứu |
| `primary_role` | Vai trò chuyên môn chính |
| `secondary_roles` | Vai trò chuyên môn khác |

Nhiều giá trị trong một ô phân tách bằng dấu `;`, ví dụ `Python; JavaScript`. Danh mục trong workbook được tổng hợp từ các nhóm tương ứng trong dữ liệu đề tài hiện có; đó là gợi ý để dùng từ nhất quán. Không cần điền tất cả nhóm và không tự thêm kỹ năng sinh viên chưa có. Nội dung đề tài/nguyện vọng không thay thế yêu cầu có ít nhất một kỹ năng/vai trò.

File mẫu không chứa sinh viên thật hay dòng sinh viên mẫu trong sheet nhập, tránh vô tình phân bổ dữ liệu minh họa. Phần hướng dẫn và danh mục kỹ năng nằm ở các sheet riêng. Với mẫu khảo sát mới, tiêu đề cột hiển thị tiếng Việt; bảng trên là các key dữ liệu được hệ thống chuẩn hóa ở bên trong.

## Khảo sát trước khi sinh viên có đề tài

Không yêu cầu sinh viên tự đặt tên đề tài, viết abstract hay chọn hướng nghiên cứu để đủ điều kiện nhập. Hai cột này nằm cuối mẫu và để trống nếu chưa có. Một hồ sơ chỉ có mã, tên và kỹ năng hiện tại vẫn matching được; không sinh tên đề tài/abstract thay thế.

Mẫu bổ sung lớp/khóa, ngành, framework mobile, công cụ phát triển, mức độ từng kỹ năng, dự án đã làm và phần việc cá nhân, link minh chứng, lĩnh vực muốn tìm hiểu và kỹ năng muốn học. Chỉ điền các nhóm công nghệ đã học hoặc thực sự sử dụng. Framework frontend/backend/AI nằm trong đúng nhóm tương ứng; framework mobile và công cụ phát triển có cột riêng. Các nhóm phương pháp nghiên cứu, bài toán AI và vai trò có thể để trống nếu chưa có kinh nghiệm.

Mức độ tự đánh giá là tùy chọn, nhập `Python|2; React|1` sau khi khai Python và React trong nhóm kỹ năng tương ứng:

| Mức | Ý nghĩa tự khai |
|---|---|
| 1 | Đã học hoặc làm theo hướng dẫn |
| 2 | Tự làm được chức năng/bài tập |
| 3 | Đã dùng trong dự án và giải thích được phần việc của bản thân |

Chỉ chấp nhận mức 1–3 và kỹ năng đã khai. Để trống mức nếu chưa tự đánh giá; hệ thống không mặc định người đó chưa biết, cũng không tự gán mức cao. Đây là thang phục vụ khảo sát, chưa phải thang năng lực đã được kiểm định. Mức tự đánh giá được lưu để người điều phối đối chiếu; chưa dùng làm trọng số matching.

### Cách tổ chức thu thập

1. Phát mẫu và giải thích một lần các mức; yêu cầu mô tả phần việc cá nhân thay vì chỉ liệt kê công nghệ của cả nhóm.
2. Thu mỗi sinh viên một dòng. Khi tổng hợp nhiều file, gộp các dòng vào một sheet KhaoSat và kiểm tra mã SV trùng trước khi upload; không ghép nhiều người vào cùng một ô.
3. Kiểm tra ngẫu nhiên minh chứng hoặc trao đổi ngắn với sinh viên; chỉnh câu trả lời khi có xác nhận. Không suy luận rằng có link GitHub đồng nghĩa sử dụng thành thạo mọi thư viện trong repository.
4. Upload để chuẩn hóa danh sách và xem lỗi; rà soát tên kỹ năng chưa thống nhất rồi sửa file gốc. Hiện hệ thống tách dấu `;`, bỏ khoảng trắng và trùng không phân biệt hoa/thường; không tự coi mọi cách viết khác nhau là cùng một công nghệ.
5. Chọn GV tham gia kỳ này rồi phân bổ; người điều phối xem các trường hợp điểm thấp/không có từ vựng giao nhau trước khi chốt.

### Từ khảo sát sang dữ liệu matching

13 nhóm tương ứng được ánh xạ trực tiếp sang contract cũ. Framework mobile/công cụ phát triển được giữ thành kỹ năng bổ sung, không ép thành framework backend hoặc kỹ năng nghiên cứu. Nội dung kỹ năng khai báo và đề tài thực có (nếu đã điền) tạo văn bản matching. Tên, mã, lớp, ngành, mô tả dự án, đường dẫn, mức độ, lĩnh vực quan tâm và kỹ năng muốn học được lưu riêng; không được biến thành bằng chứng năng lực để tăng điểm.

Danh mục lấy từ 215 hồ sơ đề tài trước đây giúp thống nhất cách phân nhóm; các giá trị trích xuất từ đề tài không tự chứng minh năng lực cá nhân của sinh viên hiện tại. Vì vậy dữ liệu khảo sát được lưu riêng, có bản gốc và hash, không tự nhập thành train/test hoặc nhãn assignment đúng. Muốn huấn luyện/đánh giá lại cần hồ sơ khảo sát thực, phân công đã được xác nhận và đánh giá từ người điều phối/GV theo quy trình riêng.

## Quota cân bằng theo GV tham gia

Gọi N là số sinh viên hợp lệ và M là số GV được chọn:

```text
q, r = divmod(N, M)
r GV nhận q + 1 sinh viên
M - r GV nhận q sinh viên
```

Với **38 SV và 4 GV**, kết quả tải là **10, 10, 9, 9**. Với 38 SV và 38 GV, mỗi GV nhận một SV. Với một GV, người đó nhận toàn bộ nhóm. Nếu số SV ít hơn số GV được chọn thì một số GV nhận 0. Không chọn GV thì không chạy phân bổ.

Quota được gán theo thứ tự danh sách GV ổn định, không phụ thuộc thứ tự click checkbox. Tổng quota bằng đúng số SV, vì vậy không sinh trường hợp 10–10–10–8 cho ví dụ 38/4. Đây là **chính sách chia tải của đợt do người điều phối chọn**, không đọc các giá trị quota còn trống trong dữ liệu cũ.

## Matching và lưu kết quả

Hệ thống tái dùng TF-IDF/cosine với kỹ năng và nội dung sinh viên so với hồ sơ GV hiện có. Hungarian chọn assignment có tổng điểm cao nhất trong quota đã xác định. Điểm tương thích không phải xác suất và không tự xác nhận năng lực thực tế hay sự đồng ý của GV. Khi không có từ vựng giao nhau, điểm có thể bằng 0; không bịa điểm để hoàn tất bảng.

Tokenizer riêng cho luồng upload giữ các kỹ năng như `C++`, `C#`, `R`; cấu hình được ghi vào provenance của kết quả. Vectorizer và checkpoint của thí nghiệm cũ giữ nguyên.

Chỉ GV được tích mới nhận SV. Kết quả lưu vào `simulation_runs` của SQLite local hoặc PostgreSQL đang cấu hình, gồm cohort, GV tham gia, quota, assignment và hash/provenance. Dữ liệu upload không thay thế 215 hồ sơ nghiên cứu hiện có, không tự thêm vào train/test, và không dùng để tự promote RL. Checkpoint RL hiện hành không được áp vào tập GV tùy chọn có không gian action khác.

Các API của trang đều cần phiên đăng nhập; POST còn kiểm Origin như các API khác. Tên GV và sinh viên thật của luồng này chỉ phục vụ người dùng đã xác thực. Không commit danh sách sinh viên thu thập hoặc database local vào Git.

## Các thành phần source

- Contract cột: `configs/student_survey_schema.json` (khảo sát mới), `configs/student_upload_schema.json` (mẫu cũ).
- Workbook: `assets/student-skills-template.xlsx`.
- API/parser/balanced matching: `backend/app/cohorts.py`, routes trong `backend/app/main.py`.
- UI: `frontend/app.js`, `frontend/student-cohorts.js`, `frontend/style.css`.
- Kiểm thử: `tests/cohorts/` và kiểm thử frontend liên quan.
