# Runbook chạy cục bộ

## Điều kiện

- Chạy từ thư mục `KLTN`.
- Python 3.12 và dependency trong `requirements.txt` đã được cài.
- Các thư mục `data/curated`, `data/features` và artifact cần thiết tồn tại.

## Cách 1: local demo trên loopback

```powershell
python run_dashboard.py --local-demo
```

Launcher bind `127.0.0.1:8000`, in email demo và mật khẩu tạm ra terminal. Mật khẩu chỉ dùng cho process hiện tại. Mở `http://127.0.0.1:8000`. Không chụp/chia sẻ terminal có mật khẩu.

Không dùng `--local-demo` với `--host 0.0.0.0`; launcher chủ động từ chối vì credential tạm chỉ dành cho loopback.

## Cách 2: credential do người vận hành cấu hình

```powershell
$env:KLTN_LOGIN_EMAIL = "operator@example.test"
$env:KLTN_LOGIN_PASSWORD = Read-Host "Mật khẩu"
$env:KLTN_COOKIE_SECURE = "false"
python run_dashboard.py
```

`KLTN_LOGIN_EMAIL` và `KLTN_LOGIN_PASSWORD` là bắt buộc. `KLTN_COOKIE_SECURE=false` chỉ phù hợp HTTP loopback. Khi phục vụ sau HTTPS reverse proxy, đặt `true` và cấu hình origin được phép.

## Kiểm tra sức khỏe

Trong terminal khác:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Phản hồi cần có `data_loaded=true` và `total_advisors=38`. `status=degraded` là cảnh báo có chủ đích khi quality gate hoặc bằng chứng release chưa đầy đủ; không được đổi thành `healthy` chỉ để qua demo. Health endpoint không chứng minh benchmark/model đã được promotion; xem catalog sau khi đăng nhập.

## Database local

Khi không đặt `DATABASE_URL`, ứng dụng dùng SQLite sẵn trong Python tại `outputs/runtime/feedback.sqlite3`. Startup nhập snapshot/sinh viên/GV/split và các request phân bổ/feedback được lưu bền vững. Khởi động lại không xóa lịch sử; phiên đăng nhập RAM sẽ mất và cần đăng nhập lại.

Nếu environment đang có `DATABASE_URL` nhưng bạn muốn SQLite cho phiên terminal hiện tại:

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
python run_dashboard.py --local-demo
```

Kiểm tra số bản ghi:

```powershell
python -c "import sqlite3; c=sqlite3.connect('outputs/runtime/feedback.sqlite3'); print({t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('snapshots','students','advisors','split_memberships','simulation_runs','feedback')}); c.close()"
```

Backup bằng API SQLite để có snapshot nhất quán, kể cả khi ứng dụng đang chạy:

```powershell
python -c "from pathlib import Path; import sqlite3; Path('backups').mkdir(exist_ok=True); s=sqlite3.connect('outputs/runtime/feedback.sqlite3'); d=sqlite3.connect('backups/local-backup.sqlite3'); s.backup(d); d.close(); s.close()"
```

Chọn tên backup mới nếu cần giữ nhiều phiên bản. Không commit database/backup/credential. PostgreSQL vẫn được hỗ trợ qua `DATABASE_URL`; chưa cài lại PostgreSQL hay chọn database cloud trong đợt local này.

## Dừng

Nhấn `Ctrl+C` tại terminal launcher. Session in-memory mất khi process dừng; credential tạm của `--local-demo` không được tái sử dụng.

## Chạy kiểm tra trọng yếu

```powershell
python -m pytest tests/rl/test_real_training_contract.py tests/serving/test_matching_service.py tests/security/test_api_security.py -q --basetemp outputs/test-tmp-local
npm --prefix frontend run check
npm --prefix frontend test
npm --prefix frontend run build
```

Chỉ báo cáo “pass” sau khi đọc exit code 0 ở máy hiện tại. Nếu frontend chưa build, launcher có thể dùng source fallback; release vẫn phải build `frontend/dist` trước khi đóng gói.

## Tạo benchmark và release manifest

```powershell
python scripts/run_benchmark.py --split validation
python scripts/verify_release.py
```

`run_benchmark.py` không tự huấn luyện model. Nó đánh giá baseline và những checkpoint nghiên cứu có trong `outputs/research-current`, ghi `outputs/benchmarks/current-validation.json`, đồng thời ghi các checkpoint bị từ chối. `verify_release.py` tạo manifest evidence nhưng cố ý giữ `production_ready=false` cho đến khi các gate bên ngoài được hoàn thành. Thiếu benchmark hiện hành sẽ được ghi rõ `benchmark_status=missing`, không suy diễn engine đã được chọn.

## Lỗi thường gặp

| Hiện tượng | Nguyên nhân/cách xử lý |
|---|---|
| `Set KLTN_LOGIN_EMAIL...` | Thiếu credential; đặt hai biến hoặc dùng `--local-demo` |
| `auth_not_configured` | Backend khởi động ngoài launcher mà chưa có hai biến bắt buộc |
| `origin_rejected` | POST không gửi Origin cùng host hoặc origin chưa được cấu hình |
| `serving artifacts failed...` | Hash/shape/split/order không khớp; không bỏ kiểm tra, sinh lại artifact đúng quy trình |
| Model không chạy real validation | Checkpoint toy 6×2 hoặc chưa được registry cho phép; dùng sample hoặc huấn luyện lại 114×38 |
| Thiếu benchmark RL | Đây là trạng thái hợp lệ; dùng Hungarian và ghi “chưa promotion”, không giả số |
