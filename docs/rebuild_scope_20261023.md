# UniMatch — điều chỉnh phạm vi ngày 23/10/2026

## Chỉ đạo làm căn cứ

Người dùng xác nhận dữ liệu hiện có là toàn bộ project/folder local và yêu cầu:

> “sử dụng toàn bộ dữ liệu này”
>
> “ở phần frontend sẽ có import hồ sơ sinh viên mới theo 1 file csv có sẵn, có các trường giống như trong thiết kế, trong các features đang sử dụng”
>
> “không cần xác thực học kì”
>
> “kiểm tra xem có mô hình RL hiện tại, nếu tăng step lên thì có tăng khả năng hội tụ, tăng độ chính xác hay không”
>
> “nếu hoàn thành tốt các phase hiện tại và các yêu cầu vừa trình bày thì tiếp tục các phase tiếp theo”

Đây là thay đổi yêu cầu trực tiếp, không phải agent tự bỏ gate. Bằng chứng/gate P6 trước đó giữ nguyên như lịch sử; gate mới phải ghi rõ phạm vi local phi thời gian và tham chiếu artifact cũ.

## Dữ liệu và phép đo

- Kiểm kê toàn bộ dữ liệu local liên quan; khử trùng theo SHA và provenance. Raw/bronze/silver/gold/checkpoint/backup là các lớp của cùng dữ liệu, không đếm thành mẫu mới. Không coi bản 215 cũ là chuẩn hoặc âm thầm đưa hồ sơ quarantine vào train.
- 194 student/35 advisor đã duyệt là snapshot chuẩn hiện tại. Dùng 135 hồ sơ train để fit/học; giữ 29 validation và 30 test theo contract đã khóa. Toàn bộ corpus được sử dụng trong quy trình, không có nghĩa mọi mẫu đều vào training.
- Thử năm seed 42–46, parent 16.384 bước và checkpoint 24.576/32.768 bước; khóa budget trước kết quả. Dùng validation để so sánh learning curve và chọn stage. Không dùng lại final test để tuning.
- Báo cáo mean/std/CI của compatibility/objective, coverage, vi phạm, thời gian và loss; so với parent và Hungarian. Nhiều step có thể cải thiện hoặc làm giảm chất lượng. Không gọi đây là tỷ lệ phân công học vụ đúng khi chưa có nhãn đó.
- Temporal forgetting/outcome có thể `unavailable`. Không đặt thêm yêu cầu xác minh học kỳ để chặn release local.

## Luồng sản phẩm

1. Trang mới bổ sung vào website hiện tại, có token truy cập local, mẫu CSV 40 cột đúng schema và giải thích trường tối thiểu/optional.
2. Import CSV: kiểm tra kích thước, header, ID trùng, taxonomy, confidence/evidence, giá trị sai và formula injection. Metadata provenance của file upload được tính từ bytes thật; không tự tạo kỹ năng hoặc phê duyệt gold.
3. Gợi ý top-K theo phù hợp chủ đề riêng với phân bổ toàn cohort. Chọn advisor tham gia, xem quota chia đều và xác nhận phạm vi lựa chọn.
4. Chạy PPO/DQN có checkpoint thật và Hungarian baseline với chung feature/constraint; lưu trace/version/checksum. Hiển thị Q-value khác probability, compatibility khác accuracy; infeasible phải báo lỗi.
5. Replay có điều khiển và bảng HTML truy cập được; export kết quả và giải thích có nguồn. Không huấn luyện trong handler.
6. Sau gate P7, thêm công cụ trợ lý chỉ đọc trên knowledge base giảng viên đã duyệt, dẫn nguồn và matching function thật. Không giả LLM nếu dùng router cục bộ; không tự tạo capacity hoặc lời cam kết hướng dẫn.

## Nghiệm thu

P6 mới: giữ các kiểm chứng kỹ thuật cũ, hoàn tất experiment năm seed/tăng step, source/holdout/checkpoint không đổi và báo cáo định lượng trung thực.

P7 local: test API/import/inference/auth/privacy, browser desktop/mobile/error flow, checkpoint-bound trace, export, runbook và clean-source dependency audit. Website cũ được giữ. Chạy API local không được mô tả là đã cập nhật cloud.

P8 local: intent routing, retrieval/citation đúng nguồn, không bịa, chống prompt injection, không truy cập cohort khác/token khác, latency và source validity tests. Trợ lý deterministic phải được ghi rõ, không quảng cáo là LLM agent.
