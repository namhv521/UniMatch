# Training, API và PostgreSQL

Mục tiêu: kiểm tra toàn bộ dữ liệu hiện có, train RL trên toàn bộ sinh viên tập train với toàn bộ giảng viên, phục vụ checkpoint đúng contract qua API hiện có, đóng gói ứng dụng và PostgreSQL bằng Docker Compose, chuẩn bị GitHub.

## Thiết kế

- Giữ nguyên frontend native và API cùng origin. Không redesign UI.
- Snapshot curated/features đã kiểm tra hash, mapping, split là nguồn đầu vào training/inference. PostgreSQL lưu snapshot, hồ sơ sinh viên/giảng viên, split, lịch sử chạy và feedback. Không lưu checkpoint hoặc ma trận lớn trong database.
- PostgreSQL là service riêng trong Compose; dashboard dùng `DATABASE_URL`, tự áp dụng schema idempotent và nhập snapshot đã được service xác thực. Không có database URL thì local vẫn dùng SQLite feedback hiện có.
- Model nghiên cứu mới dùng thư mục `outputs/research-current`, được registry nhận với provenance của snapshot hiện tại. Không sửa metadata checkpoint cũ để bỏ qua gate. Kết quả luôn chưa promote cho đến khi có đánh giá.
- Script training kiểm tra snapshot trước khi train, dùng toàn bộ hàng train và toàn bộ cột giảng viên; validation chỉ đánh giá, test/future không tham gia train. Budget mặc định 2 triệu bước; có preflight và budget nhỏ cho kiểm tra wiring.
- Image chứa source, scripts, frontend build và schema; dữ liệu, checkpoint, kết quả và PostgreSQL dùng persistent mount/volume. Training là Compose profile opt-in, không chạy khi bật web.
- `.gitignore` loại dữ liệu cá nhân, checkpoint, cache, log, secrets, kết quả sinh tự động; không tự xóa hay untrack file đã được Git quản lý.

## Kiểm chứng

Audit đọc JSON/JSONL, bảng CSV, array NumPy và cấu trúc PDF/archive, phân biệt file hỏng, extraction thất bại, dữ liệu đã cách ly và thiếu trường nghiệp vụ. Chỉ dùng snapshot active nếu kiểm tra serving, split, finite matrix và nguồn training đạt yêu cầu. Thiếu quota chính thức phải được ghi rõ là giả định nghiên cứu.

Kiểm thử gồm preflight training, từ chối resume sai contract, API catalog/dataset/simulate, PostgreSQL persistence nếu Docker khả dụng, frontend syntax/build/test và Compose config. Một run RL ngắn chỉ chứng minh training → checkpoint → API, không chứng minh model tốt hoặc đủ ngân sách. Không tự chạy 2 triệu bước trên máy người dùng.

## Phạm vi và lựa chọn

Tái sử dụng trainer hiện có thay vì tạo framework ML mới. Dùng psycopg trực tiếp thay ORM. PostgreSQL và snapshot file cùng tồn tại: database phục vụ dữ liệu ứng dụng; bundle file bảo đảm training và inference tái lập được. Nếu cần thay snapshot, chạy lại audit, tạo features/contract đồng bộ, train mới và restart web.

Triển khai tự động theo yêu cầu và autonomy directive; không commit/push, không xóa dữ liệu hỏng hay thay đổi các file dirty ngoài phạm vi.
