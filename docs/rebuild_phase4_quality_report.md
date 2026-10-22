# UniMatch — Báo cáo chất lượng Phase 4

Ngày kiểm chứng: **22/10/2026 (Asia/Saigon)**. Trạng thái: **VERIFIED — đạt Gate P4; được phép bắt đầu Phase 5**. Website hiện hành chưa thay đổi.

Run nghiệm thu: **`20261022T115327Z-1850251a`**. Chủ sở hữu trả lời nguyên văn **“Duyệt đề xuất, giữ 6 cặp uncertain”** cho gói v2 và E4 trọng số E1=0,25; E2=0,25; E3=0,50. Receipt giữ câu hỏi/câu trả lời, thời điểm ghi nhận có timezone và hash gói/experiment/feature proposal. Không coi đây là nhãn do người dùng chấm độc lập hoặc kết quả hướng dẫn thực tế.

Run đánh giá: `20261022T072424Z-6f941e2a`. Gói duyệt riêng tư: `data_rebuild/v1/review/phase4_owner_review_v2/owner_evidence_report.md`. Gói v2 bổ sung điểm/transformer E4 hiệu chỉnh và trang nguồn; các gói trước giữ nguyên để truy xuất.

Đã xác minh hash **31 artifact của run và 9 artifact của gói owner**. SHA256 manifest run: `fe8ef86cada0a8e5b4b00ccb7d771aa37806e1d07a10940767780b8b6eab2945`; manifest gói owner: `ce54f82913374c97549acbcf1322356fb39e26d9313275d75d91a597d9dac031`; report owner: `6a3fe09b72c1c30c6ca0a3a190262620b3bd1c61e5aa1f2284f6245b89fa0169`.

## Dữ liệu, phiên bản và cách chia tập

Chỉ dùng gold approved của P3 `20261021T174552Z-fa7d91f3`: **194 sinh viên, 35 giảng viên**. Snapshot SHA256 `e76978d535daff20486ab33be1c114a501fcac0fc573fff019622a25ae1ab356`. Runner kiểm tra toàn bộ artifact của P3, CSV, trạng thái approved và hash taxonomy/allowlist/exclusions; kiểm tra lại nguồn và code trước khi đóng run. Không đọc ma trận hoặc dataset 215 hồ sơ cũ.

Chia **135 train / 29 validation / 30 test**, seed 42. Group theo source hash/alias, tiêu đề chuẩn hóa chính xác và độ tương tự tiêu đề từ 0,92; giữ group trong một split. Với snapshot hiện tại có 194 group. Thứ tự input không làm thay đổi split. Đây là **non-temporal grouped split**: chưa có nhãn học kỳ lịch sử đủ kiểm chứng để tuyên bố temporal holdout hay tổng quát hóa sang học kỳ tiếp theo.

Vocabulary/IDF chỉ fit trên text của 135 sinh viên train. Catalog giảng viên và validation chỉ transform. Danh tính của gold chỉ dùng làm registry loại tên/ID và join; không học trọng số từ danh tính, không lưu nguyên registry vào transformer. **30 test không được dùng fit, chọn feature, gán nhãn hay calibration.** Sau khi owner duyệt và lựa chọn đã đóng băng, 30 hàng này được transform trong full matrix theo PRD; vẫn chưa có relevance metric test độc lập.

## Biến thể và dữ liệu thiếu

| Biến thể | Tín hiệu thực tế | Cặp có tín hiệu / 1.015 | SV không có ứng viên | GV không có tín hiệu |
|---|---|---:|---:|---:|
| E0 | TF-IDF tiêu đề ↔ research_description đã duyệt | 870 (85,71%) | 0 | 5 |
| E1 | Tiêu đề + abstract ↔ profile kỹ thuật đã duyệt | 870 (85,71%) | 0 | 5 |
| E2 | Jaccard domain/topic với namespace chuẩn | 130 (12,81%) | 24 | 9 |
| E3 | Jaccard technology/method × căn bậc hai tích confidence nguồn | 468 (46,11%) | 3 | 17 |
| E4 | Hybrid E1/E2/E3, renormalize trên thành phần quan sát được | 870 (85,71%) | 0 | 5 |

Mỗi ma trận validation có shape **29×35**, float64, score hữu hạn [0,1], mask bool và index riêng. Số 0 chỉ là score quan sát được khi mask true; mask false luôn là unavailable. Một cặp có đủ profile nhưng không có từ/tag chung được phép có score 0, khác với thiếu profile.

Gold có **194/194 abstract trống**; riêng validation cũng 29/29 trống. Không có publication summaries được duyệt hoặc preference đã xác nhận. Vì vậy E0/E1 bằng nhau trong run này; không tuyên bố E1 đo tác dụng của abstract hay công bố. Field research_description là phần research/teaching đã được P3 duyệt; gói reviewer giữ riêng hai loại nguồn, không biến nội dung giảng dạy thành cam kết chuyên môn nghiên cứu.

Validation có domain ở 3/29 hồ sơ, topic ở 2/29, confidence kỹ năng ở 26/29. Giảng viên có research_description 30/35, domain 20/35, topic 15/35 và confidence 28/35. Confidence có dữ liệu đều bằng 1.0 theo rubric bằng chứng P3; nó chưa phân biệt mức chất lượng giữa những hồ sơ đạt kiểm tra. Không suy ra trình độ hay xác suất phù hợp từ điểm này. Proficiency và preferences tiếp tục giữ unknown.

Preprocessor loại metadata định danh, tên/ID đã biết, email, URL, điện thoại, mã dài và boilerplate. Không dùng GPA, thông tin bảo vệ, contacts, filenames hoặc raw publications/profile_text làm feature. Redaction count trên text validation/catalog hiện tại bằng 0 vì các trường đã duyệt không còn chuỗi cần loại; điều này không thay thế kiểm tra dữ liệu mới. Canary tests kiểm tra loại định danh/contact và bỏ các field ngoài allowlist. Alias kiểm tra **204/204** trường hợp đã định nghĩa; không phải bằng chứng semantic robustness ngoài taxonomy.

## Nhãn relevance và bằng chứng kiểm duyệt

Theo lựa chọn của chủ sở hữu “Agent đề xuất, tôi duyệt báo cáo bằng chứng”, hai agent đọc **270 cặp** thuộc 29 validation. Packet đóng băng `20261022T070116Z-eacaa14a` che score, variant, thứ hạng và bindings trước reviewer; candidate pool là union top-5 E0–E4 cùng 10 bộ trọng số E4 đã khai báo trước. Test không xuất hiện trong packet.

Mỗi đề xuất có reviewer, grade 0–3 hoặc uncertain, lý do, trích dẫn nguyên văn hai phía và SHA của packet. Mapper kiểm tra đủ cặp, pair hash, record/snapshot hashes, quote substring và attribution. Từ chối grade không có nguồn, packet bị sửa hoặc tự nhận owner_ratified. Trích dẫn có thật xác minh provenance; tính hợp lý về ngữ nghĩa vẫn cần người có chuyên môn duyệt.

Kiểm tra chéo độc lập **30 cặp**, mỗi agent đọc 15 cặp của phần còn lại, không xem nhãn agent khác. Đồng ý tuyệt đối **25/30 = 83,33%**; chênh lệch grade tuyệt đối trung bình **0,1667**, cả 5 bất đồng lệch một bậc. Đây là mẫu giao nhau có hệ thống, không phải mẫu ngẫu nhiên đại diện hoặc hai chuyên gia con người. Bất đồng giữ uncertain, không ép đồng thuận.

Sau kết hợp: grade 0 **15**, grade 1 **112**, grade 2 **115**, grade 3 **22**, uncertain **6**. Một uncertain từ lần chấm đầu, năm từ kiểm tra chéo. Gói gốc giữ nguyên attribution **agent_advisory**. Bản nghiệm thu giữ grade/reason/evidence gốc, thêm reviewer phê duyệt, proposal_reviewer và receipt SHA với review_kind **owner_ratified_agent_report**; sáu uncertain không bị đổi thành grade số. Không sửa file lịch sử.

## Kết quả ranking và lựa chọn đề xuất

NDCG@5 dùng IDCG từ pool đã có nhãn của từng query, không giả định biết relevance đủ 35 giảng viên. MRR@5 dùng grade ≥2 là relevant. Nếu top-5 chứa nhãn thiếu/uncertain, query đó giữ unknown và không được gán điểm 0.

| Biến thể | NDCG@5 trên query đủ nhãn | MRR@5 | Query đủ nhãn /29 |
|---|---:|---:|---:|
| E0 | 0,6076 | 0,4897 | 26 |
| E1 | 0,6076 | 0,4897 | 26 |
| E2 | 0,7148 | 0,7500 | 4 |
| E3 | 0,7070 | 0,7792 | 24 |
| E4 equal weights | 0,7195 | 0,6615 | 26 |
| E4 calibrated proposal | 0,7325 | 0,7064 | 26 |

Không chọn E2/E3 chỉ vì số trung bình cao hơn khi tập query khác nhau. So sánh trên **25 query chung** của các candidate có text backbone:

| Candidate | NDCG@5 chung | MRR@5 chung |
|---|---:|---:|
| E0/E1 | 0,6136 | 0,4893 |
| E4 equal weights | 0,7138 | 0,6480 |
| E4 calibrated proposal | **0,7274** | **0,6947** |

Chủ sở hữu đã chọn **E4, trọng số E1=0,25; E2=0,25; E3=0,50**. Calibration ban đầu thử 10 điểm grid bước 0,25, giữ trọng số text tối thiểu 0,25 như policy đã khai báo trước nhãn; E2/E3 vẫn là ablation riêng. Tất cả grid so sánh trên **23 validation query chung**, NDCG@5 của điểm chọn 0,7490, MRR@5 0,6899. Các mẫu số 23/25/26 có mục đích khác nhau và được lưu rõ; không trộn để tuyên bố cải thiện. Nghiệm thu không chạy lại fitting/calibration hoặc chọn trọng số mới.

Đây là chất lượng relevance theo đề xuất agent trên dữ liệu đã dùng calibration, có thể lạc quan. Chưa phải kết quả test độc lập, hiệu quả hướng dẫn thực tế, chứng minh tốt hơn mọi giảng viên ngoài pool hay bằng chứng đủ triển khai phân bổ thật.

## Hungarian, giải thích và artifact

Hungarian chẩn đoán chia divmod slots theo thứ tự catalog ghi trong report. Với đủ **35 profile**, các biến thể báo **infeasible** vì slots của profile thiếu tín hiệu không được ép thành score 0. Với catalog chung **30 profile có tín hiệu E0/E1/E4**, E0/E1/E4 và E4 calibrated đạt coverage 100%, 0 vi phạm slots; E2/E3 vẫn infeasible. Catalog này là tập chẩn đoán, không tự loại ai khỏi roster học kỳ. Objective chỉ so sánh trong cùng định nghĩa score; không dùng tổng score khác thang để tuyên bố một thuật toán tốt hơn.

`explain_pair` lưu từ TF-IDF chung và đóng góp tích vector, giao/hợp tag, factor confidence và đóng góp hybrid theo trọng số quan sát. Test kiểm tra các đóng góp dựng lại đúng score; report riêng tư có giải thích cho cả 270 cặp, bao gồm E4 calibrated. Đây là giải thích công thức/nguồn, không phải chứng minh quan hệ nhân quả.

Run có feature manifest, split, snapshot binding, score/mask/index, chẩn đoán từng biến thể, ranking metrics, calibration grid, packet, raw proposals, labels đã map, transformer baseline và transformer calibrated proposal. Serialization dùng JSON + NPZ với allow_pickle=False, hash và phiên bản sklearn; save/load baseline và calibrated đều khớp score/mask. Không serialize raw identity registry.

Gói owner có bản sao byte nguyên gốc của bốn file review, combined proposals, crosscheck audit, lựa chọn feature proposal, toàn bộ 270 nhận xét cùng URL/hash/trang nguồn và pair explanations. Manifest đóng băng các artifact. Dữ liệu thật giữ trong data_rebuild gitignored; không có dữ liệu riêng tư mới được tracked.

## Ma trận và contract đã nghiệm thu

Run nghiệm thu mới có **15 artifact**, giữ nguyên experiment và gói owner đã được duyệt. Transformer JSON và NPZ được sao chép nguyên byte từ **transformer_calibrated_proposal**, không dùng transformer baseline và không fit lại IDF. Hash và save/load replay được kiểm tra trước khi cập nhật gate alias bằng atomic replace.

Full matrix **194×35**, float64, index canonical ID tăng dần, mask bool cùng shape: **5.820 cặp có tín hiệu, 970 cặp unavailable**, không sinh viên nào thiếu mọi ứng viên, 5 giảng viên thiếu tín hiệu cho mọi sinh viên. Những giảng viên này vẫn có trong index; mask không phải kết luận đủ điều kiện hướng dẫn hoặc tham gia học kỳ. Không tự đổi unavailable thành điểm phù hợp 0.

29 hàng validation khớp tuyệt đối với score/mask E4 calibrated trong experiment đã duyệt. Replay transformer trên toàn bộ gold khớp score/mask đã lưu. Loader dành cho P5 kiểm tra gate/manifest, receipt, gói gốc, snapshot/config/code, weights, nguyên byte transformer, grade gốc và recompute matrix; từ chối cả trường hợp output bị đổi rồi chỉ tính lại checksum.

| Artifact | SHA256 |
|---|---|
| Manifest nghiệm thu | `e12b82cb32bc4b395568e44d4272b747b36189f1a1613b6c704b42d1dd4cf86d` |
| Feature contract | `fffb85551cf9bef510317a1b86dbf866005ead6fc439809375fc5c003d4fe637` |
| Score matrix | `7a2e4028ff760c798705ad67ab80ec863e04b4cf75537474f71d196f206f1701` |
| Availability mask | `9521ae195d2a410689df2333f54682e46a28a3ce1ee3203a7e4190d4b01d6b65` |
| Index | `41cb73ecd28f20f41390253cda55828e579548baa9e77b35d36fb06cdab965be` |
| Owner receipt | `7312a4dc1866c9ec45c0e701ff4a570e9a495e10a3daaabaae94718a898acfcf` |

Owner-ratified E4 validation metric giữ nguyên **NDCG@5 0,7325 / MRR@5 0,7064 trên 26/29 query đủ nhãn**. Đây là điểm của agent report được owner chấp nhận, không phải measurement mới hay kết quả test.

## Kiểm thử và điều kiện nghiệm thu

**207 tests passed** trong `tests/rebuild`, gồm dữ liệu nguồn P0–P3 và **80 tests Phase 4**. Fixture kỹ thuật tách biệt dữ liệu thật. Các nhóm chính: stale snapshot/config/artifact, split ổn định/group overlap, train-only vocabulary/IDF, canary PII, unknown mask, convex weights, chất lượng bằng chứng hữu hạn, serialization tamper/parity, ranking uncertainty, không nhìn test khi calibration, nhãn thiếu nguồn/giả approval, kiểm tra chéo và explanation parity. Chín test nghiệm thu bổ sung kiểm tra receipt/gói sai, weights khác phê duyệt, giữ unknown/reviewer gốc, không gọi fit, chạy lại idempotent và từ chối matrix/contract bị đổi kể cả khi rehash. CLI nghiệm thu exit 0; CLI thực nghiệm chưa phê duyệt vẫn trả blocked exit 2 theo thiết kế.

Kiểm tra độc lập đối chiếu **23 file backend/frontend** với SHA trong backup Phase 0: không khác. Không triển khai, sửa runtime website hoặc thay dữ liệu production. Các file bị xóa/sửa sẵn trong working tree đã được chủ sở hữu cho phép bỏ qua; kết quả không tuyên bố clean clone/backend local đang chạy.

| Điều kiện P4 | Trạng thái |
|---|---|
| P3 nguồn/gold/config đã duyệt và hash đúng | Đạt |
| E0–E4, missingness, alias, sparse profile, leakage, explanation, Hungarian diagnostics | Đạt kỹ thuật, có giới hạn đã ghi |
| Reviewer proposals đủ nguồn và report cụ thể cho owner | Đạt, gói gốc giữ nguyên |
| Owner ratify relevance và chọn feature contract | **Đạt, receipt theo hash; giữ 6 uncertain** |
| Ma trận đầy đủ 194×35 theo contract đã chọn, SHA/index/mask khớp snapshot | **Đạt, có replay/parity và loader fail closed** |
| Bằng chứng test độc lập hoặc tương lai học kỳ | Chưa có; không dùng thay validation |
| Gate P4 verified / được chuyển P5 | **Đạt** |

Receipt chỉ được ghi sau thông điệp phê duyệt gói cụ thể ở đầu báo cáo. Quy trình chạy lại và API loader nằm trong `rebuild_phase4_operator_guide.md`. P5 được phép bắt đầu triển khai; phân bổ học kỳ thực vẫn cần coordinator xác nhận roster, quota/policy và eligibility, không được suy ra từ catalog35 này.

## Tài liệu kỹ thuật tham chiếu

Nguyên tắc fit preprocessing trên train theo [scikit-learn common pitfalls](https://scikit-learn.org/1.8/common_pitfalls.html). Cấu hình text theo [TfidfVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html). Diagnostic tối ưu tuyến tính dùng [SciPy linear_sum_assignment](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html). Các nguồn này mô tả công cụ; không xác nhận chất lượng dữ liệu UniMatch.
