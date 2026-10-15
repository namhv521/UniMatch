# Triển khai UniMatch ngày 16 tháng 10 năm 2026

## Các project mới

| Thành phần | Project hoặc service | Địa chỉ |
|---|---|---|
| Frontend Vercel | unimatch-web-20261016 | https://unimatch-web-20261016.vercel.app |
| Backend Render Free | UniMatch API 20261016 / unimatch-api-20261016 | https://unimatch-api-20261016.onrender.com |
| Database Neon Free | unimatch-db-20261016 | https://console.neon.tech/app/projects/gentle-math-08514391 |
| Source deployment private | unimatch-deploy-20261016 | https://github.com/namhv521/unimatch-deploy-20261016 |
| Lịch ping public | unimatch-uptime-20261016 | https://github.com/namhv521/unimatch-uptime-20261016/actions |

Các project được tạo mới trong phiên triển khai; không tái sử dụng service hoặc database của dự án khác. Render và Neon cùng region Singapore. Backend dùng Python 3.12.12, CPU PyTorch và một Uvicorn worker. Vercel chỉ xuất bản năm file frontend build; API được rewrite sang Render.

## Kết quả kiểm chứng

- Health trực tiếp và qua Vercel: `data_loaded=true`, `quality_ready=true`, 38 giảng viên.
- Đăng nhập và đọc session qua domain Vercel thành công; cookie có HttpOnly, Secure, SameSite=Strict.
- Request ghi từ origin không được phép bị từ chối HTTP 403; catalog chưa đăng nhập trả 401.
- Hungarian trên real-train trả 154 assignment, không vi phạm quota.
- Recommendation, benchmark summary và tải workbook ba sheet thành công.
- Workbook khảo sát tổng hợp 38 SV phân bổ cho bốn GV có tải 10–10–9–9, không vi phạm quota.
- MaskablePPO sample trả ba assignment; MaskablePPO research trên real-validation trả 20 assignment. Đây là kiểm tra inference, không phải bằng chứng promote model.
- Neon lưu 1 snapshot, 215 students, 38 advisors và 215 split memberships. Lịch sử tăng sau các lượt chạy; mốc kiểm chứng có ít nhất 5 simulation_runs và 1 feedback.
- Bộ kiểm tra liên quan tại source: 84 passed, 1 skipped; frontend 13 passed và build thành công.
- Bản checkout Git đã kiểm tra lại 92 artifact giữ nguyên byte và nạp MatchingService thành công.

Kết quả chi tiết không chứa credential: `outputs/deployment/unimatch-20261016.verification.json`.

## Lịch ping

Workflow `.github/workflows/keepalive.yml` trong repo uptime gọi health Render theo lịch `*/5 * * * *`. Lần chạy thủ công [38791428637](https://github.com/namhv521/unimatch-uptime-20261016/actions/runs/38791428637) thành công trong ba giây. Tại thời điểm ghi nhận này chưa xác minh lượt kích hoạt bằng schedule tự động.

Người dùng đã chọn GitHub Actions và chấp nhận lịch có thể trễ. GitHub có thể vô hiệu schedule của repo public sau thời gian không có hoạt động; cần theo dõi Actions. Ping không bảo đảm uptime hay ngăn restart/giới hạn quota Render. Timer trong backend không được dùng vì sẽ dừng cùng instance đang sleep.

## Quản lý source và secret

Bản triển khai độc lập nằm ở `C:\Su\KLTNv2\deployments\unimatch-20261016`. Repo nguồn công khai không được đưa dữ liệu private lên. `.gitattributes` của deployment giữ nguyên byte dưới `data/`, `outputs/`, `assets/` để tránh CRLF/LF làm sai hash.

Tài khoản đăng nhập ứng dụng dùng email `admin@unimatch.local`. Mật khẩu ngẫu nhiên và URI database được giữ ở file local bị Git bỏ qua: `outputs/deployment/unimatch-20261016.credentials.json`. Không gửi file này vào repo, báo cáo hoặc ảnh chụp màn hình.

Session ở RAM nên restart/redeploy/sleep có thể yêu cầu đăng nhập lại. PostgreSQL giữ snapshot và lịch sử; đây không phải session store. Chưa có bằng chứng tải đồng thời, uptime dài hạn hoặc đầy đủ benchmark trên toàn bộ model cloud.

## Landing page và kiểm chứng cuối

Commit deployment `8facd6b` bổ sung landing đầu tiên sau đăng nhập: xanh lấy cảm hứng từ NEU, đồ thị hai phía chiếu phối cảnh 3D, nhãn hồ sơ minh họa, nút dừng/bật chuyển động và lối vào nhập sinh viên/mô phỏng. Đồ họa minh họa không đại diện kết quả phân bổ. Font Manrope được self-host kèm giấy phép OFL, không thêm package frontend.

Đã kiểm tra trên Chrome ở desktop và mobile 390 px: không tràn ngang, prefers-reduced-motion tạo cảnh tĩnh, nút bật/dừng thay đổi trạng thái, điều hướng vào matching chạy 154 assignment. Syntax check, 13 test frontend và build đều pass sau thay đổi cuối. Lượt HTTP xác nhận lại login/catalog 200 và Hungarian 154 assignment, quota violations 0 được lưu ở `outputs/deployment/final-cloud-check.json`.

Khóa luận Word được tạo mới từ mẫu NEU, cập nhật kiến trúc, benchmark và triển khai; file gốc đề xuất không bị ghi đè. Bản đầy đủ ở `baocao/exports/11236160_HoangVanNam_KhoaLuan_UniMatch.docx`; thông tin giảng viên, lớp, chữ ký và Turnitin cần người viết bổ sung dữ liệu chính thức.
