# UniMatch — ghép cặp sinh viên và giảng viên

Dashboard nghiên cứu: đăng nhập, giới thiệu phương pháp, baseline, lựa chọn checkpoint và replay quyết định trên mô phỏng 3D. Frontend native dùng chung origin với FastAPI; không cần cài package npm.

```powershell
python run_dashboard.py --local-demo
```

Mở `http://127.0.0.1:8000`, dùng credential tạm do launcher in tại terminal. Dependency Python và curated/feature artifact phải có; xem [runbook](docs/runbook/local.md).

- [Khóa luận: 12 chương](baocao/README.md)
- [Kịch bản demo/bảo vệ](baocao/defense-script.md)
- [Kiểm chứng và trạng thái task](docs/final_validation.md)
- [Quản trị dữ liệu](docs/data_governance.md)
- [Dữ liệu hiện tại, training RL và PostgreSQL/Docker](docs/training_postgresql_deployment.md)
- [Chạy Docker, backup và chuẩn bị GitHub](docs/runbook/docker_training.md)
- [Release](docs/release.md)
- [Ảnh tham chiếu giao diện v1](docs/ui-reference/matching-ui-v1.png)

Kết quả ngày 2026-10-07 là pilot 8.192 bước × 5 seed mỗi thuật toán, không phải ngân sách 2 triệu bước. Hungarian là engine được chọn; không có RL được promote. Checkpoint cũ 2×2 chỉ dành cho mẫu; checkpoint real38 chỉ chạy qua chế độ nghiên cứu rõ nhãn. Model non-RL chưa có artifact nên bị vô hiệu hóa. Hạn mức GV là giả định thực nghiệm; tập test không được mở trên dashboard.

Không coi bản demo/bản thảo là deployment production hoặc hồ sơ đã được trường phê duyệt. Chưa commit/push các thay đổi phiên này.
