# Nghiên cứu hai hướng phát triển UniMatch: học tiếp tục theo năm và học từ kết quả hướng dẫn thực tế

Ngày nghiên cứu: **27/10/2026**.

Phạm vi: nghiên cứu tài liệu học thuật, đối chiếu một số đường huấn luyện và bảng dữ liệu hiện tại, đề xuất thiết kế nghiên cứu. Không sửa thuật toán, không huấn luyện, không cập nhật dữ liệu hay triển khai hệ thống. Các công thức và thí nghiệm bên dưới là đề xuất, chưa phải kết quả thực nghiệm.

## 1. Kết luận chính

Hai ý tưởng giải quyết hai câu hỏi khác nhau và có thể kết hợp:

1. **Phương pháp 1: Continual Reinforcement Learning**, cụ thể là tiếp tục huấn luyện chính sách theo từng năm/học kỳ, kế thừa checkpoint trước. Câu hỏi: mô hình tích lũy kiến thức thế nào khi dữ liệu thay đổi?
2. **Phương pháp 2: học từ các ca ghép có kết quả tốt**. Tên gọi tùy mục tiêu: học bắt chước có trọng số, học dự đoán kết quả, hoặc **Inverse Reinforcement Learning — học tăng cường nghịch đảo** nếu thực sự suy ra hàm thưởng từ quyết định mẫu. Câu hỏi: thế nào là một cặp sinh viên–giảng viên tốt, và bằng chứng nào hỗ trợ nhận định đó?

Khuyến nghị cho khóa luận: lấy phương pháp 1 làm khung cập nhật; nghiên cứu phương pháp 2 trước hết dưới dạng **mô hình đánh giá kết quả có sử dụng độ tin cậy của nguồn**, rồi dùng điểm dự đoán làm một thành phần reward. Chỉ chọn IRL làm đóng góp chính khi đủ dữ liệu quyết định, tập giảng viên có thể chọn và ràng buộc tại thời điểm quyết định.

Điều cần chỉnh về thuật ngữ: **train từ đầu vẫn có thể là RL; kế thừa model cũng có thể xuất hiện trong học có giám sát**. RL được xác định bởi trạng thái, hành động, chuyển trạng thái và mục tiêu tối đa hóa phần thưởng. Yêu cầu kế thừa qua các vòng của đề bài là yêu cầu bổ sung về học tiếp tục. Tổng quan của Khetarpal và cộng sự đặt continual RL trong bối cảnh môi trường không dừng và duy trì khả năng học qua thời gian. [Nguồn tổng quan continual RL](https://arxiv.org/abs/2012.13490).

## 2. Đối chiếu với hệ thống và dữ liệu hiện có

### 2.1. Những gì đã kiểm tra trực tiếp

| Thành phần | Quan sát ngày 27/10/2026 | Ý nghĩa |
|---|---|---|
| `data_rebuild/v1/gold/students.csv` | 194 hàng; cả 194 có `semester_id=pilot-next-term` | Đây chưa phải phân kỳ lịch sử 2023–2026 |
| `cohort_year` | 0/194 có giá trị | Chưa thể lấy trường này để tạo vòng theo năm |
| `preferred_advisor_ids` | 0/194 có giá trị | Chưa tách được người tự chọn và người không chọn |
| Schema bảng gold sinh viên | Không có trường điểm bảo vệ/điểm khóa luận hoặc kết quả hoàn thành | Chưa huấn luyện được mô hình outcome từ chính bảng này |
| `src/evaluation/github_retraining.py` | Mỗi job tạo agent mới; docstring ghi “never load old weights”; các milestone trong cùng job tiếp tục trên agent đang có | Có học tiếp trong một run; chưa phải chuỗi checkpoint theo năm |
| `src/rl/rebuild_ppo.py` | Lưu/tải policy, optimizer, số bước; loader so khớp contract | Có nền tảng kế thừa trọng số, nhưng chưa có giao thức chuyển kỳ |
| `src/rl/rebuild_dqn.py` | Lưu/tải online network, target network, optimizer, replay, bộ đếm và RNG của agent/replay | Đã có nhiều thành phần cần cho resume DQN |
| Tài liệu chất lượng retraining hiện có | Split cố định 135/29/30; checkpoint được chọn chưa đạt plateau đã đặt ra | Không thể dùng số bước hiện có làm bằng chứng hội tụ hoặc khả năng dự báo năm mới |

Đây là kiểm tra bảng gold và các đường code nêu trên, **không phải kết luận rằng mọi PDF hoặc mọi thư mục trong repository đều không chứa năm, giảng viên hoặc điểm**. Các nguồn thô có thể có thông tin cần thiết nhưng phải được trích xuất, xác minh và liên kết trước.

Các tài liệu nội bộ đã đối chiếu:

- [Giải thích huấn luyện và giới hạn số đo hiện tại](rebuild_rl_training_explained.md).
- [Báo cáo bổ sung nguồn và retraining](rebuild_github_faculty_quality_report.md).
- Mã nguồn: `src/evaluation/github_retraining.py`, `src/rl/rebuild_ppo.py`, `src/rl/rebuild_dqn.py`.

### 2.2. Một giới hạn đặc biệt quan trọng

Hồ sơ được suy ra từ **khóa luận đã hoàn thành** chứa kiến thức hình thành trong quá trình được hướng dẫn. Nếu dùng toàn bộ những kỹ năng đó để giả lập lựa chọn giảng viên đầu kỳ, mô hình có thể nhìn thấy thông tin tương lai.

Phải tách:

- Hồ sơ trước phân công: môn học đã học, dự án trước kỳ, nguyện vọng, đề xuất đề tài ban đầu.
- Bằng chứng sau phân công: bản khóa luận cuối, kỹ năng mới sử dụng, điểm, tiến độ và phản hồi.

Khóa luận cuối có thể dùng làm **nhãn kết quả hoặc bằng chứng về chuyên môn hướng dẫn trong các kỳ sau**. Không mặc định xem nó là hồ sơ sinh viên đã có trước khi chọn người hướng dẫn.

## 3. Phương pháp 1: mô hình kế thừa qua các vòng

### 3.1. Diễn giải đúng ý tưởng

Giả sử `D_<2023` là dữ liệu có trước năm 2023, tức đến hết 2022. Nếu muốn bao gồm cả 2023 thì phải ghi `D_<=2023`. Báo cáo giữ cách hiểu “trước 2023” theo nghĩa chặt.

```text
Khởi tạo duy nhất lần đầu
    train trên D_<2023
    chọn checkpoint V1 bằng validation lịch sử

V1 đóng băng
    đánh giá trên kỳ 2024 trước khi cập nhật
    lấy checkpoint V1, tiếp tục học từ dữ liệu 2024 đã đủ điều kiện
    chọn ứng viên V2024

V2024 đóng băng
    đánh giá trên kỳ 2025 trước khi cập nhật
    lấy checkpoint V2024, tiếp tục học từ dữ liệu 2025 đã đủ điều kiện
    chọn ứng viên V2025

V2025 đóng băng
    dự đoán/phân công cho 2026
    chỉ chấm outcome khi kết quả 2026 đã có
```

Không dùng “một phần model 2025 để check”; đối tượng được chia là **dữ liệu 2025**. Model được nạp từ checkpoint của vòng trước.

Mô tả cập nhật:

\[
\theta_k^{start}=\theta_{k-1}^{selected},\qquad
\theta_k^{candidate}=\operatorname{Update}(\theta_k^{start},D_k^{train},M_{<k}).
\]

`M_<k` là dữ liệu cũ được giữ lại nếu giao thức cho phép rehearsal. Có thể không dùng bộ nhớ cũ, nhưng khi đó cần đo mức quên. Dùng lại dữ liệu cũ **không đồng nghĩa train lại từ đầu**; yếu tố quyết định là trạng thái mô hình khởi đầu của vòng mới.

### 3.2. Phải phân biệt ba cấp kế thừa

| Cấp | Giữ lại | Cách gọi và giới hạn |
|---|---|---|
| Khởi tạo từ trọng số cũ | Weights của policy/Q-network | Warm-start hoặc fine-tuning; vẫn đáp ứng ý “không train lại từ đầu” |
| Tiếp tục trạng thái huấn luyện | Weights, optimizer, các bộ đếm và lịch cập nhật cần thiết | Resume training; gần với việc nối tiếp run |
| Học tiếp tục có kiểm soát | Các thành phần trên, giao thức dữ liệu theo kỳ, kiểm tra quên và cơ chế lưu giữ kinh nghiệm | Thiết kế continual learning đầy đủ hơn |

Đổi optimizer ở ranh giới năm vẫn có thể là fine-tuning từ model cũ. Phải ghi rõ, không trình bày nó như khôi phục hoàn toàn run trước. Tương tự, giữ đúng kích thước tensor chưa đủ: thứ tự giảng viên và nghĩa từng feature cũng phải tương thích.

Tài liệu chính thức SB3 mô tả việc lưu tham số mạng và trạng thái liên quan thuật toán, bao gồm optimizer trong định dạng checkpoint. Loader tùy biến của UniMatch cần được đánh giá theo những gì nó thực sự lưu, không mặc định có đầy đủ trạng thái của định dạng SB3 chuẩn. [SB3: saving and loading](https://stable-baselines3.readthedocs.io/en/master/guide/save_format.html).

### 3.3. Đánh giá trước khi học: lựa chọn phù hợp nhất cho yêu cầu

Giao thức nên là **đánh giá theo thời gian, dự đoán trước rồi cập nhật sau**, thường gọi prequential hoặc test-then-train.

1. Tại đầu kỳ 2024, đóng băng V1 và toàn bộ preprocessing của V1.
2. Tạo dự đoán chỉ từ thông tin đã có tại thời điểm phân công.
3. Khi outcome 2024 xuất hiện, tính kết quả của V1 và khóa báo cáo đó.
4. Sau đó mới cho dữ liệu đủ điều kiện của 2024 tham gia cập nhật model.
5. V2024 được đánh giá tương lai ở 2025, không dùng lại chính các outcome đã học để chứng minh tổng quát hóa.

Một dữ liệu có thể từng là test của V1 rồi trở thành train của V2024. Kết quả quá khứ của V1 vẫn hợp lệ nếu đã cố định trước cập nhật. Nhưng dữ liệu đó **không còn là test độc lập cho V2024**.

Trong năm có dữ liệu theo đợt, có thể chia theo thứ tự thời gian: đợt sớm để cập nhật, đợt sau để validation, đợt tiếp theo để test. Nếu chỉ có một đợt phân công/năm và cuối năm mới có điểm, không giả lập rằng outcome của cả năm đã có từ đầu năm. Khi ấy đánh giá V1 trên 2024, cập nhật sau khi có kết quả, và kiểm tra V2024 ở 2025 là thiết kế tự nhiên hơn.

### 3.4. Hai lịch dữ liệu phải ghi riêng

**Lịch A — đánh giá thích nghi thực tế:** dùng kỳ mới để đánh giá model cũ; sau đó học từ kỳ đã đánh giá. Mỗi kỳ có validation dùng cho chọn ứng viên, còn chất lượng tương lai do kỳ sau kiểm tra.

**Lịch B — giữ lại benchmark cố định:** mỗi kỳ có một tập đánh giá không tham gia cập nhật trong toàn bộ nghiên cứu. Phù hợp kiểm tra khả năng ghi nhớ qua năm, nhưng làm giảm lượng dữ liệu học.

Với chỉ khoảng vài trăm mẫu, ưu tiên lịch A cho mục tiêu ứng dụng, thêm một bộ benchmark nhỏ có kiểm duyệt để đo quên. Không tự ấn định tỷ lệ 70/15/15 khi chưa có phân bố theo kỳ; cần bảo đảm mỗi tập có đủ đề tài, giảng viên và kết quả.

Năm 2023 đang bị bỏ trống trong ví dụ. Có thể dùng làm validation chuyển tiếp cho V1 hoặc đưa thành một vòng riêng, tùy dữ liệu thật. Không âm thầm vừa bỏ năm này vừa mô tả chuỗi dữ liệu liên tục. Nếu dùng 2023 để chọn checkpoint, đó là thông tin đã được dùng trong phát triển V1 và phải công bố.

### 3.5. PPO và DQN cần tiếp tục khác nhau

**PPO / MaskablePPO:**

- Kế thừa actor và critic, cùng optimizer nếu chọn resume đầy đủ.
- Thu rollout mới bằng chính policy hiện tại trên environment của kỳ mới.
- Để chống quên, có thể trộn các bài toán/cohort lịch sử vào tập environment rồi **thu rollout mới trên chúng**.
- Không đưa tùy ý transition cũ vào loss PPO như replay buffer DQN. PPO là thuật toán on-policy; tái sử dụng lịch sử ngoài giao thức cần cơ chế hiệu chỉnh phù hợp. [PPO gốc](https://arxiv.org/abs/1707.06347).

**Double DQN:**

- Kế thừa online network, target network và optimizer; ghi rõ lịch epsilon ở vòng mới.
- Có thể giữ replay cũ và bổ sung transition mới, nhưng phải kiểm soát tỷ lệ mẫu theo kỳ.
- Nếu reward, encoder, ID giảng viên hoặc semantics trạng thái đổi, replay cũ không tự động còn đúng.
- Phân công đã xảy ra theo quota cũ không được sửa reward theo quota mới rồi coi như một transition thật mới.

Khởi điểm nghiên cứu đơn giản: so sánh fine-tuning chỉ dữ liệu mới với fine-tuning có rehearsal. Replay là một hướng đã được nghiên cứu để giảm quên, không bảo đảm mọi cách trộn lịch sử đều cải thiện. [Experience Replay for Continual Learning](https://arxiv.org/abs/1811.11682).

### 3.6. Thay roster và encoder có thể làm hỏng kế thừa

Hệ thống hiện có state gắn với registry giảng viên và taxonomy cố định. Những trường hợp cần một giao thức chuyển đổi trong nghiên cứu sau này:

- Giảng viên mới làm tăng số action.
- Giảng viên nghỉ làm action cũ không hợp lệ.
- Giữ số action nhưng đổi thứ tự khiến output cũ trỏ sang người khác.
- Fit lại TF-IDF/encoder làm nghĩa input đổi dù shape giống nhau.
- Hồ sơ giảng viên được bổ sung bằng thông tin phát sinh sau năm kiểm tra.

Thí nghiệm đầu nên cố định feature schema và registry hợp lệ cho phạm vi nghiên cứu, mask giảng viên không hoạt động theo kỳ. Registry có thể dành slot nếu khai báo trước, nhưng không đưa chuyên môn tương lai vào hồ sơ lịch sử. Giảng viên mới chưa được biết trong thiết kế ban đầu cần một phép mở rộng có mapping và kiểm chứng riêng; không âm thầm đổi contract hay bỏ kiểm tra hash.

Phân biệt **contract ngữ nghĩa** với **hash snapshot dữ liệu**: dữ liệu thay qua kỳ là bình thường; ngữ nghĩa input/output phải được giữ hoặc chuyển đổi có chủ đích. Loader hiện so khớp chặt contract, nên chưa thể khẳng định chỉ gọi `load` là hoàn thành cập nhật liên năm.

### 3.7. “Tìm điểm hội tụ” nên viết thế nào?

Không có quy tắc “train một lần là tìm được hội tụ” cho PPO/DQN dùng mạng sâu trong môi trường thay đổi. Một lần chạy gồm nhiều episode và nhiều lần cập nhật; số epoch/step không phải chứng minh hội tụ.

Đề xuất dùng khái niệm **điểm dừng thực nghiệm trong ngân sách đã định**:

1. Khai báo trước ngân sách và khoảng đánh giá.
2. Chọn checkpoint theo validation riêng của vòng, với ràng buộc hợp lệ.
3. Theo dõi cải thiện trên nhiều cửa sổ, độ biến thiên qua seed và suy giảm ở kỳ cũ.
4. Dừng nếu không còn cải thiện đủ lớn theo ngưỡng đã định, hoặc hết ngân sách.
5. Nếu chưa đạt plateau thì báo “hết ngân sách, chưa xác lập plateau”.

Ví dụ minh họa, chưa phải tham số được duyệt: patience 5 lần đánh giá; epsilon theo thang utility đã chuẩn hóa; nhiều seed độc lập. Không lấy 5 seed trên cùng một cohort làm 5 năm độc lập. Khoảng tin cậy và độ ổn định cần đi cùng điểm trung bình. [Nghiên cứu về độ tin cậy khi đánh giá deep RL](https://arxiv.org/abs/2108.13264).

**“Vòng sau phải cải tiến” nên được chuyển thành tiêu chí chấp nhận ứng viên**, không thành cam kết metric luôn tăng. Nếu V2025 học tiếp nhưng giảm chất lượng, vẫn lưu ứng viên để nghiên cứu; phiên bản được sử dụng có thể giữ V2024. Model sau phải kế thừa model trước; việc nó tốt hơn phải do thí nghiệm chứng minh.

### 3.8. Cách chứng minh kế thừa thật

Mỗi vòng cần ghi: hash checkpoint cha; weights trước/sau cập nhật; optimizer và lịch cập nhật được giữ hay reset; data snapshot; encoder; registry; reward version; seed; số bước tích lũy và số bước mới.

Một chuỗi ví dụ:

```text
V1_seed42
  parent: none
  data_cutoff: 2022-12-31

V2024_seed42
  parent: SHA256(V1_seed42)
  start_weights: giống đúng weights V1_seed42
  updated_with: các nhãn 2024 đã thực sự có tại thời điểm cập nhật

V2025_seed42
  parent: SHA256(V2024_seed42 đã chọn)
  start_weights: giống đúng checkpoint cha
```

Không nối V2024 seed43 với V1 seed42 rồi báo như một chuỗi seed độc lập. Không gọi việc train mới xong gắn tên version cũ là kế thừa.

## 4. Phương pháp 2: học từ lựa chọn và kết quả thật

### 4.1. Mô tả lại bài toán của người dùng

Có hai nhóm:

- **Nhóm A:** sinh viên có chọn/nguyện vọng giảng viên từ đầu kỳ; sau đó có phân công thực tế và kết quả.
- **Nhóm B:** sinh viên không chọn; đơn vị đào tạo phân công, có thể ngẫu nhiên hoặc theo quy tắc khác.

Mong muốn: tìm các trường hợp nhóm A có kết quả tốt và bằng chứng đáng tin, học đặc điểm của cặp ghép thành công, rồi hỗ trợ phân công nhóm B thay cho cơ chế ngẫu nhiên.

Phải lưu cả **nguyện vọng ban đầu** và **giảng viên được phân thực tế**. Đăng ký một người nhưng được người khác hướng dẫn không phải minh chứng thành công cho nguyện vọng ban đầu. Cũng phải tách trường hợp không chọn thật với trường hợp mất dữ liệu nguyện vọng.

### 4.2. Tên “inverse” có khả năng là gì?

| Cách làm thực sự | Tên phù hợp | Có phải IRL không? |
|---|---|---|
| Học chọn lại giảng viên như các ca thành công | Behavioral cloning / imitation learning | Không tự động |
| Tăng trọng số ca tốt, có provenance rõ | Outcome-weighted imitation learning, mô tả phương pháp | Không tự động; đây chưa phải tên một thuật toán duy nhất |
| Dự đoán điểm/khả năng hoàn thành của cặp | Supervised outcome modeling / reward modeling | Không |
| Suy ra hàm thưởng khiến lựa chọn mẫu có vẻ hợp lý | Inverse Reinforcement Learning | Có, nếu mô hình hóa đúng quyết định mẫu |
| Học trực tiếp chính sách từ log `(s,a,r,s')` cố định | Offline RL | Không nhất thiết có bước IRL |
| Học một quyết định chọn giảng viên từ context và outcome | Contextual bandit / logged-bandit learning | Có thể phù hợp hơn MDP nhiều bước |

IRL đi từ hành vi quan sát sang hàm thưởng giải thích hành vi. Maximum Entropy IRL là một hướng kinh điển, dùng mô hình xác suất trên chuỗi quyết định. **Có điểm khóa luận không phải điều kiện định nghĩa IRL.** [Trang tác giả và bài báo Maximum Entropy IRL](https://www.cs.cmu.edu/~bziebart/publications/maximum-entropy-inverse-reinforcement-learning.html).

### 4.3. Vì sao “tự chọn + điểm cao” chưa phải nhãn ghép đúng?

Ví dụ: sinh viên nền tảng rất mạnh được 9,0 dù ghép chưa phù hợp; sinh viên cần hỗ trợ nhiều đạt 7,5 sau một tiến bộ lớn. Chỉ giữ điểm cao sẽ học cả năng lực có sẵn của sinh viên, mức độ dễ của đề tài và xu hướng chấm điểm.

Các yếu tố cần phân biệt:

- Năng lực ban đầu, kinh nghiệm dự án và điều kiện học tập.
- Khó khăn của đề tài, loại sản phẩm và rubric đánh giá.
- Giảng viên/hội đồng chấm; vai trò của người hướng dẫn trong điểm số.
- Động lực tự chọn, quan hệ có sẵn và khả năng tiếp cận giảng viên.
- Mức tải thực tế và thời gian hướng dẫn.
- Nguồn dữ liệu có đầy đủ, đúng danh tính và đúng thời điểm hay không.

**Độ tin cậy nguồn không đồng nghĩa chất lượng outcome; outcome tốt không đồng nghĩa tác động nhân quả của giảng viên.** Đây là ba trục phải tách.

Lựa chọn quan sát trong hệ gợi ý thường có thiên lệch tự chọn; các mục chưa được chọn cũng không thể mặc định là không phù hợp. [Recommendations as Treatments](https://proceedings.mlr.press/v48/schnabel16.html).

### 4.4. Ba loại điểm khác nhau

Đề xuất đặt tên tách biệt:

1. `q_source`: độ tin cậy của liên kết sinh viên–giảng viên–kết quả và nguồn chứng minh.
2. `y_outcome`: kết quả quan sát, chẳng hạn điểm theo rubric, hoàn thành đúng hạn, phản hồi đã xác minh.
3. `m_match`: mức phù hợp giữa hồ sơ trước kỳ, nhu cầu đề tài và chuyên môn giảng viên.

Nếu tính trọng số học `w_i=q_source_i * g(y_i)`, phải xem đó là một giả thuyết cần ablation. Chỉ học ca tốt có thể giúp imitation, nhưng mô hình dự đoán outcome cần cả thành công lẫn khó khăn để học phân biệt.

Không gán `q_source=1` chỉ vì điểm cao. Không gán outcome bằng 0 cho ca thiếu điểm. Không gọi sinh viên không chọn giảng viên là nhóm chất lượng thấp.

### 4.5. Phương án 2A — học bắt chước có trọng số

Học xác suất chọn giảng viên như quyết định lịch sử của các ca đã kiểm duyệt:

\[
L_{BC}(\theta)=-\sum_i w_i\log\pi_\theta(a_i\mid s_i,\mathcal A_i).
\]

`A_i` là tập giảng viên thực sự có thể chọn lúc đó. State phải gồm quota và các ràng buộc nếu mô hình được dùng trong phân công tuần tự.

Ưu điểm: đơn giản, phù hợp khởi tạo policy, không cần suy luận reward phức tạp. Giới hạn: học hành vi lịch sử; có thể học danh tiếng và thói quen chọn hơn là chất lượng hướng dẫn. Sai lệch state khi policy tự chạy cũng cần được xét. DAgger là ví dụ nghiên cứu về vấn đề phân bố trạng thái trong imitation tuần tự; nó cần khả năng hỏi chuyên gia ở các trạng thái mới, nên không phải lựa chọn mặc định nếu chỉ có log lịch sử. [Ross, Gordon và Bagnell, 2011](https://proceedings.mlr.press/v15/ross11a.html).

Không tạo nhãn âm “ghép sai” cho tất cả giảng viên không được chọn. Softmax BC có thể học lựa chọn tương đối trong tập khả dụng, nhưng không biến các lựa chọn chưa quan sát thành outcome thất bại đã biết.

### 4.6. Phương án 2B — học mô hình outcome rồi dùng làm reward

Đây là hướng khuyến nghị làm trước nếu có điểm và thông tin trước kỳ:

\[
\hat y_{ij}=f_\phi(x_i^{before},z_j^{before},p_i^{proposal},c_{ij}^{before}).
\]

Trong đó `x_i` là hồ sơ sinh viên; `z_j` là chuyên môn giảng viên; `p_i` là đề xuất đề tài trước phân công; `c_ij` là bối cảnh tải/quota và điều kiện hợp lệ.

Một cách học đơn giản là hồi quy có regularization trên các cặp thực tế đã quan sát, dùng loss phù hợp thang điểm và trọng số nguồn. Với dữ liệu ít, bắt đầu bằng đặc trưng tương tác rõ nghĩa; chưa cần mô hình sâu hoặc graph neural network.

Nếu đã có mô hình outcome được kiểm tra độc lập, có thể nghiên cứu reward:

\[
r_t=\alpha\hat y_{i_t,a_t}+\beta m_{i_t,a_t}
       +\eta\,preference_{i_t,a_t}-\lambda\,loadCost_t.
\]

Các thành phần phải cùng thang hoặc có quy tắc chuẩn hóa. `alpha`, `beta`, `eta`, `lambda` là tham số nghiên cứu, không phải giá trị đã được xác định. Constraint cứng như quota và eligibility vẫn nên được bảo đảm bằng mask/kiểm tra khả thi, không chỉ bằng phạt reward.

Điểm dự đoán là **ước lượng có bất định**, không phải kết quả thật của cặp chưa từng xảy ra. Khi policy tối ưu mạnh reward dự đoán, nó có thể chọn đúng những vùng mô hình outcome dự đoán sai. Vì thế cần kiểm tra ngoài phân bố, coverage và đánh giá độc lập. Không dùng cùng một reward model vừa hướng dẫn học vừa làm bằng chứng duy nhất rằng policy tốt hơn thực tế.

Nếu reward model thay đổi mỗi năm, nên có một ablation giữ reward cố định để tách lợi ích của policy kế thừa khỏi lợi ích của việc thay thước đo. Mỗi vòng chỉ fit reward bằng nhãn đã có trước cutoff.

### 4.7. Phương án 2C — IRL đúng nghĩa

Đặt câu hỏi: “Tổ hợp chuyên môn, nguyện vọng và tải nào giải thích các quyết định phân công lịch sử được xem là chất lượng?”

Thiết kế nghiên cứu tối giản có thể dùng reward tuyến tính:

\[
r_\omega(s,a)=\omega^\top\phi(s,a).
\]

Trong trường hợp minh họa có chuyển trạng thái xác định, mô hình Maximum Entropy đặt xác suất trajectory hợp lệ tỷ lệ với `exp(sum r_omega)` và chuẩn hóa trên tập trajectory. Khi transition ngẫu nhiên cần mô hình tương ứng; không bỏ xác suất chuyển trạng thái khỏi diễn giải tổng quát.

Muốn áp dụng vào UniMatch phải có hoặc tái dựng có căn cứ:

- Ai là người ra quyết định: sinh viên bày tỏ nguyện vọng hay điều phối phân công?
- Giảng viên nào đang có mặt, còn quota, đủ điều kiện và chấp nhận hướng dẫn?
- Tình trạng trước mỗi quyết định; thứ tự phân công nếu có.
- Mức tối ưu giả định của hành vi mẫu và các yếu tố chưa quan sát.

Một sinh viên chọn giảng viên cho bản thân không tự động là chuyên gia tối ưu toàn cohort. Mục tiêu cá nhân và mục tiêu điều phối có thể khác. Nếu chỉ biết các cặp phân công cuối cùng, có thể nghiên cứu inverse optimization trên bài toán ghép có ràng buộc, nhưng đó là một mô hình khác cần nêu rõ giả định.

Nếu không có thứ tự phân công, không tạo một thứ tự ngẫu nhiên rồi gọi nó là trajectory chuyên gia thật. Có thể dùng thứ tự chuẩn như một quy ước mô phỏng và kiểm tra độ nhạy, nhưng không coi đó là dữ kiện quan sát.

IRL còn có vấn đề không xác định duy nhất reward: cùng hành vi có thể được giải thích bằng nhiều hàm thưởng. Vì vậy reward học được không tự động là “mức phù hợp thật” hay năng lực thực của giảng viên. [Identifiability in inverse reinforcement learning](https://arxiv.org/abs/2106.03498).

### 4.8. Phương án 2D — offline RL và contextual bandit

Nếu chỉ có một quyết định chọn giảng viên rồi nhận outcome cuối kỳ, mô hình **contextual bandit** có thể tự nhiên hơn MDP nhiều bước. Nếu quyết định cho một sinh viên làm giảm quota và ảnh hưởng sinh viên tiếp theo, phân công toàn cohort vẫn có cấu trúc tuần tự và có thể mô hình hóa thành MDP.

Phân biệt hai môi trường:

- **Environment phân công mô phỏng:** chọn bất kỳ action hợp lệ nào cũng tính được reward tương đồng hoặc reward dự đoán. Có thể thu rollout mới để train PPO/DQN. Bằng chứng thu được là tối ưu trong environment đó.
- **Log hướng dẫn thực tế:** chỉ có outcome của giảng viên thực tế đã hướng dẫn. Không có điểm thật cho mọi giảng viên khác. Đây là dữ liệu phản hồi từng phần, không phải môi trường có reward thật đầy đủ.

Offline RL học từ dữ liệu tương tác đã thu thập, không cần thu thêm tương tác online trong quá trình học. DQN thông thường không tự trở thành thuật toán offline RL đáng tin chỉ vì đầu vào là log; hành động ngoài vùng dữ liệu có thể bị đánh giá quá cao. [Tổng quan offline RL](https://arxiv.org/abs/2005.01643).

CQL nghiên cứu cách làm bảo thủ Q-value; IQL nghiên cứu cải thiện policy từ dữ liệu mà hạn chế truy vấn hành động ngoài dataset. Đây là hướng tham khảo nếu log đủ tốt, không phải khuyến nghị thêm ngay hai thuật toán vào khóa luận. [CQL](https://arxiv.org/abs/2006.04779), [IQL](https://arxiv.org/abs/2110.06169).

## 5. Dùng nhóm A để hỗ trợ nhóm B: cách kiểm chứng

### 5.1. Không được suy ra hiệu quả từ hai điểm trung bình

“Nhóm tự chọn được 8,5, nhóm không chọn được 7,5” chưa chứng minh tự chọn hay model làm tăng một điểm. Hai nhóm có thể khác nhau từ đầu về năng lực, động lực, đề tài và khả năng tiếp cận giảng viên.

Đích cần nêu rõ là **chính sách phân công cho nhóm B**, với phân bố đầu vào của nhóm B. Có thể dùng A làm nguồn demonstrations và dùng dữ liệu B để kiểm tra chuyển miền. Nếu lịch sử của B cũng có outcome, nên cân nhắc dùng các ca đó để học outcome hoặc đánh giá, không loại chúng chỉ vì sinh viên không tự chọn.

### 5.2. “Random” phải được xác minh

Không chọn giảng viên không có nghĩa đã được phân ngẫu nhiên. Thực tế có thể chia theo lớp, chuyên ngành, quota còn lại, lịch công tác hay quyết định điều phối.

Nếu lịch sử thực sự random, cần biết:

- Tập giảng viên hợp lệ tại đúng lượt phân công.
- Quy tắc và xác suất chọn, bao gồm quota, stratification hoặc ưu tiên.
- Thứ tự phân công, override và trường hợp đổi giảng viên.
- Outcome có bị thiếu phụ thuộc kết quả hay không.

Không mặc định xác suất là `1/35`. Random đồng đều trên 5 giảng viên còn quota có xác suất khác random trên toàn roster. Với quota, phân công của các sinh viên còn phụ thuộc lẫn nhau.

### 5.3. Giới hạn của đánh giá phản thực

Ví dụ: log ghi sinh viên B được giảng viên X và đạt 8,0; model đề xuất Y. Không thể lấy 8,0 gán cho cặp B–Y. Không thể suy ra model sai chỉ vì khác X.

Nếu có logging propensity đáng tin và đủ overlap, có thể nghiên cứu IPS hoặc Doubly Robust để ước lượng policy. Minh họa DR cho **bài toán bandit từng quyết định**:

\[
\hat V_{DR}(\pi)=\frac1n\sum_i\left[
\sum_a\pi(a|x_i)\hat\mu(x_i,a)
+\frac{\pi(a_i|x_i)}{b(a_i|x_i)}(y_i-\hat\mu(x_i,a_i))
\right].
\]

`b` là xác suất lịch sử; `mu` là mô hình outcome. Cần overlap, log đúng và giả định nhận dạng phù hợp. “Doubly robust” không loại bỏ thiên lệch do biến ẩn chưa quan sát, không cứu được hành động có xác suất lịch sử bằng 0. [Dudík, Langford và Li, 2011](https://arxiv.org/abs/1103.4601).

Công thức trên không được áp thẳng để xác nhận chất lượng toàn cohort khi policy mới thay đổi quota và phân bố trạng thái. Khi có coupling theo quota hoặc tải làm ảnh hưởng outcome của nhiều sinh viên, cần mô hình tuần tự/nhóm thích hợp và giả định về interference. Tích tỷ số xác suất trajectory cũng có thể có variance rất lớn.

Nếu không có propensity hoặc dữ liệu quá ít, báo cáo chỉ nên kết luận về dự đoán outcome trên cặp đã quan sát, relevance do chuyên gia chấm, hoặc mô phỏng. Không hứa một con số tăng điểm thật.

### 5.4. Đánh giá theo ba tầng bằng chứng

| Tầng | Có thể đo | Chưa chứng minh |
|---|---|---|
| Mô phỏng | Utility, quota, coverage, so với tối ưu trên cùng ma trận | Điểm khóa luận thực tế tăng |
| Lịch sử ngoài thời gian | Sai số outcome, calibration, relevance, OPE nếu đủ điều kiện | Hiệu quả khi thay đổi toàn bộ quy trình phân công |
| Áp dụng thực tế có thiết kế | Kết quả cohort mới, chấp nhận đề xuất, outcome theo quy trình đánh giá phù hợp | Không tự suy rộng ngoài phạm vi đã kiểm tra |

Nghiên cứu hiện tại dừng ở thiết kế; không tạo thử nghiệm phân công thật.

## 6. Học tương đồng sinh viên–giảng viên–skill mà tránh vòng lặp tự xác nhận

Nên phân biệt ba quan hệ:

1. Sinh viên có năng lực nào **trước kỳ**?
2. Giảng viên có bằng chứng chuyên môn nào **trước kỳ**?
3. Đề xuất đề tài cần kỹ năng nào và sinh viên mong muốn phát triển kỹ năng nào?

Tương đồng cao không phải lúc nào cũng tốt nhất: sinh viên có thể cần giảng viên bổ sung một kỹ năng còn thiếu. Do đó cần so sánh giả thuyết “giống nhau” với “bổ trợ theo nhu cầu đề tài”, thay vì mặc định cosine lớn nhất là thành công.

Từ khóa luận lịch sử đã hoàn thành, có thể suy ra **bằng chứng từng hướng dẫn một công nghệ**, kèm ngày và độ tin cậy. Không tự chuyển thành mức thành thạo, chất lượng giảng dạy hoặc xác suất hướng dẫn thành công.

Một quy tắc chống leakage quan trọng:

> Khi đánh giá sinh viên S ở năm t, hồ sơ giảng viên không được bổ sung chuyên môn bằng chính khóa luận cuối của S, hoặc bằng khóa luận chưa hoàn thành tại thời điểm phân công năm t.

Ví dụ: dùng khóa luận S để thêm “PyTorch” vào profile giảng viên rồi chấm cặp S–giảng viên có độ phù hợp cao là vòng lặp tự xác nhận. Profile lịch sử cần dựng bằng các bằng chứng đã có trước cutoff. Nếu tạo aggregate từ các khóa luận cùng tập train, dùng cơ chế loại chính mẫu hoặc cross-fitting khi cần; các tập validation/test tuyệt đối không bổ sung feature ngược về train.

Việc rút ra skill từ tài liệu sau kỳ vẫn hữu ích cho phân tích quá khứ, nhưng kết quả đó phải được gắn nhãn **retrospective analysis**, không gọi là dự báo đầu kỳ.

## 7. Dữ liệu tối thiểu cho hai hướng

| Nhóm | Trường đề xuất | Dùng để làm gì |
|---|---|---|
| Định danh | `student_id`, `thesis_id`, `advisor_id`, nhóm làm chung nếu có | Liên kết đúng và ngăn trùng giữa các split |
| Thời gian | kỳ bảo vệ, ngày phân công, ngày từng feature/nhãn được biết | Chia theo thời gian thật |
| Đầu kỳ | năng lực trước kỳ, dự án cũ, đề xuất đề tài, nguyện vọng và ngày đăng ký | Đầu vào hợp lệ tại inference |
| Cơ chế phân công | tự chọn/điều phối/random, nguyện vọng và phân công cuối, lý do đổi | Phân nhóm và mô hình hành vi lịch sử |
| Tập khả dụng | roster, chuyên môn lịch sử, capacity, điều kiện, chấp thuận | Tái dựng action mask |
| Outcome | điểm theo rubric, đúng hạn, đổi giảng viên, phản hồi, ngày có kết quả | Nhãn kết quả thật |
| Đánh giá | hội đồng, người chấm, thang điểm, rubric, độ khó nếu được định nghĩa | Kiểm tra sai lệch đo lường |
| Nguồn | nguồn gốc, bằng chứng, độ tin cậy, trạng thái thiếu | Trọng số và audit |
| Log chính sách | context, action, model version, propensity nếu có | OPE và theo dõi policy |

Không suy năm bảo vệ từ mã sinh viên nếu chưa có quy tắc được xác minh. Không suy tự chọn từ lời cảm ơn trong khóa luận. Không tạo điểm số hay propensity giả để lấp schema. Nếu giảng viên kiêm người chấm, phải ghi vai trò để phân tích.

Phải lưu cả trường hợp chậm, bỏ dở và thiếu outcome với trạng thái riêng; chỉ crawl khóa luận đã nộp có thể bỏ sót chính những ca không thành công.

Với quy mô 194 mẫu hiện quan sát, số mẫu trên mỗi năm, giảng viên và nhóm có thể rất ít. Chưa có cơ sở khẳng định đủ dữ liệu cho deep IRL. Độ khả thi cần đánh giá từ số ca có nhãn đúng thời điểm và độ bao phủ hành động, không chỉ tổng số PDF.

## 8. Thiết kế nghiên cứu kết hợp được khuyến nghị

### 8.1. Câu hỏi nghiên cứu

- **RQ1:** tiếp tục checkpoint theo năm có hiệu quả hơn giữ model cũ và có tiết kiệm cập nhật hơn train mới không?
- **RQ2:** rehearsal có giảm quên ở các kỳ trước trong khi vẫn thích nghi kỳ mới không?
- **RQ3:** tín hiệu outcome thật có giúp đánh giá ghép tốt hơn reward tương đồng thủ công không?
- **RQ4:** học từ nhóm tự chọn chuyển sang nhóm không chọn được đến mức nào?
- **RQ5, tùy dữ liệu:** IRL có thêm giá trị so với reward model đơn giản hoặc imitation có trọng số không?

Đây là giả thuyết nghiên cứu; kết quả âm vẫn có giá trị nếu giao thức đúng và giới hạn được công bố.

### 8.2. Bộ thí nghiệm tối thiểu

Không chạy tất cả tổ hợp ngay. Tách thành hai bước để tránh không biết cải thiện đến từ đâu.

**Bước A — cố định feature và reward, nghiên cứu kế thừa:**

| Mã | Mô hình | Mục đích |
|---|---|---|
| A0 | Model kỳ trước đóng băng | Mốc xem cập nhật có hữu ích không |
| A1 | Kế thừa checkpoint, học dữ liệu mới | Phương pháp 1 cơ bản |
| A2 | Kế thừa checkpoint, dữ liệu mới + rehearsal | Đo duy trì kiến thức |
| A3 | Khởi tạo mới trên cùng dữ liệu/ngân sách cập nhật | Baseline cô lập lợi ích khởi tạo từ model cũ |
| A4, nếu đủ ngân sách | Train từ đầu trên toàn bộ dữ liệu lịch sử đã được phép dùng | Mốc batch để so chất lượng và chi phí tích lũy |

A3/A4 là nhóm đối chứng khoa học, không thay đổi yêu cầu rằng mô hình chính phải kế thừa. Cần báo cả chi phí ban đầu của V1 và chi phí mỗi lần cập nhật; không chỉ báo A1 rẻ vì bỏ qua toàn bộ lịch sử huấn luyện.

**Bước B — cố định cách cập nhật tốt nhất đã chọn bằng validation, nghiên cứu tín hiệu học:**

| Mã | Tín hiệu | Mục đích |
|---|---|---|
| B0 | Reward tương đồng hiện tại | Mốc triển khai sẵn có |
| B1 | Reward có thêm outcome model | Kiểm tra phương pháp 2B |
| B2 | Imitation từ ca đã kiểm duyệt, rồi RL nếu cần | Kiểm tra giá trị demonstrations |
| B3, tùy dữ liệu | Reward suy ra bằng IRL | Chỉ thêm khi đủ điều kiện nhận dạng quyết định |

Giữ Random, Greedy và Hungarian làm đối chứng phân công trên **cùng score, constraint và tập sinh viên**. Nếu Hungarian tối ưu đúng cùng objective cộng theo cặp với quota, RL không thể được kỳ vọng vượt nghiệm tối ưu đó trên chính objective đó. Nếu RL tối ưu reward khác hoặc load cost phi tuyến, phải ghi rõ bài toán khác; không dùng khác thước đo để tuyên bố vượt baseline.

### 8.3. Các thước đo cần báo

**Theo từng kỳ:**

- Tỷ lệ phân công đủ, số vi phạm quota/eligibility, ca phải abstain hoặc review.
- Utility và gap so với baseline dưới cùng objective.
- Thời gian/số bước cập nhật, chi phí tích lũy và mức biến thiên giữa seed.
- Outcome prediction: MAE/RMSE với điểm liên tục; calibration nếu dự đoán xác suất.
- Ranking relevance nếu có nhiều cặp được chuyên gia chấm độc lập. Không dùng giảng viên lịch sử làm “đáp án đúng duy nhất”.

**Theo học tiếp tục:** lập ma trận `R[k,j]`, là chất lượng model sau vòng k trên benchmark cố định của kỳ j, dùng cùng cách đo trong mỗi cột.

\[
F_{k,j}=\max_{\ell=j,\ldots,k-1}R[\ell,j]-R[k,j],\qquad k>j.
\]

Với metric càng lớn càng tốt, `F>0` biểu thị suy giảm so với mức tốt nhất trước đó; `F<0` biểu thị cải thiện ngược. Phải nói rõ có clip về 0 khi lấy trung bình hay không. Nếu metric là lỗi thì đổi hướng trước khi tính. Để so năm có roster khác, báo riêng phần entity chung và phần entity mới, không đánh đồng độ khó.

**Theo nhóm:** báo A và B riêng, thêm lát cắt theo nền tảng đầu vào, đề tài, giảng viên ít mẫu và dữ liệu thiếu. Một model có thể tốt trên A nhưng không chuyển sang B.

Không tính khoảng tin cậy như thể mọi cặp hoàn toàn độc lập nếu nhiều sinh viên cùng cohort/giảng viên/đề tài. Bootstrap nên theo đơn vị phụ thuộc thích hợp; với chỉ vài năm, không suy ra chắc chắn về mọi năm tương lai. Không dùng các lần chạy seed để thay số cohort độc lập.

### 8.4. Ablation đủ để bảo vệ kết luận

1. Kế thừa so với khởi tạo mới, cùng dữ liệu và ngân sách.
2. Có/không rehearsal, ghi tỷ lệ và ngân sách bộ nhớ.
3. Chỉ ca điểm cao so với dùng toàn bộ outcome có trọng số nguồn.
4. Reward thủ công so với reward học; cùng cách đánh giá độc lập.
5. Có/không thông tin năng lực trước kỳ để phát hiện mô hình chỉ học “sinh viên giỏi thì điểm cao”.
6. Chỉ nhóm A so với nguồn học có cả B khi hợp lệ; đánh giá luôn nêu target group.

Không cần deep IRL, mô hình graph và nhiều thuật toán RL mới cùng xuất hiện để luận văn có giá trị. Một giao thức thời gian đúng, checkpoint có lineage rõ và phân tích outcome cẩn thận đã tạo khác biệt đáng kể so với tăng step trên cùng split.

## 9. Chọn hướng theo điều kiện dữ liệu

| Điều kiện thực tế | Hướng phù hợp | Phát biểu khoa học có thể bảo vệ |
|---|---|---|
| Chỉ có nội dung khóa luận cuối và profile hiện tại | Mô phỏng phân công; kiểm tra leakage và nguồn | Tối ưu theo utility mô phỏng; chưa chứng minh dự báo đầu kỳ |
| Có snapshot đầu kỳ và năm đáng tin; chưa có outcome | Continual RL với reward tương đồng | Khả năng thích nghi và duy trì utility qua kỳ |
| Có thêm phân công và outcome | Outcome model; imitation có trọng số; continual RL | Dự đoán kết quả trên cặp đã quan sát và tối ưu theo mô hình |
| Có thêm tập khả dụng và quyết định mẫu rõ nghĩa | IRL hoặc inverse optimization | Reward giải thích hành vi dưới giả định đã nêu |
| Có log random/propensity, overlap và bối cảnh đầy đủ | OPE phù hợp bài toán | Ước lượng policy value có giả định và bất định |
| Có cohort mới áp dụng với quy trình đánh giá thích hợp | Đánh giá tác động thực tế | Kết quả trong phạm vi thí nghiệm thực tế |

Đối với bảng gold vừa kiểm tra, chưa đủ điều kiện để khẳng định đã sẵn sàng cho chuỗi 2023–2026 hoặc phương pháp 2 theo điểm thật. Việc cần nghiên cứu tiếp ở dữ liệu là khả năng khôi phục năm, thông tin trước kỳ, cơ chế phân công và outcome từ nguồn chính thống; không phải chạy thêm step trước.

## 10. Cách trình bày trong khóa luận

### 10.1. Tên hướng 1

**“Học tăng cường liên tục cho bài toán phân công giảng viên hướng dẫn theo dữ liệu từng học kỳ.”**

Phát biểu phương pháp: mô hình của kỳ mới khởi đầu bằng checkpoint của kỳ trước; dữ liệu và nhãn được đưa vào theo thời điểm thực sự có; ứng viên được đánh giá về thích nghi, quên và tuân thủ ràng buộc.

### 10.2. Tên hướng 2 khi chưa làm IRL

**“Học mô hình đánh giá cặp sinh viên–giảng viên từ kết quả hướng dẫn lịch sử có xét độ tin cậy dữ liệu.”**

Phát biểu phương pháp: kết hợp thông tin trước kỳ, phân công thực tế và outcome để học hàm đánh giá; sử dụng các ca có bằng chứng rõ làm nguồn học; kiểm tra riêng khả năng áp dụng sang nhóm không có nguyện vọng.

### 10.3. Tên hướng kết hợp được khuyến nghị

**“Phân công giảng viên hướng dẫn bằng học tăng cường liên tục với hàm thưởng học từ kết quả lịch sử.”**

Chỉ thay thành “hàm thưởng suy ra bằng học tăng cường nghịch đảo” khi nghiên cứu thật sự giải bài toán suy reward từ hành vi mẫu. Không đổi tên thuật toán để phù hợp từ khóa khi thực chất đang hồi quy điểm.

Đóng góp nên nằm ở giao thức cập nhật và bằng chứng thực nghiệm, không khẳng định phát minh PPO/DQN. Không hứa model mỗi năm luôn tăng điểm; đặt ra phép kiểm tra để biết khi nào có cải tiến, khi nào nên giữ phiên bản cũ.

## 11. Nguồn học thuật và thứ tự đọc

Các nguồn dưới đây được mở/đối chiếu trong phiên nghiên cứu. Phần khuyến nghị ứng dụng cho UniMatch là suy luận thiết kế từ các nguồn và cấu trúc dự án, chưa phải kết quả đã được các tác giả kiểm chứng cho bài toán này.

1. **Khetarpal et al. — Towards Continual Reinforcement Learning: A Review and Perspectives.** Bản đầu 2020, cập nhật 2022. Đọc phần 5 về lưu giữ kiến thức và phần 6 về đánh giá. [Toàn văn](https://arxiv.org/html/2012.13490v2).
2. **Rolnick et al. — Experience Replay for Continual Learning.** 2018/2019. Đọc để hiểu replay và quên; không sao chép cơ chế sang PPO tùy ý. [Bài báo](https://arxiv.org/abs/1811.11682).
3. **Schulman et al. — Proximal Policy Optimization Algorithms.** 2017. Đọc cơ chế thu mẫu và tối ưu PPO. [Bài báo](https://arxiv.org/abs/1707.06347).
4. **Ziebart et al. — Maximum Entropy Inverse Reinforcement Learning.** AAAI 2008. Đọc để phân biệt suy reward với học trực tiếp điểm outcome. [Trang tác giả](https://www.cs.cmu.edu/~bziebart/publications/maximum-entropy-inverse-reinforcement-learning.html), [PDF](https://www.cs.cmu.edu/~bziebart/publications/maxentirl-bziebart.pdf).
5. **Cao, Cohen, Szpruch — Identifiability in inverse reinforcement learning.** 2021. Đọc về tính không duy nhất của reward. [Bài báo](https://arxiv.org/abs/2106.03498).
6. **Ross, Gordon, Bagnell — A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning.** AISTATS 2011. Đọc vấn đề phân bố trạng thái của imitation tuần tự. [PMLR](https://proceedings.mlr.press/v15/ross11a.html).
7. **Schnabel et al. — Recommendations as Treatments: Debiasing Learning and Evaluation.** ICML 2016. Đọc về thiên lệch tự chọn trong hệ gợi ý. [PMLR](https://proceedings.mlr.press/v48/schnabel16.html).
8. **Dudík, Langford, Li — Doubly Robust Policy Evaluation and Learning.** ICML 2011. Đọc phần 2 về evaluator và điều kiện áp dụng. [Toàn văn](https://arxiv.org/html/1103.4601v2).
9. **Levine et al. — Offline Reinforcement Learning: Tutorial, Review, and Perspectives on Open Problems.** 2020. Đọc phần 2.4 về coverage và phần 3 về OPE. [Toàn văn](https://arxiv.org/html/2005.01643v3).
10. **Kumar et al. — Conservative Q-Learning for Offline Reinforcement Learning.** 2020. Nguồn tham khảo cho Q-value ngoài phân bố. [Bài báo](https://arxiv.org/abs/2006.04779).
11. **Kostrikov, Nair, Levine — Offline Reinforcement Learning with Implicit Q-Learning.** Bản arXiv 2021. Nguồn tham khảo cho học từ log với kiểm soát khác biệt hành vi. [Bài báo](https://arxiv.org/abs/2110.06169).
12. **Peng et al. — Advantage-Weighted Regression: Simple and Scalable Off-Policy Reinforcement Learning.** 2019. Tham khảo sự kết hợp value learning với policy regression có trọng số; không đồng nhất trọng số điểm cao tùy ý với AWR đầy đủ. [Trang tác giả](https://xbpeng.github.io/projects/AWR/index.html).
13. **Agarwal et al. — Deep Reinforcement Learning at the Edge of the Statistical Precipice.** NeurIPS 2021. Đọc cách báo bất định thay vì chỉ một điểm trung bình. [Bài báo](https://arxiv.org/abs/2108.13264).
14. **Stable-Baselines3 — On saving and loading.** Tài liệu kỹ thuật chính thức; phiên bản đang hiển thị khi truy cập là 2.9.2, không mặc định là phiên bản dependency của dự án. [Tài liệu](https://stable-baselines3.readthedocs.io/en/master/guide/save_format.html).

## 12. Phạm vi kết luận của lần nghiên cứu này

Đã xác định thuật ngữ, đối chiếu đường huấn luyện và bảng gold, nghiên cứu các rủi ro phương pháp, xây dựng giao thức thí nghiệm và khuyến nghị hướng khóa luận. Chưa có phép đo mới về chất lượng mô hình, chưa xác minh tính đầy đủ của toàn bộ nguồn thô theo năm, chưa tái dựng outcome hay cơ chế random lịch sử.

Khuyến nghị cuối: **nghiên cứu chuỗi checkpoint kế thừa theo thời gian trước; dùng kết quả thật để học/kiểm tra hàm đánh giá khi có dữ liệu phù hợp; giữ IRL như nhánh có điều kiện.** Điều này giữ đúng mong muốn tích lũy qua các vòng, đồng thời tránh biến điểm cao và lựa chọn tự nguyện thành nhãn “ghép đúng” chưa được chứng minh.
