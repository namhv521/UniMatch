# Chương 8. Các thuật toán RL và vòng đời checkpoint

## 8.1. Nhóm thuật toán khảo sát

Dự án có adapter cho DQN, QR-DQN, MaskablePPO, TRPO, ARS và RecurrentPPO. TQC bị từ chối vì môi trường có action rời rạc trong khi adapter TQC yêu cầu action liên tục. Việc có script hoặc checkpoint không đồng nghĩa thuật toán đã được đánh giá hợp lệ. Mỗi thuật toán phải đi qua cùng hợp đồng dữ liệu, môi trường, benchmark và promotion.

## 8.2. DQN

DQN phù hợp action rời rạc và dùng replay buffer. Ưu điểm là inference đơn giản: chọn action có Q-value lớn nhất. Trong bài toán quota, DQN chuẩn có thể chọn advisor đã đầy. Có ba lựa chọn: mask Q-value trước argmax, phạt và thử lại, hoặc fallback. Dự án hiện theo dõi invalid proposal; bất kỳ biến thể masking nào phải được gọi tên riêng và mô tả, không ghi chung là “DQN” rồi so với bản không mask.

## 8.3. QR-DQN

QR-DQN biểu diễn phân phối return bằng nhiều quantile và có thể hữu ích khi reward phụ thuộc chuỗi phân bổ. Nhưng distributional output không tự mang nghĩa bất định nhận thức về dữ liệu. Để dùng trong UI, cần trích quantile thật ở trạng thái/action cụ thể, ghi số quantile và scale reward. Nếu chỉ có assignment, UI không được dựng biểu đồ phân phối giả.

## 8.4. MaskablePPO

MaskablePPO là ứng viên tự nhiên cho hard quota vì action mask được áp dụng trước sampling. PPO tối ưu surrogate clipped và thường thu thập rollout on-policy. Các siêu tham số quan trọng gồm learning rate, rollout length, batch size, \(\gamma\), GAE \(\lambda\), entropy coefficient và clip range. Báo cáo chỉ công bố cấu hình được đọc từ run manifest; không suy đoán từ mặc định thư viện nếu artifact không lưu.

## 8.5. TRPO, ARS và RecurrentPPO

TRPO dùng bước cập nhật bị ràng buộc trust region. ARS tìm hướng cải thiện tham số qua nhiễu ngẫu nhiên có cấu trúc; nó đơn giản về ý tưởng nhưng vẫn cần chuẩn hóa và nhiều rollout. RecurrentPPO thêm trạng thái hồi quy để ghi nhớ lịch sử; inference phải truyền `state` và `episode_start` đúng. Trong bài toán này, tải đã nằm trong observation nên lợi ích thêm của recurrent policy phải được chứng minh, không mặc định tốt hơn.

## 8.6. Phạm vi smoke và full

Smoke run dùng ma trận 2×2 trong 16 timesteps để kiểm tra wiring, import, save/load và manifest. Nó phải gắn `training_scope=synthetic-smoke`, hash riêng và không dùng cho promotion. Full run hiện hành lấy đúng **154 hàng train** từ ma trận v2 215×38, tạo 38 action và observation shape 114. Mục tiêu promotion là tối thiểu 2.000.000 timesteps trên từng seed trong tập `{42, 123, 456, 789, 1024}`, nhưng số bước lớn không chứng minh model tốt; benchmark validation và các gate mới quyết định khả năng sử dụng.

## 8.7. Manifest và resume

Run manifest cần ít nhất:

- algorithm, seed, requested/completed timesteps và trạng thái;
- dataset, split, feature và capacity-policy hash;
- training scope và environment version;
- observation shape, action count và phiên bản thư viện;
- checkpoint filename và SHA-256.

Resume chỉ được phép khi các trường hợp đồng giống nhau, checkpoint hash đúng, run trước hoàn thành và không phải smoke. Nếu dữ liệu hoặc feature thay đổi, phải khởi tạo run mới. Không sửa manifest cũ để “hợp thức hóa” checkpoint.

## 8.8. Registry fail-closed

Registry đọc trực tiếp archive để lấy observation/action space. Trạng thái đề xuất:

| Trạng thái | Ý nghĩa | Dataset được phép |
|---|---|---|
| `toy_unpromoted` | Archive 6×2, chỉ có giá trị demo | `sample-2x2`, `sample-3x2` |
| `unpromoted_research` | Archive 114×38 đúng không gian nhưng chưa qua promotion | validation ở chế độ nghiên cứu rõ ràng |
| `promoted` | Qua benchmark, provenance và gate | dataset được manifest cho phép |
| `invalid` | Hash, archive hoặc space sai | Không dataset nào |

Checkpoint toy 6×2 lịch sử thuộc `toy_unpromoted`. Report hiện hành đã đánh giá 24 checkpoint thật 114×38, sau đó chọn checkpoint có ngân sách lớn nhất theo từng cặp thuật toán–seed để tạo 20 dòng RL trong bảng chính. DQN, MaskablePPO và QR-DQN có đủ năm seed ở 2.000.000 bước; TRPO có ba seed ở 2.000.000 bước; ARS có một seed ở 2.464 bước; RecurrentPPO có một seed ở 256 bước. Các run này vẫn là `unpromoted_research`, không phải model production.

## 8.9. Promotion gate

Một candidate chỉ được cân nhắc khi quota violations bằng 0, coverage bằng 1, không có invalid/fallback, provenance đầy đủ, đủ năm seed khóa trước, mỗi seed đạt ít nhất 2.000.000 bước và optimality ratio không thấp hơn 0,88 so với Hungarian. Sau khi chọn cấu hình, test holdout chỉ chạy một lần theo quy trình đã ghi. Không chọn model từ test và không công bố “RL thắng” chỉ vì đủ timesteps.

Report `outputs/benchmarks/current-validation.json` không promote thuật toán RL nào. MaskablePPO đủ seed/ngân sách và không invalid/fallback nhưng thất bại compatibility gate. DQN và QR-DQN đủ seed/ngân sách nhưng vừa thất bại compatibility gate vừa phụ thuộc sửa proposal không hợp lệ. TRPO còn thiếu hai seed và có fallback; ARS và RecurrentPPO vừa thiếu seed/ngân sách vừa có fallback. Hệ thống vì thế chọn Hungarian với lý do không có bằng chứng RL full-budget nhiều seed được phê duyệt.

