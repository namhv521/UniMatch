# Kịch bản bảo vệ và demo

## Thông điệp chính

Hệ thống hỗ trợ hội đồng ghép cặp sinh viên–giảng viên bằng ma trận tương thích và tối ưu có quota. Đóng góp nổi bật là đường bằng chứng có thể kiểm toán và cơ chế từ chối checkpoint không tương thích. Kết quả hiện tại chọn Hungarian làm engine an toàn; RL vẫn là nghiên cứu, không tuyên bố chiến thắng.

## Kịch bản trình bày 12–15 phút

### 1. Vấn đề — 1 phút

“Phân công khóa luận phải đồng thời phù hợp chuyên môn và không vượt tải. Làm thủ công khó tái lập, còn chỉ tối đa điểm có thể bỏ qua quota. Em xây dựng hệ thống hỗ trợ quyết định, không thay thế hội đồng.”

### 2. Dữ liệu và provenance — 2 phút

Trình bày ma trận 220×38 và split 158 train, 21 validation, 21 test, 20 future. Nhấn mạnh vocabulary chỉ fit trên train; API dùng ID ẩn danh. Nói rõ quota chính thức còn thiếu nên benchmark dùng uniform ceiling thực nghiệm.

### 3. Mô hình toán — 2 phút

Trình bày biến \(x_{ij}\), mục tiêu tổng compatibility, ràng buộc mỗi sinh viên đúng một giảng viên và tải không vượt \(q_j\). Giải thích Random, Greedy và Hungarian. Nêu Hungarian là tối ưu trên ma trận/constraint hiện tại, không phải “chân lý” về chất lượng hướng dẫn.

### 4. RL — 2 phút

Trình bày trạng thái \([compatibility; remaining; load]\), 38 action và action mask. Viết ngắn hàm thưởng gồm compatibility, giảm phương sai tải và penalty invalid. Nói rõ reward/fairness là giả thuyết cần đánh giá.

### 5. Phát hiện audit — 2 phút

“Sáu checkpoint full cũ và hai smoke archive thực tế có observation 6, action 2. Manifest lại tham chiếu dữ liệu 38 giảng viên. Registry đọc archive và từ chối chúng trên real validation. Vì vậy em không dùng checkpoint cũ để kết luận RL.”

Đây là phần nên nhấn mạnh: phát hiện và công khai sai lệch làm kết quả đáng tin hơn việc giữ một con số không hợp lệ.

### 6. Kết quả — 2 phút

Mở bảng Chương 11 từ report mới nhất. Chỉ đọc số có trong artifact. Nêu cohort, seed, capacity policy và trạng thái promotion trước khi so sánh. Kết luận hiện tại: Hungarian là engine được chọn do chưa có RL full-budget nhiều seed đạt gate.

### 7. Hệ thống và demo — 3 phút

1. Chạy `python run_dashboard.py --local-demo`.
2. Đăng nhập bằng credential tạm trên loopback.
3. Mở catalog, chỉ ra Semantic khả dụng; non-RL disabled; RL toy có nhãn unpromoted.
4. Chạy sample 3×2 để giải thích event và quota.
5. Chạy Hungarian trên real validation; xem bảng, tải và provenance.
6. Thử chọn DQN legacy trên real validation để chứng minh fail-closed.

Nếu demo lỗi, dùng ảnh UI reference và report JSON; nói rõ đây là fallback trình bày, không tuyên bố live flow đã chạy.

### 8. Giới hạn và kết luận — 1 phút

Nêu ba giới hạn: quota uniform, weak label lịch sử, RL chưa full-budget/promotion. Kết thúc bằng lộ trình quota chính thức → train 114×38 → validation nhiều seed → khóa model → test holdout.

## Câu hỏi phản biện dự kiến

**Vì sao dùng RL khi Hungarian đã tối ưu?**  
Hungarian là baseline mạnh cho batch với toàn bộ cohort và mục tiêu tuyến tính đã biết. RL chỉ đáng dùng nếu chứng minh lợi ích cho luồng đến, trạng thái động hoặc mục tiêu dài hạn. Bằng chứng hiện tại chưa đủ, nên hệ thống chọn Hungarian.

**Điểm cosine có phải xác suất phù hợp không?**  
Không. Đó là tín hiệu similarity theo biểu diễn văn bản. Nó cần calibration/đánh giá chuyên gia trước khi diễn giải như xác suất.

**Lịch sử phân công có phải ground truth?**  
Không. Đây là weak label, có thể chứa ràng buộc không quan sát được. Em chỉ dùng để chẩn đoán agreement, không gọi là optimality.

**Load variance có bảo đảm công bằng không?**  
Không. Nó chỉ đo cân bằng số lượng. Fairness chính thức cần quota và quy tắc của nhà trường.

**Tại sao checkpoint ghi 2 triệu bước vẫn bị loại?**  
Vì archive chứa observation/action của toy 2 giảng viên. Số bước và hash trong manifest không sửa được mismatch của model thật.

**Tại sao chưa dùng test?**  
Test phải giữ holdout cho đến khi chọn cấu hình bằng validation. Dùng test nhiều lần sẽ gây leakage lựa chọn.

**Hệ thống có production-ready không?**  
Không. Đây là local research dashboard; session in-memory, quota chưa chính thức và deployment ngoài local chưa được xác minh.

## Checklist trước bảo vệ

- Report benchmark đã đóng băng và Chương 11 khớp hash.
- Không còn số demo bị trình bày như kết quả thật.
- Credential demo không nằm trong slide/repo.
- Có phương án offline: ảnh UI, bảng kết quả, legacy audit.
- Không mở raw PDF, tên thật hoặc ID sinh viên trong demo.
- Tập trả lời ngắn: bằng chứng nào có, điều gì chưa biết, bước nào giải quyết giới hạn.

