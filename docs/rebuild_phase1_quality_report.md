# UniMatch — Báo cáo chất lượng Phase 1

Ngày kiểm chứng: **21/10/2026**, múi giờ Asia/Saigon. **VERIFIED — đạt Gate P1 về bảo toàn nguồn và provenance; được chuyển Phase 2.**

Các số liệu dưới đây thuộc lần chạy cuối `20261021T154719Z-b40d7836`, đọc từ `data_rebuild/v1/reports/phase1_gate.json` và artifacts trong namespace của chính phiên chạy. Gate ghi nhận `code_unchanged_during_run=true`; kiểm tra PDF độc lập đã đối soát lại phiên này. Kết quả không phải chứng nhận accuracy, duyệt gold hoặc chấp thuận phân bổ chính thức.

## Phạm vi và điều kiện đầu vào

Phase 0 đã nghiệm thu **220 nguồn gốc: 208 PDF + 8 DOCX + 4 RAR**, một INI hệ thống được kiểm kê riêng và loại khỏi số nguồn. SHA256 inventory được chấp nhận: `030b5d101c8a9caa5666d5c70a2cadc6d6b1a05386117eab527224ef9a4090fb`.

Phase 1 trích xuất text theo trang PDF, đoạn/bảng Word, kiểm kê archive members và tạo hồ sơ ứng viên kèm bằng chứng. Trang ít text chỉ được OCR khi có dấu hiệu nội dung ảnh phù hợp; trang trắng và nội dung đồ họa chưa hiểu được có trạng thái riêng. Từ khóa công nghệ chỉ là nội dung luận văn có bằng chứng; không được chuyển thành kỹ năng hoặc điểm thành thạo cá nhân.

Không sửa website đang phục vụ, không train model, không tạo quota, nguyện vọng hoặc nhãn kết quả học kỳ.

## Kết quả lần chạy đã kiểm chứng

| Chỉ số | Kết quả |
|---|---:|
| Nguồn gốc được đối soát | 220/220 |
| Source records gồm nguồn dẫn xuất | 227 |
| Source records `extracted` / `quarantined` | 133 / 94 |
| Hồ sơ ứng viên | 220 |
| Lỗi kiểm tra bằng chứng | 0 |
| Trang có text trích xuất | 18.105 |
| Trang trắng | 26 |
| Trang quarantine | 94 |
| Trang đã thử OCR | 345 |
| Archive members được kiểm kê | 2.129 |
| Members được trích xuất / quarantine / thư mục | 7 / 1.589 / 533 |
| Hồ sơ được con người phê duyệt | **0** |
| Số sinh viên duy nhất | **Chưa xác định** |

Hai tổng bảo toàn: **220 nguồn gốc + 7 tài liệu dẫn xuất = 227 source records**; **7 extracted + 1.589 quarantined + 533 directory = 2.129 archive members**. Số source record hoặc candidate không được coi là số sinh viên duy nhất.

Trong manifest, 1.589 members quarantine có lý do `unsupported_format`; các file đó được ghi nhận, không bị loại im lặng. Chưa coi source code hoặc file phụ trợ trong archive là tài liệu luận văn. Archive và tài liệu dẫn xuất giữ source hash, đường dẫn member, member hash khi đã trích xuất và parser/version.

94 trang quarantine có lý do `low_text_image_requires_review`. Đây là các trang dưới 50 ký tự embedded text, có diện tích hợp ảnh từ 10% đến dưới 30%; không coi số trang hoặc footer đơn lẻ là nội dung hoàn chỉnh. Trang dưới 50 ký tự với hợp ảnh từ 30% được thử OCR; phép hợp hình chữ nhật tránh cộng trùng logo/layer. Mốc này đã sửa sau khi phát hiện bìa luận văn nằm trong ảnh báo cáo tương đồng chỉ chiếm khoảng 46,34% trang.

345/345 lần thử OCR cho ra text và lưu phiên bản engine cùng hash mô hình `vie+eng`; số này không xác nhận OCR chính xác 100%. Tất cả 18.003 trang của 208 PDF gốc được bảo toàn, thêm 222 trang từ ba PDF dẫn xuất, tổng 18.225 outcomes. Kiểm tra độc lập không phát hiện trang lặp, block ID lặp, source reference sai hoặc sự kiện nguồn thay đổi khi trích xuất.

## Độ phủ trường

Mẫu số là **220 hồ sơ ứng viên**, chưa phải tập hồ sơ duy nhất hoặc được duyệt.

| Trường | Có giá trị | Tỷ lệ |
|---|---:|---:|
| `student_id` | 219 | 99,55% |
| `student_name` | 220 | 100% |
| `thesis_title` | 212 | 96,36% |
| `thesis_abstract` | 5 | 2,27% |
| `thesis_keywords` | 3 | 1,36% |

Độ phủ không phải accuracy. Một giá trị tên có thể chỉ là ký tự zero-width hoặc parser đọc nhầm nhãn "sinh viên"; audit ngữ nghĩa phải phát hiện dù trường không rỗng và evidence trỏ đúng source. Đặc biệt, abstract/keywords có độ phủ thấp: có thể tài liệu không có nhãn rõ hoặc parser chưa nhận diện được. Cần kiểm tra nguồn thực để tách thiếu ở nguồn với thiếu do parser; không diễn giải ô thiếu thành nội dung hoặc năng lực bằng không. Các giá trị chỉ xuất hiện dưới dạng candidate, chưa được dùng để tạo gold hoặc train.

## Kiểm tra và sửa lỗi qua review độc lập

Các sửa lỗi dưới đây đã được triển khai sau review, có hồi quy và lần chạy cuối đã đối soát:

- Ràng buộc inventory với SHA256 và số nguồn được Phase 0 chấp nhận; chặn inventory rỗng, đường dẫn trùng hoặc thay đổi danh sách nguồn.
- So khớp toàn bộ metadata bằng chứng với block gốc: source ID, file/hash, locator/trang, archive chain, phương pháp và phiên bản parser; phát hiện block ID xung đột.
- Tìm ID có nhãn trên toàn tài liệu để phát hiện khả năng nhiều luận văn; quarantine trường hợp nhiều danh tính. Không tự gán chung tên/tiêu đề cho các ID khác nhau.
- Số tám chữ số không có nhãn chỉ là `observed_cover_number`; yêu cầu kiểm duyệt danh tính, không coi là ID đã xác minh.
- Xử lý tiêu đề nhiều dòng với ranh giới metadata; kiểm thử trường hợp mất một phần tiêu đề.
- Quarantine danh tính/nguồn trùng chưa được giải quyết, đồng bộ trạng thái source; gợi ý tiêu đề gần trùng được đưa vào review queue.
- Khóa hash mã nguồn trước/sau chạy để tránh gán nhầm phiên bản code khi tiến trình đang trích xuất.
- Đối soát số trang PDF gốc và tính duy nhất block ID toàn phiên chạy, bên cạnh kiểm tra source count và evidence.

Vòng kiểm tra mới nhất cho bốn module Phase 1 (`test_pdf_extract`, `test_document_sources`, `test_student_candidates`, `test_source_rebuild`): **34 tests passed**. Trong đó 12 test PDF bao gồm Unicode, OCR tiếng Việt thực, ảnh scan bị thu nhỏ còn 46%, ảnh chồng lấp, footer trên trang ít text, mã hóa, file hỏng và thay đổi hash nguồn. Đây là kết quả của nhóm kiểm thử được nêu, không phải tuyên bố toàn bộ hệ thống đã pass. Manifest giữ nguyên hash mã thực sự dùng trong từng phiên chạy; không gán hash bản vá mới cho artifacts cũ.

Audit cơ học Unicode trên corpus cuối ghi nhận ký tự replacement ở 26 trang, ký tự điều khiển ở 88 trang, private-use glyph ở 1.315 trang và text chưa NFC ở 803 trang. Đây là cảnh báo kiểm duyệt, có thể liên quan font toán học hoặc Unicode tương đương; chưa có nhãn để kết luận thành tỷ lệ lỗi. Confidence OCR giữ `null`.

## Artifacts riêng tư

Mỗi phiên có namespace riêng `data_rebuild/v1/phase1_runs/<run_id>/`; dữ liệu text và tên sinh viên không đưa lên Git. Các file ở `data_rebuild/v1/bronze/` và `reports/` chỉ là bản latest có tham chiếu phiên nguồn.

- `bronze/pdf_pages.jsonl`, `document_blocks.jsonl`, `page_outcomes.jsonl`: text/bằng chứng theo trang hoặc cấu trúc và trạng thái từng trang.
- `bronze/student_candidates.jsonl`: ứng viên, evidence, trường còn thiếu và yêu cầu kiểm duyệt; không có record tự động approved.
- `reports/source_extraction_quality.csv`, `pdf_extraction_quality.csv`: kết quả nguồn gốc và dẫn xuất.
- `reports/archive_member_manifest.csv`: member được trích xuất, thư mục và lý do quarantine/failure.
- `reports/review_queue.csv`, `near_duplicate_candidates.json`: trường hợp mơ hồ hoặc cần đọc lại.
- `reports/source_to_entity_mapping.csv`, `pdf_to_entity_mapping.csv`: đối soát nguồn với candidate; chưa xác nhận entity uniqueness.
- `reports/evidence_errors.json`, `phase1_gate.json` và `manifest.json`: lỗi bằng chứng, quyết định gate và checksum artifacts/code/input.
- `data_rebuild/v1/reports/pdf_reader_audit-20261021T154719Z-b40d7836.json`: audit PDF độc lập gắn với phiên cuối; các audit phiên trước được giữ riêng.

## Điều kiện nghiệm thu cuối và kiểm duyệt người dùng

| Điều kiện | Trạng thái |
|---|---|
| Inventory giữ đúng 220 nguồn đã nghiệm thu P0, checksum khớp | Đạt |
| Mọi nguồn gốc/tài liệu dẫn xuất có kết quả explicit | Đạt: 227 source records |
| Mọi archive member có trạng thái/lý do và chain nguồn | Đạt: 2.129 members |
| Mọi trường có dữ liệu có evidence trỏ đúng block/nguồn | Đạt: 0 evidence errors |
| Trang PDF và block IDs được đối soát, không loại im lặng | Đạt theo gate và kiểm tra artifacts |
| Test hồi quy và code/artifact/input hashes nhất quán | Đạt cho nhóm Phase 1 đã nêu; runtime hash không đổi trong phiên cuối |
| Precision/accuracy trường trên golden sample thực | **Chưa có nhãn kiểm duyệt** |
| Hồ sơ gold được con người approved | **Chưa có; không tự phê duyệt** |

Gate P1 kiểm tra **bảo toàn nguồn, truy xuất bằng chứng và hiển thị trường hợp chưa xử lý**, không chứng nhận mọi candidate đã đúng. Các điều kiện P1 đã đạt; được chuyển Phase 2 thu thập giảng viên. Việc xuất gold ở Phase 3 vẫn phải chờ duyệt record và các điều kiện schema/provenance; không đổi `needs_review` thành `approved` tự động.

Gói mẫu hiện hành là `data_rebuild/v1/review/sample-20261021T154719Z-b40d7836/`, gồm `sample.csv`, `evidence.md` và `manifest.json`: **14 tài liệu, 84 dòng kiểm trường**, khóa hash candidate artifact của phiên cuối. Gói giữ `pending_owner_review`, số nhãn con người bằng 0. Đây là mẫu chẩn đoán theo nhóm, không phải mẫu ngẫu nhiên đại diện accuracy toàn corpus. Gói mẫu của phiên cũ được giữ như lịch sử và không dùng thay bằng chứng phiên cuối.

Người dùng đã yêu cầu agent audit toàn bộ record trước khi chủ sở hữu duyệt báo cáo bằng chứng. Audit agent và các đề xuất sửa được lưu riêng dưới `data_rebuild/v1/review/full_audit/`, ràng buộc hash từng record của snapshot Phase 3; chúng không phải nhãn hoặc quyết định phê duyệt của con người. Nhóm 73 hồ sơ đầu được review text ngữ nghĩa đã phát hiện tên zero-width/nhãn metadata, title thiếu hoặc lẫn ngày/trang bìa, và ID mâu thuẫn dù tất cả liên kết evidence vẫn hợp lệ. Các lỗi phải được giải quyết hoặc giữ quarantine trước gold.

**Trước nghiệm thu Phase 3 và phát hành gold cho feature/training, chủ sở hữu cần duyệt các record được nhận và xử lý trường hợp mâu thuẫn**; việc xây validator, công cụ review và import có thể tiến hành sau Gate P2. Học kỳ thí điểm dùng dữ liệu thực và policy do chủ sở hữu xác nhận: chọn giảng viên tham gia trên frontend rồi chia quota đều trên tập đã chọn. Cần lưu lựa chọn và phiên bản policy cho mỗi lần phân bổ; hồ sơ luận văn quá khứ không tự trở thành hồ sơ đăng ký kỳ mới.

Người kiểm duyệt đối chiếu ID/tên/tiêu đề/abstract và nguồn trích dẫn, ghi giá trị đúng, sai, thiếu hoặc không xác định. Báo cáo precision/accuracy theo trường chỉ được tính sau khi có nhãn này; chưa tự đặt ngưỡng độ chính xác khi chưa có dữ liệu chuẩn.
