# Triển khai UniMatch trên máy chủ web

Stack production gồm một container FastAPI phục vụ cả frontend và API cùng origin, PostgreSQL 16 lưu lịch sử, và Caddy kết thúc HTTPS. Cấu hình này dành cho một máy chủ Linux có domain. Không cần cài thêm dependency vào ứng dụng.

## 1. Điều kiện triển khai

- Docker Engine và Docker Compose.
- Domain có bản ghi `A` trỏ tới IPv4 máy chủ. Chỉ tạo bản ghi `AAAA` khi máy chủ nhận được IPv6 công khai.
- Firewall cho phép TCP 80, TCP 443 và UDP 443. Caddy cần TCP 80/443 để cấp và gia hạn chứng chỉ tự động.
- Thư mục `data/` chứa snapshot đã kiểm chứng và `outputs/` chứa checkpoint/benchmark phù hợp. Các thư mục này không nằm trong image và không được tự sinh từ clone công khai.
- Tối thiểu một bản sao lưu database trước mỗi lần nâng cấp có thay đổi dữ liệu.

Ứng dụng hiện lưu phiên đăng nhập trong bộ nhớ của tiến trình FastAPI. Chạy đúng một replica `dashboard`; restart sẽ đăng xuất các phiên đang mở. PostgreSQL và chứng chỉ TLS vẫn được giữ trong named volume.

Runtime trong image dùng UID/GID `10001`. Trên máy chủ Linux, chuẩn bị quyền cho bind mount trước lần chạy đầu:

```bash
sudo install -d -o 10001 -g 10001 outputs
sudo find data -type d -exec chmod a+rX {} +
sudo find data -type f -exec chmod a+r {} +
```

Không đổi chủ sở hữu `data/`; container chỉ đọc thư mục này. Nếu `outputs/` đã chứa artifact, bảo đảm UID `10001` có quyền ghi mà không xóa hoặc tạo lại artifact.

## 2. Tạo cấu hình bí mật

Tại thư mục repository:

```bash
cp .env.example .env
chmod 600 .env
```

Điền các giá trị sau trong `.env`:

```dotenv
POSTGRES_DB=kltn
POSTGRES_USER=kltn
POSTGRES_PASSWORD=<mat-khau-database-dai-va-url-safe>
KLTN_LOGIN_EMAIL=<email-dang-nhap>
KLTN_LOGIN_PASSWORD=<mat-khau-dang-nhap-dai>
KLTN_DOMAIN=kltn.example.edu.vn
KLTN_WEB_PORT=8000
```

Không thêm `http://`, `https://` hoặc path vào `KLTN_DOMAIN`. Không commit `.env`. `KLTN_WEB_PORT` chỉ mở dashboard trên loopback máy chủ để chẩn đoán; người dùng truy cập qua HTTPS ở Caddy.

`docker-compose.production.yml` là override được merge sau file gốc. Compose giữ mapping loopback `127.0.0.1:$KLTN_WEB_PORT:8000` của `dashboard` và thêm cổng công khai 80/443 của `proxy`. Mapping loopback không mở API trực tiếp ra Internet; đổi `KLTN_WEB_PORT` nếu cổng đó đã được dùng trên máy chủ.

## 3. Kiểm tra cấu hình trước khi chạy

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.production.yml build dashboard
```

Lệnh `config` phải kết thúc với exit code 0. Không dùng output cấu hình đầy đủ trong log công khai vì output đó chứa credential đã render.

## 4. Khởi động

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d postgres dashboard proxy
docker compose -f docker-compose.yml -f docker-compose.production.yml ps
```

`postgres` và `dashboard` phải chuyển sang `healthy`; `proxy` phải ở trạng thái `Up`. Lần cấp chứng chỉ đầu cần DNS đã cập nhật và cổng 80/443 truy cập được từ Internet.

Kiểm tra từ máy khác:

```bash
curl --fail --show-error https://kltn.example.edu.vn/api/v1/health
curl --fail --show-error --head https://kltn.example.edu.vn/
```

Health phải trả HTTP 200. `data_loaded=true` và `total_advisors=38` chứng minh bundle hiện tại được nạp; `status=degraded` vẫn có thể đúng khi quality/release gate chưa đạt. Health không chứng minh model đã được promote.

## 5. Kiểm tra PostgreSQL và persistence

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T postgres \
  sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T postgres \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM snapshots"'
```

Đăng nhập trên web, chạy một mô phỏng, restart riêng `dashboard`, rồi kiểm tra dữ liệu vẫn có trong PostgreSQL. Phiên đăng nhập sẽ hết sau restart vì session hiện nằm trong RAM.

## 6. Backup và restore

Tạo backup ngoài named volume:

```bash
mkdir -p backups
docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "backups/kltn-$(date +%Y%m%d-%H%M%S).dump"
```

Kiểm tra file backup có kích thước lớn hơn 0 và sao chép sang nơi lưu trữ khác. Restore ghi vào database đích; chỉ chạy sau khi xác nhận đúng file và đúng máy chủ:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml stop dashboard
cat backups/kltn-YYYYMMDD-HHMMSS.dump | \
  docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T postgres \
  sh -c 'pg_restore --list' > backups/restore-contents.txt
# Kiểm tra danh sách trước khi tiếp tục. Dừng mọi writer khác nếu có.
cat backups/kltn-YYYYMMDD-HHMMSS.dump | \
  docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T postgres \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --single-transaction --clean --if-exists'
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d dashboard
docker compose -f docker-compose.yml -f docker-compose.production.yml ps
curl --fail --show-error https://kltn.example.edu.vn/api/v1/health
```

Chỉ khởi động lại dashboard sau khi `pg_restore` kết thúc thành công. Sau restore, kiểm tra snapshot, số sinh viên/GV và một lượt phân bổ qua API. Các lệnh trên dành cho Bash trên máy chủ Linux.

## 7. Cập nhật và rollback

Trước cập nhật, ghi lại Git commit/image tag và tạo backup. Sau đó:

```bash
git pull --ff-only
docker compose -f docker-compose.yml -f docker-compose.production.yml build dashboard
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d dashboard proxy
docker compose -f docker-compose.yml -f docker-compose.production.yml ps
```

Rollback bằng commit/image đã ghi lại, chạy lại stack, rồi kiểm tra health và một request đăng nhập/mô phỏng. Không rollback riêng code khi data, feature và checkpoint thuộc contract khác.

## 8. Chẩn đoán

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml logs --tail 200 dashboard
docker compose -f docker-compose.yml -f docker-compose.production.yml logs --tail 200 proxy
docker compose -f docker-compose.yml -f docker-compose.production.yml logs --tail 200 postgres
```

- Caddy không cấp chứng chỉ: kiểm tra DNS, firewall và cổng 80/443.
- POST trả `origin_rejected`: xác nhận URL trình duyệt là `https://$KLTN_DOMAIN` và cấu hình render có `KLTN_ALLOWED_ORIGIN` tương ứng.
- Đăng nhập thành công nhưng cookie không được lưu: chỉ truy cập HTTPS; production đặt `KLTN_COOKIE_SECURE=true`.
- Dashboard không healthy: kiểm tra data bundle, quyền đọc `data/`, quyền ghi `outputs/` và kết nối PostgreSQL.
- PostgreSQL lỗi sau đổi password: named volume giữ user/password từ lần khởi tạo đầu. Đổi credential bằng quy trình PostgreSQL, không xóa volume production.

Không chạy `docker compose down -v` trên production; tùy chọn `-v` xóa database và dữ liệu chứng chỉ trong named volume.

## Tài liệu nền tảng

- [Docker Compose production](https://docs.docker.com/compose/how-tos/production/)
- [Docker Compose merge rules](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Caddyfile environment variables](https://caddyserver.com/docs/caddyfile/concepts#environment-variables)
- [Caddy reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
