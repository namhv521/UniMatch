# Phase 6 — báo cáo chất lượng

Ngày địa phương: 23/10/2026. Run kỹ thuật: `20261022T182220Z-9f0ee7b0` (UTC).

**Kết luận: `partial`; chưa đủ điều kiện chuyển Phase 7.** Nền tảng kỹ thuật đã chạy được; chưa có phép đo generalization/forgetting qua học kỳ độc lập đã xác minh. Không thay website, không promote model hoặc tạo phân công học vụ thật.

## Nguồn dữ liệu bổ sung

Thư mục người dùng cung cấp ban đầu có ba thư mục rỗng; sau thông báo “đã fill”, đã kiểm tra lại 20 PDF, tổng 79.539.647 byte, 1.751 trang. Giữ audit ban đầu và revision riêng, không ghi đè bằng chứng cũ.

- 20/20 file có SHA-256 trùng nguồn trong inventory hiện tại; không thêm 20 mẫu độc lập.
- 17/20 hash đã có trong 194 hồ sơ gold; ba nguồn còn lại đã ở inventory nhưng chưa có trong gold. Không tự nhập lại hoặc tự bỏ quarantine.
- 20 bìa ghi năm 2026: 18 tháng 8, một tháng 6, một tháng 5. Mã bìa như `2025-2026.3`/`2026.3` vẫn là evidence pending, không tự chốt kỳ chỉ từ tên thư mục.
- Chưa xác minh outcome qua mẫu trang đầu/cuối. Không thấy keyword trong mẫu không có nghĩa sinh viên không có outcome.

Audit P1 đọc 320.280 text block/18.199 tổ hợp nguồn–trang của 211 nguồn PDF: 208 PDF gốc và ba PDF dẫn xuất từ archive. Đây là count PDF, khác inventory 220 tài liệu gốc gồm cả DOCX/RAR. Trong 194 gold, 187 nguồn thuộc PDF bronze và bảy thuộc nguồn khác.

Có mã bìa chưa đủ ngữ cảnh trong 125 nguồn: `2024.1` 11, `2024.2` 29, `2025.1` 22, `2025.2` 35, `2025.3` 5, `2026.1` 11, `2026.3` 12. Parser ngữ cảnh thận trọng chỉ nhận một nguồn `2025.1` làm **candidate**; vẫn pending. Các count này không phải số học kỳ đã duyệt. Hiện số snapshot học kỳ đã chốt đủ bằng chứng: **0**.

Database: không tìm thấy SQLite cục bộ trong checkout; `.env` có biến Compose PostgreSQL nhưng không có `DATABASE_URL`, Docker daemon không truy cập được. Chưa đọc được database, không kết luận database remote không tồn tại hoặc dữ liệu bên trong vô dụng. Không tạo DB mới thay thế, không sử dụng bộ 215 legacy làm chuẩn.

Bằng chứng riêng tư nằm tại `data_rebuild/v1/phase6_source_audit/`: revision của thư mục mới, `original_semester_candidates.json`, `original_semester_summary.json`. File có nội dung nguồn/PII không đưa vào Git hoặc báo cáo công khai.

## Triển khai

- Snapshot content-addressed, canonical manifest, atomic ingest, idempotence, concurrent ingest, timestamp/hash/provenance, outcome cutoff và descriptive drift.
- Queue SQLite với request hash, claim một lần bằng transaction, result manifest hash; training chỉ chạy offline.
- PPO warm start bằng weights/optimizer, rollout buffer mới; kiểm tra training registry/split/reward/quota.
- DQN giữ replay cũ và hiện tại riêng, sampling chính xác 50/50, current-buffer warmup, bridge kiểm tra encoder/code/file thật, checkpoint riêng với checksum và RNG/counter.
- Registry sandbox với checksum, frozen report, receipt và compatibility; rollback có audit và assignment history bất biến.

Giữ nguyên toàn bộ module P0–P5 đã pin hash. Không thêm dependency. Các helper temporal kiểm tra hợp đồng được cung cấp; không tự xác thực học kỳ, reviewer hoặc receipt.

## Diễn tập trên dữ liệu thật đã duyệt

Parent P5: `20261022T122801Z-fd20da3a`, seed 42. Mỗi thuật toán học thêm 1.024 bước; cả hai gặp đủ 135 hồ sơ train. Reserved holdout gồm 29 validation + 30 test, không đưa vào learner. Chỉ dùng lại 29 validation để kiểm tra regression; không đánh giá lại P4 final test trong P6.

| Kiểm chứng | Kết quả |
|---|---|
| PPO | 1.024 bước, bốn loss records, rollout mới |
| DQN | 1.024 bước, 249 gradient updates |
| DQN sampling | 7.968 old + 7.968 current samples, đúng 50/50 |
| Replay lưu | 10.000 old + 1.024 current transitions |
| Checkpoint reload | Trace PPO/DQN khớp hoàn toàn |
| Snapshot upload lặp | Cùng snapshot ID, verify thành công |
| Rollback | Hai candidate kỹ thuật, quay về bản trước, fixture assignment không đổi |
| Runtime website | Đối chiếu 23 file backend/frontend với backup P0: không đổi, không thiếu |

Mean compatibility trên **validation phi thời gian đã dùng trước đây**:

| Thuật toán | Parent | Sau rehearsal |
|---|---:|---:|
| PPO | 0,0450373 | 0,0467716 |
| DQN | 0,1225463 | 0,1517649 |

Baseline Hungarian P5 trên đúng cohort validation: 0,2329906. Cả hai RL vẫn thấp hơn baseline. Biến động trên một seed/reused validation không chứng minh cải thiện tổng quát, không phải kết quả học kỳ mới và không dùng để promote. Tolerance `0` trong báo cáo regression chỉ phục vụ kiểm tra kỹ thuật, chưa được duyệt làm policy nghiệm thu mô hình.

Replay P5 chỉ có provenance cấp cohort/registry, không có student ID từng transition. P6 giữ nguyên giới hạn này; không suy danh tính duy nhất từ fingerprint feature, không đổi nguồn cũ thành nguồn học kỳ mới.

Run lưu 25 artifact có SHA-256, kèm manifest; queue lưu ngoài run để không thay đổi checksum sau khi chốt. Gate alias: `data_rebuild/v1/reports/phase6_gate.json`.

## Test và nghiệm thu

64 test riêng P6 đạt trước rehearsal. Full suite `python -m pytest tests/rebuild -q`: **345 passed**, hai warning deprecation `env.action_masks` của Gymnasium, 50,70 giây. Bao gồm lỗi/tampering, ingest đồng thời, cutoff, holdout, source-bound checkpoint bridge, stratification, rollback và authority tách biệt.

Agent review độc lập xác minh lại 25 artifact P6 và 246 artifact P5, bảy hash code P6 và tám hash code P5; không đổi. Bốn trace/116 policy-Q vector tải lại khớp tuyệt đối. 10.000 replay cũ khớp parent, 1.024 replay hiện tại chỉ thuộc train. Registry được đọc bằng SQLite `mode=ro`, xác minh hai register/hai promotion kỹ thuật/một rollback/một fixture assignment và checksum DB không đổi. Bằng chứng: `data_rebuild/v1/phase6_source_audit/phase6_independent_validation.json`.

| Điều kiện | Trạng thái |
|---|---|
| Idempotent upload, snapshot bất biến | Đạt kỹ thuật |
| Offline job request/result manifest | Đạt kỹ thuật |
| PPO fresh rollout / DQN stratified replay | Đạt kỹ thuật |
| Holdout P4 không vào learner rehearsal | Đạt trên cohort hiện tại |
| Performance/regression report tự động | Đạt trên reused validation |
| Rollback bảo toàn assignment | Đạt với fixture rõ ràng |
| Temporal snapshot, feature availability, approval đã xác minh | Chưa đạt |
| Parent/encoder fit chỉ trên quá khứ | Chưa có baseline thời gian; P4/P5 hiện phi thời gian |
| Frozen unseen-semester evaluation và forgetting thực tế | Chưa đo được |
| Model promotion thật | Chưa cho phép |

## Điều kiện đóng P6

1. Rà và duyệt ánh xạ học kỳ từ báo cáo nguồn; bổ sung ngày bắt đầu/kết thúc/chốt, assignment đã duyệt và provenance. Dùng database/export nếu truy cập được và đối chiếu được nguồn; không tin chỉ vì bản ghi đã nằm trong DB.
2. Xác minh dữ liệu nào tồn tại trước thời điểm matching. Nội dung luận văn hoàn thành và outcome sau kỳ không tự trở thành feature trước phân công.
3. Tạo snapshot theo kỳ, khóa source-group/ID holdout và cấu hình thời gian. Với cấu hình train/validation/test hiện có cần ít nhất ba kỳ được xác minh.
4. Dựng lại encoder/baseline và parent từ quá khứ, rồi chạy continuation trên kỳ mới; parent P5 đã học dữ liệu trộn kỳ không thể dùng làm bằng chứng temporal sạch.
5. Khóa metric/tolerance, chạy đánh giá kỳ cũ/kỳ chưa thấy, cập nhật report và gate. Chỉ chuyển P7 khi các điều kiện này đạt, hoặc khi người dùng thay đổi yêu cầu nghiệm thu một cách rõ ràng.

Hướng dẫn API/lệnh: `docs/rebuild_phase6_operator_guide.md`.
