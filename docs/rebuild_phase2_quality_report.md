# UniMatch — Nghiệm thu Phase 2

Ngày kiểm chứng: 21/10/2026, Asia/Saigon. Trạng thái: **VERIFIED cho coverage/provenance nguồn giảng viên**. Chưa phê duyệt gold, chuyên môn giám sát, sự tham gia học kỳ hoặc quota.

## Nguồn và kết quả

Danh mục được chụp từ DOM đã render của [website chính thức](https://fit.neu.edu.vn/lecturer). Có 38 URL hồ sơ duy nhất được quan sát trong danh mục hiện tại; con số này được kiểm kê mới, không tái sử dụng roster lịch sử.

| Kiểm tra | Kết quả |
|---|---|
| URL hồ sơ trong danh mục / hồ sơ có nguồn | 38 / 38 |
| Fetch failures | 0 |
| Evidence snippets đối chiếu raw DOM | 809 |
| Evidence errors / contact field leaks | 0 / 0 |
| Hồ sơ thiếu research topics tường minh | 7 |
| Hồ sơ thiếu publications được liệt kê | 13 |
| Hồ sơ human-approved | 0 |
| Parser regression tests | 9 passed |

Thiếu dữ liệu được giữ nguyên và đưa vào review queue. Mỗi hồ sơ lưu URL, thời điểm lấy nguồn, SHA256, parser version, bằng chứng theo trường và nguồn danh mục. Tên lấy từ heading hồ sơ, không lấy heading chung của website. Vai trò trong danh mục là dữ liệu nguồn; không đồng nghĩa đủ điều kiện hướng dẫn.

## Truy xuất nguồn và giới hạn

Run chuẩn: `20261021T154610Z-9cfd4d06`, parser `lecturer-crawl/1.1`, BeautifulSoup `4.12.3`.

DOM danh mục có SHA256 `e4b39ab46d2f0434e25dd5d596282091542f9968caca80eb3d79831d07260ea1`. Đã kiểm chứng byte thực của snapshot bằng hash, gồm cả xử lý newline Windows.

Run HTTP đầu tiên `20261021T154229Z-646f9784` được giữ nguyên làm bằng chứng lịch sử. Parser đầu bỏ sót một số heading publications và snapshot danh mục bị đổi newline khi ghi file. Run chuẩn sửa hai lỗi này, reparse từ raw HTTP đã khóa hash, giữ nguyên thời điểm retrieval gốc và không phát sinh crawl bổ sung. Hai mẫu cấu trúc hồ sơ đã được agent đối chiếu trực tiếp; đây không phải phê duyệt của chuyên gia/người sở hữu dữ liệu.

[Robots](https://fit.neu.edu.vn/robots.txt) được kiểm tra trước crawl. Chỉ lấy các detail URL quan sát được trong danh mục, tôn trọng scope và không gọi `/api/` bị cấm. HTTP có giới hạn kích thước, timeout, throttle, retries/backoff và snapshot response. API/data input Phase 1 được ràng buộc bằng gate và immutable artifact hashes.

Giữ `active_for_semester`, `capacity_max` và `existing_load` ở trạng thái chưa biết. `profile_text` phục vụ rà soát giữ intro, teaching, research và công trình khoa học; loại phần LIÊN HỆ và awards. Chuỗi công bố có thể chứa tác giả, nên vẫn là raw evidence, chưa phải ML input được phê duyệt. Phase 3/4 phải áp dụng allowlist, loại identifier/contact/proxy và đánh giá feature trước khi matching/training.

## Artifacts và gate

Artifacts riêng tư dưới `data_rebuild/v1`, không commit raw:

- `bronze/faculty_pages.jsonl`: receipts và snapshot metadata.
- `silver/advisors.jsonl`: 38 hồ sơ với field evidence và missingness.
- `reports/advisor_crawl_quality.csv`, `advisor_review_queue.csv`.
- `reports/phase2_gate.json`, `phase2_parser_validation.json`, `phase2_independent_validation.json`.
- Immutable run manifest với SHA256 từng artifact.

Gate P2 đạt vì mọi URL đã được đối soát, mọi hồ sơ có provenance, raw/evidence đã được kiểm chứng và thông tin thiếu hiển thị rõ. Phase 3 được phép chuẩn hóa/reconcile; việc chuyển gold vẫn cần review và chấp nhận taxonomy/data riêng.
