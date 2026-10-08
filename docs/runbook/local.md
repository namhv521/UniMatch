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

`run_benchmark.py` không tự huấn luyện model. Nó đánh giá baseline và những checkpoint nghiên cứu có trong `outputs/research-real`, đồng thời ghi các checkpoint bị từ chối. `verify_release.py` tạo manifest evidence nhưng cố ý giữ `production_ready=false` cho đến khi các gate bên ngoài được hoàn thành.

## Lỗi thường gặp

| Hiện tượng | Nguyên nhân/cách xử lý |
|---|---|
| `Set KLTN_LOGIN_EMAIL...` | Thiếu credential; đặt hai biến hoặc dùng `--local-demo` |
| `auth_not_configured` | Backend khởi động ngoài launcher mà chưa có hai biến bắt buộc |
| `origin_rejected` | POST không gửi Origin cùng host hoặc origin chưa được cấu hình |
| `serving artifacts failed...` | Hash/shape/split/order không khớp; không bỏ kiểm tra, sinh lại artifact đúng quy trình |
| Model không chạy real validation | Checkpoint toy 6×2 hoặc chưa được registry cho phép; dùng sample hoặc huấn luyện lại 114×38 |
| Thiếu benchmark RL | Đây là trạng thái hợp lệ; dùng Hungarian và ghi “chưa promotion”, không giả số |
