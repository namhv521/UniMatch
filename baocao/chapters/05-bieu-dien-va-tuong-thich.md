# Chương 5. Biểu diễn ngữ nghĩa và ma trận tương thích

## 5.1. Mục tiêu biểu diễn

Đầu vào của bộ ghép không phải tên người mà là ma trận \(C\), trong đó \(C_{ij}\) biểu thị mức gần nhau giữa văn bản đề tài sinh viên \(i\) và hồ sơ chuyên môn giảng viên \(j\). Điểm này là tín hiệu xếp hạng, không phải xác suất “ghép đúng”. Một điểm cao chỉ cho biết hai văn bản chia sẻ biểu diễn gần nhau theo pipeline hiện tại; nó không đo được mức sẵn sàng hướng dẫn, xung đột lịch, nguyện vọng hay xung đột lợi ích.

## 5.2. TF–IDF và cosine similarity

Với thuật ngữ \(t\), tài liệu \(d\) và corpus train \(D\), một dạng trọng số TF–IDF là:

\[
\operatorname{tfidf}(t,d,D)=\operatorname{tf}(t,d)\cdot
\log\frac{|D|+1}{\operatorname{df}(t,D)+1}.
\]

Sau khi vector hóa, độ tương đồng cosine giữa đề tài \(u_i\) và hồ sơ \(v_j\) là:

\[
C_{ij}=\cos(u_i,v_j)=
\frac{u_i^\top v_j}{\lVert u_i\rVert_2\lVert v_j\rVert_2}.
\]

Pipeline hiện tại dùng vectorizer được fit từ văn bản train và văn bản advisor, sau đó transform toàn bộ sinh viên. Điểm được lưu dạng `float64` trong ma trận 220×38. Manifest v2 ghi phương pháp `tfidf`, hash corpus train, hash vocabulary, shape và SHA-256 của bytes ma trận.

## 5.3. Tiền xử lý và ngôn ngữ tiếng Việt

Văn bản đề tài có thể chứa tiếng Việt có dấu, từ tiếng Anh, tên framework và viết tắt. Tiền xử lý quá mạnh dễ xóa tín hiệu như `C++`, `R`, `IoT`, `BERT` hoặc `ASP.NET`. Vì vậy nguyên tắc là chuẩn hóa Unicode và khoảng trắng, giữ token công nghệ có nghĩa, không tự dịch thuật ngữ, và version hóa taxonomy nếu dùng ánh xạ đồng nghĩa.

Các bản ghi thiếu abstract thường chỉ còn tiêu đề. Độ dài ngắn làm cosine thưa và có thể tạo nhiều điểm bằng 0. Báo cáo coverage cần tách nhóm có/không có abstract để hiểu tác động. Không được bù văn bản thiếu bằng nội dung sinh tự động rồi coi đó là dữ liệu gốc.

## 5.4. Đặc trưng dense tùy chọn

`FeatureBuilder` hỗ trợ kết hợp TF–IDF với embedding dense khi cả ma trận sinh viên và giảng viên cùng số chiều:

\[
C^{mix}=\frac{C^{tfidf}+C^{dense}}{2}.
\]

Đây mới là cơ chế có trong code, không phải kết quả đã đánh giá. Trọng số 1/2–1/2 chưa được tune trên validation và chưa có bảng ablation. Do đó báo cáo kết quả hiện tại chỉ gắn với artifact `method=tfidf`. Khi đánh giá dense, cần ghi tên model, phiên bản, pooling, chuẩn hóa, license và hash embedding; nếu thiếu một trong hai phía, pipeline phải từ chối.

## 5.5. Bất biến thứ tự

Ma trận không tự chứa ID. Danh sách `student_ids` và `advisor_ids` trong manifest quyết định nghĩa của từng hàng/cột. Đặt:

\[
h_S=SHA256(JSON(S_{ordered})),\qquad
h_A=SHA256(JSON(A_{ordered})).
\]

Serving chỉ chấp nhận artifact nếu shape, hash bytes, hash dataset, hash split, \(h_S\) và \(h_A\) đều đúng. Kiểm tra này ngăn lỗi âm thầm khi CSV được sort lại nhưng `.npy` không được sinh lại.

## 5.6. Tư vấn một đề tài

Tính năng recommendation fit vectorizer trên train, transform tiêu đề mới, tính điểm với 38 hồ sơ và trả top-k. Bề mặt phục vụ sử dụng ID ẩn danh; `evidence_refs` là hash tham chiếu, không trả URL hoặc tên thật. Kết quả top-k phải kèm phiên bản feature và dataset. Vì không xét quota hiện thời trong vector similarity, đây là bước truy hồi ứng viên, không phải quyết định phân bổ cuối.

## 5.7. Đánh giá chất lượng biểu diễn

Historical top-1 accuracy có thể đo mức trùng phân công cũ trên những hàng có nhãn. Tuy nhiên nhãn cũ là weak label, nên metric này chỉ dùng chẩn đoán. Đánh giá tốt hơn cần một tập cặp được chuyên gia chấm độc lập theo rubric, hoặc so sánh ranking với nguyện vọng hai phía. Những dữ liệu đó chưa có trong artifact hiện tại và được ghi là giới hạn, không thay bằng số liệu ước đoán.

