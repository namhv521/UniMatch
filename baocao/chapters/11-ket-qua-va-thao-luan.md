# Chương 11. Kết quả validation và thảo luận

## 11.1. Phạm vi bằng chứng hiện hành

Kết quả chính của chương này lấy trực tiếp từ `outputs/benchmarks/current-validation.json`, được tạo ngày 15/10/2026 cho snapshot hiện hành **215 sinh viên/đề tài × 38 giảng viên**. Split gồm 154 train, 20 validation, 21 test và 20 future. Report chỉ đánh giá validation; test và future chưa được mở để chọn mô hình.

Artifact lưu hash dataset, feature, split, thứ tự giảng viên, seed và hash checkpoint. Capacity policy là `uniform-ceiling-experimental-v1`, nghĩa là mỗi giảng viên có capacity bằng `ceil(20/38)=1` trên validation. Đây là giả định thực nghiệm, không phải quota chính thức của nhà trường.

Report có **35 dòng kết quả**:

- 15 dòng baseline: Random, Greedy và Hungarian, mỗi phương pháp được ghi trên năm seed;
- 20 dòng RL sau khi chọn checkpoint có ngân sách lớn nhất cho từng cặp thuật toán–seed;
- 24 checkpoint RL đã được kiểm tra tổng cộng, gồm bốn checkpoint pilot 256 bước bị checkpoint ngân sách cao hơn cùng thuật toán–seed thay thế trong bảng chính;
- 0 checkpoint bị từ chối trong lần chạy report hiện hành.

Các kết quả 220×38 ngày 07/10 được giữ tại `baocao/archives/11-ket-qua-2026-10-07.md` như bằng chứng lịch sử. Chúng không được trộn với bảng hiện hành vì khác snapshot, split, feature và ngân sách.

## 11.2. Mức hoàn thành theo thuật toán

| Thuật toán | Loại | Seed có trong bảng chính | Ngân sách được chọn | Hoàn thành protocol 5 seed × 2M? |
|---|---|---:|---:|---|
| Random | Baseline | 5 | Không áp dụng | Có đủ 5 seed để đo biến thiên |
| Greedy | Baseline | 5 | Không áp dụng | Xác định; lặp seed để đồng nhất schema |
| Hungarian | Baseline | 5 | Không áp dụng | Xác định; lặp seed để đồng nhất schema |
| MaskablePPO | RL | 5 | 2.000.000 bước/seed | Có |
| DQN | RL | 5 | 2.000.000 bước/seed | Có |
| QR-DQN | RL | 5 | 2.000.000 bước/seed | Có |
| TRPO | RL | 3 | 2.000.000 bước/seed | Chưa, thiếu seed 789 và 1024 |
| ARS | RL | 1 | 2.464 bước, seed 42 | Chưa |
| RecurrentPPO | RL | 1 | 256 bước, seed 42 | Chưa |

Sáu thuật toán RL đều có mã huấn luyện, lưu checkpoint và inference. Tuy nhiên “đã hiện thực” không đồng nghĩa “đã hoàn thành thực nghiệm”: chỉ DQN, MaskablePPO và QR-DQN đủ năm seed ở ngân sách gate; TRPO, ARS và RecurrentPPO vẫn thiếu bằng chứng.

## 11.3. Kết quả tổng hợp của chín phương pháp

Các giá trị dưới đây là mean và population standard deviation trên số seed thực có của từng thuật toán. Invalid và fallback là số trung bình trên một episode 20 sinh viên.

| Thuật toán | Seed | Mean compatibility | Std | Invalid TB | Fallback TB | Quota violations TB |
|---|---:|---:|---:|---:|---:|---:|
| Hungarian | 5 | 0,103903 | 0,000000 | 0 | 0 | 0 |
| Greedy | 5 | 0,094018 | 0,000000 | 0 | 0 | 0 |
| RecurrentPPO | 1 | 0,090479 | 0,000000 | 19,0 | 19,0 | 0 |
| TRPO | 3 | 0,088986 | 0,001422 | 18,33 | 18,33 | 0 |
| ARS | 1 | 0,087716 | 0,000000 | 15,0 | 15,0 | 0 |
| QR-DQN | 5 | 0,072768 | 0,012180 | 11,2 | 11,2 | 0 |
| MaskablePPO | 5 | 0,062807 | 0,004676 | 0 | 0 | 0 |
| DQN | 5 | 0,060790 | 0,010018 | 5,4 | 5,4 | 0 |
| Random | 5 | 0,039226 | 0,004972 | 0 | 0 | 0 |

Mọi dòng có coverage bằng 1 và quota violations bằng 0 sau xử lý. Tuy nhiên kết quả có fallback không thể được đọc như chất lượng thuần của policy: khi policy đề xuất action không hợp lệ, benchmark chọn một advisor khả thi để hoàn tất assignment. Vì vậy RecurrentPPO, TRPO, ARS, QR-DQN và DQN đều chịu ảnh hưởng của cơ chế repair ở các mức khác nhau.

## 11.4. Diễn giải baseline

Hungarian đạt mean compatibility 0,103903 và được dùng làm mốc optimality ratio 1,0. Greedy đạt 0,094018, tương đương khoảng 90,49% Hungarian. Random đạt trung bình 0,039226 và thay đổi theo seed. Chênh lệch tuyệt đối giữa Greedy và Random là khoảng 0,054793; giữa Hungarian và Greedy là khoảng 0,009884.

Kết quả phù hợp với cách các thuật toán hoạt động. Greedy xử lý sinh viên theo thứ tự và chọn điểm cao nhất trong các advisor còn capacity, nên một lựa chọn sớm có thể làm mất phương án toàn cục tốt hơn. Hungarian mở rộng advisor thành các slot theo capacity rồi giải bài toán tối ưu tổng score trên toàn ma trận; với mục tiêu và ràng buộc hiện hành, đây là cận tham chiếu trực tiếp.

## 11.5. Vì sao load variance giống nhau

Load variance của mọi phương pháp xấp xỉ 0,249307. Đây không phải bằng chứng các thuật toán công bằng như nhau. Do validation có 20 sinh viên, 38 giảng viên và capacity 1, mọi assignment hoàn chỉnh hợp lệ luôn có 20 tải bằng 1 và 18 tải bằng 0. Trung bình tải là (20/38), nên phương sai quần thể là:

\[
\operatorname{Var}(L)
=\frac{20(1-20/38)^2+18(0-20/38)^2}{38}
=\frac{360}{1444}
\approx0{,}249307.
\]

Metric bị cố định bởi cấu trúc capacity, không phân biệt được chính sách. Đánh giá cân bằng tải có ý nghĩa cần quota thật hoặc cohort mà một số giảng viên có capacity lớn hơn 1.

## 11.6. Diễn giải kết quả RL

MaskablePPO là RL duy nhất vừa đủ năm seed × 2 triệu bước vừa có 0 invalid và 0 fallback. Action masking vì thế hoạt động đúng trên protocol validation này. Tuy nhiên mean compatibility chỉ bằng 0,062807, tương đương khoảng 60,45% Hungarian và thấp hơn Greedy; candidate thất bại `compatibility_gate_failed`.

DQN đủ năm seed × 2 triệu bước nhưng có trung bình 5,4 invalid/fallback trên 20 quyết định, tức khoảng 27% assignment chịu repair. Mean compatibility 0,060790 sau repair vẫn thấp hơn baseline; promotion thất bại cả `compatibility_gate_failed` và `invalid_or_repaired_policy`.

QR-DQN cũng đủ năm seed × 2 triệu bước nhưng có trung bình 11,2 invalid/fallback, tương đương 56% quyết định. Mean compatibility 0,072768 cao hơn DQN và MaskablePPO trong bảng RL, nhưng vẫn thấp hơn Greedy/Hungarian và phụ thuộc repair; candidate không được promote.

TRPO đạt mean 0,088986 trên ba seed full-budget. Mức này chưa thể so như kết quả năm seed hoàn chỉnh và trung bình 18,33/20 quyết định cần fallback. ARS và RecurrentPPO lần lượt đạt 0,087716 và 0,090479 trên một seed, nhưng ngân sách chỉ 2.464 và 256 bước; tỷ lệ fallback lần lượt là 15/20 và 19/20. Điểm sau repair của ba thuật toán này không phải bằng chứng policy đã học được chiến lược khả thi.

## 11.7. Promotion gate và engine được chọn

Gate yêu cầu đồng thời:

1. đúng năm seed `{42, 123, 456, 789, 1024}`, không thiếu hoặc trùng;
2. mỗi run hoàn thành tối thiểu 2.000.000 bước, đúng `curated-train` và validation contract;
3. coverage bằng 1, quota violations bằng 0;
4. invalid proposals và fallback bằng 0;
5. optimality ratio tối thiểu 0,88 so với Hungarian.

Kết quả gate:

| Thuật toán | Lý do không promote |
|---|---|
| MaskablePPO | `compatibility_gate_failed` |
| DQN | `compatibility_gate_failed`, `invalid_or_repaired_policy` |
| QR-DQN | `compatibility_gate_failed`, `invalid_or_repaired_policy` |
| TRPO | Hai lý do trên và `missing_or_duplicate_seeds` |
| ARS | Ba lý do trên và `training_budget_incomplete` |
| RecurrentPPO | Ba lý do trên và `training_budget_incomplete` |

Không candidate RL nào được promote. Report chọn **Hungarian** với lý do `No approved full-budget multi-seed RL evidence`. Đây là quyết định fail-closed theo gate, không phải tuyên bố rằng RL nói chung không phù hợp với bài toán.

## 11.8. Giới hạn feature snapshot

Snapshot hiện hành loại năm hàng khỏi snapshot 220: bốn hàng thuộc train gốc và một hàng thuộc validation gốc. Ma trận hiện hành chỉ còn 215 hàng và split được cập nhật đúng 154/20/21/20. Tuy nhiên TF-IDF vocabulary/IDF được đóng băng từ corpus train trước khi lọc; do đó bốn văn bản train đã loại vẫn có thể ảnh hưởng trọng số. Manifest ghi rõ `preprocessing_scope` và liên kết về parent feature hash.

Giới hạn này không làm thay đổi số hàng đánh giá, nhưng ngăn việc mô tả feature như đã fit hoàn toàn từ 154 hàng train hiện hành. Một thực nghiệm mới muốn loại ảnh hưởng đó phải refit feature, tạo hash/version mới và huấn luyện lại checkpoint; không được thay artifact âm thầm trong cùng protocol.

## 11.9. Trả lời các câu hỏi nghiên cứu

- **RQ1:** Artifact hiện hành có hash dataset, feature, split và mapping; validation/test không được dùng để fit lại trong report. Tuy nhiên vocabulary còn ảnh hưởng từ bốn văn bản train đã loại và hồ sơ advisor chưa chứng minh đóng băng hoàn toàn theo cutoff, nên chưa thể tuyên bố không có mọi dạng leakage.
- **RQ2:** Trên validation 20×38, Hungarian đạt compatibility cao nhất; Greedy là baseline đơn giản và mạnh, đạt khoảng 90,49% Hungarian. Load variance không phân biệt do capacity 1.
- **RQ3:** MaskablePPO chứng minh action mask loại invalid proposal trên năm seed, nhưng không đạt compatibility gate. DQN và QR-DQN đủ seed/ngân sách nhưng còn fallback; ba RL còn lại thiếu seed hoặc ngân sách. Không RL nào được promote.
- **RQ4:** Registry và benchmark lưu provenance, kiểm checkpoint 114×38, tách pilot khỏi full-budget và giữ Hungarian khi gate không đạt. FE/BE/API/database/Docker đã có mã nguồn và tài liệu triển khai; public deployment vẫn cần hạ tầng thực tế và kiểm chứng tại môi trường đích.

## 11.10. Kết luận thực nghiệm

Kết luận được phép từ artifact hiện hành là: **Hungarian là engine được chọn cho validation với ma trận TF-IDF và capacity thực nghiệm hiện có.** Sáu RL đã được hiện thực, ba thuật toán đã hoàn thành năm seed × 2 triệu bước, nhưng không candidate nào đạt đầy đủ compatibility và safety gate. Test holdout 21 hàng chưa được dùng để lựa chọn. Quota chính thức, feature refit sạch, các seed/ngân sách còn thiếu và đánh giá chuyên gia vẫn là điều kiện để nâng mức kết luận học thuật hoặc vận hành.
