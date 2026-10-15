# UniMatch đã triển khai

Cập nhật ngày 16/10/2026. Mã nguồn frontend, backend, database schema và lịch ping nằm trong [namhv521/UniMatch](https://github.com/namhv521/UniMatch).

| Thành phần | Project | Địa chỉ |
|---|---|---|
| Frontend | Vercel `unimatch` | https://unimatch-neu.vercel.app |
| Backend | Render `unimatch-api-20261016` | https://unimatch-api-20261016.onrender.com/api/v1/health |
| Database mới | Neon `unimatch`, Singapore | Project `patient-tree-18935199` |
| Ping | GitHub Actions cùng repo | `.github/workflows/keepalive.yml` |

Tên `unimatch.vercel.app` đã thuộc project khác. Project đã đổi tên thành `unimatch`; domain chính là `unimatch-neu.vercel.app`. Domain `unimatch-web-20261016.vercel.app` chuyển hướng 307 sang domain chính.

## Hợp đồng triển khai

Vercel dùng root `frontend`, chạy `npm ci` và `npm run build`, xuất thư mục `dist`. `frontend/vercel.json` rewrite `/api/*` tới Render. Three.js 0.186.1 được self-host; không gọi CDN thư viện hoặc dịch vụ font khi sử dụng.

Render dùng Python 3.12.12, một worker; build bằng CPU PyTorch và `requirements.txt`. Start:

```sh
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

Biến môi trường: `DATABASE_URL` (URI Neon có TLS), `KLTN_ARTIFACT_BUNDLE=unimatch-20261016-v1`, `KLTN_LOGIN_EMAIL`, `KLTN_LOGIN_PASSWORD`, `KLTN_COOKIE_SECURE=true`, `KLTN_DATABASE_SCHEMA=public`. `KLTN_ALLOWED_ORIGIN` chứa domain chính và domain cũ, phân tách bằng dấu phẩy. Sau thay đổi Origin cần deploy/restart áp dụng cấu hình, rồi thử login thật; tên project không tự cập nhật danh sách Origin.

Không đưa credential, PDF nguồn, hồ sơ hoặc checkpoint vào Git công khai. Bảng `serving_artifacts` giữ bundle inference: 92 file, 6.612.229 byte. `scripts/upload_serving_artifacts.py` tải một phiên bản bất biến lên database khi quản trị viên đã đặt `DATABASE_URL`; `backend/app/artifacts.py` kiểm allowlist đường dẫn và toàn bộ SHA-256 trước khi ghi file. Bundle sai hoặc thiếu khiến khởi động thất bại. MatchingService còn kiểm dimension, split và mapping.

## Kết quả mới nhất

- 197 test Python pass, 1 skipped, 1 warning; 16 test frontend pass; syntax/build pass.
- Health trực tiếp và qua Vercel: healthy, data_loaded=true, quality_ready=true, 38 GV.
- Catalog chưa đăng nhập bị 401; login/session 200; cookie HttpOnly, Secure, SameSite=Strict; Origin ngoài allowlist bị 403.
- Hungarian sample: 3 assignment; real-train: 154; validation: 20; quota violations bằng 0.
- MaskablePPO mẫu: 3 assignment; nghiên cứu validation: 20. Kết quả inference không phải bằng chứng promote RL.
- Workbook template có ba sheet. Workbook tổng hợp 38 SV không cần đề tài phân bổ cho bốn GV với quota 10–10–9–9. Assignment đã đọc lại đúng từ PostgreSQL.
- Neon mới: 1 snapshot, 215 students, 38 advisors, 215 split memberships, 92 artifact. Mốc kiểm chứng có 11 simulation_runs và 2 feedback; số đếm tăng khi sử dụng.
- Checkout sạch khôi phục đủ 92 artifact từ Neon và nạp được 38 GV.

Bằng chứng chi tiết, không chứa credential: `outputs/deployment/unimatch-release.verification.json`. Credential cục bộ nằm ở `outputs/deployment/unimatch-release.credentials.json`, bị Git bỏ qua.

## Đồ họa

Landing dùng WebGL: hai cụm hồ sơ dạng nhân vật, bệ 3D, quỹ đạo, đường cong có hạt sáng và parallax. Đây là minh họa cơ chế kết nối. Matching dùng trace thật: sinh viên đi đến nhóm giảng viên, cột tải tăng theo assignment duy nhất và đường hiện hành được nhấn mạnh. Có xoay/zoom, chọn cột, điều khiển bàn phím, replay, reset, reduced motion và fallback Canvas. Chuyển route thu hồi tài nguyên GPU.

## Ping và giới hạn

Workflow trong UniMatch gọi Render mỗi năm phút và kiểm `data_loaded=true`, có retry và timeout. Timer trong backend không được dùng vì timer cũng dừng khi instance sleep. GitHub Actions có thể chậm hoặc vô hiệu lịch sau thời gian không hoạt động; Render Free có thể restart hoặc hết quota. Ping không phải SLA, không bảo đảm luôn thức. Xem [Render Free](https://render.com/docs/free) và [GitHub schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Session ở RAM có thể mất sau restart. Chưa kiểm tải đồng thời dài hạn, uptime dài hạn hoặc phê duyệt nghiệp vụ học vụ.

Lượt ping thủ công trong UniMatch đã thành công: [38810602340](https://github.com/namhv521/UniMatch/actions/runs/38810602340), job chạy bốn giây. Lịch năm phút đã cấu hình; đây không phải bằng chứng uptime dài hạn.
