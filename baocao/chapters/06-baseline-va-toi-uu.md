# Chương 6. Baseline và tối ưu có ràng buộc

## 6.1. Vai trò của baseline

Baseline trả lời hai câu hỏi khác nhau. Random cho biết mức kết quả khi không dùng thông tin ngữ nghĩa nhưng vẫn tôn trọng quota. Greedy cho biết một heuristic dễ triển khai đạt được gì. Hungarian tạo cận tối ưu cho đúng mục tiêu tổng compatibility dưới quota đã chọn. Một mô hình RL chỉ có ý nghĩa nếu được so với cả ba trên cùng ma trận và split.

## 6.2. Random theo slot

Từ vector capacity \(q\), tạo danh sách slot:

\[
L=[\underbrace{1,\ldots,1}_{q_1},
\underbrace{2,\ldots,2}_{q_2},\ldots,
\underbrace{M,\ldots,M}_{q_M}].
\]

Thuật toán lấy mẫu \(N\) slot không hoàn lại với seed cố định. Vì mỗi slot chỉ được lấy một lần, quota được thỏa theo xây dựng. Random phải chạy nhiều seed vì một seed đơn lẻ có phương sai ngẫu nhiên và không đại diện cho phân phối kết quả.

## 6.3. Greedy theo thứ tự

Với sinh viên \(i\), tập giảng viên còn chỗ là \(F_i=\{j:L_j<q_j\}\). Greedy chọn:

\[
a_i=\arg\max_{j\in F_i}C_{ij}.
\]

Sau đó tăng tải của \(a_i\). Thuật toán có chi phí gần \(O(NM)\), dễ tạo event trace và phù hợp làm phương án dự phòng. Điểm yếu là phụ thuộc thứ tự. Một phép phân tích cần thiết là chạy nhiều hoán vị sinh viên hoặc cố định thứ tự theo protocol, không chọn thứ tự thuận lợi sau khi nhìn kết quả.

## 6.4. Hungarian với slot mở rộng

Mỗi cột giảng viên \(j\) được lặp \(q_j\) lần thành ma trận slot \(C'\). Vì thư viện giải bài toán cực tiểu, ta dùng chi phí \(-C'\). `linear_sum_assignment` trả một slot cho mỗi sinh viên, sau đó ánh xạ slot về giảng viên.

Hungarian là “tối ưu toàn cục” chỉ trong phạm vi hàm mục tiêu và ràng buộc đã mô hình hóa. Nếu \(C\) chưa phản ánh chất lượng thật hoặc quota là giả định uniform, nghiệm tối ưu toán học không phải quyết định học thuật tối ưu. Cụm từ “upper bound” trong báo cáo vì vậy có nghĩa cận trên của tổng điểm trên ma trận cụ thể, không phải cận trên của chất lượng hướng dẫn ngoài đời.

## 6.5. Gale–Shapley và ổn định

Ghép cặp ổn định tối ưu một khái niệm khác: không tồn tại một cặp hai phía cùng thích nhau hơn phương án hiện tại. Để dùng đúng, cần preference list cho cả sinh viên và giảng viên cùng chính sách capacity. Dự án hiện chưa có preference hai phía đã xác minh; suy ra cả hai danh sách từ cùng một cosine matrix sẽ làm yếu ý nghĩa “ổn định”. Vì vậy Gale–Shapley được giữ trong phần phương pháp tiềm năng, không xuất hiện trong bảng kết quả hiện tại nếu chưa có artifact thực thi cùng protocol.

## 6.6. Metrics

Với assignment \(a_i\), mean compatibility là:

\[
\bar C=\frac{1}{N}\sum_{i=1}^{N}C_{i,a_i}.
\]

Tải giảng viên \(L_j=|\{i:a_i=j\}|\). Số vi phạm quota:

\[
V_q=\sum_{j=1}^{M}\max(L_j-q_j,0).
\]

Phương sai tải:

\[
Var(L)=\frac{1}{M}\sum_{j=1}^{M}(L_j-\bar L)^2.
\]

Tỉ lệ so với Hungarian:

\[
R_{opt}=\frac{\bar C_{method}}{\bar C_{Hungarian}},
\]

chỉ có nghĩa khi cùng cohort, ma trận, capacity policy và cách xử lý thiếu dữ liệu. Nếu mẫu số bằng 0, metric phải là `null`, không ép thành 0 hay 1.

## 6.7. Phân biệt cân bằng tải và công bằng

Load variance nhỏ nói rằng số lượng phân bổ gần nhau, không nói rằng phân bổ công bằng theo chính sách chính thức. Một giảng viên có nhiệm vụ quản lý, nghỉ phép hoặc chuyên môn hẹp có thể có quota thấp hợp lý. Do đó báo cáo gọi metric này là **cân bằng tải thực nghiệm**. Muốn đánh giá công bằng chính thức cần quota có thẩm quyền và phân tích theo các nhóm được phép, có phê duyệt đạo đức và quyền riêng tư.

