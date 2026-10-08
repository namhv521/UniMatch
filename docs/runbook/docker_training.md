# Chạy dashboard, PostgreSQL và huấn luyện RL bằng Docker

Stack gồm `dashboard`, `postgres` và service `train` thuộc profile tùy chọn. Việc bật web không tự khởi động huấn luyện. Image chỉ chứa source, frontend đã build và schema; `data/` được mount chỉ đọc, còn `outputs/` và database dùng persistent storage ngoài image.

## Chuẩn bị

Docker Desktop phải đang chạy. Từ thư mục `KLTNv2/KLTN`, tạo file cấu hình local:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Điền `POSTGRES_PASSWORD`, `KLTN_LOGIN_EMAIL` và `KLTN_LOGIN_PASSWORD` bằng giá trị riêng. Mật khẩu PostgreSQL nên dùng ký tự URL-safe vì Compose ghép nó vào `DATABASE_URL`. Không commit `.env`.

Một clone mới không chứa dữ liệu cá nhân hay model. Khôi phục private bundle vào đúng các đường dẫn sau trước khi chạy:

- `data/curated/`
- `data/features/`
- các thư mục nguồn khác dưới `data/` nếu cần audit hoặc rebuild
- `outputs/` nếu cần phục vụ checkpoint/kết quả đã có

Giữ nguyên manifest, mapping, split và checksum trong bundle. Không dùng test/future để train.

## Kiểm tra dữ liệu và training contract

Chạy audit toàn bộ kho dữ liệu trên host:

```powershell
python scripts/audit_data.py
```

Chạy preflight bằng đúng image training:

```powershell
docker compose --profile train run --rm train python scripts/train_real_rl.py --preflight
```

Preflight phải xác nhận toàn bộ sinh viên thuộc split `train`, toàn bộ cột giảng viên, ma trận hữu hạn và provenance hiện tại. Nó không huấn luyện model.

## Khởi động web và PostgreSQL

```powershell
docker compose up --build -d postgres dashboard
docker compose ps
docker compose logs -f dashboard postgres
```

Mở `http://127.0.0.1:8000` hoặc port đã đặt trong `KLTN_WEB_PORT`. PostgreSQL không publish port ra host. Dashboard đợi database healthy, áp dụng schema idempotent và dùng `DATABASE_URL`; phản hồi/runtime được giữ trong database/`outputs` sau khi container được tạo lại.

Dừng stack nhưng giữ database:

```powershell
docker compose down
```

Không dùng `docker compose down -v` nếu chưa chủ động muốn xóa volume database.

## Huấn luyện

Lệnh mặc định chạy toàn bộ thuật toán, seed và budget do `train_real_rl.py` định nghĩa (budget chuẩn là 2.000.000 bước). Đây là tác vụ dài và chỉ chạy khi gọi rõ ràng:

```powershell
docker compose --profile train run --rm train
```

Ví dụ chạy budget nhỏ để kiểm tra wiring:

```powershell
docker compose --profile train run --rm train python scripts/train_real_rl.py --algorithms DQN --seeds 42 --timesteps 16 --output-dir outputs/research-current
```

Theo dõi container đang chạy:

```powershell
docker compose --profile train ps
docker compose --profile train logs -f train
```

Checkpoint mới được ghi vào `outputs/research-current/`. Trainer hiện chạy CPU với cấu hình thuật toán sẵn có; budget hoặc việc hoàn thành training không chứng minh hyperparameter tối ưu hay chất lượng model. Một run ngắn chỉ chứng minh đường đi data → training → checkpoint → API. Sau training, restart dashboard để registry nạp artifact mới:

```powershell
docker compose restart dashboard
docker compose logs --tail 100 dashboard
docker compose exec dashboard python scripts/verify_rl_api.py --base-url http://127.0.0.1:8000
```

## Backup và restore

Tạo PostgreSQL backup dạng custom, sau đó copy ra host:

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
docker compose exec postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/kltn.dump'
docker compose cp postgres:/tmp/kltn.dump ./backups/kltn.dump
```

Restore vào database đang chạy:

```powershell
docker compose stop dashboard
docker compose cp ./backups/kltn.dump postgres:/tmp/kltn.dump
docker compose exec postgres pg_restore --list /tmp/kltn.dump
docker compose exec postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --single-transaction --clean --if-exists /tmp/kltn.dump'
docker compose start dashboard
```

Restore có `--clean` sẽ thay thế các object tương ứng trong database; chỉ chạy khi đã chủ động chọn đúng backup và đã dừng writer. `--list` cho phép kiểm tra nội dung trước, còn `--single-transaction` tránh để lại restore nửa chừng. Backup `data/` và `outputs/` riêng theo chính sách lưu trữ private của dự án. Database không thay thế feature bundle hoặc checkpoint.

## Chuẩn bị push GitHub

Kiểm tra trước khi stage:

```powershell
git status --short
git check-ignore -v .env data/curated/theses.json outputs/research-current/model.zip frontend/dist/index.html
git ls-files data outputs .env
python scripts/check_publish.py
```

`.gitignore` chỉ ngăn file chưa tracked được thêm mới; nó không tự xóa file đã được Git quản lý. Trong thay đổi chuẩn bị publish hiện tại, `data/manual_crawl_queue.csv`, `outputs/data_quality/baseline_manifest.json` và các cache Python đã được loại khỏi Git index nhưng bản local được giữ nguyên. Vẫn phải dùng `git ls-files data outputs '*.pyc'` làm kiểm tra cuối và review bất kỳ kết quả còn lại trước khi commit. Clone từ GitHub sẽ cần private data bundle để audit, train và phục vụ model thật.

## Tài liệu tham khảo

- [Psycopg 3 — Basic module usage](https://www.psycopg.org/psycopg3/docs/basic/usage.html)
- [Docker Compose service reference](https://docs.docker.com/reference/compose-file/services/)
- [PostgreSQL 16 — pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)
- [PostgreSQL 16 — pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html)
