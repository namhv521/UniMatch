# Chương 3. Cơ sở lý thuyết và công trình liên quan

## 3.1. Ghép cặp có hạn mức

Bài toán trong Chương 2 có thể chuyển thành bài toán gán bằng cách mở rộng mỗi giảng viên \(j\) thành \(q_j\) slot. Khi đó ma trận chi phí có một cột cho mỗi slot và thuật toán Hungarian tìm phương án tối ưu tổng điểm trên ma trận đã mở rộng. Cách làm này phù hợp với phân bổ batch khi toàn bộ cohort đã biết. Nó tạo một cận tham chiếu hữu ích cho mục tiêu tổng tương thích, nhưng không tự giải quyết mọi mục tiêu như ổn định, nguyện vọng hai phía hay thay đổi theo thời gian.

Greedy chọn giảng viên khả thi có điểm cao nhất cho từng sinh viên theo thứ tự. Độ phức tạp thấp và trace dễ giải thích, nhưng kết quả phụ thuộc thứ tự sinh viên; lựa chọn tốt cục bộ có thể lấy mất slot cần thiết cho sinh viên sau. Random với danh sách slot hữu hạn là cận dưới thực nghiệm và kiểm tra tính đúng của quota, không phải mô hình thông minh.

## 3.2. Học tăng cường

Trong học tăng cường, agent quan sát trạng thái \(s_t\), chọn hành động \(a_t\), nhận thưởng \(r_t\) và chuyển sang \(s_{t+1}\). Mục tiêu là tối đa hóa kỳ vọng tổng thưởng chiết khấu:

\[
J(\pi)=\mathbb{E}_{\pi}\left[\sum_{t=0}^{T-1}\gamma^t r_t\right].
\]

Với phân bổ tuần tự, mỗi bước tương ứng một sinh viên. Hành động là chỉ số giảng viên. Trạng thái phải chứa ít nhất điểm tương thích của sinh viên hiện tại và tình trạng tải. Một episode kết thúc sau khi phân bổ hết cohort hoặc bị cắt bởi giới hạn bước an toàn.

## 3.3. DQN và QR-DQN

DQN xấp xỉ hàm giá trị hành động \(Q(s,a)\). Target một bước thường có dạng:

\[
y_t=r_t+\gamma\max_{a'}Q_{\theta^-}(s_{t+1},a'),
\]

và mạng được tối ưu để giảm sai số giữa \(y_t\) với \(Q_\theta(s_t,a_t)\). Replay buffer giảm tương quan giữa các mẫu liên tiếp; target network làm mục tiêu ổn định hơn. Công trình gốc của Mnih và cộng sự trình bày deep Q-learning với đầu vào cảm giác có chiều cao [1]. Trong đề tài này, DQN là một ứng viên value-based cho action rời rạc; tên thuật toán không tự bảo đảm quota. Nếu không mask hành động, môi trường phải ghi nhận đề xuất không hợp lệ và áp dụng quy tắc xử lý minh bạch.

QR-DQN không chỉ ước lượng kỳ vọng của return mà xấp xỉ phân phối return bằng các quantile. Với \(K\) quantile \(\theta_k(s,a)\), giá trị kỳ vọng có thể lấy trung bình các quantile, còn phân phối cho biết thêm cấu trúc bất định. Dabney và cộng sự xây dựng phương pháp quantile regression cho distributional RL [2]. Trong hệ thống hiện tại, chỉ được hiển thị phân phối quantile khi checkpoint hoặc trace thật cung cấp dữ liệu; không suy diễn phân phối từ một action cuối.

## 3.4. TRPO và PPO

Policy gradient tối ưu trực tiếp tham số policy. Thay đổi policy quá lớn sau một update có thể làm hiệu năng suy giảm. TRPO ràng buộc khoảng cách giữa policy cũ và policy mới bằng một trust region, thường biểu diễn qua KL divergence. Schulman và cộng sự xây dựng mục tiêu surrogate cùng ràng buộc để có cập nhật thận trọng [3].

PPO đơn giản hóa ý tưởng này bằng tỉ số xác suất

\[
\rho_t(\theta)=\frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{old}}(a_t|s_t)}
\]

và mục tiêu clipped:

\[
L^{CLIP}(\theta)=\mathbb{E}_t\left[
\min\left(\rho_t\hat A_t,
\operatorname{clip}(\rho_t,1-\epsilon,1+\epsilon)\hat A_t\right)
\right].
\]

Clipping hạn chế lợi ích từ cập nhật quá xa policy cũ. Bài báo PPO của Schulman và cộng sự là nguồn chính cho công thức này [4]. MaskablePPO bổ sung mặt nạ hành động ở tầng phân phối policy; đây là cơ chế triển khai phù hợp với hard quota, nhưng vẫn phải kiểm tra tổng capacity và trường hợp không còn hành động hợp lệ.

## 3.5. Khoảng trống áp dụng

Các công trình RL trên giải quyết tối ưu policy nói chung, không trực tiếp chứng minh hiệu quả cho phân công khóa luận. Đề tài phải tự chứng minh tính phù hợp thông qua protocol theo thời gian, baseline mạnh, nhiều seed và audit quota. Lợi thế “online” của RL cũng chỉ có ý nghĩa khi thí nghiệm mô phỏng luồng đến và so sánh công bằng; không thể suy ra từ việc một policy có thể gọi `predict()` tuần tự.

## Tài liệu tham khảo chính

1. Mnih và cộng sự, *Playing Atari with Deep Reinforcement Learning*, 2013: <https://arxiv.org/abs/1312.5602>.
2. Dabney và cộng sự, *Distributional Reinforcement Learning with Quantile Regression*, 2017: <https://arxiv.org/abs/1710.10044>.
3. Schulman và cộng sự, *Trust Region Policy Optimization*, 2015: <https://arxiv.org/abs/1502.05477>.
4. Schulman và cộng sự, *Proximal Policy Optimization Algorithms*, 2017: <https://arxiv.org/abs/1707.06347>.

