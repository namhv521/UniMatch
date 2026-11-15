# Đặc tả kỹ thuật UniMatch Web

Phiên bản 1.1 · 15/11/2026

Yêu cầu sản phẩm tại [UniMatch Web PRD](unimatch_web_prd.md).

## Kiến trúc và giao diện

- Trang `frontend/thesis.html` là điểm vào chung. `portal.js` lấy vai trò từ `GET /api/auth/me`. `thesis.js` hiển thị nghiệp vụ theo vai trò và tái sử dụng màu, font, nút, bảng của portal.
- Trang sinh viên có các phần đánh giá, gợi ý, nguyện vọng và trợ lý. Trang giảng viên ưu tiên danh sách cần duyệt. Trang trưởng khoa đặt ngưỡng cạnh luồng tạo phương án và kiểm tra chỉ tiêu.
- Trang `rebuild.html` dành cho luồng nhập Excel và so sánh nghiên cứu của trưởng khoa. Ngưỡng hiển thị ở bảng cặp. Trang `dashboard.html` giữ báo cáo huấn luyện. Luồng khóa luận sử dụng đăng ký từ web làm đầu vào phân công.
- Nội dung đổi theo trạng thái tải, trống, lỗi, sẵn sàng hoặc đã công bố. Bảng dài cuộn trong vùng riêng. Điều khiển có nhãn, focus và trạng thái chờ. Màu xanh và vàng luôn có nhãn văn bản.

## Xác thực và cấu hình

- Cookie OAuth hiện hữu xác thực người dùng. Vai trò được gán từ cặp `provider:subject` trên máy chủ. `subject` là định danh bất biến lưu ở cột `users.subject`, lấy từ bản ghi đã được quản trị viên đối chiếu.
- Đăng ký email tại `login.html?mode=register` tạo tài khoản sinh viên với mật khẩu tối thiểu 12 ký tự. Email đăng ký chưa được xác minh. Tài khoản được cấp qua `UNIMATCH_EMAIL_ACCOUNT_SEED` phải cung cấp mã kích hoạt và đổi mật khẩu trước khi nhận phiên. Cấu hình seed lưu hash, chỉ thêm tài khoản mới và giữ nguyên mật khẩu đã đổi khi deploy lại.
- Ba tài khoản kiểm thử sử dụng kỳ `demo-2026`. Quyền trưởng khoa và liên kết hồ sơ giảng viên của hai tài khoản demo chỉ có hiệu lực trong kỳ thử nghiệm đã cấu hình.
- Biến `UNIMATCH_ROLE_ROSTER` nhận JSON. Mỗi tài khoản giảng viên cần mã `advisor_id` chính xác trong danh mục mô hình, mỗi mã được gắn tối đa một tài khoản. Tài khoản ngoài danh sách được cấp quyền sinh viên. Cấu hình các tài khoản trưởng khoa hiện có trước khi khởi động phiên bản này.

```json
{
  "google:SUBJECT_TRUONG_KHOA": {"role": "dean"},
  "google:SUBJECT_GIANG_VIEN": {"role": "faculty", "advisor_id": "MA_GIANG_VIEN_TRONG_DANH_MUC"}
}
```

- Đặt `UNIMATCH_THESIS_SEMESTER` thành mã kỳ muốn mở, ví dụ `2026.1`. Bỏ trống để đóng workspace khóa luận. Đổi cấu hình cần khởi động lại tiến trình.
- Khi production chưa có cả danh sách vai trò lẫn mã kỳ, server giữ quyền điều phối hiện có cho luồng cũ và đóng đăng ký. Cấu hình danh sách có tài khoản trưởng khoa trước khi mở kỳ.
- API ghi kiểm tra origin và vai trò. API của công cụ nhập Excel, so sánh và huấn luyện yêu cầu vai trò trưởng khoa đối với phiên trình duyệt. Bearer hiện tại vẫn dành cho script cục bộ. Trợ lý tiếp tục dùng API tra cứu riêng với cookie hợp lệ.
- Các tài khoản OAuth ngoài danh sách có thể lưu hồ sơ của mình khi kỳ mở. Việc triển khai cho nhóm sinh viên đã xác minh cần dữ liệu định danh học vụ để áp dụng điều kiện ghi danh.

## Dữ liệu và giao dịch

| Bảng | Khóa | Nội dung |
| --- | --- | --- |
| `thesis_semesters` | Mã kỳ | Ngưỡng mặc định 70, số lần sửa, phương án nháp, phương án công bố |
| `thesis_students` | Kỳ, tài khoản | Phiên bản bài đánh giá, mức tự đánh giá, câu trả lời và kết quả |
| `thesis_requests` | Kỳ, tài khoản, mã giảng viên | Trạng thái nguyện vọng theo cặp |

Schema bổ sung chạy qua `database/portal.sql` trên SQLite và PostgreSQL. Chỉ mục duy nhất có điều kiện bảo đảm mỗi sinh viên có tối đa một yêu cầu `accepted`. Các thay đổi cùng kỳ tuần tự hóa qua cập nhật hàng kỳ trong một giao dịch. Dữ liệu đăng ký, nguyện vọng và báo cáo cũ gắn với khóa riêng của chúng.

- `pending` có thể chuyển thành `accepted`, `rejected` hoặc `withdrawn`.
- Bảng `thesis_preferences` lưu danh sách tối đa ba mã giảng viên theo thứ tự và mô tả đề tài tối đa 2.000 ký tự. Khi một giảng viên nhận, hệ thống rút các yêu cầu đang chờ khác trong cùng giao dịch. Mô tả có thể cập nhật sau khi được nhận, đến lúc công bố.
- `accepted` giữ chỗ. `rejected` lưu lại quyết định và chặn gửi lại cùng người.
- Sửa hồ sơ, nguyện vọng hoặc quyết định làm mất hiệu lực phương án nháp. Đổi ngưỡng chỉ đổi cách đánh dấu các cặp.
- Công bố bằng ID của phương án nháp khả thi hiện hành. Sau công bố, các thao tác sửa kỳ trả HTTP 409.

## Đánh giá và gợi ý

Luồng chọn định hướng, công cụ và nguyện vọng tham khảo [Khảo sát dữ liệu KLTN](https://docs.google.com/forms/d/e/1FAIpQLSeauOjaZdBcQK9-ABrIF8JGsYWz5M7Fhd786710c9G3xXsV0w/viewform).

- `roles-v2` có 22 vai trò, mỗi vai trò 5 câu trắc nghiệm. Sinh viên chọn vai trò trước khi làm bài, tự đánh giá 0–4 và có thể khai báo công cụ đã dùng. Hồ sơ `starter-v1` được đọc tiếp. API chấm điểm ở máy chủ.
- **Điểm mạnh** khi tự đánh giá từ 3 và đúng ít nhất 4/5 câu trong `roles-v2`. **Có tín hiệu từ bài làm** khi đúng ít nhất một câu và chưa đạt nhóm điểm mạnh. **Tự đánh giá** khi có mức tự đánh giá nhưng chưa trả lời đúng. **Chưa đủ tín hiệu** cho các nhóm còn lại.
- Pipeline E4 dùng vai trò đã chọn làm tín hiệu định hướng. Công cụ tự khai chỉ được đưa vào biểu diễn nếu vai trò tương ứng có tín hiệu từ bài làm. Kết quả tự đánh giá và trắc nghiệm hiển thị theo từng vai trò.
- Danh sách gợi ý trả tối đa 5 cặp có điểm dương và có đặc trưng khả dụng. Sắp xếp điểm giảm dần rồi theo mã giảng viên. Gợi ý cá nhân độc lập với chỉ tiêu phân công.
- Nút gợi ý câu hỏi chỉ đưa nhãn kỹ năng vào ô soạn. Sau khi sinh viên gửi, giao diện gọi `POST /api/rebuild/assistant`. Trợ lý dùng nguồn giảng viên đã duyệt theo cấu hình hiện hành.

## Phân công

Gọi `S` là số hồ sơ đã đăng ký, `A` là số đã được nhận, `k` là số giảng viên trong danh sách trưởng khoa chọn. Chia `S − A` thành `k` phần gần đều. Phần dư đi theo thứ tự mã giảng viên. Với mỗi giảng viên, cộng phần được chia vào số chỗ đã nhận để ra chỉ tiêu tổng.

Ví dụ có 10 hồ sơ, ba giảng viên A, B, C và A đã nhận 2. Tám hồ sơ còn lại chia 3, 3, 2. Chỉ tiêu tổng là 5, 3, 2. Hai hồ sơ đã nhận của A vẫn là cặp cố định.

Solver Hungarian hiện hữu tối đa hóa tổng điểm phù hợp dưới các ràng buộc chỉ tiêu và cặp cố định. Khi tối ưu, các nguyện vọng đang chờ được cộng tối đa 0,1 theo ưu tiên, với trọng số lần lượt là 1, 2/3 và 1/3. Điểm hiển thị luôn lấy từ E4. Cặp bị từ chối bị loại khỏi tập ứng viên. Cặp thiếu điểm có thể dùng để hoàn thành phân công khi phù hợp ràng buộc, với điểm hiển thị để trống và nhãn vàng. Nếu không có nghiệm đủ, phương án ghi trạng thái `infeasible` và không thể công bố. Giới hạn mỗi lần tạo phương án là 1.000 sinh viên.

Ngưỡng là số nguyên 0–100, áp dụng điều kiện `100 × E4 ≥ threshold` cho cặp có điểm. Hiển thị giá trị phần trăm và nhãn riêng. E4 chưa hiệu chuẩn xác suất. Phương án theo kỳ dùng Hungarian, còn PPO/DQN và mô phỏng phục vụ so sánh ở luồng Excel.

## API

| Đường dẫn | Quyền | Dữ liệu chính |
| --- | --- | --- |
| `GET /api/auth/me` | Đã đăng nhập | Vai trò và mã giảng viên khi có |
| `GET /api/thesis` | Đã đăng nhập | Trạng thái kỳ, ngưỡng và dữ liệu theo vai trò |
| `GET /api/thesis/catalog` | Đã đăng nhập | Mã và tên giảng viên |
| `GET /api/thesis/recommendations` | Sinh viên | Điểm và danh sách gợi ý của tài khoản |
| `POST /api/thesis/assessment` | Sinh viên | `survey`, `answers` theo mã nhóm kỹ năng |
| `POST /api/thesis/choice` | Sinh viên | `advisor_ids` theo thứ tự, danh sách rỗng để rút, kèm `topic_description` tùy chọn |
| `POST /api/thesis/topic` | Sinh viên | Cập nhật `topic_description` cho nguyện vọng đang chờ hoặc đã nhận |
| `POST /api/thesis/decision` | Giảng viên | `user_id`, `decision` bằng `accepted` hoặc `rejected` |
| `POST /api/thesis/threshold` | Trưởng khoa | `threshold` |
| `POST /api/thesis/proposal` | Trưởng khoa | `advisor_ids`, trả về chỉ tiêu và cặp nháp |
| `POST /api/thesis/publish` | Trưởng khoa | `id` của phương án |
| `POST /api/rebuild/assistant` | Đã đăng nhập | `question`, có thể kèm `previous_question` |

## Kiểm tra tích hợp

Chạy `python -m pytest -q tests/rebuild/test_thesis_portal.py tests/rebuild/test_portal.py tests/rebuild/test_phase7_api.py tests/rebuild/test_phase8_api.py` ở gốc repo. Kiểm tra gói frontend bằng `npm --prefix frontend run check` và `npm --prefix frontend run build`. Khi triển khai, cấu hình đúng kỳ, OAuth, danh sách tài khoản và artifact trước khi thử một lượt đăng ký, duyệt và công bố bằng dữ liệu thử.
