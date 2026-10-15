# UniMatch
<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
Người điều phối đợt khóa luận cần nhập khảo sát năng lực sinh viên, chọn giảng viên tham gia và xem phương án phân bổ. Người nghiên cứu so sánh thuật toán và xem trace.

## Product Purpose
Hỗ trợ phân bổ sinh viên và giảng viên theo tương thích nội dung và quota, có provenance và kết quả giải thích được. Người có thẩm quyền phê duyệt quyết định cuối.

## Capabilities and Constraints
Frontend HTML CSS JavaScript hiện có, Vercel static; FastAPI Render; PostgreSQL Neon. Không thêm framework; Three.js 0.186.1 là dependency 3D duy nhất. Hungarian đang được chọn, không RL nào được promote. Số liệu phải đến từ API. Chế độ non RL scorer chưa có artifact nên không được mô tả như tính năng hoạt động.

## Brand Commitments
Người dùng yêu cầu trang đầu sau đăng nhập thành landing page đẹp, có 3D và hiệu ứng, phù hợp đề tài; màu chủ đạo xanh như website Đại học Kinh tế Quốc dân. Phạm vi thay đổi gồm landing page và mô phỏng matching 3D; giữ hợp đồng đăng nhập, nhập Excel và kết quả.

## Evidence on Hand
Snapshot 215 hồ sơ và 38 giảng viên; tập train 154. Benchmark validation 20 sinh viên. Live Vercel Render Neon đã kiểm chứng ngày 16/10/2026. Đồ họa landing là minh họa cơ chế kết nối, không phải kết quả phân bổ.

## Accessibility & Inclusion
Hỗ trợ mobile, bàn phím, focus rõ và prefers-reduced-motion. Hoạt ảnh trang trí có thể dừng. Nội dung thiết yếu là HTML, không phụ thuộc canvas.
