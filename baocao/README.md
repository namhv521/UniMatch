# Báo cáo khóa luận: Hệ thống hỗ trợ ghép cặp sinh viên – giảng viên

Tài liệu này mô tả bài toán, dữ liệu, phương pháp, kiến trúc và bằng chứng thực nghiệm của hệ thống KLTN Matching. Báo cáo chủ động phân biệt ba mức: **đã hiện thực và có artifact**, **thiết kế đang hoàn thiện**, và **kết quả chưa đủ điều kiện kết luận**.

## Mục lục

1. [Giới thiệu](chapters/01-gioi-thieu.md)
2. [Bài toán và yêu cầu](chapters/02-bai-toan-va-yeu-cau.md)
3. [Cơ sở lý thuyết và công trình liên quan](chapters/03-co-so-ly-thuyet.md)
4. [Dữ liệu, nguồn gốc và quản trị](chapters/04-du-lieu-va-quan-tri.md)
5. [Biểu diễn ngữ nghĩa và ma trận tương thích](chapters/05-bieu-dien-va-tuong-thich.md)
6. [Baseline và tối ưu có ràng buộc](chapters/06-baseline-va-toi-uu.md)
7. [Mô hình MDP, action masking và hàm thưởng](chapters/07-mdp-va-ham-thuong.md)
8. [Các thuật toán RL và vòng đời checkpoint](chapters/08-thuat-toan-rl.md)
9. [Kiến trúc hệ thống và giao diện mô phỏng](chapters/09-kien-truc-va-giao-dien.md)
10. [Thiết kế thực nghiệm và tiêu chí đánh giá](chapters/10-thiet-ke-thuc-nghiem.md)
11. [Kết quả validation và thảo luận](chapters/11-ket-qua-va-thao-luan.md)
12. [Kết luận, giới hạn và hướng phát triển](chapters/12-ket-luan.md)

Tài liệu hỗ trợ:

- [Kịch bản bảo vệ và demo](defense-script.md)
- [Mô tả kỹ thuật toàn bộ mã nguồn và thuật toán](../docs/technical_explanation.md)
- [Kiểm chứng hoàn thiện hiện hành](../docs/completion_validation.md)
- [Hướng dẫn triển khai web](../docs/deployment.md)
- [Quản trị dữ liệu](../docs/data_governance.md)
- [Runbook chạy cục bộ](../docs/runbook/local.md)
- [Quy trình release](../docs/release.md)
- [Lưu trữ Chương 11 của snapshot 220×38 ngày 07/10](archives/11-ket-qua-2026-10-07.md)

## Quy ước bằng chứng

| Nhãn | Ý nghĩa |
|---|---|
| Đã xác minh | Có mã nguồn/artifact và phép kiểm tra tương ứng trong checkout hiện tại |
| Sơ bộ | Có đầu ra đo được nhưng protocol chưa đủ để trả lời câu hỏi nghiên cứu cuối cùng |
| Thiết kế | Mục tiêu hoặc giao diện dự kiến; không đồng nghĩa đã triển khai/chạy thành công |
| Chưa đánh giá | Thiếu benchmark cùng split, seed hoặc protocol; không được suy diễn kết quả |

Các số liệu trong Chương 11 lấy từ `outputs/benchmarks/current-validation.json`: snapshot 215×38, split 154/20/21/20, 35 dòng kết quả và 24 checkpoint đã được kiểm tra. Sáu RL đã được hiện thực nhưng chỉ DQN, MaskablePPO và QR-DQN đủ năm seed × 2 triệu bước; không candidate nào được promote. Hungarian là engine được chọn. Kết quả 220×38 chỉ còn giá trị lịch sử và được lưu riêng.


## Bản hoàn thiện ngày 16/10/2026

Bản hợp nhất theo bố cục bốn chương ở [khoa_luan_20261016.md](khoa_luan_20261016.md). Bản Word và PDF local nằm trong `exports/11236160_HoangVanNam_KhoaLuan_UniMatch_hoan_thien.*`. Bản gốc được giữ nguyên.

Đã tham khảo cấu trúc ba báo cáo trong `data/1.pdfs` và đối chiếu quy định chính thức của FIT NEU. Word dùng A4, Times New Roman 13, giãn dòng 1,3, lề trái 3,5 cm; các lề còn lại 2,5 cm. Mục lục/danh mục/số trang và tham khảo đã cập nhật bằng field Word, rồi xuất PDF để kiểm tra. Còn cần thông tin GVHD, lớp, kỳ/năm học, chữ ký và Turnitin từ nguồn chính thức trước khi nộp.

Bản Word/PDF cuối: 81 trang; nội dung chính 64 trang (PDF trang 14–77), không có field tham chiếu lỗi. Đã thay ảnh landing, matching và ping bằng ảnh Chrome từ topology hiện hành. Mục lục và danh mục hình đã refresh trong Word.
