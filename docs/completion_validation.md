# Kiểm chứng hoàn thiện KLTN — 15/10/2026

## Kết quả và phạm vi

Đã sửa các lỗi tái hiện được, giữ source FE/BE/API/database/thuật toán trong repository hiện có, bổ sung cấu hình HTTPS và mô tả kỹ thuật chi tiết. **Chưa xác minh triển khai Internet và chưa đạt mọi điều kiện kết thúc nghiên cứu/học thuật.** Không tạo URL public, không push/commit hay công bố private data trong đợt này.

- [Mô tả source, kiến trúc, API, database, thuật toán](technical_explanation.md)
- [Deploy HTTPS, backup/restore, rollback](deployment.md)
- [Bản thảo khóa luận](../baocao/README.md)
- [Kế hoạch và phạm vi thay đổi](superpowers/plans/2026-10-15-web-completion.md)

## Bản local đang chạy

Dashboard: **http://127.0.0.1:8000**, bind loopback. Thông tin đăng nhập tạm của instance này nằm trong `outputs/runtime/local-web-20261015.json` (file riêng tư đã bị Git ignore). Không công bố file này. Database local: `outputs/runtime/feedback.sqlite3`.

SQLite đã nạp **1 snapshot, 215 sinh viên, 38 GV, 215 split membership**. Live API smoke chạy sample 3 assignment, Hungarian real-train 154 assignment, MaskablePPO research validation 20 assignment, recommend top-3, benchmark 35 row, feedback test có nhãn `smoke_test`, khóa holdout và thu hồi phiên sau logout. Đọc lại database bằng connection mới xác nhận thêm **3 simulation run và 1 feedback**, `PRAGMA integrity_check=ok`. Đây là request kiểm chứng, không phải preference của chuyên gia. Artifact: `outputs/final_validation/local-smoke-2026-10-15.json` và script tái kiểm chứng cùng tên `.py`.

Browser QA chạy lại trên instance thật tại cổng 8000 sau khi hoàn thiện SQLite và pass desktop/mobile. Instance được giữ chạy để người dùng kiểm tra. Lượt full suite cuối sau thay đổi SQLite: **156 passed, 1 skipped, 1 warning**, **93,07 giây**, lưu tại `outputs/final_validation/pytest-local-2026-10-15.xml`. Skip duy nhất là PostgreSQL integration tùy chọn; SQLite thật đã được kiểm chứng riêng.

Backup SQLite bằng `Connection.backup()` đã được mở lại độc lập: integrity `ok`, đủ 215 sinh viên, 38 GV và sáu lượt phân bổ sau smoke/browser QA. File backup riêng tư nằm tại `outputs/final_validation/local-db-backup-2026-10-15.sqlite3`; kết quả kiểm tra `.json` cùng tên. Chưa dùng bản backup để ghi đè database đang chạy.

## Lỗi được tái hiện và sửa

| Lỗi | Nguyên nhân và cách sửa | Bằng chứng |
|---|---|---|
| `pytest` báo 23 lỗi collection/WinError 5 | Quét vào thư mục output test cũ bị khóa; thêm `pytest.ini`, chỉ collect `tests` | Lần chạy đầu fail 23 lỗi; suite sau cấu hình chạy thành công |
| Release đọc kết quả ngày 07/10 và bỏ sót artifact hiện tại | Đường dẫn benchmark/checkpoint hardcode; đổi sang `current-validation` và hash `research-current`, DB schema, cấu hình HTTPS | Hai regression test release đã RED rồi GREEN |
| CLI benchmark mặc định ghi vào report lịch sử | Default output/checkpoint còn trỏ snapshot cũ; đồng bộ với artifact API đang đọc | Benchmark mới có 35 row/24 checkpoint, provenance hiện hành |
| PostgreSQL custom schema chưa tồn tại | `SET search_path` trước tạo schema; tạo schema có tên đã validate trước khi dùng | Regression storage đã RED rồi GREEN; unit security/storage pass |
| Kéo/xoay canvas bị kẹt hoặc bị touch thứ hai chiếm | Drag không gắn pointer và không hủy khi gián đoạn; gắn pointerId, xử lý cancel/lost capture/blur | Hai regression frontend RED rồi GREEN; 9/9 unit test pass |
| Catalog nói RL research unavailable dù có model hợp lệ | Giá trị `available=false` hardcode; tính từ checkpoint hợp lệ trong registry | Regression catalog RED rồi GREEN |
| Local không lưu dữ liệu/lịch sử phân bổ | SQLite chỉ hiện thực feedback, `initialize`/`add_run` là no-op; thêm schema và persistence sáu bảng, giữ feedback cũ | 4 regression RED rồi GREEN; API→SQLite live readback và browser pass |

Các thay đổi có sẵn trước phiên được giữ lại: FE kết nối real-train/checkpoint/benchmark, bảng kết quả, QA và service integrity. Không restore hàng loạt và không xóa dữ liệu/output cũ để che lỗi collection.

## Kiểm chứng phần mềm

Lượt trước khi bổ sung SQLite đầy đủ: **152 passed, 1 skipped, 1 warning**, 239,37 giây, lưu trong `outputs/final_validation/pytest-2026-10-15.xml`. Sau điều chỉnh trạng thái thiếu benchmark theo review, hai regression test release được chạy lại: **2 passed**. Lượt cuối với SQLite là **156 passed, 1 skipped** như mục bản local ở trên; storage/security riêng **29 passed, 1 skipped**.

- `npm --prefix frontend run check`: pass.
- `npm --prefix frontend test`: **9/9 pass**.
- `npm --prefix frontend run build`: pass, bốn file runtime.
- `python frontend/qa_browser.py`: pass với server QA cô lập tại loopback 4180, credential tạm, desktop 1440 px và Chromium mobile 390 px.
- Browser kiểm real-train semantic, sample replay, real-validation RL, cập nhật kết quả, xử lý logout 503 và đăng xuất thành công; không có page JavaScript error. Server QA đã được dừng.
- Ruff trên các file Python thay đổi: pass; `compileall` và `git diff --check`: pass. Cảnh báo LF/CRLF chỉ là thông báo Git về line ending.
- `python scripts/check_publish.py`: `publish_index_safe=true`, không có private file được Git track. Đây là kiểm tra index, không phải chứng nhận mọi nội dung được phép công bố.
- Compose local + production render với environment tạm: exit 0, đủ `dashboard/postgres/proxy`, Secure cookie, HTTPS Origin, volume PostgreSQL/TLS.

Một test PostgreSQL integration bị skip do không có `KLTN_TEST_DATABASE_URL`. Docker Desktop đã được gọi start; pipe xuất hiện nhưng `docker info`, `docker version`, `docker desktop status` không phản hồi trong các lượt giới hạn hơn 30 giây. Bộ PostgreSQL 18 có sẵn thiếu `initdb.exe`/`createdb.exe`; `postgres.exe`, `pg_ctl.exe`, `psql.exe` thoát `-1073741515` (`STATUS_DLL_NOT_FOUND`). Cluster PostgreSQL cũ được giữ nguyên, không sửa/cài lại toàn hệ thống. SQLite local dùng standard library nên hoạt động độc lập với hai lỗi môi trường này. **Chưa có bằng chứng mới về Docker build, Caddy runtime, PostgreSQL thật, restore drill PostgreSQL hay container smoke**.

Cảnh báo Gymnasium về wrapper `action_masks` xuất hiện ở test training; môi trường Python toàn cục còn `RequestsDependencyWarning` do phiên bản thư viện. Không sửa môi trường toàn cục để giấu cảnh báo. Mobile QA là giả lập, chưa kiểm trên thiết bị cảm ứng vật lý.

## Dữ liệu và thực nghiệm mới

`python scripts/train_real_rl.py --preflight` xác minh train **154 × 38**, observation **114**, action **38**. Snapshot toàn bộ có **215 × 38**, split **154/20/21/20**. Benchmark được chạy lại bằng `python scripts/run_benchmark.py`; bản trước được sao lưu tại `outputs/benchmarks/pre-completion-20261015-validation.json`.

Artifact mới: `outputs/benchmarks/current-validation.json`, tạo lúc `2026-10-14T19:15:33.256266+00:00`, tức **02:15:33 ngày 15/10/2026, giờ Việt Nam**. Validation **20 SV × 38 GV**, **35 dòng kết quả**, **24 checkpoint được đánh giá**, **0 checkpoint bị từ chối**. Nhiều budget của cùng seed được kiểm nhưng chỉ chọn budget cao nhất để tổng hợp, không chọn theo score validation.

| Thuật toán | Số seed tổng hợp | Tương thích TB | Invalid/fallback TB |
|---|---:|---:|---:|
| Hungarian | 5 | 0,103903 | 0 |
| Greedy | 5 | 0,094018 | 0 |
| Random | 5 | 0,039226 | 0 |
| MaskablePPO | 5 | 0,062807 | 0 |
| DQN | 5 | 0,060790 | 5,4 |
| QRDQN | 5 | 0,072768 | 11,2 |
| TRPO | 3 | 0,088986 | 18,3333 |
| ARS | 1 | 0,087716 | 15 |
| RecurrentPPO | 1 | 0,090479 | 19 |

Các điểm RL có fallback là chất lượng kết quả sau repair, không phải policy thô. MaskablePPO/DQN/QRDQN đã có năm seed 2.000.000 bước; TRPO có ba seed đạt budget; ARS và RecurrentPPO chưa đủ budget/multi-seed. **Không RL nào được promote; engine vẫn là Hungarian.** Không chạy thêm training hàng triệu bước hoặc mở final test chỉ để tạo nhãn “hoàn thiện”.

Quality report hiện có `ready=true` và preflight/service integrity pass. Điều đó không xác nhận quota chính thức, point-in-time advisor profile hay duyệt học thuật. Vocabulary snapshot còn giữ ảnh hưởng một số văn bản train trước khi lọc năm bản ghi; giới hạn này vẫn phải nêu trong báo cáo.

## Artifact bàn giao và giới hạn còn lại

- Source đầy đủ nằm trong repository `KLTN`; map từng module và contract trong tài liệu kỹ thuật.
- `docker-compose.production.yml`, `deployment/Caddyfile`, `.env.example`: cấu hình triển khai cùng một domain HTTPS.
- `outputs/final_validation/release-manifest-2026-10-15.json`: hash source/runtime/data/checkpoint hiện tại; vẫn gắn `production_ready=false`.
- `frontend/qa-artifacts/`: ảnh QA desktop/mobile và dữ liệu thật; không đưa vào image.
- `outputs/final_validation/pytest-2026-10-15.xml`: JUnit trước khi bổ sung persistence SQLite đầy đủ.
- `outputs/final_validation/pytest-local-2026-10-15.xml`: JUnit chốt sau khi bổ sung persistence SQLite đầy đủ.
- `outputs/final_validation/verification-2026-10-15.json`: tổng hợp kiểm chứng và hash artifact.

Theo cập nhật của người dùng ngày 15/10, **ưu tiên local**, sau này FE dự kiến Vercel, BE Render, database chưa quyết định. Chưa public là đúng phạm vi hiện tại. Cấu hình VPS/Caddy được giữ như phương án tùy chọn. Khi triển khai thật phải kiểm lại HTTPS/login/phân bổ/DB persistence/backup, routing và cookie giữa các dịch vụ. Phiên RAM hiện yêu cầu một process/replica; local SQLite lưu đầy đủ sáu bảng và lịch sử phân bổ. Cần hoàn tất quota, các thực nghiệm còn thiếu, duyệt báo cáo và nộp/bảo vệ theo yêu cầu trường; không tự ghi rằng các bước này đã hoàn thành.
