# UniMatch — RL hai cấp và danh sách URL giảng viên

Phạm vi hiện tại: **chỉ lưu URL để người dùng bổ sung**. Chưa thu thập nội dung, trích xuất, làm sạch, chuẩn hóa hoặc xây dataset mới. Corpus và công cụ trích xuất tạm của lượt trước được loại bỏ; raw/gold/checkpoint/runtime có từ trước giữ nguyên.

## 1. Một folder, một CSV

File duy nhất: `data_rebuild/advisor_urls/giang_vien_urls.csv`, UTF-8 BOM, mở được bằng Excel.

Năm cột, một hàng mỗi giảng viên: **Tên giảng viên | FIT NEU | Google Scholar | GitHub | ResearchGate**.

Giữ 38 identity từ danh sách nguồn đã có, không tự giới hạn còn 35 người trong gold cũ. URL chưa có để ô trống. Không thêm placeholder, ghi chú, dữ liệu cá nhân hay kết quả suy diễn vào ô URL. Chỉ giữ liên kết đã quan sát trên hồ sơ chính thức hoặc tài khoản đã được người dùng xác nhận. Bảng URL không phải roster đã duyệt, dữ liệu training hoặc xác nhận tham gia hướng dẫn.

Không tạo folder riêng cho từng giảng viên/năm, bản raw, JSON, manifest, report hay script thu thập ở bước này. Không crawl Google Scholar/ResearchGate/GitHub. Người dùng bổ sung trực tiếp vào CSV.

## 2. Quy ước phiên bản dữ liệu do người dùng xác định

Mã kỳ biểu thị năm bắt đầu năm học, không phải chỉ năm dương lịch. Ví dụ `2024.1` là kỳ 1 của năm học 2024–2025.

| Phiên bản | Mã kỳ | Năm học | Dữ liệu mới của phiên bản | Snapshot tích lũy đến hết |
|---|---|---|---|---|
| V1 | 2024.1 | 2024–2025, kỳ 1 | Toàn bộ dữ liệu đủ điều kiện từ trước đến **31/12/2024** | 31/12/2024 |
| V2 | 2024.2 | 2024–2025, kỳ 2 | **01/01/2025–30/06/2025** | 30/06/2025 |
| V3 | 2025.1 | 2025–2026, kỳ 1 | **01/07/2025–31/12/2025** | 31/12/2025 |
| V4 | 2025.2 | 2025–2026, kỳ 2 | **01/01/2026–30/06/2026** | 30/06/2026 |

Các mốc đều theo Asia/Saigon. Dùng khoảng nửa mở khi xử lý timestamp: V1 `<2025-01-01`; V2 `[2025-01-01,2025-07-01)`; V3 `[2025-07-01,2026-01-01)`; V4 `[2026-01-01,2026-07-01)`. Như vậy tháng 12/2024 thuộc V1, tháng 6/2025 thuộc V2, tháng 12/2025 thuộc V3; không chồng lặp ở tháng ranh giới.

Đây là quy ước được người dùng chốt cho khóa luận, không phải suy luận từ tên thư mục hoặc lịch trường. Đến bước thu thập sau này, record thiếu/mâu thuẫn ngày phải chờ xác minh; không tự gán vào một phiên bản.

Phân biệt dữ liệu mới của V2 với kiến thức V2 kế thừa từ V1. Snapshot V2 có thể tham chiếu lịch sử đến 30/06/2025, nhưng cửa sổ dữ liệu mới chỉ là 01/01–30/06/2025. Rehearsal lịch sử, nếu dùng, được ghi riêng, không đếm lại là mẫu mới.

## 3. RL hai cấp trong bước triển khai tương lai

**Vòng ngoài:** bootstrap model V1 từ dữ liệu đủ điều kiện đến 31/12/2024; V2 kế thừa checkpoint V1; V3 kế thừa V2; V4 kế thừa V3, khi các candidate đạt điều kiện chấp nhận. Không khởi tạo ngẫu nhiên lại mỗi kỳ. Phiên bản dữ liệu và phiên bản model là hai định danh riêng: snapshot tồn tại không bảo đảm model tương ứng đã đạt chất lượng hoặc được phát hành.

**Vòng trong:** trong từng kỳ, giữ cohort của kỳ đó và cập nhật từ model vòng trước khi có tín hiệu thật. Ví dụ: phù hợp chuyên môn, nguyện vọng đã xác nhận, phản hồi giảng viên, rà soát của điều phối. Bốn vòng là ví dụ; thiếu tín hiệu thì bỏ qua có ghi nhận, không tạo phản hồi giả.

Mỗi vòng tương lai cần parent/checkpoint hash, dataset/signal version, cutoff, thời điểm tín hiệu có thật, split, encoder/action/reward/constraint version, seed, số bước và quyết định accept/reject/inconclusive. PPO thu rollout mới; DQN chỉ replay transition còn đúng ngữ nghĩa. Quota và eligibility là ràng buộc, không chỉ là điểm thưởng.

Chấm parent/candidate trên cùng bối cảnh và tiêu chí, đo giữ mục tiêu cũ và quên liên kỳ. So sánh cả trường hợp chỉ train thêm bước để tách tác dụng tín hiệu mới khỏi tác dụng ngân sách. Không hứa mỗi vòng đều tăng chất lượng; candidate không đạt thì giữ bản đã chấp nhận gần nhất.

## 4. Ranh giới thời gian khi nghiên cứu sau này

Ngày công bố/sự kiện, ngày thu thập và thời điểm thông tin có sẵn cho quyết định phải được lưu riêng. Một URL hiện có không chứng minh toàn bộ nội dung trang đã có vào 2024.1. Cutoff cuối kỳ quy định dữ liệu được phép cho phiên bản cuối kỳ; không cho phép dùng feedback cuối kỳ để giả lập một dự đoán đầu kỳ.

V1 được chốt cuối tháng 12/2024 để kiểm tra/cập nhật trong kỳ 2024.2. Khi đánh giá ở một vòng trong kỳ, chỉ sử dụng dữ liệu thực sự đã có trước cutoff của vòng đó; sau khi đã học một tập dữ liệu, không gọi chính tập đó là final test độc lập.

Hiện tại chỉ bàn giao bảng URL và quy ước trên. Chưa có thu thập/cleaning/training mới theo các phiên bản này; không sửa model hoặc phục vụ website.
