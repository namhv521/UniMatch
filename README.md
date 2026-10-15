# UniMatch — ghép cặp sinh viên và giảng viên

Dashboard nghiên cứu: đăng nhập, giới thiệu phương pháp, baseline, lựa chọn checkpoint và replay quyết định trên mô phỏng 3D. Frontend native dùng chung origin với FastAPI; cài dependency frontend bằng `npm --prefix frontend ci` trước khi build.

```powershell
python run_dashboard.py --local-demo
```

Mở `http://127.0.0.1:8000`, dùng credential tạm do launcher in tại terminal. Dependency Python và curated/feature artifact phải có; xem [runbook](docs/runbook/local.md).

Local mặc định dùng SQLite để lưu snapshot, sinh viên/GV, split, lịch sử phân bổ và feedback; không cần Docker. Đặt `DATABASE_URL` để dùng adapter PostgreSQL. Giai đoạn hiện tại ưu tiên local; FE Vercel và BE Render là phương án triển khai sau, database cloud chưa chọn.

Trang **Nhập sinh viên** nhận Excel kỹ năng, cho tích chọn GV tham gia và phân bổ cân bằng theo nhóm đã chọn: **38 SV / 4 GV = 10–10–9–9**. Xem [hướng dẫn nhập và chia quota](docs/student_cohort_upload.md); Excel mẫu nằm tại [assets/student-skills-template.xlsx](assets/student-skills-template.xlsx) và tải trực tiếp trong trang sau đăng nhập.

- [Khóa luận: 12 chương](baocao/README.md)
- [Kịch bản demo/bảo vệ](baocao/defense-script.md)
- [Kiểm chứng và trạng thái task](docs/final_validation.md)
- [Kiểm chứng đợt hoàn thiện 15/10/2026](docs/completion_validation.md)
- [Mô tả chi tiết source, FE/BE/API/database và thuật toán](docs/technical_explanation.md)
- [Triển khai web HTTPS với PostgreSQL](docs/deployment.md)
- [Quản trị dữ liệu](docs/data_governance.md)
- [Dữ liệu hiện tại, training RL và PostgreSQL/Docker](docs/training_postgresql_deployment.md)
- [Chạy Docker, backup và chuẩn bị GitHub](docs/runbook/docker_training.md)
- [Release](docs/release.md)
- [Ảnh tham chiếu giao diện v1](docs/ui-reference/matching-ui-v1.png)

Snapshot hiện tại: **215 sinh viên/đề tài × 38 giảng viên**, split **154/20/21/20**. Benchmark tái chạy ngày 15/10/2026 có 35 dòng kết quả và đánh giá 24 checkpoint; một số thuật toán đã có năm seed 2 triệu bước nhưng chưa qua gate. **Hungarian vẫn được chọn; chưa có RL được promote.** Xem bảng kết quả và giới hạn tại Chương 11 và tài liệu kiểm chứng mới.

Source có Random, Greedy, Hungarian và sáu thuật toán RL: MaskablePPO, DQN, QRDQN, TRPO, ARS, RecurrentPPO. TQC bị chặn do action space không phù hợp. Checkpoint cũ 2×2 chỉ dành cho mẫu; checkpoint real38 chỉ chạy qua chế độ nghiên cứu rõ nhãn. Model non-RL chưa có artifact nên bị vô hiệu hóa. Hạn mức GV là giả định thực nghiệm; tập test không được mở trên dashboard.

Triển khai production dùng `docker-compose.yml` kết hợp `docker-compose.production.yml`: Caddy HTTPS, FE/API cùng origin và PostgreSQL trong mạng nội bộ. Cần domain/hosting thật và bộ private artifact; clone Git không tự chứa dữ liệu/checkpoint. Trạng thái Docker/runtime/public deployment được ghi rõ trong tài liệu kiểm chứng, không suy ra từ file cấu hình.

Không coi bản demo/bản thảo là deployment production hoặc hồ sơ đã được trường phê duyệt. Chưa commit/push các thay đổi phiên này.

## Bản triển khai hiện hành

Ứng dụng: https://unimatch-neu.vercel.app. FE Vercel, API Render và Neon được cấu hình từ một repository `namhv521/UniMatch`; lịch ping nằm trong `.github/workflows/keepalive.yml`. Xem [trạng thái và bằng chứng triển khai](docs/cloud_deployment_status.md).

Frontend dùng Three.js 0.186.1 tự phục vụ. Trước khi build chạy `npm --prefix frontend ci`, sau đó `npm --prefix frontend run build`. Bộ inference private được nạp từ PostgreSQL, không được công bố trong Git.
