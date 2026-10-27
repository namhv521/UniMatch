# UniMatch — RL hai cấp và corpus nguồn mới

**Ủy quyền triển khai 28/10/2026:** người dùng đã yêu cầu sao lưu lên branch `backup`, sau đó liên tục triển khai hướng RL hai cấp này, bắt đầu thu thập dữ liệu mới từ đầu vào folder mới. Hạn chế “chỉ lưu URL” của giai đoạn 27/10 bên dưới được thay thế bởi ủy quyền mới; quy ước V1–V4 và yêu cầu vòng phản hồi vẫn giữ nguyên. Không sử dụng các spec cũ làm chỉ đạo thay thế. Raw/gold/checkpoint cũ không bị ghi đè.

Namespace mới: `data_rebuild/nested_rl_20261028/<run>/`, gồm nguồn faculty/publications được lấy HTTP mới, tài liệu sinh viên được đọc lại từ bytes gốc, phân kỳ, feature/suite và artifact nghiên cứu mới. Thiếu GitHub/Scholar/ResearchGate thì chỉ dùng FIT NEU; thu thập cả các mục công bố và năm có bằng chứng. Năm không đủ phân biệt kỳ thì để chưa xác định, không tự gán tháng. Có thể phát triển/chạy pipeline kỹ thuật nhưng không tự tạo nguyện vọng, outcome hay phản hồi học vụ.

Pipeline, lệnh chạy và kết quả mới: [báo cáo triển khai 28/10](nested_rl_rebuild_20261028.md). Đợt train hiện hành dùng derivative `students_reviewed`, suite trong `research/suites/`; các checkpoint nghiên cứu không tự thay model phục vụ.

## 1. Danh bạ URL làm seed cho thu thập mới

Danh bạ seed: `data_rebuild/advisor_urls/giang_vien_urls.csv`, UTF-8 BOM, mở được bằng Excel.

Năm cột, một hàng mỗi giảng viên: **Tên giảng viên | FIT NEU | Google Scholar | GitHub | ResearchGate**.

Giữ 38 identity từ danh sách nguồn đã có, không tự giới hạn còn 35 người trong gold cũ. URL chưa có để ô trống. Không thêm placeholder, ghi chú, dữ liệu cá nhân hay kết quả suy diễn vào ô URL. Chỉ giữ liên kết đã quan sát trên hồ sơ chính thức hoặc tài khoản đã được người dùng xác nhận. Bảng URL không phải roster đã duyệt, dữ liệu training hoặc xác nhận tham gia hướng dẫn.

Giữ danh bạ gọn, không tạo boilerplate theo từng người/năm. Dữ liệu thu thập mới được lưu tập trung theo loại nguồn với raw bytes/provenance, bảng giảng viên và bảng công bố; không coi nội dung cũ là dữ liệu vừa crawl. External account chỉ sử dụng khi có nguồn danh tính rõ; tài khoản không có để trống và tiếp tục nguồn FIT NEU. Không vượt CAPTCHA hoặc đăng nhập.

## 2. Học kỳ học vụ và phiên bản training là hai định danh khác nhau

**Điều chỉnh mới nhất ngày 28/10/2026:** phân học kỳ tự động từ ngày có bằng chứng trên **trang 1–2** của tài liệu sinh viên. Không lấy ngày ở tài liệu tham khảo, nội dung các trang sau, tên file hoặc ngày hiện tại để gán học kỳ. Nội dung các trang khác vẫn có thể được trích xuất phục vụ mô tả đề tài.

Với năm dương lịch `Y`: tháng 9–12 → học kỳ `Y.1`; tháng 1–5 → `(Y-1).2`; tháng 6–8 → `(Y-1).3` (hè). Quy tắc này thay thế các ngoại lệ tháng và khoảng trống trước đó; các học kỳ cũ vẫn giữ mã học vụ thực tế, không đổi tất cả thành `2024.1`.

| Ngày nguồn sinh viên | Học kỳ học vụ | Phiên bản dữ liệu training |
|---|---|---|
| Đến hết 31/12/2024 | Theo quy tắc tháng/năm trên, kể cả học kỳ cũ và `2023.3` vào 06–08/2024 | V1 / `2024.1`, pool lịch sử |
| 01–05/2025 | `2024.2` | V2 / `2024.2` |
| 06–08/2025 | `2024.3` (hè) | V3 / `2025.1` |
| 09–12/2025 | `2025.1` | V3 / `2025.1` |
| 01–05/2026 | `2025.2` | V4 / `2025.2` |
| 06–08/2026 | `2025.3` (hè) | Chưa ánh xạ; cần chính sách riêng |
| 09–12/2026 | `2026.1`, khi ngày nguồn hỗ trợ | Chưa ánh xạ; không tự tạo V5 |

Thiếu tháng/ngày hoặc có bằng chứng mâu thuẫn thì giữ học kỳ chưa xác định, kèm lý do và nguồn. Năm đơn lẻ ≤2024 có thể xác định pool lịch sử V1 nhưng không đủ xác định học kỳ học vụ. Năm 2025 đơn lẻ không đủ phân biệt V2/V3; không tự gán nửa năm. Học kỳ hiện tại `2026.1` không chứng minh tài liệu thuộc kỳ này.

### Cutoff snapshot giảng viên/model đã chốt, tách khỏi cửa sổ sinh viên

| Phiên bản | Mã training | Cửa sổ bổ sung faculty đã chốt | Snapshot giảng viên/model tích lũy đến hết |
|---|---|---|---|
| V1 | `2024.1` | Toàn bộ lịch sử đủ điều kiện đến 31/12/2024 | 31/12/2024 |
| V2 | `2024.2` | 01/01/2025–30/06/2025 | 30/06/2025 |
| V3 | `2025.1` | 01/07/2025–31/12/2025 | 31/12/2025 |
| V4 | `2025.2` | 01/01/2026–30/06/2026 | 30/06/2026 |

**Hai đồng hồ độc lập:** điều chỉnh tháng học vụ chuyển sinh viên tháng 6/2025 sang hè `2024.3`, pool training V3; không thay các cutoff snapshot faculty/model tháng 6 đã chốt. Sinh viên V2 chỉ 01–05/2025, V3 gồm 06–12/2025, V4 chỉ 01–05/2026; 06–08/2026 chưa ánh xạ. Không dùng cutoff faculty để kéo sinh viên tháng 6 vào V2/V4.

Các cửa sổ bổ sung faculty theo Asia/Saigon, triển khai bằng khoảng nửa mở: V1 `<2025-01-01`; V2 `[2025-01-01,2025-07-01)`; V3 `[2025-07-01,2026-01-01)`; V4 `[2026-01-01,2026-07-01)`. Snapshot faculty V2 tham chiếu lịch sử đủ điều kiện đến 30/06/2025, không chỉ công bố mới trong V2. Rehearsal lịch sử được ghi riêng, không đếm lại là mẫu mới.

Năm công bố đơn lẻ ≤2024 có thể nhóm sự kiện vào V1, nhưng chưa chứng minh thông tin có sẵn trong lịch sử. Công bố chỉ có năm 2025 giữ chưa phân kỳ V2/V3. Không suy tháng từ số tập/số tạp chí. Ngày chụp nguồn mới không thay thế ngày công bố hoặc thời điểm thông tin có sẵn.

## 3. RL hai cấp trong triển khai nghiên cứu

**Vòng ngoài:** bootstrap model V1 từ dữ liệu đủ điều kiện đến 31/12/2024; V2 kế thừa checkpoint V1; V3 kế thừa V2; V4 kế thừa V3, khi các candidate đạt điều kiện chấp nhận. Không khởi tạo ngẫu nhiên lại mỗi kỳ. Phiên bản dữ liệu và phiên bản model là hai định danh riêng: snapshot tồn tại không bảo đảm model tương ứng đã đạt chất lượng hoặc được phát hành.

**Vòng trong:** trong từng kỳ, giữ cohort của kỳ đó và cập nhật từ model vòng trước khi có tín hiệu thật. Ví dụ: phù hợp chuyên môn, nguyện vọng đã xác nhận, phản hồi giảng viên, rà soát của điều phối. Bốn vòng là ví dụ; thiếu tín hiệu thì bỏ qua có ghi nhận, không tạo phản hồi giả.

Mỗi vòng cần parent/checkpoint hash, dataset/signal version, cutoff, thời điểm tín hiệu có thật, split, encoder/action/reward/constraint version, seed, số bước và quyết định accept/reject/inconclusive. PPO thu rollout mới; DQN chỉ replay transition còn đúng ngữ nghĩa. Quota và eligibility là ràng buộc, không chỉ là điểm thưởng.

Chấm parent/candidate trên cùng bối cảnh và tiêu chí, đo giữ mục tiêu cũ và quên liên kỳ. So sánh cả trường hợp chỉ train thêm bước để tách tác dụng tín hiệu mới khỏi tác dụng ngân sách. Không hứa mỗi vòng đều tăng chất lượng; candidate không đạt thì giữ bản đã chấp nhận gần nhất.

## 4. Ranh giới thời gian và bằng chứng nghiên cứu

Ngày công bố/sự kiện, ngày thu thập và thời điểm thông tin có sẵn cho quyết định phải được lưu riêng. Một URL hiện có không chứng minh toàn bộ nội dung trang đã có vào 2024.1. Cutoff cuối kỳ quy định dữ liệu được phép cho phiên bản cuối kỳ; không cho phép dùng feedback cuối kỳ để giả lập một dự đoán đầu kỳ.

V1 được chốt cuối tháng 12/2024 để kiểm tra/cập nhật trong kỳ 2024.2. Khi đánh giá ở một vòng trong kỳ, chỉ sử dụng dữ liệu thực sự đã có trước cutoff của vòng đó; sau khi đã học một tập dữ liệu, không gọi chính tập đó là final test độc lập.

Các phần thu thập/feature/learner mới phải có báo cáo bằng chứng riêng; không gán các số đo cũ cho chúng. Các vòng chưa có signal thật được báo unavailable/skipped; dữ liệu thiếu thời điểm không được dùng để tuyên bố backtest sạch. Candidate chưa đạt gate không thay model phục vụ hiện tại. Tiến độ ở [kế hoạch triển khai mới](superpowers/plans/2026-10-28-nested-rl-rebuild.md).
