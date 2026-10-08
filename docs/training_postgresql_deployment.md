# Dữ liệu, huấn luyện RL và triển khai PostgreSQL/Docker

## Kết quả kiểm tra ngày 09/10/2026

Snapshot đang dùng gồm **215 sinh viên/luận văn và 38 giảng viên**. Split: train **154**, validation **20**, test **21**, future **20**. Ma trận tương thích có kích thước **215 × 38**. Training chỉ lấy 154 hàng train và toàn bộ 38 cột giảng viên; không lấy validation/test/future để cập nhật policy.

`scripts/audit_data.py` kiểm kê 777 file: 746 file được kiểm tra cấu trúc, 31 file không có kiểm tra định dạng phù hợp, trong đó 25 file cache. Không phát hiện lỗi parse hoặc blocker ở snapshot active. Đây không phải kết luận rằng tất cả nội dung của 777 file đều đúng: PDF chỉ được kiểm tra header/EOF; kiểm tra JSON, CSV, NPY, ZIP không thay thế kiểm định ngữ nghĩa hoặc xác nhận của trường. Report nằm tại `outputs/data_quality/audit-current.json` và được giữ ngoài Git.

Năm bản ghi lỗi trích xuất lịch sử nằm trong `data/excluded/requested-five/`: thiếu tên, tiêu đề, bằng chứng ID trực tiếp hoặc năm. Chúng đã được cách ly theo yêu cầu trước đó; một số đã có bản sửa trước khi bị loại. Snapshot active không sử dụng năm hàng này. Sáu hồ sơ giảng viên thiếu serving text và chưa có quota chính thức cho 38 giảng viên. Vì vậy dữ liệu dùng được cho nghiên cứu, chưa đủ chứng cứ để phân công chính thức.

## Vì sao `research-real` bị chặn

Checkpoint cũ được train trên snapshot 220 hàng. Sau khi loại năm bản ghi, dataset hash, split hash và feature matrix hash thay đổi. Registry kiểm tra đồng thời snapshot, mapping, native observation/action space, checkpoint checksum và số bước thực sự nằm trong ZIP. Do đó model cũ bị từ chối trên snapshot 215 hàng. Không sửa metadata checkpoint để vượt qua kiểm tra.

`outputs/training-smoke` là model toy 2 giảng viên, observation 6/action 2, được train 16 bước. Dữ liệu thật cần observation 114/action 38, nên smoke cũng không dùng để ghép 38 giảng viên.

Checkpoint mới được ghi vào `outputs/research-current`. Feature bundle hiện vẫn dùng vocabulary đã fit từ corpus train cũ, có các tài liệu train bị loại; không có bằng chứng dùng test để fit, nhưng đây là preprocessing đóng băng và phải được ghi nhận khi diễn giải kết quả. Nếu muốn đánh giá lại preprocessing sau curation thì cần rebuild và xác thực bundle, rồi train lại. Bộ kiểm tra nguồn giảng viên từ chối profile thay đổi khi checksum trong quality report chưa được cập nhật qua quy trình xác thực bundle.

## Chạy training

Tại thư mục `KLTNv2/KLTN`, dùng môi trường Python đã cài `requirements.txt`:

```powershell
python scripts/audit_data.py
python scripts/train_real_rl.py --preflight
python scripts/train_real_rl.py --timesteps 2000000 --seeds 42 123 456 789 1024 --resume
```

Lệnh cuối chạy sáu thuật toán: MaskablePPO, DQN, QRDQN, TRPO, ARS, RecurrentPPO; năm seed, budget ít nhất 2 triệu bước mỗi run. Nếu không truyền `--seeds`, mặc định chỉ seed 42. Có thể giới hạn bằng `--algorithms MaskablePPO DQN`. `--resume` chỉ chấp nhận checkpoint cùng contract và đủ kiểm tra native space/số bước; target hoàn tất hợp lệ được giữ lại. Thuật toán có thể vượt budget do kích thước rollout.

Trainer tái sử dụng cấu hình CPU hiện có, gồm mạng nhỏ và replay buffer DQN nhỏ; đây là cấu hình nghiên cứu cơ sở, chưa được tune cho chất lượng tốt nhất. Wrapper bảo đảm phạm vi train và tính nhất quán artifact, không bảo đảm model tốt hơn baseline. Sau mỗi run, benchmark trên validation được cập nhật và ghi fingerprint model đã đánh giá. Test holdout tiếp tục khóa trên web.

Đã chạy kiểm tra tích hợp sáu thuật toán với budget yêu cầu 256 bước; ARS thực tế chạy 2.464 bước. **Chưa chạy chiến dịch 2 triệu bước × 5 seed.** Các model mới chỉ có trạng thái research chưa promote; Hungarian vẫn là engine được chọn.

## PostgreSQL và API

Schema tại `database/schema.sql`; adapter tại `backend/app/storage.py`. FastAPI và frontend giữ cùng origin, nên giao diện gọi API mà không cần thêm proxy/CORS riêng.

| Bảng | Nội dung |
| --- | --- |
| `snapshots` | Snapshot bất biến, khóa hash từ toàn bộ provenance: dataset, split, feature, thứ tự sinh viên/giảng viên và nội dung profile giảng viên |
| `students` | ID và profile JSONB, khóa theo snapshot |
| `advisors` | ID và profile JSONB, khóa theo snapshot |
| `split_memberships` | Thành viên train/validation/test/future và vị trí trong split |
| `simulation_runs` | Request mode/algorithm/dataset/seed và kết quả JSONB cùng snapshot |
| `feedback` | Đánh giá hữu ích, thuật toán/mode và snapshot |

Import snapshot nằm trong transaction, chạy lại không nhân bản hàng của cùng snapshot. Snapshot mới được giữ tách biệt để bảo toàn lịch sử. Ma trận feature và checkpoint vẫn là file có checksum; PostgreSQL không thay thế các artifact này. Khi cấu hình `DATABASE_URL`, lỗi database được báo lỗi, không âm thầm chuyển sang SQLite. Chạy local không cấu hình PostgreSQL vẫn hỗ trợ SQLite feedback cũ.

Đã kiểm tra PostgreSQL thật: import, ghi run/feedback, restart dashboard và đọc lại. Hai snapshot lịch sử đang tồn tại trong volume kiểm tra; tổng 430 hàng sinh viên/76 hàng giảng viên không có nghĩa active dataset bị nhân đôi. Mỗi snapshot có 215/38 hàng riêng.

## Docker

Dockerfile build frontend bằng Node rồi đóng runtime Python/FastAPI, source training, schema và configs vào image chạy dưới non-root user. Compose gồm PostgreSQL 16, dashboard và training profile tùy chọn. `data/` mount chỉ đọc; `outputs/` mount ghi được; database dùng named volume. Private data/model/secret không được bake vào image.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Điền credential riêng trong .env trước lần chạy đầu.
docker compose up --build -d postgres dashboard
docker compose --profile train run --rm train python scripts/train_real_rl.py --preflight
docker compose --profile train run --rm train python scripts/train_real_rl.py --timesteps 2000000 --seeds 42 123 456 789 1024 --resume
docker compose restart dashboard
docker compose exec -T dashboard python scripts/verify_rl_api.py --base-url http://127.0.0.1:8000 --dataset real-train --algorithm MaskablePPO
```

Stack hiện tại chạy tại **http://127.0.0.1:8010** theo `.env` local đã tạo. Credential không đưa vào tài liệu/Git. Một clone GitHub mới cần khôi phục private data bundle trước khi chạy. Backup/restore và cấu hình chi tiết: [Docker training runbook](runbook/docker_training.md).

## Chuẩn bị GitHub

`.gitignore` loại data, outputs, `.env`, model, backup, khóa riêng, cache, virtualenv và frontend build artifacts. `.dockerignore` chỉ cho phép source cần thiết vào build context. Các file private/cache trước đây đã tracked được loại khỏi index, bản local được giữ nguyên.

```powershell
git status --short
python scripts/check_publish.py
git diff --check
```

`check_publish.py` kiểm tra **Git index hiện tại**, kể cả file private được force-add dù đã ignore. Không có commit/push hoặc sửa lịch sử Git trong công việc này. Dữ liệu đã từng có trong commit cũ có thể vẫn nằm trong lịch sử; kiểm tra index không chứng minh lịch sử đã sạch. Những thay đổi không liên quan có sẵn trong working tree được giữ nguyên, cần review phạm vi khi commit.

## Bằng chứng kiểm chứng

- Full Python suite trước bước siết kiểm tra nguồn cuối: 142 passed, 1 skipped. Test PostgreSQL opt-in được chạy riêng trong Docker và passed trên database thật.
- API RL real-train: 154 sinh viên, 38 giảng viên, 0 quota violations, kết quả gắn fingerprint checkpoint đã benchmark.
- API DQN real-validation: 20 sinh viên/38 giảng viên; có 16 đề xuất không hợp lệ được fallback. Đây là hạn chế của policy nghiên cứu, không phải chứng cứ chất lượng tốt.
- Browser QA desktop/mobile và luồng kết quả trên Docker passed; frontend checks/build passed.
- PostgreSQL giữ feedback sau restart dashboard; cả hai service Docker healthy.
- Các regression test cho nguồn stale, checkpoint native steps, snapshot profile và Git private files được chạy bổ sung sau review.
- Regression cuối sau siết kiểm tra nguồn: 50 passed, 1 skipped; test PostgreSQL thật được kiểm chứng riêng. Review độc lập không còn blocker nghiêm trọng.

Giới hạn còn lại: quota thực nghiệm, hồ sơ thiếu nội dung, preprocessing đóng băng, hyperparameter chưa tune và chưa có full-budget multi-seed evidence để promote RL.
