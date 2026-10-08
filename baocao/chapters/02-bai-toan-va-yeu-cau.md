# Chương 2. Bài toán và yêu cầu

## 2.1. Phát biểu bài toán

Cho tập sinh viên \(S=\{1,\ldots,N\}\), tập giảng viên \(A=\{1,\ldots,M\}\), ma trận tương thích \(C\in[0,1]^{N\times M}\) và hạn mức \(q_j\) của giảng viên \(j\). Biến quyết định nhị phân \(x_{ij}=1\) khi sinh viên \(i\) được gán cho giảng viên \(j\), ngược lại bằng 0.

Bài toán tối đa hóa tổng tương thích được viết:

\[
\max_x \sum_{i=1}^{N}\sum_{j=1}^{M} C_{ij}x_{ij}
\]

với các ràng buộc:

\[
\sum_{j=1}^{M}x_{ij}=1\quad \forall i,
\qquad
\sum_{i=1}^{N}x_{ij}\le q_j\quad \forall j,
\qquad
x_{ij}\in\{0,1\}.
\]

Ràng buộc thứ nhất yêu cầu mỗi sinh viên được gán đúng một lần. Ràng buộc thứ hai bảo đảm không vượt hạn mức. Điều kiện khả thi tối thiểu là \(\sum_j q_j\ge N\). Trong dữ liệu hiện tại chưa có quota chính thức cho toàn bộ 38 giảng viên; vì vậy thí nghiệm dùng chính sách đồng đều \(q_j=\lceil N/M\rceil\). Đây là giả định thực nghiệm, không phải quy định đào tạo.

## 2.2. Nhiều mục tiêu và thứ tự ưu tiên

Ba nhóm tiêu chí được tách rõ:

1. **Ràng buộc cứng:** đủ độ phủ, không gán trùng, không vượt quota, ID tồn tại và quan hệ đề tài–sinh viên hợp lệ.
2. **Chất lượng ghép:** mean compatibility và tổng compatibility.
3. **Chỉ báo phụ:** phương sai tải, độ ổn định giữa các lần chạy, mức trùng với lịch sử và số đề xuất không hợp lệ.

Ràng buộc cứng không được đổi lấy điểm số. Một policy có điểm trung bình cao nhưng vượt quota phải bị loại khỏi promotion. Ngược lại, quota violations bằng 0 chưa đủ chứng minh chất lượng học thuật: thuật toán Random cũng có thể đạt 0 vi phạm nếu chỉ lấy mẫu từ các slot còn trống.

## 2.3. Tác nhân và nhu cầu

Sinh viên cần xem gợi ý giảng viên theo nội dung đề tài. Người điều phối cần chạy phân bổ cohort, kiểm tra hạn mức, xem nguồn dữ liệu và hiểu thuật toán thực sự đã chạy. Giảng viên cần xem danh sách sau khi được phê duyệt, không phải truy cập dữ liệu riêng của toàn bộ cohort. Người nghiên cứu cần tái lập benchmark theo split, seed và hash. Hội đồng giữ quyền phê duyệt cuối cùng và có thể bác bỏ đề xuất máy.

Các vai trò này dẫn đến một nguyên tắc thiết kế: kết quả thuật toán là **đề xuất có provenance**, không phải quyết định hành chính tự động.

## 2.4. Yêu cầu chức năng

- Đăng nhập bằng thông tin cấu hình cục bộ và duy trì phiên ở server.
- Liệt kê dataset, baseline và model cùng trạng thái khả dụng.
- Cho phép chạy Random, Greedy và Hungarian trên sample hoặc validation thật khi artifact hợp lệ.
- Chỉ cho phép checkpoint toy chạy trên sample được gắn nhãn rõ.
- Trả về assignments, event trace, tải trước/sau, score, reward, cờ invalid và fallback.
- Gợi ý top-k giảng viên từ tiêu đề đề tài, chỉ trả ID ẩn danh và evidence reference.
- Trình bày đồ thị 3D như một cách quan sát; luôn có bảng/log 2D tương đương.

## 2.5. Yêu cầu phi chức năng

**Tái lập:** mỗi run phải gắn dataset hash, feature hash, split hash, seed, thuật toán và phiên bản code/model. **An toàn:** API riêng yêu cầu session, ghi dữ liệu dùng same-origin, lỗi không phản chiếu input hay đường dẫn. **Riêng tư:** raw PDF, tên thật, email và ID gốc không xuất hiện trong API công khai. **Khả dụng:** thiếu model không làm hệ thống tự đổi sang model khác; UI phải nói rõ “không khả dụng”. **Khả năng kiểm toán:** event trace phải khớp assignments và tải cuối.

## 2.6. Tiêu chí chấp nhận

Một bản chạy được coi là hợp lệ khi: tất cả sinh viên trong split được gán đúng một lần; quota violations bằng 0; số hàng/cột khớp thứ tự đã hash; output ghi đầy đủ provenance; không lộ PII; và thuật toán được báo cáo đúng tên. Một model RL chỉ đủ điều kiện so sánh khi checkpoint có 114 chiều quan sát, 38 hành động, được đánh giá trên cùng split và capacity policy với baseline, qua nhiều seed đã định trước. Các checkpoint 6×2 không đáp ứng điều kiện này dù manifest cũ ghi hash của dữ liệu thật.

