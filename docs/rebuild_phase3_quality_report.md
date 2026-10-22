# UniMatch — Báo cáo nghiệm thu Phase 3

Ngày kiểm chứng: **22/10/2026 (Asia/Saigon)**. Trạng thái: **VERIFIED — đạt Gate P3; được chuyển Phase 4**.

Run được nghiệm thu: `20261021T174552Z-fa7d91f3`. Đây là snapshot dữ liệu nguồn đã duyệt cho pilot; chưa phải kết quả phân bổ, chứng nhận năng lực hay triển khai website mới.

## Kết quả đối soát

| Nhóm | Hồ sơ canonical | Gold approved | Quarantine / chưa approved |
|---|---:|---:|---:|
| Sinh viên | 219 | **194** | **25** |
| Giảng viên | 38 | **35** | **3** |

Đầu vào là Phase 1 `20261021T154719Z-b40d7836` và Phase 2 `20261021T154610Z-9cfd4d06`, cùng inventory 220 nguồn gốc đã nghiệm thu. Không dùng dataset 215 hồ sơ làm chuẩn. Một cặp cùng byte nguồn và ID được gộp với alias/provenance giữ nguyên; không đồng nhất số file với số người đã xác minh.

Gold của cả hai nhóm vượt validator, không có `review_errors`, mọi hàng có `review_status=approved`. Mọi hồ sơ còn lại vẫn có mặt trong staging, review records và CSV quarantine. Trường thiếu, mâu thuẫn ID/bìa, font/layout hỏng, abstract từ bài báo đính kèm, vai trò nhân sự hỗ trợ chưa rõ và tag chưa đủ nghĩa không được tự điền hoặc tự hợp nhất.

## Phê duyệt và phiên bản cấu hình

Chủ sở hữu chấp nhận gói báo cáo `owner-package-20261021T162922Z-98498168` qua thông điệp “chấp nhận tất cả, bắt đầu phase3”, sau đó chấp nhận rubric tỷ lệ bằng chứng hợp lệ. Receipt lưu nguyên nội dung phê duyệt, thời điểm ghi nhận, hash manifest và phạm vi. Gói gốc cùng 32 artifact vẫn giữ nguyên; không sửa lịch sử để biến review của agent thành nhãn người dùng tự chấm.

Taxonomy gồm 12 nhóm/70 ID, cùng feature allowlist/exclusions, được phê duyệt theo hash. SHA256 taxonomy: `fdaefab78f208d497275aa6d45f8b0194b8c3b7d390e7ff26748cc01a654b679`. Các YAML gốc giữ nguyên nội dung/nhãn draft ban đầu; trạng thái được duyệt có hiệu lực nằm trong receipt, `taxonomy_approval.json` và snapshot manifest, không phải đổi nội dung đã được ký nhận bằng hash.

38 đề xuất/46 thay đổi trường từ đợt rà trước được replay và kiểm tra canonical evidence. Mỗi record sau sửa có hash riêng; approval cũ không thể áp vào nội dung khác. Sửa optional field chỉ cho loại phần bị lấy nhầm, không tạo nội dung thay thế. Sửa research/teaching của giảng viên chỉ cho lấy tập con của nội dung nguồn đã có.

## Rubric chất lượng bằng chứng

Rubric `source-span-semantic-v1` dùng **số tag vượt kiểm tra nguồn, span và ngữ nghĩa / tổng tag**. Đơn vị mẫu số là cặp CSV `(output_column, canonical_tag)` riêng biệt trong từng record; các lần xuất hiện bên dưới đều được giữ để truy xuất. Bất kỳ kiểm tra chưa rõ/chưa làm khiến điểm giữ `null`; record không có tag cũng có điểm `null`.

Đã kiểm tra **1.068 occurrences, tương ứng 1.013 tag riêng biệt: 999 đạt, 14 pending, 0 fail**. 226 record có điểm 1.0; 25 record không tag và 6 record có tag pending giữ null. Kết hợp với kiểm tra trường cốt lõi tạo ra tập gold/quarantine trong bảng trên.

Điểm 1.0 chỉ có nghĩa các kiểm tra bằng chứng trong rubric đã đạt. Nó không phải trình độ cá nhân, xác suất được calibration, xác nhận công nghệ đã triển khai hay mức phù hợp với một giảng viên. Thuật ngữ luận văn vẫn là `inferred_from_thesis`; nguồn giảng viên vẫn phân biệt teaching với research. Proficiency và preferences chưa có dữ liệu tiếp tục để trống.

## Mẫu trích xuất và giới hạn accuracy

Mẫu 14 tài liệu/84 trường được ràng buộc đúng candidate/source/hash của Phase 1. Kết luận trường cốt lõi được suy ra bảo thủ từ **báo cáo agent đã được chủ sở hữu chấp nhận** và các đề xuất sửa đã duyệt. Optional fields chưa được chấm trong báo cáo gốc giữ `uncertain`; review bổ sung chỉ có thể giữ chờ hồ sơ, không tự sinh một phê duyệt mới.

| Trường của parser trước sửa | Đúng / nhãn đủ kết luận | Accuracy trên phần có nhãn | Uncertain |
|---|---:|---:|---:|
| MSSV | 9 / 9 | 100% | 5 |
| Tên | 8 / 9 | 88,89% | 5 |
| Tiêu đề | 7 / 11 | 63,64% | 3 |
| Abstract, keywords, technology list | 0 nhãn đủ kết luận | Chưa đo | 14 mỗi trường |

Đây là mẫu chẩn đoán phân tầng của **kết quả parser trước sửa**, không phải ước lượng ngẫu nhiên accuracy toàn corpus hoặc accuracy gold. Lỗi của record được nhận phải có bản sửa nguồn hợp lệ; uncertainty cốt lõi của record được nhận chặn gate. Trường `human_golden_sample_accuracy` giữ null; các con số trên nằm trong `owner_ratified_sample_accuracy`. Không tuyên bố có nhãn do người dùng chấm trực tiếp hoặc đo OCR accuracy.

## Kiểm tra gate và truy xuất nguồn

**127 tests passed** trong `tests/rebuild`. Fixtures kỹ thuật nằm riêng, không trộn vào dữ liệu thật. Kiểm thử bao gồm CSV/schema/taxonomy theo nhóm, Unicode, archive traversal/budgets, source conservation, stale/duplicate approval, sửa không có nguồn, xóa trường bắt buộc, thiếu sample rows và uncertainty cốt lõi.

Review độc lập còn bổ sung regression từ chối receipt tùy ý, approve trái eligibility HOLD, tag sai nguồn dù đã tính lại checksum, span/evidence khác canonical và trạng thái occurrence không hợp lệ. Gate trung tâm tự kiểm tra receipt/package, hash của tất cả record, quality occurrences và quyết định được dựng lại; không chỉ tin vào CLI bên ngoài. Inputs review được đọc một lần, lưu nguyên byte và hash trong immutable run. Code không đổi trong lần chạy nghiệm thu.

Artifacts riêng tư trong run:

- `gold/students.csv`, `gold/advisors.csv`, `gold/snapshot_manifest.json` có snapshot ID.
- `silver/*_staging.csv`, `silver/*_quarantine.csv`, `silver/review_records.jsonl`, `silver/reconciliation_report.md`.
- `reports/import_validation.json`, missingness, normalization evidence, sample metrics và gate.
- `review/` giữ receipt, decisions, taxonomy approval, quality assessments, eligibility và sample được ratify.
- `manifest.json` ghi SHA256 toàn bộ artifacts. Dữ liệu riêng tư dưới `data_rebuild/` vẫn gitignored.

## Phạm vi vận hành còn lại

`pilot-next-term` là ID draft kỹ thuật, không phải mã học kỳ chính thức được suy ra từ luận văn. Hồ sơ giảng viên được duyệt không đồng nghĩa đủ điều kiện hướng dẫn, đã tham gia học kỳ hoặc có capacity. Coordinator sẽ chọn roster và áp dụng chính sách chia đều `divmod(N, M)` đã được chủ sở hữu chỉ định.

Website hiện tại và dữ liệu triển khai chưa được thay đổi. Phase 4 được phép dùng snapshot gold cho đánh giá feature; chưa được công bố assignment, train từ holdout hay suy diễn outcome/feedback còn thiếu. Cách chạy lại nằm trong `rebuild_phase3_operator_guide.md`.
