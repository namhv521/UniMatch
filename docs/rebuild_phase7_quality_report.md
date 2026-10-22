# Phase 7 — kiểm chứng tích hợp local

Ngày: 23/10/2026. Phạm vi: local CSV inference theo `rebuild_scope_20261023.md`, không phải cloud deployment.

## Kết quả

Đã có API riêng `backend.app.rebuild_api:app`, service dùng frozen P4 encoder và selected PPO 32.768/DQN 24.576, cùng trang `/rebuild.html`. Website cũ không bị chuyển entrypoint. Thay đổi compatibility tối thiểu: `backend/app/__init__.py` lazy-load legacy exports để app mới không nhập các module legacy đã bị xóa.

**375 tests pass**, hai warning Gymnasium deprecation hiện có; full suite 54,37 giây. Riêng service/API có 18 tests. Frontend syntax/build đạt. Không thêm framework UI hoặc dependency ngoài các package đã có; environment local được pin bằng `requirements-rebuild-web.txt`.

## Đã kiểm chứng

- CSV sinh viên 40 cột, UTF-8/BOM, metadata thật từ upload, unknown giữ trống, import lặp idempotent.
- Header/duplicate/formula/taxonomy/unsupported eligibility/size/row-error bounds; preference/proficiency chưa dùng được cảnh báo và lưu audit.
- Token fail-closed, localhost-only, cross-origin rejection, private cohort/run theo token scope; client từ chối gửi token tới host ngoài loopback.
- Top-K không quota tách riêng với cohort allocation; quota 3 hồ sơ/2 giảng viên là 2/1 đúng thứ tự canonical.
- Native HTTP trên ba hồ sơ QA sao chép title/tag đã duyệt, ID QA rõ ràng: PPO/DQN/Hungarian đều coverage 100%, 0 constraint violation, trace replay đúng. Đây là kiểm chứng kỹ thuật, không phải ba sinh viên mới độc lập hoặc academic accuracy.
- Native model versions/checkpoint SHA nằm trong run/trace. Không fit vocabulary/IDF, train hoặc promote model trong handler.
- Faculty CSV intake chỉ đọc: profile giống catalog tương thích; ID/feature mới báo requires_rebuild. Không đổi gold/catalog/roster/quota/model.
- Chrome: import CSV hợp lệ, lỗi header hiển thị từng dòng bằng tiếng Việt, chọn roster/confirm, ba thuật toán, top-K, next-step replay và tải CSV ba hàng đúng kết quả.
- Responsive DOM ở 390 CSS px: một cột, các control trong chiều rộng trang, nút chính 44 px; không overflow ngang toàn trang. Bảng metric có vùng cuộn riêng. Ảnh desktop đã lưu riêng tư. Driver screenshot ở viewport override có lỗi crop/blank; không dùng ảnh đó để tuyên bố mobile screenshot đạt.

CSV faculty/student giữ nguyên bytes UTF-8 hợp lệ kể cả BOM bằng TextDecoder fatal/ignoreBOM; source hash server khớp SHA file fixture. Dữ liệu sai encoding bị từ chối, không sửa nội dung âm thầm.

## Bằng chứng

Trong `data_rebuild/v1/local_release_audit/`:

- `phase7_native_http_validation.json` — auth/origin/idempotence/native matching/top-K/export.
- `phase7_faculty_http_validation.json` — intake readonly, source SHA và incompatible registry.
- `browser_download_validation.json` — file browser thực tế có ba hàng PPO; event hook download timeout nhưng file được kiểm tra độc lập.
- `ui_desktop.jpg` — bảng kết quả và assignment QA, không dùng tên/ID sinh viên thật.

Selection và 117 artifact convergence được review độc lập; xem `data_rebuild/v1/reports/convergence_independent_pdf_extract.json`.

## Điều kiện và giới hạn nghiệm thu

Gate P6 local đã verified trước khi chạy tích hợp. Các điều kiện import, checkpoint-bound inference, feasibility, trace, privacy, error state, export, build/test và runbook của **release local** đã đạt. Chưa tuyên bố cloud Vercel/Render/Neon, Docker, migration production, clean public clone có private data tự chạy, nhiều vai trò hoặc phê duyệt phân công thật đã được nghiệm thu.

Intake faculty thay đổi chưa kích hoạt profile mới vì sẽ đổi feature/action contract; phải rebuild trước khi dùng. Trợ lý ở trang P7 hiện bị khóa cho tới khi P8 có endpoint và knowledge base được kiểm chứng. Rule không biến data thiếu thành profile/feedback/approval giả.

Runbook: `docs/rebuild_local_runbook.md`. Các chức năng semester database/thu thập outcome có trong thiết kế dài hạn; theo chỉ đạo mới, thiếu dữ liệu kỳ lịch sử không chặn workflow local này.
