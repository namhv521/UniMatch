# Chương 12. Kết luận, giới hạn và hướng phát triển

## 12.1. Kết luận

Đề tài xây dựng nền tảng hỗ trợ quyết định cho ghép cặp sinh viên–giảng viên theo chuỗi dữ liệu → đặc trưng → tối ưu/RL → serving → giao diện. Điểm mạnh của thiết kế là coi provenance và ràng buộc là thành phần trung tâm. Snapshot hiện hành có ma trận **215×38** và split **154/20/21/20**. Registry đọc trực tiếp checkpoint archive giúp phát hiện checkpoint toy 2 giảng viên, đồng thời report mới kiểm 24 checkpoint thật 114×38 trước khi chọn 20 dòng RL để tổng hợp cùng 15 dòng baseline.

Kết quả validation hiện hành cho thấy Hungarian đạt mean compatibility cao nhất và được chọn làm engine. DQN, MaskablePPO và QR-DQN đã đủ năm seed × 2 triệu bước; TRPO, ARS và RecurrentPPO chưa đủ toàn bộ seed/ngân sách. Không RL candidate nào qua promotion gate. Vì vậy báo cáo không tuyên bố RL vượt baseline và không lấy số timesteps làm đại diện chất lượng.

## 12.2. Giới hạn dữ liệu

Dữ liệu nguồn có coverage chưa hoàn toàn đồng đều. Trích xuất từ PDF/DOCX và crawl web có thể thiếu abstract, sai dấu hoặc chưa giải quyết định danh. Hồ sơ kỹ năng giảng viên suy ra từ đề tài lịch sử có nguy cơ vòng lặp nhãn. Split theo thời gian vẫn có thể rò rỉ nếu hồ sơ giảng viên dùng bằng chứng sau cutoff. Năm hàng đã được loại khỏi snapshot 220; bốn hàng trong số đó thuộc train gốc, nhưng vocabulary/IDF hiện hành vẫn đóng băng từ corpus trước khi lọc. Đây là giới hạn tiền xử lý cần xử lý bằng một feature version và đợt huấn luyện mới nếu muốn protocol 154-train hoàn toàn sạch.

Toàn bộ 38 quota chính thức đang thiếu; uniform ceiling chỉ là giả định thực nghiệm. Vì validation có 20 sinh viên và 38 giảng viên, capacity bằng 1 làm load variance cố định ở khoảng 0,2493 cho mọi assignment hoàn chỉnh hợp lệ. Giá trị này không mô phỏng đầy đủ tải thực tế của một cohort lớn. Khi có quota chính thức, mọi benchmark phải chạy lại và được coi là protocol mới.

## 12.3. Giới hạn mục tiêu và fairness

Cosine similarity đo gần văn bản, không đo chất lượng hướng dẫn. Phân công lịch sử là weak label, không phải optimality ground truth. Load variance là cân bằng số lượng, không phải fairness chính thức. Một hệ thống vận hành cần thêm nguyện vọng, ràng buộc hai phía, availability, xung đột lợi ích và quy tắc học vụ do hội đồng xác nhận.

Hàm thưởng đa mục tiêu có trọng số thiết kế và chưa có ablation đầy đủ. RL có thể tối ưu reward proxy mà không cải thiện kết quả học thuật. Do đó human review và quyền override là bắt buộc.

## 12.4. Giới hạn thực nghiệm

Artifact baseline full-cohort 220×38 là bằng chứng lịch sử, không phải holdout của snapshot hiện hành. Benchmark validation hiện có 35 dòng, nhưng chỉ ba trong sáu RL hoàn thành đủ năm seed × 2 triệu bước; không candidate nào được promote. Năm seed vẫn là quy mô nhỏ cho kết luận thống kê mạnh. Chưa có convergence log đáng tin thì không được dựng đường hội tụ. Chưa có đánh giá chuyên gia độc lập thì historical accuracy không thể thay thế.

Backend, frontend và Docker chỉ được gọi là hoàn thành sau test/smoke mới. Dockerfile hợp lệ về cú pháp không chứng minh image build hoặc container start trong môi trường khác. Session in-memory và credential môi trường phù hợp local demo, chưa phù hợp production Internet.

## 12.5. Hướng phát triển

Ưu tiên tiếp theo theo thứ tự:

1. thu quota chính thức và version hóa capacity policy;
2. khóa evidence cutoff cho hồ sơ giảng viên;
3. refit feature trên đúng 154 hàng train hiện hành và huấn luyện lại candidate với manifest mới;
4. hoàn tất seed/ngân sách còn thiếu, khóa lựa chọn trên validation trước khi mở test;
5. bổ sung preference hai phía để đánh giá matching stability;
6. thu đánh giá chuyên gia theo rubric và đo agreement;
7. triển khai session store, secret manager, rate limit và audit log nếu chuyển khỏi local;
8. audit accessibility và kiểm thử end-to-end trên browser;
9. theo dõi drift về chủ đề, advisor availability và phân phối cohort.

## 12.6. Nguyên tắc triển khai có trách nhiệm

Hệ thống phải trình bày score như tín hiệu hỗ trợ, nêu rõ dữ liệu thiếu, cho phép con người sửa và ghi lý do override. Không công bố tên/ID thật trong artifact nghiên cứu. Không tự động hóa quyết định có ảnh hưởng học tập nếu thiếu cơ chế khiếu nại. Model mới chỉ được dùng sau gate kỹ thuật và phê duyệt nghiệp vụ.

## 12.7. Kết lời

Giá trị học thuật của đề tài nằm ở cách biến một bài toán phân công nhiều ràng buộc thành hệ thống có thể đo, kiểm tra và phản biện. Kết quả tốt không chỉ là điểm compatibility cao, mà còn là khả năng trả lời: dữ liệu nào đã được dùng, model nào thực sự chạy, ràng buộc nào được bảo đảm, và điều gì vẫn chưa biết.

