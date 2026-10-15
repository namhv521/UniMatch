# Kế hoạch hoàn thiện UniMatch/KLTN

**Mục tiêu:** sửa lỗi tái hiện được, kiểm chứng FE–API–database–thuật toán và bàn giao mã nguồn, cấu hình triển khai HTTPS, tài liệu kỹ thuật chi tiết.

**Kiến trúc:** giữ frontend native và FastAPI cùng origin; PostgreSQL lưu snapshot, thực thể, split, lượt chạy và phản hồi; phiên đăng nhập nằm trong bộ nhớ một process. Docker Compose chạy ứng dụng/database; reverse proxy kết thúc TLS. Giữ giao diện v1, dữ liệu riêng tư ngoài Git/image, tập test khóa khỏi dashboard.

**Phạm vi:** sửa tại `C:/Su/KLTNv2/KLTN`; bảo toàn các thay đổi có sẵn. Không tự công bố dữ liệu riêng tư hay tạo dịch vụ trả phí. Không tự gắn nhãn RL được duyệt khi chưa qua gate. Triển khai công khai cần đích hosting/domain thực tế.

## Các phần việc và kiểm chứng

- [x] API/database: test auth/Origin/cookie/storage, custom PostgreSQL schema; SQLite local đầy đủ và live API→SQL readback. PostgreSQL thật chưa chạy do môi trường.
- [x] Frontend: check/test/build và browser QA desktop/mobile trên bản local thật, giữ giao diện v1.
- [x] Thuật toán và artifact: preflight dữ liệu, benchmark 35 dòng/24 checkpoint, registry/catalog và release regression pass.
- [x] Deploy: Compose HTTPS render pass; runbook backup/restore và điều kiện hosting đã có. Docker Engine không phản hồi; public deploy hoãn theo lựa chọn local của người dùng.
- [x] Tài liệu: bản đồ source, kiến trúc, API, schema DB, thuật toán, lệnh chạy, kết quả thực tế và giới hạn; báo cáo 12 chương đồng bộ snapshot mới.
- [x] Tích hợp: full pytest 156 passed/1 skipped, frontend 9/9, Ruff/compileall/diff check pass, live API/browser/SQLite backup pass; manifest 104 source hash và bốn runtime asset đã kiểm tra lại.

## Điểm cần rà soát

1. Thiếu private artifact phải báo degraded rõ ràng.
2. Sai hash/split hoặc checkpoint cũ không được phục vụ như model thật.
3. Hết phiên, API lỗi, lỗi database không được hiển thị thành thành công.
4. HTTPS proxy phải khớp cookie Secure và Origin; DB không mở port ra Internet.
5. Tài liệu/release phải dùng snapshot hiện hành thay vì số liệu lịch sử.

## Phân công

API/storage, frontend và deployment có ba phạm vi file độc lập. Agent chính sở hữu `src`, release tooling, tài liệu tổng hợp và kiểm chứng tích hợp. Không commit/push tự động vì worktree đang có thay đổi có sẵn.

## Cập nhật phạm vi từ người dùng

Người dùng chọn local trước; sau này FE Vercel, BE Render, database chưa quyết định. Docker Engine không phản hồi. Bộ PostgreSQL 18 có sẵn thiếu `initdb.exe`/`createdb.exe`; các binary còn lại lỗi `STATUS_DLL_NOT_FOUND`. Không sửa cluster cũ hoặc cài lại toàn hệ thống. Hoàn thiện adapter SQLite sẵn có để local lưu đủ snapshot/thực thể/split/lượt chạy/feedback bằng standard library, giữ adapter PostgreSQL cho giai đoạn sau. Thêm regression migration giữ feedback cũ và kiểm chứng persistence thật qua API.
