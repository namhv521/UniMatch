# Quản trị dữ liệu và quyền riêng tư

## Phạm vi

Tài liệu này quy định cách lưu, xử lý và phục vụ dữ liệu của KLTN Matching. Mục tiêu là giữ nguồn gốc có thể kiểm toán mà không đưa raw document, PII hoặc secret ra API/artifact công khai.

## Phân loại dữ liệu

| Lớp | Ví dụ | Quyền mặc định | Có thể công khai? |
|---|---|---|---|
| Raw/private | PDF, DOCX, snapshot web, URL nguồn | Chỉ nhóm nghiên cứu được phê duyệt | Không |
| Extracted/private | Văn bản trích xuất, tên, email, ID gốc | Hạn chế; dùng cho curate/audit | Không |
| Curated/restricted | `theses.json`, `advisors.json`, split | Pipeline và reviewer được phép | Không mặc định |
| Derived/research | Ma trận tương thích, manifest, benchmark ẩn danh | Nhóm nghiên cứu | Có điều kiện |
| Public/demo | sample hư cấu, ID `SV-*`, `GV-*` | Người dùng dashboard | Có |

`data/1.pdfs`, `data/raw`, `data/extracted` và cache không được đưa vào image/public release. Dữ liệu derived chỉ được chia sẻ khi không cho phép suy ngược PII theo đánh giá của owner dữ liệu.

## Định danh và tối thiểu hóa

- API dùng ID ẩn danh như `SV-VAL-001` và `GV-001`; không trả mã sinh viên, tên, email hoặc đường dẫn local.
- Evidence công khai dùng hash tham chiếu, không trả URL nguồn.
- Chỉ thu trường cần cho ghép cặp và kiểm toán. Không thêm thuộc tính nhạy cảm vào feature nếu chưa có mục đích, cơ sở pháp lý và phê duyệt.
- Feedback hiện chỉ lưu `mode`, `algorithm`, `helpful` và thời gian; không lưu nội dung tự do.

## Provenance bắt buộc

Mỗi artifact feature/benchmark phải ghi:

- schema và dataset version;
- SHA-256 của dataset, split và feature matrix;
- thứ tự sinh viên/giảng viên hoặc hash thứ tự;
- split, seed, thuật toán và capacity policy;
- checkpoint hash, observation shape và action count nếu có RL.

Không sửa artifact đã công bố. Khi input thay đổi, sinh phiên bản mới và giữ quan hệ `derived_from`.

## Retention và xóa

Raw snapshot được giữ theo chính sách của owner dữ liệu và yêu cầu kiểm toán học thuật. Runtime feedback ở local SQLite có giới hạn 10.000 dòng theo hiện thực hiện tại; owner phải định kỳ xóa database khi kết thúc đợt thử nghiệm. Temporary credential chỉ tồn tại trong process chạy local demo và không được ghi vào tài liệu, ảnh chụp hay Git.

Yêu cầu xóa PII phải được áp dụng cho raw/curated theo thẩm quyền, sau đó sinh lại feature, benchmark và hash phụ thuộc. Không chỉ xóa tên ở frontend trong khi dữ liệu gốc vẫn nằm trong public artifact.

## Truy cập và secret

Hai biến bắt buộc khi chạy credential cố định:

```text
KLTN_LOGIN_EMAIL
KLTN_LOGIN_PASSWORD
```

Không commit giá trị thật vào `.env`, `.env.example`, shell history hoặc log. Cookie phiên do server tạo, có `HttpOnly` và `SameSite=Strict`; bật `KLTN_COOKIE_SECURE=true` khi dùng HTTPS. Chế độ `--local-demo` chỉ được bind loopback và sinh mật khẩu tạm.

## Logging và lỗi

- Không ghi request body chứa tiêu đề đề tài, email hoặc mật khẩu.
- Không trả stack trace, đường dẫn Windows/Linux hoặc nội dung input trong lỗi validation.
- Có thể log mã lỗi, route, timestamp, request ID ẩn danh và thời gian xử lý.
- Không log token cookie.

## Cổng kiểm tra trước khi chia sẻ/release

1. Quét secret và đường dẫn local trong source/output.
2. Kiểm API response không chứa ID gốc, URL nguồn hoặc tên thật.
3. Kiểm `.dockerignore` loại raw, extracted, cache và runtime database.
4. Xác nhận benchmark chỉ dùng ID/chỉ số ẩn danh.
5. Ghi rõ dataset scope, excluded records và coverage chưa biết.
6. Owner dữ liệu phê duyệt artifact định chia sẻ.

## Sự cố dữ liệu

Khi phát hiện rò rỉ: dừng chia sẻ/deploy, lưu bằng chứng tối thiểu không sao chép thêm PII, thu hồi credential/session có thể bị lộ, xác định artifact dẫn xuất, xóa hoặc cô lập bản công khai, sinh lại hash và ghi báo cáo sự cố. Không sửa âm thầm manifest cũ.

## Giới hạn hiện tại

Hệ thống là local research dashboard. Chưa có IAM nhiều vai trò, secret manager, database mã hóa, retention tự động hay đánh giá tác động bảo vệ dữ liệu chính thức. Không triển khai Internet/public production trước khi các kiểm soát này được thiết kế và phê duyệt.

