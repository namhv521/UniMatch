# Thiết kế giao diện

Mode: Operate. Một bàn làm việc học thuật dùng ban ngày trên laptop và màn hình trình chiếu.
Mục tiêu đầu tiên là đọc phân bổ và phát hiện GV đầy quota, không phải trang quảng cáo.

Palette: canvas #f6f7f4, paper #ffffff, ink #172c28, green #174b3b,
muted #66746c, rule #dce1d9. Màu chỉ hỗ trợ, trạng thái luôn có chữ.
Chữ nội dung Segoe UI/system sans để tiếng Việt rõ và offline; tiêu đề Georgia serif.
Layout: header gọn, thanh tác vụ phía trên bảng phân bổ; cột tải giảng viên bên phải.
Mobile gộp một cột; bảng cuộn ngang trong vùng riêng, không làm tràn toàn trang.
Không hero metrics, không gradient, không phụ thuộc font/CDN bên ngoài.
Focus ring rõ; label gắn input; trạng thái loading/error/empty có hướng xử lý.
Tối ưu hệ thống nhỏ: React, CSS native, SVG cho biểu đồ hình học nếu có số liệu thật.
