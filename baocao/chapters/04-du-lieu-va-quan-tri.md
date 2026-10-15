# Chương 4. Dữ liệu, nguồn gốc và quản trị

## 4.1. Các tầng dữ liệu

Đường dữ liệu được tổ chức theo nguyên tắc không sửa bằng chứng gốc. `data/raw/` chứa snapshot và sự kiện fetch; `data/extracted/` chứa kết quả trích xuất; `data/curated/` chứa bản ghi đã chuẩn hóa; `data/features/` chứa ma trận và manifest. Mỗi tầng có mục đích khác nhau. Raw phục vụ kiểm toán, không phải API. Curated phục vụ mô hình nhưng vẫn có thể chứa thông tin cần bảo vệ. Chỉ ID ẩn danh và trường đã duyệt mới đi ra tầng serving.

Artifact hiện tại có **215 hàng sinh viên/đề tài và 38 cột giảng viên** trong `compatibility_matrix_v2.npy`. Năm bản ghi đã được loại khỏi snapshot 220 hàng theo manifest `data/excluded/requested-five/manifest.json`; dữ liệu trước khi lọc được lưu ở `outputs/snapshot-220-before-exclusion` để kiểm toán. Manifest hiện hành lưu `matrix_shape`, hash ma trận, hash dataset và hash split. Một ma trận đúng kích thước nhưng sai thứ tự hàng/cột vẫn nguy hiểm, vì action 5 có thể trỏ sang giảng viên khác. Do đó serving hash cả danh sách `student_id` và `advisor_id` theo thứ tự, không chỉ hash tập hợp.

## 4.2. Chuẩn hóa và định danh

Quy trình định danh phải tách tên hiển thị khỏi khóa ổn định. Dấu tiếng Việt, học hàm, khoảng trắng và biến thể viết tắt có thể tạo nhiều biểu diễn cho cùng một người. Identity resolution tạo ánh xạ có bằng chứng; trường hợp mơ hồ phải vào hàng chờ rà soát, không tự hợp nhất chỉ vì tên gần giống.

Quan hệ giảng viên–đề tài lịch sử có thể dùng làm bằng chứng về lĩnh vực đã hướng dẫn, nhưng không đồng nghĩa mọi công nghệ trong đề tài là kỹ năng chính thức của giảng viên. Mỗi kỹ năng suy ra cần `evidence_ref`, phương pháp trích xuất và trạng thái xác minh. Điều này hạn chế vòng lặp tự củng cố: một gán lịch sử yếu không được biến thành nhãn chắc chắn rồi dùng để “chứng minh” chính gán đó.

## 4.3. Chia tập theo thời gian

Split schema v2 hiện tại có **154 mẫu train, 20 validation, 21 test và 20 future**. Các tập không giao nhau theo `student_id`. Train dùng để huấn luyện policy; validation dùng để chọn cấu hình và kiểm promotion; test chỉ dùng sau khi quyết định đã khóa; future chứa bản ghi sau mốc đánh giá và không được trộn vào train/test hiện tại.

Split theo thời gian phản ánh tình huống triển khai tốt hơn random split thuần túy: mô hình học từ dữ liệu cũ rồi phục vụ cohort mới. Việc nhóm theo sinh viên ngăn cùng một sinh viên xuất hiện ở nhiều tập qua các phiên bản tài liệu. Seed 42 chỉ dùng để chia phần cùng năm một cách tái lập; nó không biến split thành ngẫu nhiên hoàn toàn.

## 4.4. Kiểm soát rò rỉ

Vectorizer theo thiết kế phải fit trên văn bản train cùng hồ sơ giảng viên được phép tại thời điểm đó; validation/test chỉ được `transform`. Snapshot 215 hàng hiện hành là một phép chuyển có kiểm chứng từ snapshot 220 hàng: bốn văn bản train và một văn bản validation đã bị loại, nhưng vocabulary/IDF được **đóng băng từ corpus train gốc** và ma trận chỉ lấy lại các hàng còn giữ. Vì vậy văn bản của bốn bản ghi train đã loại vẫn có thể ảnh hưởng vocabulary/IDF. Manifest ghi rõ `preprocessing_scope` và `parent_feature_sha256`; đây là giới hạn tiền xử lý được giữ lại để bảo toàn protocol, không phải bằng chứng đã refit sạch trên 154 hàng.

Khi thiết lập protocol mới, cần fit lại vectorizer chỉ trên 154 hàng train hiện hành, sinh hash mới và huấn luyện lại mọi checkpoint phụ thuộc. Không được thay vocabulary giữa một benchmark đang dùng rồi so trực tiếp hai kết quả như cùng protocol.

Một điểm cần lưu ý là hồ sơ giảng viên là phía đối tác chung cho mọi split. Nếu hồ sơ được tổng hợp từ các đề tài tương lai, nó có thể mang thông tin sau mốc thời gian. Vì vậy phiên bản nghiêm ngặt hơn cần đóng băng bằng chứng giảng viên theo `evidence_date` và chỉ dùng nguồn có trước cutoff. Đây là giới hạn cần xử lý trước khi tuyên bố đánh giá thời gian hoàn toàn sạch.

## 4.5. Chất lượng và coverage

Báo cáo chất lượng phải ghi số dòng hợp lệ, số bản ghi loại, nguyên nhân, coverage nguồn và advisor chưa xác minh. “Pipeline chạy xong” không đồng nghĩa dữ liệu đầy đủ. Những hồ sơ crawl thất bại phải nằm trong failure report hoặc manual queue. Artifact chất lượng cũ ghi `complete_dataset: false`; do đó các kết quả dựa trên subset phải mang nhãn subset.

## 4.6. Quota và dữ liệu thiếu

Hiện toàn bộ 38 giảng viên thiếu quota chính thức có thể dùng cho benchmark. Hệ thống áp dụng uniform ceiling để đảm bảo bài toán khả thi. Với validation 20 sinh viên và 38 giảng viên, capacity của mỗi giảng viên bằng 1. Mọi assignment hoàn chỉnh và không vi phạm capacity vì thế có đúng 20 tải bằng 1 và 18 tải bằng 0. Trung bình tải là (20/38), còn phương sai quần thể cố định là

\[
\frac{20(1-20/38)^2+18(0-20/38)^2}{38}
=\frac{20\times18}{38^2}\approx0{,}249307.
\]

Vì vậy load variance xấp xỉ 0,2493 ở mọi thuật toán hợp lệ và không có sức phân biệt trong protocol này. Mọi bảng kết quả phải ghi rõ capacity policy. Khi nhận quota chính thức, cần version hóa file quota, kiểm tra tổng capacity, chạy lại baseline/RL và không so trực tiếp với kết quả uniform nếu protocol khác.

## 4.7. Quyền riêng tư

Raw PDF, tên, email, ID sinh viên gốc và URL nguồn được giữ private. API trả `SV-VAL-xxx`, `GV-xxx` và evidence hash. Log lỗi không ghi request body. Dữ liệu mẫu 2×2 hoặc 3×2 phải được gắn `sample: true` để tránh nhầm với đánh giá thật. Quy trình chi tiết nằm trong `docs/data_governance.md`.

