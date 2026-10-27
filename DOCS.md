# Báo cáo tóm tắt huấn luyện và đánh giá mô hình UniMatch

**Đối tượng đọc:** Giáo viên hướng dẫn / hội đồng theo dõi tiến độ  
**Phạm vi:** Kết quả thực nghiệm RL đang được hệ thống tham chiếu, không phải kết luận phân công học vụ chính thức.  
**Run được báo cáo:** `20261022T205827Z-16010d68`  
**Nguồn số liệu:** `data_rebuild/runtime/portable-verification/db88f3b2ebee91efdc4129699384b97657911a48379f9cba70aa57a9e0040ff5/training_report.json`

---

## 1. Tóm tắt điều hành

UniMatch thử nghiệm hai mô hình học tăng cường (RL) là **PPO** và **DQN** cho bài toán gợi ý phân công sinh viên–giảng viên dưới các ràng buộc quota và tính hợp lệ của cặp ghép. Kết quả được so sánh trên cùng một tập validation cố định với baseline **Hungarian**.

Kết luận chính tại thời điểm báo cáo:

1. Huấn luyện đã hoàn tất **10 job độc lập**: 2 thuật toán × 5 seed.
2. Mọi lần đánh giá được ghi nhận đều đạt coverage 100%, không có vi phạm ràng buộc và không có invalid action.
3. PPO và DQN có cải thiện nội bộ qua quá trình huấn luyện ở một số mốc; tuy nhiên, trên validation hiện tại, **Hungarian vẫn đạt objective và compatibility trung bình cao hơn** các checkpoint RL được chọn.
4. Cả PPO và DQN **chưa đạt plateau** theo tiêu chí đã định nghĩa trước. Do đó không có cơ sở để khẳng định mô hình đã hội tụ hoặc sẵn sàng thay thế baseline.
5. Không dùng test set để chọn checkpoint trong run này; test gồm 30 sinh viên đã được giữ lại và không được đánh giá/tune lại trong run hiện tại.

> **Cách diễn giải đúng:** các chỉ số dưới đây đo chất lượng tối ưu trên dữ liệu phân công/compatibility của thí nghiệm, **không phải độ chính xác học thuật, năng lực cá nhân, hay cam kết hướng dẫn**.

---

## 2. Dữ liệu và phạm vi thực nghiệm

| Hạng mục | Giá trị hiện tại |
|---|---:|
| Tổng số sinh viên trong snapshot | 194 |
| Số giảng viên | 35 |
| Giảng viên có feature có thể chấm điểm | 32 |
| Số feature | 78 |
| Kích thước state RL | 472 |
| Train / validation / test | 135 / 29 / 30 |
| Thuật toán train | PPO, DQN |
| Thuật toán baseline | Hungarian, Greedy, Random |
| Khởi tạo | Train from scratch |
| Test được dùng trong run hiện tại | Không |

Tập validation gồm 29 sinh viên được giữ cố định trong toàn bộ quá trình chọn checkpoint. Vì vậy, kết quả phản ánh mức độ ổn định theo seed trên **một validation cohort cố định**, chưa đo được khả năng tổng quát hóa sang cohort mới độc lập.

---

## 3. “Seed để train model” nghĩa là gì?

### 3.1. Seed là gì?

`Seed` là một số nguyên khởi tạo bộ sinh số giả ngẫu nhiên trong quá trình huấn luyện. Với RL, những yếu tố như khởi tạo trọng số mạng, thứ tự episode/sinh viên, hành vi khám phá và lấy mẫu replay buffer có thể thay đổi kết quả dù dữ liệu và hyperparameter giữ nguyên.

Nói cách khác, seed giúp trả lời câu hỏi:

> Nếu train lại cùng một thiết kế thí nghiệm nhiều lần, kết quả có ổn định hay chỉ tốt do một lần ngẫu nhiên thuận lợi?

### 3.2. Seed hiện tại

Run hiện tại dùng đủ 5 seed:

```text
42, 43, 44, 45, 46
```

Mỗi seed train độc lập từ đầu cho cả PPO và DQN. Tổng cộng:

```text
2 thuật toán × 5 seed = 10 lần train độc lập
```

Điểm hiển thị dưới dạng **mean** là trung bình của 5 lần đánh giá tương ứng 5 seed. Khoảng tin cậy 95% mô tả biến thiên quan sát được giữa 5 lần đó.

### 3.3. Vì sao checkpoint phục vụ ghi seed 42?

Checkpoint được đóng gói để phục vụ là bản của **seed 42**, nhưng seed 42 không được chọn vì có điểm đơn lẻ cao nhất. Quy tắc chọn checkpoint dùng **mean validation objective trên đủ 5 seed**, đồng thời yêu cầu:

- Tất cả đánh giá ở mốc đó an toàn/hợp lệ.
- Checkpoint seed 42 tại mốc được chọn không được kém hơn seed 42 tại mốc đối chiếu ban đầu.
- Nếu hòa điểm, ưu tiên mốc sớm hơn.

Do đó, seed 42 là checkpoint đại diện có thể tải lại/tái lập; tiêu chí chọn vẫn dựa trên kết quả 5 seed, không dựa vào một lần chạy duy nhất.

---

## 4. Mô hình được huấn luyện và các mốc đánh giá

### 4.1. Thuật toán

| Thuật toán | Vai trò |
|---|---|
| Hungarian | Baseline tối ưu hóa có ràng buộc, không cần train RL. |
| PPO | Policy optimization với action masking để không chọn action vi phạm ràng buộc. |
| DQN | Double DQN với action masking và replay buffer. |

Action masking loại bỏ các lựa chọn phân công có thể làm bài toán còn lại không khả thi, ví dụ vượt capacity hoặc làm một sinh viên sau đó không còn cặp hợp lệ.

### 4.2. Ngân sách train và mốc đánh giá

- Đánh giá định kỳ mỗi **8.192 bước** từ 8.192 đến 131.072 bước.
- Các mốc checkpoint khai báo trước: 16.384; 24.576; 32.768; 49.152; 65.536; 98.304; 131.072 bước.
- DQN giảm epsilon tuyến tính từ 1 xuống 0,05 trong 16.384 bước đầu, sau đó giữ ở 0,05.
- PPO và DQN sử dụng CPU một thread cho mỗi process trong run này.

### 4.3. Checkpoint được chọn

| Mô hình | Checkpoint phục vụ đại diện | Seed checkpoint | Lý do chọn |
|---|---:|---:|---|
| PPO | 131.072 bước | 42 | Mốc có mean validation objective an toàn cao nhất theo quy tắc chọn đã khai báo. |
| DQN | 98.304 bước | 42 | Mốc có mean validation objective an toàn cao nhất theo quy tắc chọn đã khai báo. |

Các checkpoint đều được kiểm tra load lại và replay trace trước khi được đưa vào selection manifest.

---

## 5. “Điểm trung bình đánh giá” được tính theo tiêu chí nào?

### 5.1. Objective (tiêu chí chính để chọn checkpoint)

Trên mỗi phương án phân công hợp lệ, objective được tính là tổng utility của các cặp sinh viên–giảng viên:

```text
objective = Σ(score + 0,1 × observed_preference)
```

Trong đó:

- `score`: compatibility score của cặp sinh viên–giảng viên, nằm trong [0, 1], sinh từ feature pipeline đã đóng băng.
- `observed_preference`: preference chỉ được dùng khi dữ liệu preference thực sự có mặt/được quan sát.
- Hệ số preference là `0,1`.
- Các phương án phải thỏa quota, eligibility, availability, fixed assignment (nếu có) và coverage đầy đủ.

**Mean objective** là trung bình objective qua 5 seed. Đây là tiêu chí dùng để chọn mốc checkpoint, nhưng không phải accuracy phân loại và không có đơn vị phần trăm.

### 5.2. Mean compatibility

```text
mean_compatibility = trung bình score của các cặp được phân công
```

Chỉ số này đo mức tương thích trung bình của các cặp đã chọn theo score pipeline. Nó được báo cáo riêng để dễ diễn giải hơn objective, nhưng không thay thế objective trong quy tắc chọn checkpoint.

### 5.3. Các tiêu chí an toàn bắt buộc

Một checkpoint chỉ được xem là an toàn trong quy tắc chọn nếu đồng thời đạt:

| Tiêu chí | Yêu cầu |
|---|---:|
| Coverage | 1,0 — mọi sinh viên trong validation đều được phân công |
| Constraint violations | 0 — không vi phạm ràng buộc |
| Invalid action count | 0 — policy không chọn action bị mask cấm |
| Reload trace equal | Đúng — checkpoint load lại tái lập đúng trace/kết quả |

Vì vậy, “điểm cao” một mình không đủ để checkpoint được chọn.

---

## 6. Kết quả validation hiện tại

### 6.1. So sánh tại các checkpoint được chọn

Các số liệu dưới đây là mean trên 5 seed; CI 95% là khoảng tin cậy t mô tả giữa 5 quan sát seed.

| Phương pháp | Mốc | Mean objective [CI 95%] | Mean compatibility [CI 95%] | Coverage | Vi phạm ràng buộc |
|---|---:|---:|---:|---:|---:|
| Hungarian | Không train | 6,8852 [6,8852; 6,8852] | 0,2374 [0,2374; 0,2374] | 1,0 | 0 |
| PPO | 131.072 | 4,4470 [3,6819; 5,2121] | 0,1533 [0,1270; 0,1797] | 1,0 | 0 |
| DQN | 98.304 | 4,8588 [4,1969; 5,5208] | 0,1675 [0,1447; 0,1904] | 1,0 | 0 |

Nhận xét:

- Cả PPO và DQN tạo được phương án hợp lệ theo các hard constraint trên toàn bộ validation.
- Ở snapshot hiện tại, Hungarian cao hơn PPO/DQN cả objective và mean compatibility.
- DQN có kết quả trung bình cao hơn PPO tại các checkpoint được chọn, nhưng chưa vượt Hungarian.
- Hungarian là thuật toán xác định trên input hiện tại nên lặp lại ở các seed cho cùng một giá trị; seed ở baseline chỉ phục vụ protocol so sánh thống nhất.

### 6.2. Cải thiện nội bộ so với mốc 16.384 bước

| Mô hình | Objective ban đầu → checkpoint chọn | Thay đổi objective trung bình | Mean compatibility ban đầu → checkpoint chọn | Thay đổi compatibility trung bình |
|---|---:|---:|---:|---:|
| PPO | 2,6521 → 4,4470 | +1,7949; CI delta [1,1525; 2,4373] | 0,0915 → 0,1533 | +0,0619; CI delta [0,0397; 0,0840] |
| DQN | 4,4971 → 4,8588 | +0,3617; CI delta [-0,2711; 0,9945] | 0,1551 → 0,1675 | +0,0125; CI delta [-0,0093; 0,0343] |

Diễn giải thận trọng:

- PPO cho thấy cải thiện nội bộ rõ hơn giữa mốc 16.384 và checkpoint được chọn trên validation cố định.
- Với DQN, khoảng CI của delta bao gồm 0; dữ liệu 5 seed hiện tại chưa đủ để khẳng định cải thiện ổn định theo delta này.
- Cải thiện nội bộ so với checkpoint đầu không đồng nghĩa vượt Hungarian hoặc tổng quát hóa sang cohort khác.

---

## 7. Kiểm tra plateau/hội tụ

Plateau được kiểm tra mô tả trên 3 evaluation hoàn chỉnh/an toàn cuối cùng: 114.688, 122.880 và 131.072 bước. Tiêu chí đặt trước là range của mean compatibility không vượt quá `0,005`.

| Mô hình | Mean compatibility ở 3 mốc cuối | Range | Ngưỡng | Kết luận |
|---|---|---:|---:|---|
| PPO | 0,1610; 0,1497; 0,1533 | 0,0113 | ≤ 0,005 | Chưa plateau |
| DQN | 0,1607; 0,1716; 0,1663 | 0,0109 | ≤ 0,005 | Chưa plateau |

Không có early stopping dựa trên plateau. Kết luận “chưa plateau” không đồng nghĩa mô hình chắc chắn sẽ tốt hơn nếu train thêm; nó chỉ cho biết trong ngân sách đã thử, đường đánh giá cuối vẫn dao động vượt ngưỡng mô tả đã đặt.

---

## 8. Các kiểm tra đã đạt trong run

| Kiểm tra | Trạng thái |
|---|---|
| 10 job train hoàn thành | Đạt |
| 160 điểm trên dense curve | Đạt |
| Toàn bộ allocation hợp lệ | Đạt |
| Checkpoint được load/replay lại | Đạt |
| Trọng số thay đổi sau train | Đạt |
| Tách train và holdout | Đạt |
| Không dùng test trong run | Đạt |
| Mã nguồn và nguồn dữ liệu không đổi trong run | Đạt |

Các kiểm tra trên bảo đảm tính toàn vẹn kỹ thuật của thí nghiệm; chúng **không tự động chứng minh** chất lượng phân công ngoài dữ liệu validation.

---

## 9. Hạn chế khoa học và cách trình bày kết quả

1. Validation chỉ gồm 29 sinh viên và được giữ cố định; 5 seed không thay thế cho đánh giá trên cohort độc lập mới.
2. Test gồm 30 sinh viên không được dùng trong run hiện tại, nhưng đã từng được Phase 5 xem xét; do đó run này không cung cấp estimate test mới độc lập.
3. Khoảng tin cậy 95% là mô tả giữa 5 seed và không điều chỉnh cho việc so sánh/chọn nhiều checkpoint.
4. Plateau không phải bằng chứng hội tụ toán học.
5. Dữ liệu giảng viên và khởi tạo khác các run cũ; không nên so sánh chênh lệch cross-dataset như thể cùng một thí nghiệm.
6. Compatibility/objective không phải điểm chính xác phân loại, không phải điểm chất lượng học thuật, và không dự báo kết quả hướng dẫn thực tế.
7. Trạng thái checkpoint là `production_promoted = false`; Hungarian vẫn là fallback/baseline an toàn.

---

## 10. Kiến nghị thảo luận với giáo viên hướng dẫn

1. **Xác nhận mục tiêu nghiên cứu:** cần tối ưu objective hiện tại, hay cần thay đổi reward/feature/evaluation để phản ánh tiêu chí nghiệp vụ khác?
2. **Giữ Hungarian làm baseline bắt buộc:** báo cáo mọi cải tiến RL tương đối so với Hungarian trên cùng problem definition.
3. **Không claim RL tốt hơn baseline ở giai đoạn này:** số liệu validation hiện tại chưa hỗ trợ claim đó.
4. **Thiết kế đánh giá tiếp theo trước khi tune thêm:** dùng cohort/snapshot độc lập, tách rõ train–validation–test và xác định tiêu chí promotion trước.
5. **Bổ sung đánh giá định tính bởi điều phối viên:** kiểm tra các cặp đề xuất, ràng buộc thực tế chưa có trong dữ liệu và mức chấp nhận của người dùng.
6. **Chỉ cân nhắc promotion sau khi có bằng chứng mới:** gồm evaluation độc lập, tiêu chí nghiệp vụ được phê duyệt và quy trình human review.

---

## 11. Kết luận

Hệ thống đã xây dựng được quy trình train/evaluate có seed lặp lại, kiểm tra hard constraint, checkpoint integrity và truy vết selection. PPO/DQN có thể tạo phân công hợp lệ và PPO thể hiện cải thiện nội bộ theo objective/compatibility trên validation cố định. Tuy nhiên, Hungarian hiện vẫn là phương pháp đạt chỉ số cao hơn trong thí nghiệm đã báo cáo; PPO và DQN chưa plateau và chưa có đánh giá độc lập mới để chứng minh khả năng tổng quát hóa.

Vì vậy, kết quả hiện tại nên được xem là **bằng chứng kỹ thuật cho pipeline nghiên cứu hoạt động**, không phải bằng chứng đủ để đưa RL thành phương án phân công chính thức.

---

## Phụ lục: truy vết số liệu

| Artifact | Vai trò |
|---|---|
| `data_rebuild/runtime/portable-verification/db88f3b2ebee91efdc4129699384b97657911a48379f9cba70aa57a9e0040ff5/training_report.json` | Báo cáo số liệu, curve, baseline, plateau, gate checks và checkpoint được chọn. |
| `data_rebuild/github_training/github_retraining_runs/20261022T205827Z-16010d68/selection_manifest.json` | Manifest checkpoint PPO/DQN được chọn và contract/checksum tương ứng. |
| `src/evaluation/github_retraining.py` | Kế hoạch seed, protocol train/evaluate và quy tắc selection. |
| `src/evaluation/rebuild_benchmark.py` | Định nghĩa metric objective, compatibility, coverage và constraint violations. |
| `src/environment/rebuild_env.py` | Reward contract, action masking và kiểm tra allocation episode. |

*Báo cáo này mô tả artifact hiện có trong workspace tại thời điểm lập báo cáo. Các con số nên được cập nhật cùng run ID khi thực hiện thí nghiệm mới.*