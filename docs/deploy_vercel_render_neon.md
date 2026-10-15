# Triển khai UniMatch từ một repository

Hướng dẫn hiện hành và bằng chứng nằm tại [cloud_deployment_status.md](cloud_deployment_status.md). Repo duy nhất là `namhv521/UniMatch`; không tạo repo deployment hoặc uptime riêng.

1. Tạo database Neon riêng, giữ URI TLS trong secret backend.
2. Đặt `DATABASE_URL` trong terminal quản trị, rồi upload bundle inference bất biến bằng `python scripts/upload_serving_artifacts.py --source <thư-mục-artifact> --bundle <phiên-bản-mới>`. Không upload thư mục PDF gốc. Script từ chối ghi đè phiên bản có sẵn.
3. Tạo Render Web Service Python từ UniMatch. Cấu hình build/start và các biến trong tài liệu trạng thái. Đặt đúng `KLTN_ARTIFACT_BUNDLE`; backend khôi phục artifact từ PostgreSQL trước khi nạp MatchingService.
4. Tạo Vercel project từ cùng UniMatch, root `frontend`, build `npm run build`, output `dist`. Rewrite trong `frontend/vercel.json` phải trỏ đúng Render service. Đổi tên project và domain là hai thao tác riêng.
5. Cập nhật `KLTN_ALLOWED_ORIGIN` với domain thực, deploy lại và kiểm login, cookie, catalog, matching, upload Excel, lưu và đọc lại database.
6. Bật workflow `.github/workflows/keepalive.yml` trong UniMatch. Kiểm lượt chạy thực và lịch sử schedule; không coi cấu hình cron là bằng chứng uptime.

Credential chỉ nằm trong môi trường backend hoặc file local bị Git bỏ qua. Bản public clone có source và template, không có hồ sơ/checkpoint; để chạy đầy đủ cần bundle được cấp hợp lệ trong database. Để chạy local với dữ liệu sẵn có, xem [runbook/local.md](runbook/local.md).
