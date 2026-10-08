# Chương 10. Thiết kế thực nghiệm và tiêu chí đánh giá

## 10.1. Mục tiêu protocol

Protocol phải ngăn ba lỗi phổ biến: so sánh khác cohort, chọn model bằng test, và gắn nhãn dữ liệu thật cho checkpoint toy. Mọi bảng so sánh chỉ gồm các run có cùng feature matrix, split, capacity policy và mapping ID. Run khác protocol được báo riêng, không gộp mean.

## 10.2. Dữ liệu và split

Ma trận v2 có 220 sinh viên và 38 giảng viên. Split schema v2:

| Tập | Số hàng | Vai trò |
|---|---:|---|
| Train | 158 | Fit vocabulary, huấn luyện model |
| Validation | 21 | Chọn cấu hình và đánh giá pilot/promotion |
| Test | 21 | Holdout cuối sau khi khóa lựa chọn |
| Future | 20 | Ngoài phạm vi train/test hiện tại |

Do quota chính thức thiếu cho cả 38 giảng viên, capacity policy là uniform ceiling và phải ghi trong mọi run. Kết quả này không đại diện quota vận hành chính thức.

Với policy này, train158/38 có capacity 5 mỗi GV, còn validation21/38 có capacity 1. Đây là dịch chuyển ràng buộc giữa train và validation; các phương pháp được so trên cùng capacity validation nhưng pilot chưa chứng minh tổng quát hóa qua các phân phối quota khác.

## 10.3. Thuật toán

Baseline bắt buộc: Random, Greedy và Hungarian. Random chạy các seed \(\{42,123,456,789,1024\}\); Greedy và Hungarian xác định với thứ tự hiện tại nên chỉ cần một run, nhưng vẫn ghi seed/protocol. RL candidate dùng cùng danh sách seed khi đủ tài nguyên. Pilot ít bước dùng để kiểm pipeline và ước lượng, không dùng làm kết luận cuối.

Các checkpoint legacy 6×2 được audit riêng. Chúng không tham gia benchmark validation 21×38. TQC không tham gia vì action-space mismatch. Gale–Shapley không tham gia nếu chưa có preference hai phía và adapter cùng protocol.

## 10.4. Metrics chính và phụ

Metric chính là mean compatibility trên assignment hoàn chỉnh, kèm 95% confidence interval hoặc mean±std khi có nhiều seed. Các gate bắt buộc:

- quota violations = 0;
- assignment coverage = 1;
- checkpoint/data/feature/split hash hợp lệ;
- không fallback ẩn;
- observation shape 114 và action count 38 cho dữ liệu thật.

Metrics phụ gồm load variance, invalid proposals, fallback count, runtime và theoretical optimality ratio so với Hungarian. Historical top-1 chỉ báo cáo khi nhãn lịch sử có coverage rõ và luôn gọi là weak-label agreement.

## 10.5. Giả thuyết

- **H1:** Greedy có mean compatibility cao hơn Random trên validation.
- **H2:** Hungarian không thấp hơn Greedy về mục tiêu tổng compatibility khi cùng capacity policy.
- **H3:** MaskablePPO đạt quota violations bằng 0 nếu action mask được dùng đúng.
- **H4:** Một candidate RL chỉ đáng promotion nếu kết quả nhiều seed cạnh tranh baseline và không đổi bằng việc dùng fallback.

H1–H2 có thể kiểm từ baseline artifact. H3–H4 chưa được khẳng định bởi checkpoint legacy. Pilot mới chỉ là bằng chứng pipeline cho đến khi đủ seed và protocol khóa.

## 10.6. Quy trình chạy

1. Kiểm hash curated dataset, split, feature matrix và mapping order.
2. Chạy baseline trên validation, lưu từng seed và summary.
3. Huấn luyện candidate từ train với manifest đầy đủ.
4. Audit archive và chỉ cho benchmark nếu 114×38.
5. Chạy inference trên validation, lưu assignment/event/metrics.
6. Tổng hợp theo seed; chọn cấu hình bằng tiêu chí khóa trước.
7. Sau khi chọn, chạy đúng một vòng test holdout và đóng băng report.
8. Sinh bảng/figure trực tiếp từ report; không vẽ learning curve nếu không có training log.

## 10.7. Kiểm định thống kê

Chỉ năm seed tạo ước lượng còn rộng; báo cáo phải công bố từng seed, không chỉ p-value. Nếu so paired, các run phải cùng seed và cùng instance. Kiểm định t ghép cặp yêu cầu giả định về phân phối chênh lệch; khi số mẫu nhỏ, nên bổ sung bootstrap interval hoặc kiểm định không tham số, nhưng không “chọn” phép kiểm định sau khi xem kết quả để đạt ý nghĩa.

## 10.8. Tái lập

Mỗi report lưu timestamp, code revision nếu có, Python/library version, platform, seed list, lệnh, hash input và output. Figure script chỉ đọc report đã đóng băng. Một con số không truy ngược được tới run entry không được đưa vào Chương 11.
