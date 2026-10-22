# Phase 8 — trợ lý chỉ đọc, trích dẫn và nghiệm thu local

Ngày địa phương: 23/10/2026. Phạm vi: `owner_authorized_local_release`, theo `rebuild_scope_20261023.md`.

## Kết quả

P6 local và P7 local đã đạt trước khi kích hoạt P8. Đã bổ sung entrypoint `backend.app.rebuild_assistant_api:app` và bật **Tra cứu có nguồn** trên `/rebuild.html`. Launcher tự chọn entrypoint này khi gate P8 verified. Các endpoint matching P7 được giữ lại; knowledge base lỗi chỉ khóa trợ lý.

**399 tests đạt**, full suite 53,16 giây, hai warning deprecation Gymnasium. Frontend syntax/build, Python compile và `git diff --check` đạt. Workflow CI đã cập nhật theo dependency/source hiện có; chưa chạy GitHub Actions từ xa. Đây là nghiệm thu local, chưa triển khai cloud hoặc phê duyệt phân công học vụ.

## Thiết kế và nguồn

- Công cụ `search_advisor_profiles`, `get_advisor_evidence`, `match_topic_to_advisors`, `explain_assignment` là hàm deterministic chỉ đọc. Không gọi LLM, external network hoặc training. UI ghi rõ cơ chế này.
- Knowledge base gồm đúng 35 giảng viên đã duyệt, ràng buộc P3 gold/silver/manifest với SHA, URL và advisor ID/name. Ba hồ sơ quarantine bị loại, kể cả lookup trực tiếp.
- Chỉ dẫn trường research/teaching/profile_intro có evidence khớp nguyên văn và locator; trích tối đa 20 từ mỗi passage. Citation chứa URL, thời gian crawl, SHA, field/index/span, attribution và phạm vi. Đây là bản nguồn đã lưu, không phải xác minh live mới.
- `evidence_confidence` lấy nguyên `expertise_confidence` trong approved gold hoặc `null`. Ý nghĩa là tỷ lệ bằng chứng hợp lệ theo rubric đã duyệt, không phải trình độ hoặc xác suất hướng dẫn thành công.
- Điểm chủ đề dùng frozen E4. Query expansion chỉ nối alias có sẵn của concept xuất hiện trực tiếp theo taxonomy đã duyệt. API trả original/expanded query, alias, concept, policy và taxonomy version để truy vết. Không tạo skill, không sửa gold, không fit vocabulary/IDF, không đổi P4/PPO/DQN/state.
- NLP/Computer vision tiếng Anh và mô tả tiếng Việt đều có kết quả có nguồn. `ai/ml` viết thường không tự kích hoạt alias AI/ML phân biệt hoa thường; AI/ML viết hoa chỉ mở rộng concept trực tiếp, không suy diễn phân cấp sang NLP/CV. Câu không đủ overlap trả chưa biết.
- Khi query chứa concept trực tiếp, passage hiển thị phải chứa ít nhất một concept đó. Chọn window tối đa 20 từ quanh literal mention, giữ exact offsets; concept ở sau từ thứ 20 của field vẫn được trích đúng. Profile chỉ trùng từ chung về máy tính/đồ thị bị loại sau E4; không thay điểm hoặc thứ tự tương đối của các profile còn lại. CV hiện có hai kết quả có nguồn, NLP năm ở top-K=5; không điền thêm để đủ K.
- Có roster thì giới hạn theo roster; chưa chọn roster thì tra cứu toàn bộ 35 profile công khai. Đây không phải xác nhận giảng viên tham gia kỳ này. Xếp hạng chủ đề không áp quota toàn cohort.

## Kiểm chứng

| Phép kiểm | Kết quả |
|---|---|
| Audit độc lập trên nguồn thật | 27 truy vấn thường và hai truy vấn scoped, 35 profile có evidence an toàn |
| Đúng nguồn/locator/span/SHA/URL/thời gian | 92 lượt kiểm tra đạt, 59 span duy nhất |
| Confidence đúng approved catalog | 92 lượt đạt |
| Concept trong snippet hiển thị | 45 lượt đạt; 18 window bắt đầu sau vị trí 0 |
| Điểm xếp hạng | 53 hàng khớp chính xác frozen E4 trên expanded query |
| Alias hợp lệ | 17 lượt kiểm tra; English NLP/CV không rỗng; AI/ML không suy diễn hierarchy |
| Roster giới hạn | Trường hợp có kết quả thực, score/citation đúng profile đã chọn |
| Không phát sinh side effect | 0 external network/training attempts; encoder/runtime files không đổi |
| HTTP thực tế | 9 truy vấn, 16 citation khớp span gốc; snippet có concept khi query nhận diện concept; unauthorized bị từ chối |
| Giải thích cặp | Chỉ cohort được phép và duy nhất sinh viên/giảng viên; `assignment_verified=false` |
| Chrome | Truy vấn tiếng Anh trả danh sách có URL; mở được crawl date/SHA; capacity thiếu trả unknown; disclosure hiển thị |

Độ trễ audit độc lập bản cuối sau khởi tạo: median 0,744 giây, p95 0,813 giây, max 0,890 giây; startup khoảng 10,52 giây trong phép đo có tải local đó. Đây là chi phí local trên query set nhỏ, không phải SLA hoặc semantic accuracy. Chỉ dùng bản cuối cho số đo hiện hành; revision trước có chi phí khác khi chưa lọc snippet theo concept.

Token/loopback/origin/scoped cohort vẫn qua bảo vệ P7. API giới hạn body 32 KiB, câu hỏi 4.000 ký tự, top-K 1–10 và allowlist argument. Prompt injection, bí mật, liên hệ/danh sách sinh viên, nguồn có chỉ dẫn nguy hiểm không được thực thi/xuất. Không mở quyền đọc file tùy ý. Test bao gồm knowledge-base failure không phá matching.

## Bằng chứng và gate

Private artifacts không đưa vào Git:

- `data_rebuild/v1/reports/phase8_independent_pdf_extract_v3.json`: audit độc lập cuối, source/code/taxonomy/encoder SHA và chi tiết kết quả.
- `data_rebuild/v1/local_release_audit/phase8_native_http_validation_v3.json`: API thực tế trên checkpoint và nguồn đã duyệt.
- `data_rebuild/v1/local_release_audit/phase8_browser_qa.json`, `ui_phase8_desktop_v3.jpg`: kiểm chứng Chrome.
- `data_rebuild/v1/reports/phase8_local_gate.json`: gate local tham chiếu gate P7 và evidence bằng SHA.

Các report revision đầu được giữ để truy vết lỗi English-query, sửa alias và lọc passage thiếu concept. Không sửa số đo cũ thành số đo mới. Báo cáo P6 partial lịch sử vẫn đúng trong phạm vi temporal ban đầu; kết luận hiện hành nằm trong gate P6 local và `rebuild_rl_convergence_quality_report.md`.

Điều kiện nghiệm thu P8 local đã đạt: registry/source đúng, citation đúng span, score đúng matching function, query expansion truy vết được, unknown/refusal đúng ca kiểm tra, privacy/injection và latency có bằng chứng. Chưa có bộ relevance/outcome độc lập cho truy vấn mới để tuyên bố precision/accuracy tổng quát, mức hài lòng hoặc hội tụ hoàn toàn. Agent audit không thay cho nhãn chuyên gia mới.

Concept gate dùng điều kiện có ít nhất một concept trực tiếp chung với query; nó không chứng nhận hồ sơ đáp ứng mọi concept trong một câu hỏi nhiều chủ đề. Named-profile retrieval giữ whitelist trường nguồn an toàn; chỉ topic ranking áp concept gate. Hai truy vấn scoped dùng một fixture sinh viên QA được đánh dấu rõ, ngoài gold/training; không phải bằng chứng phân công thật.

Runbook: `docs/rebuild_local_runbook.md`. PPO 32.768/DQN 24.576 là checkpoint nghiên cứu dùng trong comparison local; Hungarian vẫn có objective cao hơn trên validation. Chưa promote model hoặc tự gửi phân công chính thức.
