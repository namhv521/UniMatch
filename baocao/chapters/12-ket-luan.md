# Chương 12. Kết luận, giới hạn và hướng phát triển

## 12.1. Kết luận

Đề tài xây dựng nền tảng hỗ trợ quyết định cho ghép cặp sinh viên–giảng viên theo chuỗi dữ liệu → đặc trưng → tối ưu/RL → serving → giao diện. Điểm mạnh của thiết kế là coi provenance và ràng buộc là thành phần trung tâm. Ma trận 220×38, split theo thời gian và baseline có quota tạo nền tảng thực nghiệm. Registry đọc trực tiếp checkpoint archive giúp phát hiện một sai lệch nghiêm trọng: checkpoint cũ có môi trường 2 giảng viên dù manifest tham chiếu hash dữ liệu thật.

Phát hiện này thay đổi cách diễn giải dự án. Các checkpoint legacy không phải bằng chứng rằng RL đã học trên cohort thật; chúng chỉ dùng cho sample demo. Vì vậy báo cáo không tuyên bố RL vượt baseline, không lấy số timesteps làm đại diện chất lượng, và không dùng metadata sai để hợp thức hóa model.

## 12.2. Giới hạn dữ liệu

Dữ liệu nguồn có coverage chưa hoàn toàn đồng đều. Trích xuất từ PDF/DOCX và crawl web có thể thiếu abstract, sai dấu hoặc chưa giải quyết định danh. Hồ sơ kỹ năng giảng viên suy ra từ đề tài lịch sử có nguy cơ vòng lặp nhãn. Split theo thời gian vẫn có thể rò rỉ nếu hồ sơ giảng viên dùng bằng chứng sau cutoff. Các vấn đề này cần data card và review chuyên gia trước triển khai thật.

Toàn bộ 38 quota chính thức đang thiếu; uniform ceiling chỉ là giả định thực nghiệm. Vì validation có 21 sinh viên và 38 giảng viên, phần lớn capacity là 1, không mô phỏng đầy đủ tải thực tế của một cohort lớn. Khi có quota chính thức, mọi benchmark phải chạy lại và được coi là protocol mới.

## 12.3. Giới hạn mục tiêu và fairness

Cosine similarity đo gần văn bản, không đo chất lượng hướng dẫn. Phân công lịch sử là weak label, không phải optimality ground truth. Load variance là cân bằng số lượng, không phải fairness chính thức. Một hệ thống vận hành cần thêm nguyện vọng, ràng buộc hai phía, availability, xung đột lợi ích và quy tắc học vụ do hội đồng xác nhận.

Hàm thưởng đa mục tiêu có trọng số thiết kế và chưa có ablation đầy đủ. RL có thể tối ưu reward proxy mà không cải thiện kết quả học thuật. Do đó human review và quyền override là bắt buộc.

## 12.4. Giới hạn thực nghiệm

Artifact baseline full-cohort cũ không phải holdout. Benchmark validation mới phải được đọc theo đúng seed và trạng thái pilot. Năm seed vẫn là quy mô nhỏ cho kết luận thống kê mạnh. Chưa có convergence log đáng tin thì không được dựng đường hội tụ. Chưa có đánh giá chuyên gia độc lập thì historical accuracy không thể thay thế.

Backend, frontend và Docker chỉ được gọi là hoàn thành sau test/smoke mới. Dockerfile hợp lệ về cú pháp không chứng minh image build hoặc container start trong môi trường khác. Session in-memory và credential môi trường phù hợp local demo, chưa phù hợp production Internet.

## 12.5. Hướng phát triển

Ưu tiên tiếp theo theo thứ tự:

1. thu quota chính thức và version hóa capacity policy;
2. khóa evidence cutoff cho hồ sơ giảng viên;
3. huấn luyện lại candidate trên train 158×38 với manifest space đầy đủ;
4. benchmark validation nhiều seed, chọn cấu hình trước khi mở test;
5. bổ sung preference hai phía để đánh giá matching stability;
6. thu đánh giá chuyên gia theo rubric và đo agreement;
7. triển khai session store, secret manager, rate limit và audit log nếu chuyển khỏi local;
8. audit accessibility và kiểm thử end-to-end trên browser;
9. theo dõi drift về chủ đề, advisor availability và phân phối cohort.

## 12.6. Nguyên tắc triển khai có trách nhiệm

Hệ thống phải trình bày score như tín hiệu hỗ trợ, nêu rõ dữ liệu thiếu, cho phép con người sửa và ghi lý do override. Không công bố tên/ID thật trong artifact nghiên cứu. Không tự động hóa quyết định có ảnh hưởng học tập nếu thiếu cơ chế khiếu nại. Model mới chỉ được dùng sau gate kỹ thuật và phê duyệt nghiệp vụ.

## 12.7. Kết lời

Giá trị học thuật của đề tài nằm ở cách biến một bài toán phân công nhiều ràng buộc thành hệ thống có thể đo, kiểm tra và phản biện. Kết quả tốt không chỉ là điểm compatibility cao, mà còn là khả năng trả lời: dữ liệu nào đã được dùng, model nào thực sự chạy, ràng buộc nào được bảo đảm, và điều gì vẫn chưa biết.

