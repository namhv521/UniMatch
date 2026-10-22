# UniMatch — Báo cáo chất lượng Phase 5

Ngày kiểm chứng: **22/10/2026 (Asia/Saigon)**. Trạng thái: **VERIFIED — đạt Gate kỹ thuật P5 cho nghiên cứu offline; được phép bắt đầu Phase6**. Chưa cấp quyền phân bổ học kỳ thật hoặc promote RL.

Run đầy đủ: `20261022T122801Z-fd20da3a`; smoke đã kiểm chứng: `20261022T122557Z-27000354`. Đây là matching/training offline trên dữ liệu thật đã duyệt, với policy eligibility mô phỏng có khai báo. Không phải phân công học kỳ được phê duyệt; không deploy hoặc promote PPO/DQN.

## Nguồn và phạm vi chính sách

Đọc bằng `load_approved_features` từ P4 verified `20261022T115327Z-1850251a`, feature contract SHA256 `fffb85551cf9bef510317a1b86dbf866005ead6fc439809375fc5c003d4fe637`. P3 snapshot SHA256 `e76978d535daff20486ab33be1c114a501fcac0fc573fff019622a25ae1ab356`. P4 loader kiểm tra receipt, source/config/code hashes, calibrated transformer và full matrix replay; adapter đối chiếu snapshot lần đọc tiếp theo để không trộn phiên bản.

Giữ nguyên E4 **0,25 E1 + 0,25 E2 + 0,50 E3** và ma trận194×35; không fit text lại, không lấy dataset215 làm chuẩn. Không dùng270 nhãn relevance P4 làm outcome reward. Sáu uncertain của P4 giữ nguyên; Phase5 không tự giải quyết chúng.

Benchmark chọn **30 profile có score available trên toàn bộ train** làm catalog mô phỏng. Năm profile thiếu tín hiệu vẫn ở registry35 và bị presence/action mask loại trong benchmark; không bị sửa gold hoặc coi là không có năng lực. Đây không phải xác nhận30 giảng viên tham gia học kỳ. Rule quota chủ sở hữu đã chỉ định được version hóa thành `equal-division-canonical/1.0`: chia divmod theo số sinh viên và số giảng viên được chọn, remainder theo advisor ID tăng dần, capacity trả đúng thứ tự registry.

Phân bổ thật cần policy riêng chứa mã kỳ, ordered student/advisor IDs, roster được chọn, pair eligibility boolean đã xác nhận, reviewer/evidence reference, existing loads và fixed assignments. Existing loads phải được biểu diễn bằng chính các fixed rows trong cohort đầy đủ; không tự đặt0 hay trừ tải hai lần. Policy cùng shape nhưng đảo thứ tự ID bị từ chối. Không có policy thật trong đợt này; `operational_allocation_authorized=false`.

## Dữ liệu và protocol cố định

| Tập | Số SV | Vai trò |
|---|---:|---|
| Train | 135 = 3 nhóm45 không giao nhau | Rollouts PPO và replay DQN; chỉ shuffle thứ tự SV khi train |
| Validation | 29 | Đánh giá cấu hình đã khai báo; dùng trong smoke |
| Test | 30 | Không train, không replay; chỉ đánh giá model trong full protocol |

Ba nhóm train là nhóm sinh viên tách biệt của **một snapshot**, không phải ba học kỳ được xác minh. Chia tập kế thừa non-temporal grouping P4. Không có thời gian học kỳ/outcome để chứng minh chronological hoặc future-semester generalization. Exact Hungarian đã được chạy preflight sau khi ngân sách/cấu hình được chốt; không dùng kết quả đó để chỉnh hyperparameter. Không mô tả dữ liệu này là prospective temporal holdout chưa từng được inspect.

Budget khai báo trước kết quả: **seeds42,43,44,45,46; mỗi PPO và DQN16.384 bước/seed**, tổng163.840 transition steps cho hai thuật toán. PPO rollout256/batch64/5epochs, MLP128×128, learning rate0,0003, gamma0,99. DQN MLP128×128, learning rate0,001, gamma0,99, batch64, replay10.000, learning starts128, update mỗi4 bước, target update200; epsilon1,0 giảm tới0,05. Đây là budget CPU giới hạn, không phải ngưỡng hội tụ hoặc thay thế benchmark tối ưu hyperparameters.

Môi trường hiện tại dùng CPU, một Torch thread, deterministic algorithms; phiên bản thực tế lưu trong input manifest. Requirements worker tách khỏi web. Source hash được chụp trước training và kiểm tra lại khi kết thúc; không thay code/hyperparameters giữa các seed.

## Ràng buộc, baseline và môi trường chung

`AllocationProblem` giữ arrays đã copy/read-only, canonical action registry, score/missingness, eligibility/presence, capacities, fixed assignments, preference và source-term vectors. Điểm0 chỉ là observed score khi mask true; unknown giữ mask false. Preferences thiếu giữ known=false; không suy nguyện vọng từ PDF hoặc danh tính.

Hungarian dùng slot expansion và tối ưu tổng compatibility cộng preference có chứng cứ. Greedy/Random/PPO/DQN đều dùng cùng bài toán và validator. Mask kết hợp score availability, presence, eligibility, capacity, fixed rows và **khả thi toàn cục của phần còn lại sau action**. Không chỉ kiểm tổng quota. Vét cạn64 đồ thị eligibility3×2 kiểm chứng Hall feasibility, mask và optimum nhỏ.

State **9M+2K+1 = 472**, M35, K78 cặp namespace/tag, tương ứng70 ID taxonomy phân biệt. State gồm current scores, remaining ratios, normalized loads, allowed mask, remaining demand fraction, presence, score known, preference/known, source-term vector/known và remaining student fraction. Term presence không phải proficiency; tên, ID, contact, filename không trở thành feature. ID registry chỉ xác định semantics của action và truy xuất trace.

Reward mỗi bước: **score + 0,1 × observed preference + 0,15 × Δ(-variance(normalized loads)) + 1 khi hoàn tất**. Hành động sai bị chặn, đếm violation và raise, không dùng negative reward thay ràng buộc. Các thành phần reward và trạng thái tải trước/sau được lưu từng bước. Với quota tổng bằng N và hoàn tất mọi slot, normalized final load đều1; fairness cuối0 là hệ quả ràng buộc, không phải bằng chứng RL cải thiện fairness.

Hungarian là chuẩn tối ưu cho **objective tuyến tính được báo cáo**. RL học reward có shaping/discount; optimality_ratio chỉ so objective tổng cùng feasible set, không chia shaped return cho exact score. Không yêu cầu RL thắng Hungarian.

## PPO, Double DQN và artifact

PPO dùng `sb3_contrib.MaskablePPO` thật; rollout lấy action_masks từ env, prediction và phân phối policy luôn truyền mask. Evaluator riêng cũng truyền mask từng bước; không dùng evaluator SB3 không có mask. Log loss, policy/value loss, entropy và approximate KL là số đo từ quá trình optimize, không phải placeholder.

DQN thực hiện **masked epsilon exploration, masked greedy argmax và masked Double-DQN target**: online network chọn argmax trong next-state mask, target network đánh giá action đó. Replay lưu next mask, termination/truncation và copies trạng thái. True terminal không bootstrap; nonterminal không có action bị từ chối. Kiểm tra provenance mỗi training cohort/reset và khi tải replay; thiếu/sai feature hash hoặc taxonomy-order hash bị chặn ngay cả khi số chiều giống nhau.

Checkpoint PPO chỉ lưu policy/optimizer state dictionaries + metadata/hash; DQN lưu online/target/optimizer, replay NPZ và RNG/provenance. Load bằng `weights_only=True`, NPZ không pickle, expected contract phải khớp registry/state/features/taxonomy. Không deserialize arbitrary model/cloudpickle. Checkpoint parity xác minh inference; chưa tuyên bố resume training tái hiện từng rollout như một tiến trình không bị ngắt.

Mỗi case/seed/algorithm có assignments, objective, mean/min/p10 compatibility, normalized load imbalance, runtime, invalid-action/constraint count và trace. Trace có pre-action mask, action ID/index, student order, score/known, preferences/known, tải, reward components, registry/version. PPO xuất xác suất có mask; DQN xuất Q-value, không gọi là xác suất. Replay trace tái chạy env và so quyết định thực; model tải lại được so với model trước save.

## Kết quả đo

<!-- PHASE5_RESULTS -->
**Cả10 model đã hoàn tất đúng16.384 bước/model**, tổng163.840 bước, tổng thời gian learn669,223 giây trên CPU. Mỗi model đã gặp đủ135/135 sinh viên train. Mỗi PPO có64 loss-log rows hữu hạn, mỗi DQN có4.065 lần cập nhật/loss hữu hạn. Checkpoint cùng optimizer/target/replay được lưu theo seed.

Mean compatibility dưới đây là score E4, **không phải accuracy hoặc tỷ lệ hướng dẫn thành công**. Mỗi dòng là mean ± sample std qua5seeds:

| Thuật toán | Validation29 | Test30 | CI95 test | Objective test trung bình | Ratio với Hungarian trên test |
|---|---:|---:|---|---:|---:|
| Hungarian | 0,232991 ± 0 | **0,259276 ± 0** | [0,259276; 0,259276] | **7,778293** | **1,000000** |
| Greedy | 0,136852 ± 0 | 0,170531 ± 0 | [0,170531; 0,170531] | 5,115916 | 0,657717 |
| Random | 0,061826 ± 0,007979 | 0,072226 ± 0,016948 | [0,051183; 0,093270] | 2,166795 | 0,278569 |
| MaskablePPO | 0,060061 ± 0,018336 | 0,076970 ± 0,013000 | [0,060828; 0,093112] | 2,309103 | 0,296865 |
| Masked Double DQN | 0,133497 ± 0,009139 | 0,168374 ± 0,010895 | [0,154845; 0,181902] | 5,051211 | 0,649398 |

Kết luận lựa chọn: **giữ Hungarian làm mặc định/fallback**. DQN gần Greedy nhưng thấp hơn exact; PPO gần Random trong budget này. Không có cơ sở promote PPO/DQN. Không điều chỉnh hoặc chạy thêm hyperparameter theo test đã xem. Các model vẫn là research checkpoints để nghiên cứu/cập nhật có kiểm soát ở Phase6.

| Thuật toán | Mean local evaluation test (giây, gồm trace) | Min compatibility test | P10 compatibility test |
|---|---:|---:|---:|
| Hungarian | 0,0211 | 0 | 0,0350 |
| Greedy | 0,0275 | 0 | 0,0337 |
| Random | 0,0257 | 0 | 0 |
| PPO | 0,1164 | 0 | 0 |
| DQN | 0,0333 | 0 | 0 |

Tất cả feasible case có coverage100%,0hard violations và normalized load imbalance0. **Điểm minimum bằng0 ở mọi thuật toán**, và lower-tail của RL/Random yếu; quota đầy đủ không chứng minh mọi đề xuất phù hợp tốt về ngữ nghĩa. Exact chỉ tối ưu score đã định nghĩa, chưa tối ưu max-min hoặc outcome thật. Những assignment score thấp cần được điều phối kiểm duyệt; không phát hành phân công tự động.

200 kết quả case/algorithm/seed: **125 feasible hoàn tất**, **75 infeasible được từ chối với assignments rỗng**. Sáu stress scenarios gồm2×2,3×2, fixed assignment ở tương lai, thiếu profile, thiếu quota và xung đột Hall; ba loại cuối infeasible. Hai trường hợp thực29/30 giữ tách biệt synthetic. Tổng125 trace feasible đều replay;50 trường hợp learned model sau tải lại khớp model trước save. Không có invalid action hoặc quota/eligibility violation.
<!-- END_PHASE5_RESULTS -->

CI95 trong summary là Student-t theo5 seeds, không phải confidence về chất lượng hướng dẫn hoặc dân số sinh viên. Runtime là phép đo local process có trace, không phải SLO của Render hay cold-load API. Loss log hỗ trợ kiểm tra tối ưu thực; loss thấp hơn không tự chứng minh matching tốt hơn.

## Kiểm thử và kiểm chứng độc lập

**281 tests passed**, gồm **74 tests Phase5**, trong `tests/rebuild`. Các regression quan trọng: Hall/fixed future, capacity/eligibility/score masks, quota/index permutations, invalid action không đổi allocation, Gymnasium lifecycle và deterministic resets, masked exploration/target, terminal/truncation, replay copying, checkpoint corruption/incompatible contract, source snapshot thay giữa hai lần đọc, policy ordered IDs, feature/taxonomy semantics cùng shape, trace bị đổi reward và smoke không mở real test.

Smoke256steps/seed42 được giữ `partial`: chưa đủ seeds/budget, không phải release proof. Kiểm chứng độc lập49artifact SHA/8code SHA, không có test IDs trong input/evaluation, replay20 trace feasible và72 vector probability/Q khớp tuyệt đối model tải lại. Seed42 của full run được kiểm chứng135/135train IDs, finite loss, 10.000 replay rows có chữ ký current/nonterminal-next state khớp nguồn train, không có holdout replay.

Kiểm chứng độc lập cuối xác nhận **246artifact hashes,10checkpoints,125trace feasible,660vector policy/Q** khớp tuyệt đối; summary được tính lại từ per-seed results và khớp. Tính lại feasibility từ payload xác nhận đúng ba loại stress infeasible và75 kết quả từ chối. Ba training-problem hashes khớp contract. Tổng50.000 retained replay rows của năm DQN có chữ ký thuộc nguồn train, không có chữ ký chỉ xuất hiện ở holdout.

Giới hạn của kiểm chứng bằng fingerprint:135train rows chỉ tạo133 chữ ký score/term/known-mask phân biệt;59holdout rows có59 chữ ký và **một chữ ký trùng với train**, ảnh hưởng377 replay states trong kiểm tra chữ ký. Vector giống nhau không đồng nghĩa cùng người hoặc có leakage; không dùng fingerprint để khẳng định định danh duy nhất. Cách ly tập được chứng minh bằng source/ID bindings, cohort membership và learner provenance; fingerprint chỉ là kiểm tra bổ sung.

Một deprecation warning về truy cập env.action_masks qua wrapper của Gymnasium0,29/SB3 còn tồn tại; test hành vi mask và replay vẫn đạt. Không thay dependency production hoặc nâng phiên bản giữa benchmark để che warning.

Đối chiếu trực tiếp23 file backend/frontend với ZIP bảo vệ Phase0: **0 khác biệt**. Checkpoint/trace/provenance thật vẫn dưới data_rebuild gitignored, không có file data_rebuild nào tracked. Kiểm chứng máy đọc được lưu ở `data_rebuild/v1/reports/phase5_verification.json`; đây là kiểm chứng local, không phải clean-clone/deployment proof.

## Điều kiện nghiệm thu và giới hạn sử dụng

<!-- PHASE5_GATE -->
Run manifest **246 artifacts**, tất cả đúng SHA256. SHA manifest: `fee17c973b1f9977ea49e532d09dcf7e5a35e38e228f3166c1e71436362daea2`. Model contract SHA: `db39c33a53ece921d06aa0b00786b352f01aba57ff21e92d867def40e058b1e8`. Tám source/dependency hashes và P4 binding không đổi trong toàn bộ full run.

| Điều kiện kỹ thuật P5 | Kết quả |
|---|---|
| P4 verified, source/feature/split/action registry đúng hash | Đạt |
| Common Hungarian/Greedy/Random/PPO/DQN, cùng input/constraints/reward trace | Đạt |
| Feasible input coverage100%,0quota/eligibility/invalid-action violations | Đạt trong bộ kiểm chứng, có exact mask/validator |
| Infeasible thiếu nguồn/quota/Hall báo rõ, không bịa assignment | Đạt |
| Masks ở PPO rollout/predict/eval và DQN exploration/argmax/target/replay | Đạt test và checkpoint replay |
| Năm seed, đúng budget, optimize thật, train/validation/test không giao | Đạt |
| Trace fidelity, save/load inference parity, version/seed/checksum | Đạt |
| Report mean/std/CI, score distribution/lower tail, fairness/runtime vs exact | Đạt, đã ghi hạn chế |
| RL promotion | **Không** — kết quả chưa đủ tốt, giữ Hungarian |
| Roster/eligibility học kỳ thật và prospective outcome benefit | **Chưa có** — không cấp quyền phân bổ thật |
| Gate P5 kỹ thuật / được bắt đầu P6 | **Đạt** |
<!-- END_PHASE5_GATE -->

Gate P5 ở đây là **gate kỹ thuật nghiên cứu offline**. Không tự xác nhận faculty eligibility, active semester, outcome benefit hoặc cho phép phân công chính thức. Model promotion vẫn false; Hungarian là lựa chọn mặc định cho objective hiện tại. Website, DB và deployment incumbent không thay đổi. Phase6 chỉ được bắt đầu sau gate đầy đủ; vận hành thật vẫn cần dữ liệu/policy học kỳ và các gate tích hợp sau.

## Tài liệu kỹ thuật

Cách truyền mask và cảnh báo evaluator theo [MaskablePPO2.3.0](https://sb3-contrib.readthedocs.io/en/v2.3.0/modules/ppo_mask.html). Tách chọn action/evaluate target theo [Double Q-learning](https://arxiv.org/abs/1509.06461); hard action mask là ràng buộc thêm của bài toán này, không phải kết quả được paper xác nhận cho UniMatch. Loader state dictionaries theo [torch.load2.8](https://docs.pytorch.org/docs/2.8/generated/torch.load.html). Xem lệnh thực thi, policy và cách đọc artifact trong `rebuild_phase5_operator_guide.md`.
