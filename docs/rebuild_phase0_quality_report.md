# UniMatch — Báo cáo nghiệm thu Phase 0

Ngày kiểm chứng: **21/10/2026**, múi giờ Asia/Saigon. Trạng thái: **VERIFIED — được chuyển Phase 1** theo định nghĩa nguồn đã được chủ sở hữu xác nhận và cập nhật trong PRD.

Đã đọc đầy đủ ba tài liệu PRD, RL Spec và Feature Data Dictionary. Thứ tự phase lấy từ PRD; roadmap cũ trong RL Spec không thay thế thứ tự này.

## Kết quả nguồn dữ liệu

| Hạng mục | Kết quả kiểm chứng |
|---|---|
| Tổng nguồn yêu cầu / thực tế | **220 / 220** |
| Phân loại nguồn | **208 PDF + 8 DOCX + 4 RAR** |
| File hệ thống loại khỏi số nguồn | 1 INI; có hash và lý do loại |
| Tổng file / thư mục con / PDF ẩn | 221 / 0 / 0 |
| PDF parse thành công | 208/208 |
| Tổng trang | 18.003 |
| Trang dưới 50 ký tự text | 495, thuộc 185 PDF |
| Nhóm trùng SHA256 | 1; giữ nguyên mọi file |
| Số sinh viên duy nhất | Chưa xác định |

Trang ít text chỉ là ứng viên kiểm tra OCR, có thể là trang trắng. Không coi từ khóa luận văn là kỹ năng đã xác minh. Không dùng dữ liệu 215 hồ sơ cũ làm nguồn chuẩn.

Chủ sở hữu đã xác nhận **220 là tổng nguồn đa định dạng**, không phải số PDF. Vì vậy blocker thiếu 12 PDF đã được gỡ; không thay đổi dữ liệu để đáp ứng số đếm. Chưa giải nén/chuyển đổi Word và archive; đây là công việc Phase 1. Mỗi nguồn có SHA256, kích thước và định dạng. PDF đã được hash lại; số trang/text từ lần parse trước chỉ được tái sử dụng khi SHA256 hiện tại và phiên bản PyMuPDF khớp; checksum CSV cache cũng được xác minh.

## Repository và bảo vệ hệ thống

- HEAD: `1054dce0cf4bc782e47fd9fb8487781fcaee9b19`, branch `feature/task-01-to-21-completion`.
- Có 200 tracked files đã bị xóa trước tác vụ. Người dùng xác nhận giữ trạng thái và build mới theo tài liệu; không khôi phục tự động.
- Frontend kiểm tra cú pháp thành công. Local backend chưa import được `MatchingService`; suite cũ và requirements hiện thiếu. Đây là baseline hiện tại, không phải lỗi do audit mới.
- Live frontend HTTP 200; Render health sau retry HTTP 200, `healthy`, `data_loaded=true`. Đây là deployment legacy; chưa kiểm chứng end-to-end matching trong phiên này.
- Không sửa backend/frontend, không deploy, không train, không đổi database/model đang phục vụ.
- Đã tạo Git bundle và verify thành công, ZIP working files, sao lưu 221 file nguồn với đối chiếu SHA256. Bản sao cùng ổ đĩa, có read-only flag; chưa phải backup ngoài máy hoặc WORM.
- Legacy curated/features/checkpoints không còn ở local để sao lưu. PostgreSQL chưa backup: không có DATABASE_URL khả dụng, thiếu pg_dump và Docker chưa chạy. Cần giải quyết trước migration/deployment; không tự kết nối DB bằng cấu hình suy đoán.

## Nguồn giảng viên

[Danh mục giảng viên chính thức](https://fit.neu.edu.vn/lecturer) trả HTTP 200. HTML hiện chưa có detail anchors; chưa xác nhận roster đầy đủ. Đã lưu response gốc, URL, thời gian và SHA256.

[Robots](https://fit.neu.edu.vn/robots.txt) cho phép `/lecturer`, cấm `/api/` và `/admin`. Không gọi API bị cấm. [Điều khoản](https://fit.neu.edu.vn/terms) cho phép trích dẫn học tập/nghiên cứu phi thương mại có nguồn; hạn chế tái bản toàn văn và thu thập gây quá tải. Phase 2 phải xác minh đường truy cập được phép, không tự dùng roster 38 người cũ hoặc suy ra quota.

## Test và artifacts

Chạy `python -m pytest tests/rebuild/test_phase0_inventory.py -q`: **7 passed**. Test dùng file kỹ thuật tạm thời, không tạo hồ sơ giả vào nguồn thực. Word/archive fixtures kiểm tra inventory, chưa chứng minh parser Phase 1.

Bao phủ: PDF đuôi hoa/thường; nested/hidden; checksum duplicate; file hỏng; encrypted; blank/low-text; thư mục nguồn thiếu; CLI trả mã 2 khi thiếu nguồn; báo cáo có checksum; chặn output chồng lên source; tính cả Word/archive; INI có lý do loại; format lạ bị chặn; cache PDF chỉ dùng khi hash khớp.

Chạy lại inventory từ repository:

```powershell
python scripts/audit_rebuild_phase0.py
```

CLI tạo báo cáo dưới `data_rebuild/v1/reports/`, giữ nguồn nguyên trạng và lưu báo cáo cũ dưới `reports/history/<UTC timestamp>/` trước khi tạo lại. Lần chạy thực tế: **exit 0**, đủ 220 nguồn và không có source inventory failure. Exit 2 có nghĩa input gate bị chặn; nghiệm thu toàn Phase 0 còn phụ thuộc audit/protection. Cờ `scan_candidate` chỉ là heuristic. Tool cần Python và PyMuPDF; phiên này dùng Python 3.12.9, PyMuPDF 1.27.2.3.

Artifacts riêng tư, được Git ignore:

- `input_inventory.csv`: **220 dòng** nguồn, path, format, size, SHA256; PDF thêm pages, text length, encryption, low-text và parser status. Word/archive có `inventoried`, chờ Phase 1; không ghi giả số trang/text.
- `all_source_entries.csv`, `non_pdf_entries.csv`, `input_discrepancies.md`: đối soát mọi file và nhóm trùng.
- `environment_audit.md`, `environment_audit.json`, `missing_tracked_files.json`: baseline repository/dependencies/checks.
- `legacy_manifest.json`: vị trí backup, checksum, giới hạn và dữ liệu chưa backup được.
- `source_verification.json`, `health_retry.json`: kiểm chứng nguồn web/health.
- `input_quality.json`, `phase0_gate.json`, `phase0_tests.txt`: quality, quyết định gate và log test.
- `specification_manifest.json`: khóa hash ba tài liệu yêu cầu.

Không commit PDF, tên sinh viên, nội dung nguồn hoặc báo cáo chứa path định danh. Báo cáo này chỉ có số liệu tổng hợp.

## Điều kiện nghiệm thu và tiếp tục

| Điều kiện | Trạng thái |
|---|---|
| Kiểm kê/hash tất cả file nguồn, lỗi công khai trong báo cáo riêng tư | Đạt |
| Đủ 220 nguồn thuộc định dạng được chấp nhận và có hash | **Đạt: 208 PDF + 8 DOCX + 4 RAR** |
| Backup nguồn hiện có + Git verify | Đạt, giới hạn cùng ổ đĩa |
| Backup legacy offline/PostgreSQL khi có quyền truy cập | Chưa khả dụng; đã ghi lý do, chặn trước migration/deployment |
| Test inventory và bảo vệ raw khỏi Git | Đạt |
| Xác minh đầy đủ hồ sơ giảng viên | Chưa thực hiện; thuộc Phase 2 |

**Được chuyển Phase 1**: trích xuất PDF/Word và kiểm kê archive members, lưu provenance và xử lý các trường hợp mơ hồ trong review queue. Gate Phase 1 chưa được tuyên bố đạt. Không có thay đổi website, model, production database hoặc dữ liệu legacy trong Phase 0.
