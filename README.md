# Hệ Thống Phân Bổ Sinh Viên - Giảng Viên Khóa Luận Tốt Nghiệp Bằng Học Tăng Cường (Reinforcement Learning)

---

## 1. Giới Thiệu Tổng Quan & Tính Cấp Thiết

Trong các cơ sở giáo dục đại học, bài toán phân bổ sinh viên làm Khóa luận Tốt nghiệp (KLTN) cho giảng viên hướng dẫn là một bài toán tối ưu hóa tổ hợp có điều kiện biên phức tạp. Một phương án phân bổ lý tưởng cần thỏa mãn đồng thời ba mục tiêu lớn:

1. **Tối đa hóa độ tương thích chuyên môn:** Đề tài nghiên cứu và nguyện vọng của sinh viên phải phù hợp với lĩnh vực nghiên cứu, chuyên môn sâu và năng lực của giảng viên.
2. **Tuân thủ nghiêm ngặt ràng buộc trần dung lượng (Hard Capacity Constraints):** Mỗi giảng viên có một chỉ tiêu hướng dẫn tối đa được giao bởi Khoa/Viện. Số lượng sinh viên phân cho mỗi giảng viên không bao giờ được phép vượt quá hạn mức này.
3. **Cân bằng tải công bằng (Fairness & Workload Balance):** Phân bổ đều khối lượng công việc, hạn chế tình trạng dồn ứ sinh viên vào một nhóm giảng viên trong khi các giảng viên khác nhận quá ít chỉ tiêu.


---

## 2. Mô Hình Hóa Bài Toán Toán Học (MDP Formulation)

Bài toán được chuẩn hóa thành một MDP tuần tự biểu diễn bởi bộ 5 thành tố $(\mathcal{S}, \mathcal{A}, \mathcal{P}, \mathcal{R}, \gamma)$:

### 2.1. Không Gian Trạng Thái (Observation / State Space $\mathcal{S}$)
Tại bước ra quyết định $t$ (khi cần phân bổ cho sinh viên thứ $t$ trong danh sách $N$ sinh viên), trạng thái $s_t$ được biểu diễn dưới dạng một vector liên tục kích thước $3 \times M$ (trong đó $M$ là tổng số giảng viên trong hội đồng):

1. **Vector Độ Tương Thích Chuyên Môn (Compatibility Vector):**
   - Biểu diễn độ tương đồng ngữ nghĩa giữa đề tài của sinh viên $t$ và hồ sơ chuyên môn của từng giảng viên $j \in \{1, \dots, M\}$.
   - Được chuẩn hóa chặt chẽ trong khoảng $[0.0, 1.0]$.
2. **Vector Tỷ Lệ Dung Lượng Còn Lại (Remaining Capacity Ratio Vector):**
   - Biểu diễn tỷ lệ chỉ tiêu còn nhận được của từng giảng viên tại thời điểm hiện tại: $C_j^{\text{rem}} / C_j$.
   - Khi giảng viên còn trống toàn bộ chỉ tiêu, giá trị bằng $1.0$; khi đã nhận đủ sinh viên, giá trị về $0.0$.
3. **Vector Tỷ Lệ Tải Hiện Tại (Current Load Ratio Vector):**
   - Biểu diễn tỷ trọng sinh viên đã nhận trên chỉ tiêu: $L_j / C_j$, phản ánh mức độ bận rộn hiện thời của giảng viên.

### 2.2. Không Gian Hành Động (Action Space $\mathcal{A}$)
Không gian hành động là tập rời rạc gồm $M$ phần tử: $\mathcal{A} = \{0, 1, \dots, M - 1\}$, trong đó hành động $a_t = j$ thể hiện quyết định phân công sinh viên thứ $t$ cho giảng viên thứ $j$.

### 2.3. Cơ Chế Mặt Nạ Hành Động (Action Masking)
Để đảm bảo **không bao giờ vi phạm chỉ tiêu hướng dẫn**, hệ thống áp dụng cơ chế Action Masking thời gian thực:
- Tại mỗi bước $t$, một mặt nạ nhị phân boolean kích thước $M$ được tính toán.
- Nếu giảng viên $j$ đã đạt trần dung lượng ($L_j = C_j$), mặt nạ tại vị trí $j$ bị khóa thành `False`.
- Thuật toán Maskable PPO sẽ gán xác suất chọn bằng 0 tuyệt đối cho các hành động bị khóa trước khi lấy mẫu hành động, triệt tiêu 100% lỗi vi phạm ràng buộc dung lượng ngay từ quá trình huấn luyện và suy luận.

---

## 3. Kiến Trúc Luồng Dữ Liệu & Các Tầng Thành Phần

Hệ thống được thiết kế theo kiến trúc module hóa phân tầng, tách biệt hoàn toàn giữa các luồng tính toán:

```
[ Dữ Liệu Nguồn FIT-NEU: 198 đề tài khóa luận & 39 giảng viên ]
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ 1. Data & NLP Pipeline (Temporal Split Anti-Leakage)   │
│    - Làm sạch văn bản tiếng Việt & kiểm toán schema   │
│    - Trích xuất đặc trưng TF-IDF & Dense Embeddings    │
│    - Xây dựng ma trận tương thích Cosine N x M         │
└────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ 2. Môi Trường Mô Phỏng Gymnasium (GymMatchingEnv)     │
│    - Không gian quan sát 3xM & hành động Discrete(M)   │
│    - Action Masking triệt tiêu vi phạm dung lượng      │
│    - Hàm thưởng đa mục tiêu Pareto (Comp + Variance)   │
└────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ 3. Huấn Luyện & Đánh Giá Đa Thuật Toán (8 Models)     │
│    - Baselines Cổ điển: Random, Greedy, Gale-Shapley   │
│    - Theoretical Upper Bound: Exact Hungarian Solver   │
│    - RL Models: Maskable PPO, DQN, QR-DQN, A2C        │
│    - Đánh giá 5-Seed & Kiểm định thống kê (T-test)     │
└────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ 4. Cổng Thăng Hạng & Đóng Gói (Promotion Gate)         │
│    - Kiểm định 0 Quota Violations & 0 Invalid Proposals│
│    - Xuất Manifest SHA-256 bất biến xác thực mô hình   │
└────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ 5. Ứng Dụng Sản Phẩm (Inference Backend & UI)         │
│    - FastAPI Backend phục vụ suy luận Batch & Stream   │
│    - Single Page Application Web Dashboard trực quan   │
└────────────────────────────────────────────────────────┘
```

---


---

## 5. Chiến Lược Kiểm Thử & Đảm Bảo Tính Chặt Chẽ Học Thuật

Để đảm bảo kết quả nghiên cứu khách quan, minh bạch và có thể tái lập 100%:

1. **Giao Thức Phân Tách Dữ Liệu Theo Thời Gian Chống Rò Rỉ (Temporal Split Anti-Leakage Protocol):**
   - Dữ liệu lịch sử các năm trước + 75% năm gần nhất được đưa vào tập Huấn luyện (Train).
   - 12.5% tiếp theo dành cho Thẩm định (Validation) để tinh chỉnh siêu tham số.
   - 12.5% còn lại được khóa làm tập Kiểm thử độc lập (Test Set) và chỉ chạy suy luận duy nhất một lần.
   - Toàn bộ pipeline tiền xử lý từ vựng và trích xuất đặc trưng (TF-IDF Vectorizer) chỉ được học (`fit`) trên tập Train; các tập Validation và Test chỉ được chuyển đổi (`transform`) nhằm phản ánh chính xác năng lực tổng quát hóa.
2. **Kiểm Định Đa Hạt Giống (Multi-Seed Benchmark):**
   - Toàn bộ 8 thuật toán được đánh giá trên 5 hạt giống ngẫu nhiên độc lập (`42, 123, 456, 789, 1024`).
   - Kết quả được báo cáo dạng Giá trị Trung bình $\pm$ Độ lệch chuẩn (`Mean ± Std`).
3. **Kiểm Định Ý Nghĩa Thống Kê (Statistical Hypothesis Testing):**
   - Áp dụng kiểm định Paired Student's T-test và Wilcoxon Signed-Rank Test.
   - Bắt buộc đạt mức ý nghĩa $p < 0.05$ để khẳng định sự vượt trội không phải do ngẫu nhiên.
4. **Cổng Thăng Hạng Nghiêm Ngặt (Promotion Gate):**
   - Bất kỳ mô hình RL nào muốn trở thành engine phân bổ chính thức đều phải thỏa mãn 3 điều kiện:
     - Số lần vi phạm chỉ tiêu hướng dẫn bằng 0 tuyệt đối (Quota Violations = 0).
     - Số lần đề xuất hành động không hợp lệ bằng 0 (Invalid Proposals = 0).
     - Điểm tương thích trung bình $\ge 88\% - 92\%$ so với Cận trên lý thuyết Exact Hungarian và vượt trội so với Heuristic Greedy cơ sở.

---

## 4. Các Vòng Đời Nghiệp Vụ Thực Tế (Lifecycles V1 – V4)

Đề tài giải quyết và mô phỏng 4 kịch bản vận hành thực tế tại trường đại học:

- **Lifecycle V1 (Batch Matching Chuẩn):** Toàn bộ danh sách đề tài và giảng viên được chốt trước kỳ học. Hệ thống thực hiện ghép cặp đồng loạt toàn bộ khóa sinh viên.
- **Lifecycle V2 (Ghép Cặp Kèm Nguyện Vọng Sinh Viên):** Sinh viên được đăng ký danh sách Top-3 nguyện vọng ưu tiên. Hệ thống tối ưu hóa hàm mục tiêu kết hợp giữa điểm tương thích ngữ nghĩa và thứ bậc nguyện vọng.
- **Lifecycle V3 (Online Streaming Sequential Arrival):** Sinh viên nộp đề tài bất đồng bộ theo dòng thời gian ngẫu nhiên. Trạng thái dung lượng của các thầy cô biến thiên liên tục. Đây là kịch bản chứng minh ưu thế vượt trội của Agent RL so với thuật toán Hungarian truyền thống.
- **Lifecycle V4 (Vòng Lặp Phản Hồi Chuyên Gia - Human-in-the-Loop):** Hội đồng khoa học có quyền điều chỉnh, đổi giảng viên sau khi nhận kết quả gợi ý. Hệ thống ghi nhận phản hồi này để tiếp tục tinh chỉnh (fine-tune) mô hình trong các học kỳ tiếp theo.


### 2.4. Hàm Thưởng Đa Mục Tiêu (Multi-Objective Reward Function $\mathcal{R}$)
Hàm thưởng tại mỗi bước $t$ được thiết kế nhằm đạt trạng thái cân bằng Pareto giữa độ phù hợp chuyên môn và tính công bằng:

$$r_t = w_{\text{comp}} \cdot \text{comp}(t, a_t) + w_{\text{fair}} \cdot (\text{Var}_{\text{load}}(t-1) - \text{Var}_{\text{load}}(t)) - w_{\text{pen}} \cdot \mathbb{I}_{\text{invalid}}$$

Trong đó:
- **Thành phần tương thích ($\text{comp}$):** Điểm số tương quan ngữ nghĩa trực tiếp giữa sinh viên và giảng viên được chọn.
- **Thành phần cân bằng tải ($\Delta \text{Var}$):** Thưởng khi quyết định gán làm giảm phương sai tải của toàn bộ giảng viên, phạt nếu quyết định làm độ lệch tải tăng lên.
- **Thành phần phạt vi phạm ($\mathbb{I}_{\text{invalid}}$):** Trừ điểm nghiêm khắc nếu agent đề xuất giảng viên đã kín chỗ (áp dụng cho các mô hình baseline không có Action Masking như Standard DQN).

### Hạn Chế Của Các Tiếp Cận Truyền Thống:
- **Phân loại / Hồi quy tĩnh một bước (Single-step Supervised Learning):** Không thể xử lý được tính chất phụ thuộc lẫn nhau giữa các quyết định. Khi một sinh viên được gán cho một giảng viên, dung lượng khả dụng của giảng viên đó giảm đi, làm thay đổi trực tiếp không gian hành động hợp lệ cho các sinh viên tiếp theo.
- **Thuật toán tham lam (Greedy Heuristic):** Dễ rơi vào bẫy tối ưu cục bộ — ưu tiên ghép cặp các sinh viên đầu tiên và đẩy các sinh viên phía sau vào những giảng viên hoàn toàn lệch chuyên ngành khi các vị trí tốt đã cạn.
- **Quy hoạch tĩnh toàn cục (Hungarian / Gale-Shapley):** Mặc dù tìm được lời giải tối ưu trong bài toán tĩnh toàn bộ (offline batch), nhưng các thuật toán này hoàn toàn thất bại hoặc phải tính toán lại từ đầu với độ phức tạp cao khi bước vào bài toán thực tế: sinh viên nộp hồ sơ bất đồng bộ theo thời gian thực (online streaming sequential arrival).

### Lý Do Lựa Chọn Học Tăng Cường (Reinforcement Learning):
Mô hình hóa bài toán dưới dạng **Quá trình Ra quyết định Markov tuần tự (Sequential MDP)** cho phép Agent học được chiến lược phân bổ dài hạn (long-term policy). Agent không chỉ nhìn vào sự phù hợp trước mắt của sinh viên hiện tại, mà còn biết bảo lưu dung lượng của các chuyên gia đầu ngành cho những đề tài chuyên sâu xuất hiện ở các bước tiếp theo, đồng thời tự động thích nghi tối ưu trong cả hai chế độ: phân bổ cả đợt (batch) lẫn phân bổ luồng thời gian thực (online streaming).
