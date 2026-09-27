# Đặc trưng sinh viên và giảng viên

Cập nhật theo yêu cầu trực tiếp ngày 27/09/2026. Schema thực thi: src/data_pipeline/extraction_schema.py. Không tự điền GPA, nguyện vọng hoặc kỹ năng khi nguồn không cung cấp. null/[] thể hiện chưa có bằng chứng.

## Sinh viên / đề tài

| Trường | Kiểu | Nội dung |
|---|---|---|
| thesis_title | string/null | Tên đề tài tiếng Việt |
| field_category | string/null | Lĩnh vực, có thể suy luận có dẫn chứng |
| web_languages, app_languages | list[string] | Ngôn ngữ thực sự sử dụng |
| frontend_frameworks, backend_frameworks, ai_frameworks | list[string] | Framework triển khai |
| database_cache, app_db_backend | list[string] | Cơ sở dữ liệu, caching, backend di động |
| ai_problems, data_tools, data_models | list[string] | Bài toán, công cụ, mô hình dữ liệu/AI |
| research_methods | list[string] | Phương pháp nghiên cứu có bằng chứng |
| primary_role, secondary_roles | string/null, list[string] | Vai trò kỹ thuật, được phép suy luận |

Metadata: student_id, student_name, submission_year, major, advisor_name, abstract. Mã SV giữ dạng chuỗi; năm lấy từ tài liệu, không suy ra từ mã SV. Mỗi giá trị có evidence: field, value, page (hoặc khối DOCX), quote, kind. Trích dẫn phải khớp nguồn. Giá trị không đủ bằng chứng bị loại; raw_profile và rejected_evidence được giữ để kiểm toán. Công nghệ chỉ xuất hiện trong so sánh/tài liệu tham khảo không chứng minh đã triển khai.

feature_text nối các trường đề tài/kỹ năng/vai trò trên. Không đưa tên, mã SV, GV hướng dẫn lịch sử hoặc năm vào vector tương thích. Các phiên bản cùng sinh viên được nhóm; giữ toàn bộ nguồn trong thesis_source_records.jsonl.

## Giảng viên

Nguồn: https://fit.neu.edu.vn/lecturer và https://fit.neu.edu.vn/publication. Snapshot có 38 hồ sơ; không tạo người để khớp 39 trong kế hoạch cũ.

| Trường | Ý nghĩa |
|---|---|
| advisor_id, advisor_name | Định danh nguồn, họ tên |
| academic_title | Học hàm/học vị từ hồ sơ |
| primary_field | Lĩnh vực từ hồ sơ |
| skill_text, skill_count | Kỹ năng từ nguồn và luật trích xuất |
| publication_evidence_count | Số mục công bố trong hồ sơ, không mặc nhiên là tổng cả sự nghiệp |
| primary_field_inferred, skill_text_inferred, inferred_skill_count | Phân tích tiêu đề/học phần, tách khỏi khẳng định trực tiếp |
| profile_text | Văn bản hồ sơ phục vụ biểu diễn |
| quota | Chỉ tiêu cấu hình; null nếu chưa có quy chế |

Tiêu đề publication liên kết bằng tên người kê khai chính xác sau chuẩn hóa. Người kê khai không mặc nhiên là tác giả đã xác minh. Lưu relationship, source_url, source_ids, năm và lý do suy luận. Tiêu đề deep learning không đủ để khẳng định PyTorch/TensorFlow.

## Vector và ràng buộc

TF-IDF fit chỉ trên tập train; cosine tạo ma trận N×M hữu hạn trong [0,1]. Nhánh dense dùng frozen paraphrase-multilingual-mpnet-base-v2, 768 chiều; cosine dense phải chặn vào [0,1]. TF-IDF hiện là đầu vào mặc định, chưa tuyên bố kết hợp hai phương pháp. MPNet mặc định tối đa128 token; manifest ghi giới hạn này.

Nếu chưa cấu hình quota: C_j = ceil(N/M) theo cohort. Tổng quota ≥ N. Khởi tạo L_j,0 = 0; mỗi phân công hợp lệ tăng một đơn vị, không vượt C_j.

    rem_j,t = (C_j - L_j,t) / max(C_j, 1)
    load_j,t = L_j,t / max(C_j, 1)
    obs_t = [scores_i, rem_t, load_t] ∈ [0,1]^(3M)

M=39 →117 chiều; snapshot M=38 →114 chiều. Mask chọn GV còn quota. Hành động sai bị phạt, không làm mất SV; giới hạn số đề xuất tránh vòng lặp vô hạn.

## Chống rò rỉ và giới hạn

Nhóm theo mã SV trước khi chia. Dữ liệu trước2025 vào train; cohort2025 chia train/val/test có seed; dữ liệu2026 giữ future_indices. Holdout không dùng chọn siêu tham số. Dữ liệu trích xuất dở chỉ dùng smoke test.

Hồ sơ GV crawl2026 là snapshot hiện thời, có nguồn không rõ ngày. Split SV theo năm chưa đủ chứng minh backtest lịch sử hoàn toàn. Muốn tuyên bố dự báo tại mốc quá khứ cần snapshot hồ sơ đúng mốc, lọc công bố theo thời gian và xử lý nguồn không có ngày.

Nguyện vọng/feedback LifecycleV2 phải là đầu vào có nguồn, không suy từ GV hướng dẫn lịch sử. Observation3M không chứa riêng các tín hiệu này; không khẳng định trạng thái Markov đầy đủ khi reward phụ thuộc tín hiệu ẩn.
