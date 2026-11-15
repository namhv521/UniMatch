# PRD UniMatch Web

Phiên bản 1.1 · 15/11/2026

Đặc tả kỹ thuật đi kèm tại [UniMatch Web Spec](unimatch_web_spec.md).

## Mục tiêu

UniMatch hỗ trợ một đợt đăng ký và phân công hướng dẫn khóa luận theo kỳ. Sinh viên có thể tự đánh giá, đối chiếu kỹ năng với chuyên môn giảng viên và gửi nguyện vọng. Giảng viên chủ động nhận người phù hợp vào nhóm trước. Trưởng khoa rà soát và công bố kết quả cho cả kỳ.

## Vai trò và quyền

| Vai trò | Công việc | Dữ liệu được xem |
| --- | --- | --- |
| Sinh viên | Làm khảo sát, làm trắc nghiệm, hỏi trợ lý, chọn giảng viên | Hồ sơ của mình, danh mục giảng viên, nguyện vọng và kết quả của mình |
| Giảng viên | Xem số sinh viên đăng ký, nhận hoặc từ chối nguyện vọng | Tổng số đăng ký của kỳ, hồ sơ kỹ năng tóm tắt của người đã chọn mình, danh sách nhóm đã công bố |
| Trưởng khoa | Chọn giảng viên tham gia, đặt ngưỡng, tạo phương án và công bố | Tổng số đăng ký, chỉ tiêu theo giảng viên, các cặp trong phương án và báo cáo đối chiếu mô hình |

## Luồng sinh viên

1. Đăng nhập, vào **Khóa luận**, chọn mức tự đánh giá và hoàn thành bài trắc nghiệm.
2. Lưu bài làm để ghi danh vào kỳ. Xem số câu đúng và phân loại từng nhóm kỹ năng. Chọn trong 22 vai trò, mỗi vai trò có 5 câu và danh sách công cụ đã dùng. Hồ sơ ghi nhận mức rõ ràng của ý tưởng khóa luận.
3. Xem tối đa năm giảng viên theo điểm phù hợp. Có thể dùng nút soạn câu hỏi từ hồ sơ kỹ năng để hỏi chatbot về các kỹ năng đã ghi nhận.
4. Chọn từ một đến ba giảng viên theo thứ tự ưu tiên. Mô tả đề tài là tùy chọn, có thể bổ sung sau và hiển thị cho giảng viên đang xem xét. Khi một giảng viên nhận, các yêu cầu còn chờ được rút.
5. Xem giảng viên được phân công sau khi trưởng khoa công bố.

## Luồng giảng viên

1. Xem tổng số sinh viên đã lưu hồ sơ đăng ký kỳ này và số đã nhận.
2. Mở danh sách nguyện vọng gửi đến mình, xem tên và kết quả kỹ năng tóm tắt.
3. Chọn **Nhận hướng dẫn** hoặc **Từ chối**. Một quyết định nhận cộng một chỗ trước khi chia số sinh viên còn lại.
4. Xem nhóm cuối cùng sau công bố. Nhóm gồm các sinh viên đã nhận và các sinh viên được phân bổ bổ sung.

## Luồng trưởng khoa

1. Chọn danh sách giảng viên tham gia. Giảng viên đã nhận sinh viên bắt buộc có mặt.
2. Tạo phương án. Mỗi giảng viên có chỉ tiêu bằng số sinh viên đã nhận cộng số chỗ chia đều từ nhóm còn lại.
3. Đặt ngưỡng tin tưởng theo kỳ. Mặc định 70%. Điểm phù hợp bằng hoặc vượt ngưỡng hiển thị xanh với nhãn **Đạt ngưỡng tin tưởng**. Dưới ngưỡng hiển thị vàng với nhãn **Độ tin tưởng chưa cao**. Cặp thiếu điểm hiển thị vàng với nhãn **Chưa đủ dữ liệu**.
4. Kiểm tra số chỗ, các cặp điểm thấp và trường hợp thiếu dữ liệu. Trưởng khoa xác nhận đã rà soát rồi công bố phương án khả thi. Công bố khóa thay đổi trong kỳ.

## Tiêu chí nghiệm thu

- Đăng nhập bằng cùng cơ chế hiện tại và thấy đúng trang theo quyền. Truy cập API trực tiếp cũng phải tuân theo vai trò.
- Một tài khoản sinh viên lưu nhiều lần vẫn chỉ được tính một đăng ký trong một kỳ.
- Chatbot trả lời về chuyên môn giảng viên qua nguồn đã duyệt. Sinh viên có thể kiểm tra câu hỏi trước khi gửi.
- Giảng viên chỉ xem và quyết định với nguyện vọng gửi đến mã giảng viên gắn với tài khoản mình.
- Mỗi sinh viên có tối đa ba nguyện vọng đang chờ và tối đa một cặp được nhận. Cặp đã nhận xuất hiện đúng trong kết quả. Cặp bị từ chối bị loại khỏi phân công.
- Phương án khả thi phân công đủ mỗi sinh viên một lần và không vượt chỉ tiêu. Nếu ràng buộc xung đột, giao diện hiển thị nguyên nhân nghiệp vụ để trưởng khoa điều chỉnh danh sách.
- Màu đi kèm nhãn văn bản. Người dùng có thể thực hiện khảo sát, duyệt nguyện vọng và đọc bảng trên điện thoại hoặc bằng bàn phím.
- Kết quả công bố chỉ hiển thị cho người liên quan. Thay đổi hồ sơ hoặc nguyện vọng trước công bố buộc tạo lại phương án.

## Phạm vi phiên bản hiện tại

- Một kỳ đang phục vụ, cấu hình ở máy chủ. Dữ liệu từng kỳ được lưu riêng.
- Kết quả trắc nghiệm là chỉ báo nhập môn và hồ sơ kỹ năng khai báo, chưa phải chứng chỉ.
- Ngưỡng dựa trên điểm tương thích của cặp. Khoa có thể sửa ngưỡng cho kỳ trước khi công bố. Độ chính xác thực tế cần dữ liệu xác nhận sau kỳ.
- Phiên bản này dùng đăng nhập OAuth hiện có. Các quyết định học vụ như điều kiện làm khóa luận và xác minh mã sinh viên cần quy trình riêng của khoa.
