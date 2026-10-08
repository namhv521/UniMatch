# Chương 4. Dữ liệu, nguồn gốc và quản trị

## 4.1. Các tầng dữ liệu

Đường dữ liệu được tổ chức theo nguyên tắc không sửa bằng chứng gốc. `data/raw/` chứa snapshot và sự kiện fetch; `data/extracted/` chứa kết quả trích xuất; `data/curated/` chứa bản ghi đã chuẩn hóa; `data/features/` chứa ma trận và manifest. Mỗi tầng có mục đích khác nhau. Raw phục vụ kiểm toán, không phải API. Curated phục vụ mô hình nhưng vẫn có thể chứa thông tin cần bảo vệ. Chỉ ID ẩn danh và trường đã duyệt mới đi ra tầng serving.

Artifact hiện tại có 220 hàng sinh viên/đề tài và 38 cột giảng viên trong `compatibility_matrix_v2.npy`. Manifest lưu `matrix_shape`, hash ma trận, hash dataset và hash split. Một ma trận đúng kích thước nhưng sai thứ tự hàng/cột vẫn nguy hiểm, vì action 5 có thể trỏ sang giảng viên khác. Do đó serving cần hash cả danh sách `student_id` và `advisor_id` theo thứ tự, không chỉ hash tập hợp.

## 4.2. Chuẩn hóa và định danh

Quy trình định danh phải tách tên hiển thị khỏi khóa ổn định. Dấu tiếng Việt, học hàm, khoảng trắng và biến thể viết tắt có thể tạo nhiều biểu diễn cho cùng một người. Identity resolution tạo ánh xạ có bằng chứng; trường hợp mơ hồ phải vào hàng chờ rà soát, không tự hợp nhất chỉ vì tên gần giống.

Quan hệ giảng viên–đề tài lịch sử có thể dùng làm bằng chứng về lĩnh vực đã hướng dẫn, nhưng không đồng nghĩa mọi công nghệ trong đề tài là kỹ năng chính thức của giảng viên. Mỗi kỹ năng suy ra cần `evidence_ref`, phương pháp trích xuất và trạng thái xác minh. Điều này hạn chế vòng lặp tự củng cố: một gán lịch sử yếu không được biến thành nhãn chắc chắn rồi dùng để “chứng minh” chính gán đó.

## 4.3. Chia tập theo thời gian

Split schema v2 hiện tại có 158 mẫu train, 21 validation, 21 test và 20 future. Các tập không giao nhau theo `student_id`. Train dùng để fit vocabulary và huấn luyện. Validation dùng để chọn cấu hình/promotion. Test chỉ dùng sau khi quyết định đã khóa. Future chứa bản ghi sau mốc đánh giá và không được trộn vào train/test hiện tại.

Split theo thời gian phản ánh tình huống triển khai tốt hơn random split thuần túy: mô hình học từ dữ liệu cũ rồi phục vụ cohort mới. Việc nhóm theo sinh viên ngăn cùng một sinh viên xuất hiện ở nhiều tập qua các phiên bản tài liệu. Seed 42 chỉ dùng để chia phần cùng năm một cách tái lập; nó không biến split thành ngẫu nhiên hoàn toàn.

## 4.4. Kiểm soát rò rỉ

Vectorizer phải fit trên văn bản train cùng hồ sơ giảng viên được phép tại thời điểm đó. Validation/test chỉ được `transform`. Bất kỳ preprocessing nào học thống kê toàn tập—vocabulary, IDF, scaler hoặc selection threshold—đều phải fit ở train. Nếu thay dữ liệu hoặc thứ tự, phải sinh lại hash và vô hiệu checkpoint phụ thuộc.

Một điểm cần lưu ý là hồ sơ giảng viên là phía đối tác chung cho mọi split. Nếu hồ sơ được tổng hợp từ các đề tài tương lai, nó có thể mang thông tin sau mốc thời gian. Vì vậy phiên bản nghiêm ngặt hơn cần đóng băng bằng chứng giảng viên theo `evidence_date` và chỉ dùng nguồn có trước cutoff. Đây là giới hạn cần xử lý trước khi tuyên bố đánh giá thời gian hoàn toàn sạch.

## 4.5. Chất lượng và coverage

Báo cáo chất lượng phải ghi số dòng hợp lệ, số bản ghi loại, nguyên nhân, coverage nguồn và advisor chưa xác minh. “Pipeline chạy xong” không đồng nghĩa dữ liệu đầy đủ. Những hồ sơ crawl thất bại phải nằm trong failure report hoặc manual queue. Artifact chất lượng cũ ghi `complete_dataset: false`; do đó các kết quả dựa trên subset phải mang nhãn subset.

## 4.6. Quota và dữ liệu thiếu

Hiện toàn bộ 38 giảng viên thiếu quota chính thức có thể dùng cho benchmark. Hệ thống áp dụng uniform ceiling để đảm bảo bài toán khả thi. Với validation 21 sinh viên và 38 giảng viên, ceiling bằng 1; điều này làm load variance có cách diễn giải khác cohort lớn và không phản ánh chính sách phân công thực tế. Mọi bảng kết quả phải ghi rõ capacity policy. Khi nhận quota chính thức, cần version hóa file quota, kiểm tra tổng capacity, chạy lại baseline/RL và không so trực tiếp với kết quả uniform nếu protocol khác.

## 4.7. Quyền riêng tư

Raw PDF, tên, email, ID sinh viên gốc và URL nguồn được giữ private. API trả `SV-VAL-xxx`, `GV-xxx` và evidence hash. Log lỗi không ghi request body. Dữ liệu mẫu 2×2 hoặc 3×2 phải được gắn `sample: true` để tránh nhầm với đánh giá thật. Quy trình chi tiết nằm trong `docs/data_governance.md`.

