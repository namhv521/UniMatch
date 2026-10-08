# Quy trình release nghiên cứu

## Trạng thái hỗ trợ

Release hiện tại nhắm tới **demo/research cục bộ**. Không có tuyên bố production-ready, không có deployment Internet đã xác minh và không có model RL được mặc định promotion chỉ vì checkpoint tồn tại.

## Thành phần release

- source `src/`, `backend/`, `frontend/`;
- curated/feature artifact cần cho serving, được mount read-only khi dùng Docker Compose;
- baseline/benchmark report và figure sinh từ report;
- checkpoint được kiểm hash; checkpoint legacy toy chỉ phục vụ sample;
- tài liệu governance, runbook và báo cáo khóa luận.

Raw PDF, extracted text, cache, credential và runtime SQLite không thuộc release.

## Cổng release

1. **Data:** hash, shape, split 158/21/21/20 và mapping order hợp lệ.
2. **Model:** archive hash đúng; space tương thích; trạng thái promotion rõ.
3. **Backend/security:** test session, same-origin, redaction và error handling pass.
4. **Frontend:** syntax check, unit test và build pass.
5. **Benchmark:** report parse được, mọi row có provenance; figure không chứa số ngoài report.
6. **Container:** image build và container health check pass trên môi trường release.
7. **Human:** rà soát luận văn, dữ liệu, license và phê duyệt chia sẻ.

Thiếu một gate phải ghi blocker; không đổi `production_ready` chỉ để hoàn thành thủ tục.

## Lệnh kiểm tra

```powershell
python -m pytest tests/ -q --basetemp outputs/test-tmp-release
npm --prefix frontend run check
npm --prefix frontend test
npm --prefix frontend run build
python scripts/run_benchmark.py --split validation
python scripts/verify_release.py
```

Docker, khi daemon và mạng khả dụng:

```powershell
docker build -t kltn-dashboard:20261007 .
docker run --rm -p 127.0.0.1:8000:8000 `
  -e KLTN_LOGIN_EMAIL=operator@example.test `
  -e KLTN_LOGIN_PASSWORD=replace-me `
  -e KLTN_COOKIE_SECURE=false `
  kltn-dashboard:20261007
```

Lệnh Docker trên là quy trình dự kiến; chỉ ghi “đã xác minh” khi image build xong và `/api/v1/health` trả thành công. Không dùng mật khẩu ví dụ cho môi trường thật.

## Release manifest

`python scripts/verify_release.py` ghi `outputs/final_validation/release-manifest.json`, gồm source bundle hash, evidence hash, model được promotion, selected engine và limitations. Manifest là ảnh chụp bằng chứng tại thời điểm chạy, không phải chữ ký phát hành và không thay thế Git revision/CI log.

## Chính sách model

- `toy_unpromoted`: chỉ sample, không real dataset.
- `unpromoted_research`: chỉ chế độ nghiên cứu được gắn nhãn.
- `promoted`: cần đủ seed, budget, compatibility gate, quota/coverage gate và provenance.
- Không có candidate đạt gate: selected engine là Hungarian và UI phải nói rõ lý do.

## Rollback

Release phải giữ image/tag trước và manifest tương ứng. Rollback khôi phục đồng bộ code, data/feature artifact và model; không chỉ thay checkpoint. Sau rollback, chạy health và một baseline smoke. Nếu hash không khớp, dừng serving thay vì dùng artifact gần đúng.

## Những gì chưa được xác minh

Evidence cục bộ ngày 2026-10-07: full pytest chốt đạt 120 test pass và 1 cảnh báo; các sửa review được kiểm bằng 51 test trọng yếu. Frontend syntax/unit test đạt 5 test pass. Docker runtime build, authenticated API và browser smoke trong container cuối đã chạy thành công. Xem `docs/final_validation.md` để biết các điều kiện chưa đạt; local pass không phải remote CI hay production approval.

Production deployment, HTTPS proxy, secret manager, backup/restore và vận hành nhiều replica chưa được xác minh. Docker phụ thuộc image/package bên ngoài và phải được ghi theo kết quả thực tế của từng phiên release.
