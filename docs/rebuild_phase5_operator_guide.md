# Vận hành Phase 5 — matching và RL offline

## 1. Phạm vi và trạng thái

Phase 5 tạo **đề xuất phân bổ và benchmark nghiên cứu offline** từ snapshot đã được nghiệm thu Phase 3–4. Chạy worker không đồng nghĩa triển khai website, xác nhận quyền hướng dẫn, phê duyệt phân công hoặc promote mô hình.

Đầu vào hiện tại được kiểm tra từ manifest, không dùng dataset 215 hồ sơ cũ:

| Thành phần | Contract hiện tại |
|---|---|
| Gate Phase 4 | `20261022T115327Z-1850251a`, phải `verified`, `can_start_phase5=true` |
| Ma trận gold | 194 sinh viên × 35 hồ sơ giảng viên; thứ tự ID có checksum |
| Train | 135 sinh viên, chia thành 3 cohort × 45 |
| Validation / test | 29 / 30 sinh viên; nhóm tách biệt với train |
| Không gian action | Registry cố định 35 advisor IDs; không đánh lại chỉ số khi bỏ chọn giảng viên |
| Catalog nghiên cứu được chấm điểm | 30/35 giảng viên có compatibility available cho mọi sinh viên train |
| Vector sinh viên | K=78 cặp `(taxonomy_group, tag)`; không phải 78 kỹ năng đã xác minh |
| Observation | `9M + 2K + 1 = 472`, `float32`, kèm known/presence masks |

Việc chọn 30 hồ sơ chỉ dựa trên tính sẵn có của feature **train** cho mô phỏng. Đây không phải danh sách 30 giảng viên đã đồng ý tham gia học kỳ. Preference thực tế chưa có nên để unknown; không tự tạo nguyện vọng, mức thành thạo hay điểm kết quả hướng dẫn.

**Benchmark đã hoàn tất:** run `20261022T122801Z-fd20da3a`, gate kỹ thuật `verified`,5seeds42–46,10model×16.384 bước,281tests đạt. Hungarian có mean compatibility test0,259276; DQN0,168374; PPO0,076970. Giữ Hungarian mặc định, PPO/DQN chưa promote. Xem `rebuild_phase5_quality_report.md` để đọc đầy đủ số liệu/giới hạn; không gọi đây là phê duyệt phân bổ thật.

## 2. Chuẩn bị CPU worker riêng

Chạy tại repository `C:\Su\KLTNv2\KLTN`, trong terminal/worker riêng. Không cài bộ RL vào môi trường FastAPI đang phục vụ website và không gọi training trong HTTP handler.

```powershell
python -m venv .venv-rebuild-rl
$workerPython = Join-Path $PWD '.venv-rebuild-rl\Scripts\python.exe'
& $workerPython -m pip install --upgrade pip
& $workerPython -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
& $workerPython -m pip install -r requirements-rebuild-rl.txt
& $workerPython -m pip check
```

`requirements-rebuild-rl.txt` bao gồm `requirements-rebuild.txt` và pin Torch, Gymnasium, Stable-Baselines3, sb3-contrib. Worker chọn `device='cpu'`; benchmark đặt một Torch thread và deterministic algorithms. Manifest lưu phiên bản thư viện thực tế, seed và checksum source code.

Nguồn riêng tư và `data_rebuild/v1` phải có sẵn trên máy worker. Kiểm tra gate trước khi chạy:

```powershell
Get-Content data_rebuild/v1/reports/phase3_gate.json
Get-Content data_rebuild/v1/reports/phase4_gate.json
```

`load_approved_features()` xác minh snapshot, owner receipt, artifact hashes, order/index, dtype, frozen splits và transformer roundtrip. Không thay đường dẫn bằng ma trận cũ hoặc sửa gate bằng tay. Nếu hash/config/contract thay đổi, dừng và xử lý nguồn thay đổi trước.

Các test kỹ thuật liên quan nằm trong `tests/rebuild/test_phase5_*.py`; chạy bằng môi trường kiểm thử đã cài pytest. Test tổng hợp không phải bằng chứng chất lượng phân bổ thực tế.

## 3. Smoke run: kiểm tra wiring, không dùng real test

```powershell
& $workerPython scripts/benchmark_rebuild_matching.py --output data_rebuild/v1 --timesteps 256 --seeds 42 --smoke
$LASTEXITCODE
```

Smoke chỉ đánh giá **validation và synthetic stress cases**, không đánh giá hoặc xuất evaluation problem của real test. Train vẫn chỉ nhận cohort train.

Exit code **2** và gate `partial` là kết quả dự kiến của smoke: có `SMOKE_NOT_RELEASE_BENCHMARK`, chưa đủ 5 seed và chưa đạt budget phát hành. Với 256 bước cũng có thể chưa gặp đủ 135 sinh viên train. Tuy nhiên exception, checkpoint không tải được, trace không replay, action/constraint violation hoặc loss không hữu hạn vẫn là lỗi cần xử lý; không coi mọi exit 2 là smoke hợp lệ.

Mỗi lần chạy tạo thư mục mới dưới `data_rebuild/v1/phase5_runs/`. Run dở có thể chưa có manifest/gate hoàn chỉnh. Đọc tiến độ và log; không suy diễn hoàn tất từ việc thư mục/checkpoint đã xuất hiện.

## 4. Full benchmark đã khai báo trước

Sau khi smoke hợp lệ, cố định code, budget, hyperparameters và protocol rồi chạy:

```powershell
& $workerPython scripts/benchmark_rebuild_matching.py --output data_rebuild/v1 --timesteps 16384 --seeds 42 43 44 45 46
$LASTEXITCODE
```

Mỗi seed huấn luyện PPO và DQN **16.384 bước mỗi thuật toán** trên 3 cohort train. PPO dùng rollout nên luôn xem cả `requested_timesteps` và `actual_timesteps`; không thay số bước thực tế bằng số yêu cầu trong báo cáo.

Validation dùng để kiểm tra lựa chọn đã khai báo. Real test chỉ mở trong protocol cuối này; không tiếp tục chọn hyperparameters theo kết quả test. Nếu thay protocol sau khi đã xem test, phải ghi rõ holdout đã được sử dụng, không tiếp tục gọi nó là đánh giá độc lập chưa chạm tới.

Exit code **0** chỉ khi gate `verified`, mọi check bắt buộc đạt và `can_start_phase6=true`. Gate nghiên cứu này không promote PPO/DQN hoặc cấp quyền phân bổ thật. Hungarian vẫn là baseline/fallback mặc định.

## 5. Policy phân bổ học kỳ thật

Trước khi cấp quyền phân bổ thật, điều phối viên phải nhập/xác nhận policy qua `validate_operational_policy(policy, student_ids, advisor_ids)`:

- `semester_id`, `reviewer`, `policy_evidence_ref` không rỗng; `eligibility_confirmed=true`.
- `student_ids` và `advisor_ids` trong policy phải **đúng thứ tự** danh sách đang dùng. Ma trận `eligibility` có shape N×M, boolean thật, không dùng số 0/1 hoặc suy từ hồ sơ website.
- `selected_advisor_ids` là tập con không rỗng, không trùng của registry đầy đủ. Giữ M action cố định; `present` biểu diễn chọn/bỏ chọn.
- `existing_loads` phải có đúng các advisor được chọn, số nguyên không âm; mỗi giá trị phải bằng số `fixed_assignments` tương ứng trong **chính cohort đầy đủ đó**.
- `fixed_assignments` dùng `student_id -> advisor_id`, chỉ chứa sinh viên trong cohort và advisor được chọn. Không tự sửa assignment cố định khi conflict; trả infeasible để điều phối giải quyết.

Policy hiện tại: `equal-division-canonical/1.0`. Với N sinh viên và A advisor được chọn, dùng `divmod(N,A)`; phần dư được cộng 1 lần lượt theo **advisor ID đã sort**, rồi trả capacity trong thứ tự registry đầy đủ. Advisor không chọn có capacity 0. Đây là chính sách pilot chủ sở hữu cho phép, không phải quota suy từ trang giảng viên.

Domain nhận capacity như ngân sách slot khả dụng cho toàn bộ input cohort. Khi fixed rows đã nằm trong cohort, policy vẫn chia quota trên toàn cohort và giữ các row đó cố định; không trừ existing load lần nữa rồi vẫn phân bổ lại cùng sinh viên. Existing assignments ngoài cohort chưa được adapter này hỗ trợ: phải đưa về cohort đầy đủ hoặc dừng, không tự đặt load 0.

`eligible`, `available`, `present` và fixed assignments cùng tạo mask. Tổng capacity đủ chưa chứng minh khả thi: `feasible()` kiểm tra matching toàn cục/Hall; `action_mask()` chỉ cho action mà phần còn lại vẫn khả thi, kể cả fixed rows xuất hiện muộn. Không có phương án hoàn chỉnh thì trả `infeasible`, không tạo kết quả hoàn tất giả.

## 6. API và checkpoint đúng contract

| Module | API chính |
|---|---|
| `src/domain/rebuild_matching.py` | `AllocationProblem`, `equal_quotas`, `feasible`, `action_mask`, `validate_assignments` |
| `src/baselines/rebuild_baselines.py` | `solve(problem, algorithm='hungarian'|'greedy'|'random', seed=42)` |
| `src/data_pipeline/rebuild_cohorts.py` | `build_research_suite`, `assemble_research_suite`, `validate_operational_policy` |
| `src/environment/rebuild_env.py` | `MatchingEnv`, `action_masks`, `state_contract`, `training_provenance` |
| `src/rl/rebuild_ppo.py` | `MaskedPPOAgent.learn/predict/probabilities/save/load` |
| `src/rl/rebuild_dqn.py` | `MaskedDQN.learn/predict/q_values/save/load` |
| `src/evaluation/rebuild_benchmark.py` | `run_benchmark`, `evaluate_problem`, `verify_trace`, `summarize_seeds` |

Lấy expected contract từ `input_manifest.json` của run đã được kiểm chứng; dựng env từ đúng feature/snapshot/registry/taxonomy contract. Ví dụ API, không phải lệnh tự chọn checkpoint mới nhất:

```python
from pathlib import Path
import json
from src.data_pipeline.rebuild_cohorts import build_research_suite
from src.environment.rebuild_env import MatchingEnv
from src.rl.rebuild_ppo import MaskedPPOAgent
from src.rl.rebuild_dqn import MaskedDQN

run = Path("data_rebuild/v1/phase5_runs/20261022T122801Z-fd20da3a")
contract = json.loads((run / "input_manifest.json").read_text(encoding="utf-8"))["model_contract"]
suite = build_research_suite(Path("data_rebuild/v1"))
env = MatchingEnv(suite["train"], shuffle_students=True)
ppo = MaskedPPOAgent.load(run / "checkpoints/ppo/seed-42", env, expected_contract=contract)
dqn = MaskedDQN.load(run / "checkpoints/dqn/seed-42", expected_contract=contract)
```

Luôn truyền `expected_contract`, đặc biệt với DQN dù API cho phép bỏ qua. Contract bao gồm feature hash, taxonomy order hash, registry/state layout, reward/quota version và các training problem hashes. Cùng số chiều chưa đủ tương thích nếu ý nghĩa feature/action thay đổi.

PPO sử dụng MaskablePPO và truyền mask khi predict/phân phối policy. DQN dùng masked exploration/argmax và masked next-state target; replay có next masks. `learn` yêu cầu train-only provenance và feature/taxonomy hashes phù hợp.

PPO lưu `state.pt` cùng `metadata.json`; DQN lưu `weights.pt`, `replay.npz`, `metadata.json`, `checksums.json`. Loader xác minh checksum/contract và dùng `torch.load(..., weights_only=True)`, NumPy `allow_pickle=False`. Dùng API riêng này thay vì nạp model pickle/cloudpickle tùy ý. Parity checkpoint kiểm chứng inference, không phải cam kết resume tái tạo từng rollout học giống hệt.

## 7. Đọc và kiểm chứng kết quả

Trong run hoàn tất, kiểm tra:

1. `input_manifest.json`: đúng snapshot/P4 feature hash; train/validation/test IDs không giao nhau; đúng 5 seed, budget và phiên bản dependency/source.
2. `training/{ppo,dqn}-seed-*.json`: loss hữu hạn, có tối ưu thực, actual steps đủ, đủ 135 sinh viên train đã gặp. Số lần resample/episode không phải số học kỳ thật.
3. `reports/per_seed_results.json`, `reports/summary.json`: cùng cohort, scores, available/eligibility/presence/fixed/quota cho Hungarian, Greedy, Random, PPO, DQN. Stress thiếu profile, quota và Hall phải bị từ chối; fixed-future khả thi phải hoàn tất.
4. `traces/<case>/<algorithm>-seed-*.json`: pre-action masks, IDs, registry hash, score/known, preference/known, loads, reward components và student order. `verify_trace(problem, trace)` tái chạy từng action và so sánh quyết định; sửa reward/action/load phải bị phát hiện.
5. `reports/reproducibility.json`: checkpoint tải lại và model trước lưu cho cùng assignments và trace. PPO hiển thị policy probabilities có mask; DQN hiển thị Q-values, **không gọi Q-value là xác suất**.
6. `reports/phase5_gate.json` và `manifest.json`: checks bắt buộc đều true; tính lại SHA-256 từng artifact trong manifest; shared alias `reports/phase5_gate.json` phải trỏ đúng gate của run được nghiệm thu. Code/P4 binding thay đổi trong lúc chạy phải chặn gate.

Định nghĩa metric:

- `objective = sum(compatibility + preference_weight × preference)`; preference chỉ góp khi known. Nghiên cứu hiện tại chưa có preference nên thành tổng compatibility.
- Mean/min/p10 compatibility lấy từ ma trận gốc, không tin score do caller tự cung cấp.
- `normalized_load_imbalance = max(load/capacity) - min(load/capacity)` trên advisor present có capacity dương. Không phạt chỉ vì capacity 2 và 1 dẫn tới load 2 và 1 khi cả hai sử dụng 100%.
- `coverage` là tỷ lệ sinh viên được phân bổ; feasible case phải 1, constraint/invalid-action count phải 0. Infeasible có assignments rỗng và diagnostic rõ.
- `optimality_ratio = objective_algorithm / objective_Hungarian` trong cùng feasible set; nếu mẫu số 0 thì `null`, không tự gán 1.
- Summary báo mean, sample standard deviation và Student-t CI95 trên seed; không chuyển CI này thành bằng chứng chất lượng hướng dẫn hoặc outcome thật.

Artifact chứa IDs, hồ sơ và nguồn riêng tư: giữ trong khu vực dữ liệu riêng; không commit raw data/checkpoint trace có định danh lên Git công khai.

## 8. Điều kiện chuyển Phase 6 và giới hạn

Chỉ chuyển khi full benchmark gate verified và artifact checksum được kiểm chứng. Không sửa code giữa full run; nếu thay code sau run phải ghi nhận phiên bản và chạy lại phần kiểm chứng cần thiết, không tự cập nhật hash để hợp thức hóa.

Đây là một snapshot nguồn với split nhóm **phi thời gian**. Ba cohort train không phải ba học kỳ; không có cohort year/dates được tự tạo. Chưa đo future-semester generalization, chất lượng hướng dẫn, sự hài lòng hay kết quả luận văn. Budget CPU cố định cũng không chứng minh hội tụ hoặc RL vượt Hungarian.

Phase 6 mới xử lý cập nhật/replay/promotion/rollback theo contract. Website hiện tại tiếp tục hoạt động; worker Phase 5 không sửa production model, database hay phân công đã duyệt. Chọn Hungarian fallback với cùng constraints khi model không tương thích; nếu bài toán infeasible thì yêu cầu điều phối sửa policy, không dùng fallback để bỏ hard constraint.
