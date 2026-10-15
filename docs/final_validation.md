# Kiểm chứng và bàn giao — 2026-10-07

> Đây là bằng chứng lịch sử của snapshot 220×38 ngày 07/10. Trạng thái hiện hành 215×38, kết quả benchmark và kiểm chứng đợt 15/10 nằm tại [completion_validation.md](completion_validation.md). Không dùng bảng lịch sử bên dưới như kết quả của snapshot mới.

## Kết quả triển khai

Đã hiện thực luồng đăng nhập → trang chủ → ghép cặp → kết quả; API kiểm phiên phía server, Origin write, cookie HttpOnly; registry kiểm hash, provenance, không gian action/observation và ngân sách thực tế. Mô phỏng 3D dùng tọa độ xyz, xoay/zoom, phát từng event, hạn mức, invalid proposal và fallback. Giao diện giữ bố cục ảnh v1; reward chỉ hiển thị với RL. Không thêm dependency frontend.

Bản thảo khóa luận gồm 12 chương, khoảng 10,9 nghìn từ, công thức, phương pháp, bảng kết quả, giới hạn và kịch bản demo. Năm hình được tạo từ artifact và gắn hash; hình sample 3D được ghi là minh họa, không phải kết quả RL. Không dựng đường hội tụ khi chưa có log.

## Bằng chứng thực nghiệm

Nguồn: `outputs/benchmarks/validation-2026-10-07.json`; validation 21 SV × 38 GV, train 158 SV, seeds 42/123/456/789/1024. Ma trận và split có hash kiểm chứng. Quota uniform-ceiling là giả định, không phải quota chính thức.

| Phương pháp | Tương thích TB | SD giữa seed | Invalid/fallback TB |
|---|---:|---:|---:|
| Hungarian | 0.1034604013 | 0 | 0 |
| Greedy | 0.0921611246 | 0 | 0 |
| DQN pilot + sửa bằng Greedy | 0.0874018853 | 0.0033817453 | 18.2 |
| MaskablePPO pilot | 0.0577374312 | 0.0021821958 | 0 |
| Random | 0.0407430503 | 0.0044219151 | 0 |

Có 10 checkpoint real38, mỗi checkpoint 8.192 bước. Tất cả kết quả cuối sau sửa đáp ứng hạn mức thực nghiệm; DQN thô vẫn có invalid, không được coi là policy hợp lệ. Không thuật toán RL nào vượt gate chất lượng/ngân sách 2M. Legacy checkpoint có observation6/action2 bị loại khỏi benchmark real38 dù metadata cũ gắn hash dữ liệu thật. Hungarian được giữ làm baseline/fallback, không phải model RL được promote.

## Kiểm tra đã chạy

- Full Python trước các sửa review cuối: **113 passed, 1 warning**, 680,91 giây.
- Sau sửa promotion/release/holdout: **51 passed**, 18,45 giây, tập evaluation/real-training/serving/security.
- Hai test mới public CI và release hashing: **2 passed**, 15,54 giây.
- Frontend syntax pass, **5 unit tests pass**, build 4 asset; hash source/dist trùng nhau.
- Browser kiểm desktop/mobile, semantic và research replay; kết quả cuối ghi bổ sung ở mục chốt bên dưới.
- Docker build thành công; container có dữ liệu mount read-only, API smoke trả operational=true, catalog=true, 3 assignments. Kiểm bundle cuối được ghi bổ sung bên dưới.

Gymnasium có một cảnh báo wrapper action_masks; môi trường Python hiện tại có RequestsDependencyWarning do package toàn cục. Không sửa environment toàn cục để che cảnh báo.

## Trạng thái 21 task

Đây là trạng thái hiện hành, không ghi đè bằng chứng lịch sử. “Đã hiện thực” không đồng nghĩa mọi điều kiện vận hành/học thuật đã đạt.

| Task | Trạng thái hiện hành |
|---|---|
| 01–02 | Inventory/schema/layout có artifact; suite data pipeline pass. |
| 03–04 | Crawl/extraction/provenance đã hiện thực và test; vẫn còn nguồn/GV chưa xác minh, không claim crawl đủ. |
| 05 | Quality gate hoạt động fail-closed; subset dùng nghiên cứu, quality_ready=false. |
| 06–07 | Features fit trên train và temporal split có test/hash; chưa chứng minh hồ sơ GV point-in-time không rò rỉ. |
| 08–11 | Domain, env, reward, metrics, Random/Greedy/Hungarian đã hiện thực/test. |
| 12–13 | Training thật/smoke tách biệt, resume/hash/masking được test; pilot 5 seed chạy; full-budget còn thiếu. |
| 14 | Benchmark validation 5 seed và promotion gate đã hiện thực; gate trả KHÔNG promote, là kết quả hợp lệ. |
| 15 | Registry/recommend/research serving đã hiện thực; **production DoD chưa đạt**, thiếu model được phê duyệt và consumer approval artifact. |
| 16–18 | API/UI/integrated flows đã hiện thực/test; non-RL không có artifact nên disabled; real-test khóa khỏi API/UI. |
| 19 | Auth/privacy/quota/feedback guard và tài liệu quản trị có test; chưa chứng minh production security. |
| 20 | Docker/local release đã thực thi; public CI có contract/smoke/build, **remote CI và clean private-data replay chưa xác minh**. |
| 21 | Bản thảo/hình/bảng/demo/manifest đã tạo; **clean-run toàn bộ protocol và duyệt/nộp học thuật còn thiếu**. |

## Cách tái kiểm chứng

Chạy từ `KLTN`, dùng dependency trong requirements và cùng bộ artifact:

```powershell
python -m pytest tests -q -p no:cacheprovider --basetemp outputs/test-tmp-recheck
npm --prefix frontend run check
npm --prefix frontend test
npm --prefix frontend run build
python scripts/run_benchmark.py
python scripts/generate_thesis_figures.py
python scripts/verify_release.py
python run_dashboard.py --local-demo
```

Benchmark load checkpoint cần thời gian import PyTorch ở lần đầu. Browser QA dùng `frontend/qa_browser.py`, credential truyền qua env, không lưu vào source/artifact. CI public kiểm auth/degraded state khi private data vắng mặt; không biến fixture synthetic thành bằng chứng full dataset. Private-data repeat và 2M×5 cần protocol riêng.

## Chốt kiểm chứng bundle

- Full suite chốt: **120 passed, 1 warning**, 208,30 giây.
- Scoped Ruff: **All checks passed**; compileall và git diff --check pass (chỉ có cảnh báo LF/CRLF).
- Review cuối: không còn lỗi code trong phạm vi đã review; production/private-data gates giữ mở.
- Browser QA trong image runtime cuối đã pass semantic/research replay, responsive và lỗi logout; API smoke pass, health degraded/data_loaded=true/38 GV đúng chủ đích. Image chỉ chứa asset frontend runtime, không kèm QA log/source browser. Container QA được dừng sau kiểm tra.
- Manifest bao gồm code/scripts/CI/deployment, dữ liệu thực tế và checkpoint hash; kiểm source/dist để từ chối bundle cũ. Test release hashing chạy lại pass sau thay đổi cuối.

## Điều kiện còn thiếu

1. Quota chính thức và giải quyết nguồn/GV còn thiếu.
2. Full-budget, các algorithm/seed còn thiếu và log hội tụ; frozen model selection trước final test. Không mở tập test trên dashboard để chọn model.
3. Approval artifact hash-bound cho production serving; không tự promote pilot từ benchmark.
4. Clean private-data checkout/replay, remote CI, external deployment/HTTPS/backup.
5. Thông tin bìa, biểu mẫu/chuẩn trích dẫn của trường, người hướng dẫn duyệt và nộp/bảo vệ. Bản Markdown là bản thảo có nội dung, không tự nhận đã được thông qua.

Các thay đổi có sẵn/xóa có sẵn của worktree được giữ nguyên; không restore hàng loạt, không commit/push.
