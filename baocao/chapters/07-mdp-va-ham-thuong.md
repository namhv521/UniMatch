# Chương 7. Mô hình MDP, action masking và hàm thưởng

## 7.1. MDP hữu hạn

Một episode gồm \(N\) bước, mỗi bước xử lý một sinh viên theo thứ tự đã khóa. Với \(M\) giảng viên, quan sát hiện tại ghép ba vector:

\[
s_t=[\mathbf c_t;\mathbf r_t;\mathbf l_t]\in[0,1]^{3M},
\]

trong đó \(\mathbf c_t\) là điểm tương thích của sinh viên hiện tại, \(r_{t,j}=(q_j-L_{t,j})/q_j\) là tỷ lệ còn lại và \(l_{t,j}=L_{t,j}/q_j\) là tỷ lệ tải. Với 38 giảng viên, shape đúng là 114; action space là `Discrete(38)`.

Môi trường kết thúc khi `student_index == N`. Gọi `step()` sau terminal là lỗi. Ma trận rỗng, chứa NaN/vô cực, điểm ngoài [0,1], capacity âm hoặc tổng capacity thiếu đều bị từ chối. `TimeLimit` giới hạn tối đa \(4N\) bước để ngăn vòng lặp vô hạn nếu policy liên tục đề xuất action không hợp lệ.

## 7.2. Action masking

Mặt nạ khả thi tại bước \(t\):

\[
m_{t,j}=\mathbb{1}[L_{t,j}<q_j].
\]

Với policy hỗ trợ masking, logit của action không hợp lệ được đặt về \(-\infty\) trước softmax. Khi ít nhất một slot còn trống, tổng xác suất trên action hợp lệ bằng 1. Masking thực thi quota trong lúc chọn action và hiệu quả hơn việc liên tục phạt sau khi vi phạm.

Tuy nhiên masking không thay thế kiểm tra domain. Nếu tổng capacity nhỏ hơn \(N\), sẽ có trạng thái không còn action hợp lệ; môi trường phải từ chối ngay khi khởi tạo. Kết quả cuối vẫn phải chạy `quota_violations` vì lỗi adapter hoặc mapping có thể xảy ra ngoài policy.

## 7.3. Hàm thưởng

Hàm thưởng đang dùng:

\[
r_t=w_c C_{t,a_t}+w_f\left[Var(\mathbf L_t)-Var(\mathbf L_{t+1})\right]
-w_p\mathbb{1}_{invalid}.
\]

Giá trị mặc định trong code là \(w_c=1.0\), \(w_f=0.15\), \(w_p=2.0\). Thành phần compatibility khuyến khích chọn chuyên môn gần. Hiệu phương sai dương khi bước mới làm tải cân bằng hơn. Penalty áp dụng nếu action không hợp lệ.

Hàm thưởng là giả thuyết thiết kế, không phải định nghĩa chân lý. Trọng số 0.15 cần ablation trên validation. Một policy có return cao có thể lợi dụng cách scale reward mà không cải thiện metric cuối; vì vậy promotion phải dựa trên metrics của assignment, không dựa riêng episode reward.

## 7.4. Xử lý action không hợp lệ

Môi trường hiện không tăng `student_index` khi nhận action không hợp lệ. Nó trả penalty và giữ trạng thái để policy thử lại. Event trace phải lưu `invalid_proposal=true`; không được xóa dấu vết rồi chỉ báo assignment cuối. Nếu đến giới hạn bước mà chưa phân bổ hết, run có coverage nhỏ hơn 1 và không đủ điều kiện promotion.

Fallback, nếu có, phải được khai báo: ví dụ sau số lần thử giới hạn, chọn advisor khả thi có score cao nhất. Khi dùng fallback, kết quả là policy kết hợp heuristic, không phải output thuần của model. Bảng phải có cả `invalid_proposals`, `fallback_count` và `assignment_coverage`.

## 7.5. Markov và thứ tự sinh viên

Quan sát chứa tải hiện tại và điểm của sinh viên hiện tại nên đủ cho transition của môi trường đã định nghĩa. Nhưng thứ tự sinh viên ảnh hưởng mạnh đến quỹ đạo. Nếu thứ tự luôn cố định, policy có thể học vị trí thay vì quy luật tổng quát. Thiết kế thực nghiệm cần nói rõ có shuffle trong train hay không, giữ thứ tự cố định ở evaluation, và báo cáo độ nhạy với các hoán vị nếu mục tiêu là streaming.

## 7.6. Tính nhất quán train–serve

Checkpoint phải được nạp vào môi trường có đúng observation/action space. Sáu checkpoint cũ gồm ARS, DQN, MaskablePPO, QR-DQN, RecurrentPPO và TRPO đều chứa Box(6) và Discrete(2), mặc dù manifest gắn hash dữ liệu 220×38. Archive là bằng chứng mạnh hơn nhãn manifest: registry phải đánh dấu `toy_unpromoted` và không cho chạy `real-validation`. Đây là một phát hiện audit trọng yếu của đề tài.

