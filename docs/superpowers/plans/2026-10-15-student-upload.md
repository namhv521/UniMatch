# Nhập sinh viên và phân bổ theo GV tham gia

**Yêu cầu:** thêm trang riêng nhận Excel kỹ năng theo dữ liệu hiện hành, checkbox tên GV thật, chia tải cân bằng theo GV được chọn, tối ưu skill matching và lưu kết quả.

**Thiết kế:** giữ UI v1. Trang `#/students` có tải mẫu, chọn file `.xlsx`, xem trước, chọn GV, dự báo quota và kết quả phân bổ. Backend kiểm toàn bộ input và chỉ trả danh sách tên GV khi đã đăng nhập. Không sửa snapshot train/validation hoặc áp checkpoint RL 38-action vào tập GV tùy chọn.

**Quota:** với N sinh viên và M GV đã chọn, `q,r=divmod(N,M)`. R GV nhận q+1, còn lại q theo thứ tự danh sách GV ổn định. Hungarian trên đúng N slot bảo đảm mọi quota được lấp đầy; không chỉ đặt ceil làm capacity vì có thể sinh tải 10/10/10/8 thay vì 10/10/9/9. Trường hợp N<M chấp nhận một số GV nhận 0. Không chọn GV thì từ chối.

**Excel contract:** `configs/student_upload_schema.json`, sheet `SinhVien`, header row 1 là các key máy đọc; 17 cột gồm student_id/name, title/abstract và 13 nhóm skill/role đang có. ID/tên và ít nhất một skill bắt buộc. Nhiều skill phân tách `;`. File mẫu trống không trộn sinh viên ví dụ vào upload; danh mục skill và hướng dẫn ở sheet riêng.

**API:**

- `GET /api/v1/student-cohorts/advisors`: `data.advisors=[{id,name,primary_field}]`.
- `GET /api/v1/student-cohorts/template`: tải `assets/student-skills-template.xlsx`.
- `POST /api/v1/student-cohorts/preview`: body binary XLSX, trả `{student_count,students:[{student_id,student_name,thesis_title,skills}],warnings}`. `skills` là list string đã chuẩn hóa cho preview.
- `POST /api/v1/student-cohorts/allocate?advisor_ids=id1&advisor_ids=id2`: body binary cùng file, trả `{student_count,advisor_count,source_sha256,cohort_hash,capacity_policy,algorithm,advisors:[{id,name,quota,assigned}],assignments:[{student_id,student_name,advisor_id,advisor_name,score,skills}],metrics,warnings}`.

Mọi API cần session, POST cần Origin; trả envelope success/error hiện có. Giới hạn 5MiB/1000 SV; từ chối duplicate ID/header, file lỗi, công thức trong dữ liệu, thiếu skill và GV lạ/trùng. Đọc XLSX bằng openpyxl (dependency chuyên dụng duy nhất; không dùng để author file mẫu). Matching tái dùng TF-IDF/cosine với hồ sơ GV có sẵn, không tự bịa skill hay điểm.

**Persistence:** dùng simulation_runs hiện có, endpoint allocate/mode semantic/algorithm hungarian-balanced-v1/dataset uploaded-<hash>, FK snapshot GV hiện hành. Result JSON lưu đủ cohort, GV chọn, quota, assignment và provenance; không nhập cohort vào tập nghiên cứu đóng băng.

- [x] Backend/API/import/balanced matching và regression 38 SV/4 GV.
- [x] Excel mẫu artifact-tool, danh mục skill có nguồn thật, render và readback.
- [x] Trang UI mới, chọn/bỏ GV, trạng thái lỗi/loading, preview/kết quả.
- [x] Kiểm thử bảo toàn hành vi cũ, full suite, browser desktop/mobile, readback database và restart local giữ dữ liệu.
