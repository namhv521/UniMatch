# Phase 6 — cập nhật mô hình theo học kỳ

## Phạm vi

Pipeline chạy offline, dùng module mới; không nối training vào FastAPI hay thay website. Snapshot, queue và registry kỹ thuật lưu dưới `data_rebuild/v1/`, được Git ignore. Registry mặc định là `research_sandbox`, không phải registry production.

Các API hiện có hỗ trợ snapshot, kiểm tra provenance/cutoff, drift, tiếp tục PPO/DQN, queue và rollback. Chưa có job học kỳ thực tế được nghiệm thu. Worker CLI hiện chạy **rehearsal**, không tự nhập các tài liệu vừa tìm thấy vào gold.

## Chạy lại kiểm chứng

```powershell
python -m pytest tests/rebuild -q
python scripts/rehearse_semester_learning.py --timesteps 1024 --seed 42
```

CLI trả exit code `2` khi gate còn `partial`; đây không phải chấp thuận chuyển phase. Trong PowerShell, dùng `exit $LASTEXITCODE` khi cần chuyển nguyên mã thoát sang runner bên ngoài.

Worker kiểm tra gate P5, toàn bộ artifact P5, source hash và cohort P4 trước khi học. Mỗi lần chạy có thư mục riêng, `input_manifest.json`, snapshot reference, request, training logs, evaluation, checkpoint, rollback drill và manifest SHA-256. Queue không thực thi learning khi enqueue; worker mới claim job. Job bị gián đoạn giữ `running`, cần kiểm tra artifact rồi tạo attempt rõ ràng; không tự chạy đè.

## Tạo snapshot học kỳ thực tế

Dùng `src.data_pipeline.semester_snapshots.create_snapshot` với:

- `semester_id` lấy từ nguồn đã kiểm duyệt; mã `2025.1` là kỳ 1/2025 theo quy ước người dùng, không suy từ năm tuyển sinh.
- `captured_at` có timezone; `feature_sha256`, `taxonomy_sha256`, `policy_sha256` là hash thật.
- `files`: ánh xạ tên tương đối sang file nguồn hiện có; thư mục nguồn không được sửa khi ingest.
- Trạng thái `draft`, `research`, `approved` hoặc `closed`. `closed` yêu cầu ngày bắt đầu/kết thúc/chốt rõ ràng và assignment có provenance, reviewer, thời điểm duyệt.
- `assignments` và `outcomes` chỉ gồm bản ghi có nguồn. `source_ref` phải trỏ đúng file trong snapshot và `source_sha256` phải khớp. Thiếu outcome giữ `unknown_not_supplied`, không đổi thành thất bại hoặc điểm 0.

`verify_snapshot(store, snapshot_id)` kiểm tra lại content hash, canonical manifest, file, kích thước và provenance. Cùng bytes **và cùng metadata** trả cùng snapshot ID, kể cả ingest đồng thời. Thay đổi metadata hoặc bytes tạo phiên bản khác, không sửa snapshot trước. `outcome_availability(..., as_of=...)` loại nhãn chưa được quan sát/duyệt tại cutoff khỏi tập sử dụng lúc đó.

Snapshot container không thay việc kiểm duyệt nội dung CSV. Dữ liệu mới phải qua validator và quy trình approval đã xây ở P1–P3; một ô `approved` hoặc metadata reviewer tự khai không chứng minh phê duyệt của nhà trường.

## Chuẩn bị cập nhật thật

1. Kiểm duyệt ánh xạ học kỳ theo từng hồ sơ, nguồn/alias trùng, assignment đã chốt và thời điểm dữ liệu sẵn có. Giữ báo cáo hoàn thành luận văn là dữ liệu sau phân công; không tự coi nội dung cuối kỳ đã có lúc matching.
2. Xác minh bytes của snapshot/receipt, rồi dùng `temporal_split` kiểm tra hợp đồng thời gian, ID và source-group không giao nhau. Hàm này kiểm tra hợp đồng được cung cấp; không tự xác thực receipt. Cần ít nhất ba kỳ cho cấu hình train/validation/test này.
3. Fit vocabulary/IDF và chọn trọng số chỉ trên dữ liệu được phép ở quá khứ. P4/P5 hiện tại dùng split phi thời gian và parent đã học 135 hồ sơ thuộc bộ trộn kỳ; không dùng chúng để tuyên bố backtest lịch sử sạch. Muốn đánh giá liên kỳ, phải dựng lại baseline và parent theo split thời gian đã duyệt.
4. Khóa holdout và metric/tolerance trước khi học. Registry/action order, taxonomy, encoder, reward và quota phải tương thích. Thay roster/taxonomy/state semantics cần rebuild, không chỉ đổi tên checkpoint.
5. `continue_ppo` tạo agent và rollout buffer mới, sao chép weights/optimizer từ parent có checksum. `ContinualDQN.from_checkpoint` giữ replay cũ riêng và ghi replay hiện tại riêng; mỗi batch chẵn lấy đúng một nửa mỗi nguồn, chờ đủ transition hiện tại trước khi update.
6. Nếu dataset contract thay đổi nhưng representation giữ nguyên, cung cấp bridge descriptor có hash của hai contract và encoder/code/artifact thật. Bridge không cho phép đổi ý nghĩa state, taxonomy, reward hoặc action map. Không ghi provenance kỳ mới đè lên replay cũ.
7. Enqueue request nguồn-bound bằng `OfflineJobs`, claim ở worker riêng, lưu manifest và trạng thái cuối. Các hàm learner có thể dùng trong worker học kỳ sau; CLI rehearsal hiện không phải entrypoint hoàn chỉnh cho dữ liệu học kỳ mới.
8. Chạy baseline, parent, candidate trên đúng các cohort đóng băng, báo cáo hiệu năng kỳ mới và forgetting từng kỳ cũ. `forgetting_report` ghép theo `cohort_sha256`; thiếu phép đo trả `unavailable`, không phải pass. Chỉ đăng ký/chọn candidate khi safety, frozen evaluation, compatibility và approval đều hợp lệ.

PPO dùng rollout mới theo [MaskablePPO](https://sb3-contrib.readthedocs.io/en/v2.3.0/modules/ppo_mask.html); lưu/load theo cách kiểm soát state, không tải arbitrary pickled object. Worker hiện dùng CPU và dependency P5 đã pin.

## Registry và rollback

`CandidateRegistry.register(checkpoint_dir, contract, evaluation_reports)` kiểm tra native checkpoint hash, report `gate`/`evaluation`, checkpoint/contract/evaluation binding và compatible contract. `promote` cần receipt gắn đúng candidate và report. `rollback` chỉ về candidate đã được duyệt, kiểm tra lại bytes trước khi đổi active pointer trong transaction SQLite.

Assignment batch có hash/receipt nguồn riêng, có trigger chặn UPDATE/DELETE. Đổi active model không sửa lịch sử phân công. Đây là bảo vệ trong ứng dụng, không phải chữ ký số hay bảo vệ trước quản trị viên có quyền sửa toàn bộ filesystem/DB.

`technical_drill` chỉ nhận authority `automated_test_fixture`/`phase6-drill`; `research_sandbox` từ chối loại receipt này. Không đưa registry drill hoặc fixture assignment sang vận hành. Hiện không có model nào được promote thật; Hungarian vẫn là phương án mặc định.
