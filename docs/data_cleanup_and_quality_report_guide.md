# Rà soát data và hướng dẫn Quality report

Ngày: 08/10/2026. Đã kiểm tra file, caller trong code và metadata hiện tại. Chỉ dọn cache JavaScript xác định được là dư; chưa thay dữ liệu nghiệp vụ, features, model hoặc logic readiness.

## Kết quả kiểm tra dữ liệu hiện tại

- `theses.json`: 220 bản ghi; `advisors.json`: 38 bản ghi.
- Cả `advisors.json` và `advisors.csv` đều không có giá trị quota ở 38/38 bản ghi. `quota_source` mô tả quota không được công bố và dùng `ceil(N/M)` theo cohort.
- JSON có 30 giảng viên có `skill_text`, 32 có `profile_text`, 32 có `skill_text_inferred`. Không thể chỉ dựa vào tỷ lệ thiếu `skill_text` để kết luận mọi hồ sơ đó thiếu kỹ năng: phải kiểm tra hợp các trường và nguồn evidence.
- Nhánh serving hiện dùng `profile_text` rồi `skill_text`; không fallback sang `skill_text_inferred`. Thiếu trường mà code dùng và thiếu mọi thông tin chuyên môn là hai tiêu chí khác nhau.
- Kiểm tra hợp cả ba trường cho thấy 6/38 giảng viên không có text ở bất kỳ trường nào kể trên. Đây là thống kê trường text, không phủ nhận thông tin định danh hoặc các nguồn khác vẫn tồn tại. CSV và JSON có cùng tập advisor ID.
- Backend đang đọc `data/curated/quality_report_v2.json`; báo cáo này không có hash file đầu vào, nên không chứng minh được freshness chỉ từ tên hoặc thời gian sửa file.
- Tuy nhiên các chỉ số 220/38, quota trống toàn bộ và thiếu `skill_text` 8/38 của báo cáo khớp với dữ liệu đã kiểm tra. Chưa có bằng chứng rằng báo cáo đang sai riêng ở phần quota.

Đủ dữ liệu sinh viên/giảng viên để làm nghiên cứu không đồng nghĩa có quota chính thức. Nếu thiết kế bài toán dùng quota chia đều thì quota thiếu trong hồ sơ không cần chặn readiness cho nghiên cứu; phải ghi rõ chính sách này thay vì điền số giả thành quota chính thức.

## Vì sao các báo cáo cho kết quả khác nhau?

| Báo cáo | Ý nghĩa và hạn chế |
|---|---|
| `data/curated/curation_report.json` | 220 nguồn đã extract, pending=0, `ready_for_full_experiment=true`: hoàn thành extraction/curation theo tiêu chí của báo cáo |
| `data/curated/quality_report_v2.json` | Structural audit, `ready=false`; có thống kê null quota/skill nhưng không có danh sách lý do đủ chi tiết để suy ra chính xác nguyên nhân tạo cờ false |
| `outputs/data_quality/v2026-09-28/quality_report.json` | `ready=true` cho tập con 215 đề tài, 38 giảng viên, 36 assignments; vẫn `complete_dataset=false`, loại 5 bản ghi |

`scripts/build_curated_dataset.py` tạo báo cáo thứ ba, không cập nhật báo cáo v2 mà web đọc. Validator của nhánh này kiểm tra ID, evidence, propagation và leakage; không kiểm quota hay chứng minh chất lượng semantic. Không lấy `ready=true` của tập con ghi đè báo cáo snapshot 220 đề tài.

## Các file giữ và xoá

Xoá 27 file `data/cache/fit/research/*.js`: đây là bundle/chunk JavaScript của website nguồn, không phải code ứng dụng trong repo. Không tìm thấy caller ngoài data/outputs dùng các file này. Giữ HTML, JSON và RSC đã lưu để không mất nội dung crawl.

Giữ các nhóm sau:

| Nhóm | Lý do |
|---|---|
| `data/1.pdfs` | Nguồn gốc để đối chiếu và extract lại |
| `data/raw` | Crawl snapshots/fetch events, provenance |
| `data/extracted` | Evidence, kết quả extraction; builder version vẫn dùng `extracted/llm` |
| `data/curated` | Dữ liệu phục vụ, nguồn/evidence, CSV dùng bởi crawler/builder, snapshot version |
| `data/features` | V2 đang phục vụ; ma trận/manifest cũ là artifact lịch sử, không mặc định là bản trùng |
| `data/embeddings` | Artifact phương pháp dense để đối chiếu/tái lập; chưa dùng trong serving TF-IDF hiện tại |
| Cache Hugging Face | Model local cho tái lập embeddings/offline; không cần runtime web nhưng xoá sẽ mất khả năng dựng lại không cần tải |

Không dùng tiêu chí “web hiện không đọc” để xoá nguồn và artifact thí nghiệm. Một file có thể cần cho audit/rebuild dù không cần inference. Chưa thấy file tạm/log/pyc cần dọn trong data ở lượt kiểm tra này.

Danh sách file, dung lượng, SHA-256 trước dọn và danh sách xoá nằm trong `outputs/data_cleanup/2026-10-08/audit_before_cleanup.json`; kết quả xoá/kiểm tra sau dọn nằm trong cùng thư mục. Hash được giữ để xác định chính xác artifact, không phải bản backup nội dung file đã xoá.

## Hướng dẫn triển khai report mới sau review

### 1. Chốt scope readiness

Tách ít nhất hai trạng thái:

- `research_ready`: snapshot hợp lệ để chạy giao thức nghiên cứu với capacity policy được khai báo rõ.
- `operational_ready`: có quota chính thức, hồ sơ đã review và các điều kiện cần cho phân công vận hành.

Tách thêm `model_evaluation_ready` hoặc trạng thái model trong registry; dữ liệu hợp lệ không chứng minh checkpoint đạt chất lượng. Không biến một cờ `ready` thành khẳng định tất cả các điều kiện này.

Với quota chia đều: ghi `capacity_policy=uniform-ceiling-experimental-v1`, `official_quota_available=false`; kiểm tra capacity tính ra hợp lệ cho từng split. Chỉ dùng quota thật cho vận hành khi có nguồn và phạm vi học kỳ tương ứng.

### 2. Audit đúng input của serving

Report phải được sinh từ `theses.json`, `advisors.json`, `split_indices.json`, `feature_manifest_v2.json`, `compatibility_matrix_v2.npy` đang được backend nạp. CSV kiểm như một bản xuất/phụ thuộc pipeline và ghi lỗi khi khác JSON ở các trường cần đồng nhất.

Các gate tối thiểu:

1. File đọc được, schema và ID hợp lệ; không trùng ID; quan hệ sinh viên–giảng viên không trỏ tới ID không tồn tại.
2. Số hàng/cột, thứ tự ID, hash dataset/split/features khớp contract. Split không chồng lấn; preprocessing chỉ fit dữ liệu được phép.
3. Ma trận finite và trong miền giá trị của phương pháp được khai báo.
4. Hồ sơ có đúng phần text serving sử dụng; thống kê riêng kỹ năng gốc và suy diễn. Không coi kỹ năng suy diễn là bằng chứng trực tiếp.
5. Evidence và nguồn kiểm chứng được; `needs_review` được xử lý hoặc nêu giới hạn theo giao thức nghiên cứu. Không âm thầm bỏ record để đạt ready.
6. Capacity policy hợp lệ; kiểm quota chính thức là gate vận hành, không tự động áp cho mọi nghiên cứu.

### 3. Gắn freshness vào report

Schema đề xuất gồm: `schema_version`, `generated_at`, `validator_version`, `scope`, `input_files` với SHA-256, `counts`, `checks`, `blocking_reasons`, `warnings`, `research_ready`, `operational_ready`, `capacity_policy`.

Khi web đọc report: tính lại hash đầu vào và đối chiếu. Sai hash trả trạng thái `stale`/`unverified`; report thiếu hoặc lỗi cũng không coi là ready. Báo rõ gate nào fail và gate nào chỉ cảnh báo.

Giữ tương thích hoặc chuyển đồng bộ caller: `MatchingService.catalog()` hiện chỉ lấy `quality.ready`; health cũng dựa trên quality. Không thêm schema mới rồi để UI tiếp tục giải thích cờ cũ theo nghĩa khác.

### 4. Cách sinh và kiểm tra report

Chưa có một lệnh hiện tại đã xác nhận sinh report v2 cho snapshot serving. Cần thêm validator nhỏ tái sử dụng contract đang có; chạy read-only trên snapshot, ghi report ra file tạm, kiểm tra rồi thay report đích một cách atomic. Không cần tái crawl/extract/train chỉ để cập nhật báo cáo.

Không chạy `build_features.py` cho tác vụ report: script này ghi lại split và features. Không chạy `build_curated_dataset.py` chỉ để “sửa ready”: nó tạo snapshot subset và báo cáo khác phạm vi.

Kiểm tra cần có khi triển khai: input hợp lệ cho research; quota giả định không được nhận thành quota chính thức; thay một input làm report stale; ID/shape/hash sai bị chặn; subset không được nhận thành full snapshot; report lỗi không chuyển thành ready.

### 5. Rollout

1. Lưu báo cáo v2 hiện tại làm evidence lịch sử ngoài input phục vụ.
2. Sinh report mới đúng snapshot và hiển thị đầy đủ lý do/cảnh báo để review.
3. Cập nhật backend/UI để phân biệt research, operational và stale.
4. Kiểm tra health/catalog trên web với cùng snapshot; xác nhận không thay kết quả phân công do tác vụ report.

Chưa triển khai các thay đổi validator/backend/UI nói trên trong lượt này. Đã dọn cache được xác định dư và ghi evidence audit; phần report mới là hướng dẫn để review.
