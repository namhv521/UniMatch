# Chương 1. Giới thiệu

## 1.1. Bối cảnh

Phân công giảng viên hướng dẫn khóa luận là một bài toán ra quyết định có nhiều mục tiêu. Mỗi sinh viên cần một giảng viên có chuyên môn phù hợp với đề tài; đồng thời mỗi giảng viên chỉ có thể nhận một số lượng sinh viên hữu hạn. Một phương án có tổng điểm tương thích cao nhưng dồn phần lớn sinh viên vào vài giảng viên không phải là phương án sử dụng được. Ngược lại, một phương án cân bằng tải tuyệt đối nhưng bỏ qua nội dung đề tài cũng không đáp ứng mục tiêu học thuật.

Quy trình thủ công thường dựa trên bảng tính, kinh nghiệm của hội đồng và lịch sử phân công. Cách làm này có giá trị chuyên môn nhưng khó tái lập: tiêu chí có thể thay đổi giữa các đợt, nguồn bằng chứng cho hồ sơ chuyên môn không luôn được ghi lại, và rất khó kiểm tra toàn bộ ràng buộc khi quy mô tăng. Đề tài này hướng tới một **hệ thống hỗ trợ quyết định**, không thay thế hội đồng. Hệ thống cung cấp điểm tương thích, phương án ghép cặp có ràng buộc, dấu vết từng quyết định và cơ chế từ chối artifact không tương thích.

## 1.2. Mục tiêu

Mục tiêu tổng quát là xây dựng đường ống có thể kiểm toán từ dữ liệu đến giao diện:

1. thu thập và chuẩn hóa hồ sơ đề tài, sinh viên và giảng viên;
2. tạo ma trận tương thích ngữ nghĩa có thứ tự hàng/cột cố định;
3. giải bài toán ghép cặp bằng baseline cổ điển và khảo sát các thuật toán học tăng cường;
4. thực thi ràng buộc hạn mức tại tầng domain, môi trường và serving;
5. lưu provenance gồm phiên bản dữ liệu, hash đặc trưng, split, seed và checkpoint;
6. trình bày kết quả bằng giao diện có bảng 2D và mô phỏng đồ thị 3D, nhưng không biến hiệu ứng trực quan thành bằng chứng khoa học.

Đóng góp thực tế quan trọng nhất của đề tài không phải một con số đơn lẻ. Đó là hợp đồng fail-closed: checkpoint chỉ được dùng khi kích thước quan sát, số hành động, hash và phạm vi dữ liệu phù hợp. Kiểm tra này đặc biệt cần thiết vì các checkpoint cũ trong dự án có không gian quan sát 6 và 2 hành động, tức môi trường đồ chơi 2 giảng viên, trong khi ma trận thật có 38 giảng viên và cần vector quan sát 114 chiều.

## 1.3. Câu hỏi nghiên cứu

Báo cáo tổ chức đánh giá quanh bốn câu hỏi:

- **RQ1:** Biểu diễn văn bản và quy trình provenance có tạo được ma trận tương thích tái lập, không rò rỉ split hay không?
- **RQ2:** Các baseline Random, Greedy và Hungarian khác nhau thế nào về tương thích, tải và chi phí tính toán trên cùng một cohort?
- **RQ3:** Khi huấn luyện và đánh giá trên không gian thật 38 giảng viên, các policy RL có đạt ràng buộc quota và cạnh tranh được với baseline trên validation/test hay không?
- **RQ4:** Hệ thống có thể phục vụ kết quả an toàn, ẩn danh, giải thích được nguồn dữ liệu và từ chối model không tương thích hay không?

RQ1 và RQ2 có artifact hiện hành để kiểm tra trên snapshot 215×38. RQ3 đã có benchmark validation cho ba baseline và sáu thuật toán RL, nhưng chưa có candidate RL nào vượt toàn bộ promotion gate; vì vậy Hungarian vẫn là engine được chọn. RQ4 có mã nguồn FE, BE, API, PostgreSQL, Docker và kiểm tra phát hành cục bộ; việc công bố trên Internet vẫn cần hạ tầng, secret, domain/HTTPS và smoke test tại môi trường đích.

## 1.4. Phạm vi và không phạm vi

Phạm vi hiện tại gồm dữ liệu cục bộ, ma trận **215×38**, split v2 gồm **154 train, 20 validation, 21 test và 20 future**, baseline có hạn mức, môi trường Gymnasium, sáu adapter RL, API FastAPI, PostgreSQL và frontend cùng origin. Hệ thống dùng ID ẩn danh ở bề mặt phục vụ. Snapshot 220×38 chỉ còn là mốc lịch sử trước khi loại năm bản ghi theo yêu cầu và không được dùng như trạng thái hiện hành.

Đề tài không tuyên bố phân công lịch sử là đáp án tối ưu. Lịch sử chỉ là **weak label** phản ánh quyết định trong bối cảnh cũ, có thể chứa ràng buộc hoặc ưu tiên không quan sát được. Đề tài cũng không tuyên bố load variance là định nghĩa đầy đủ của công bằng. Đây chỉ là một chỉ báo vận hành; công bằng chính thức phải do đơn vị đào tạo quy định, có thể bao gồm học hàm, khối lượng công việc, nguyện vọng, xung đột lợi ích và yêu cầu chuyên môn.

## 1.5. Cấu trúc báo cáo

Chương 2 phát biểu bài toán và yêu cầu. Chương 3 trình bày nền tảng tối ưu và RL. Chương 4–5 mô tả dữ liệu và đặc trưng. Chương 6–8 trình bày baseline, MDP và thuật toán RL. Chương 9 mô tả kiến trúc hệ thống và UI. Chương 10 định nghĩa protocol thực nghiệm. Chương 11 chỉ báo cáo kết quả có nguồn. Chương 12 tổng kết giới hạn và lộ trình hoàn thiện.

