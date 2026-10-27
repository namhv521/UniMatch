# UniMatch — Vận hành Phase 4

## Phạm vi

Pipeline riêng tư, đọc snapshot P3 đã verified. Không cập nhật website, DB, roster hay quota học kỳ. **Gate P4 đã verified** tại run `20261022T115327Z-1850251a` sau phê duyệt gói v2/E4 và kiểm chứng full matrix194×35. Các run thực nghiệm cũ vẫn blocked để giữ lịch sử.

## Chuẩn bị và chạy

Từ repository root trên PowerShell, dùng Python tương thích requirements-rebuild.txt. Tránh thay môi trường website đang chạy; có thể cài trong virtualenv riêng.

```powershell
python -m pip install -r requirements-rebuild.txt
python -m pytest tests/rebuild -q
python scripts/evaluate_rebuild_features.py --output data_rebuild/v1 --seed 42
```

CLI tạo immutable run và cập nhật alias `reports/phase4_gate.json`. Exit 2 nghĩa gate blocked; xem blocking_reasons. Run mới không ghi đè P3 hoặc run cũ. Gold/config thay hash làm pipeline fail closed; không sửa manifest để hợp thức hóa dữ liệu mới.

## Reviewer packet

Packet đã được hai agent chấm: `data_rebuild/v1/phase4_runs/20261022T070116Z-eacaa14a/review`. Không sửa packet. `blinded_pairs.jsonl` có 270 cặp validation, title/profile đã loại định danh và nguồn. `pair_bindings.json` dành cho mapper, không cho reviewer. Reviewer không đọc điểm, thứ hạng hay nhãn của người khác trước khi chấm.

Proposal JSONL cần pair_id, grade 0–3/uncertain, reviewer agent:, attribution agent_advisory, packet_manifest_sha256, reason, student_evidence và advisor_evidence nguyên văn. Không có nguồn thì giữ uncertain. Quote check chỉ chứng minh đoạn văn tồn tại; owner vẫn cần xét phù hợp ngữ nghĩa.

Hai primary files và hai crosscheck files nằm ở `data_rebuild/v1/review/phase4_advisory`. Mỗi reviewer đọc 135 cặp và kiểm tra chéo thêm 15 cặp. Khi tái tạo gói, dùng destination mới chưa tồn tại:

```powershell
python scripts/prepare_rebuild_feature_review.py `
  --packet data_rebuild/v1/phase4_runs/20261022T070116Z-eacaa14a/review `
  --destination data_rebuild/v1/review/phase4_owner_review_new `
  --primary data_rebuild/v1/review/phase4_advisory/pdf_extract.jsonl `
  --primary data_rebuild/v1/review/phase4_advisory/phase0.jsonl `
  --crosscheck data_rebuild/v1/review/phase4_advisory/phase0_crosscheck.jsonl `
  --crosscheck data_rebuild/v1/review/phase4_advisory/pdf_extract_crosscheck.jsonl
```

Script kiểm tra cả hai ý kiến với frozen packet trước khi kết hợp. Bất đồng giữ uncertain; ý kiến gốc không bị xóa. Sau đó chạy calibration validation, ghi report, explanations và manifest. Gói v2 hiện tại là `phase4_owner_review_v2`; không chỉnh gói đã đóng băng sau khi gửi owner.

Để chạy scorer trên raw combined proposals đã được đóng băng:

```powershell
python scripts/evaluate_rebuild_features.py `
  --labels data_rebuild/v1/review/phase4_owner_review_v2/combined_proposals.jsonl `
  --review-packet data_rebuild/v1/phase4_runs/20261022T070116Z-eacaa14a/review
```

Không truyền labels đã map để bỏ qua kiểm tra nguồn. Runner từ chối attribution owner_ratified ở đầu vào agent. Mỗi lần chạy mới giữ toàn bộ raw bytes, record/snapshot hashes và code hashes.

## Đọc kết quả

- `feature_manifest.json`: field contract, missingness, nguồn, baseline/calibrated weights và hash transformer.
- `splits.json`: group/split, seed và metadata non-temporal. Không dùng 30 test để chọn weights.
- `validation_scores/index.json`, `*.npy`, `*_available.npy`: score và mask phải luôn đi cùng nhau; index order là bắt buộc.
- `transformer/`, `transformer_calibrated_proposal/`: JSON + hashed NPZ. Load yêu cầu đúng identity redaction registry và phiên bản sklearn; registry lấy từ gold đã duyệt, không đưa vào feature.
- `reports/ranking_metrics.json`: attribution, metric scope và query coverage; không so sánh average trên các query khác nhau.
- `reports/hybrid_calibration.json`: 10 grid points trên common validation queries; không phải final test score.
- `reports/experiment_diagnostics.json`: full catalog và common catalog Hungarian đều là chẩn đoán; không phải assignment được cấp quyền.
- `reports/phase4_gate.json`, `manifest.json`: blockers và SHA từng artifact.

## Nghiệm thu với phê duyệt đã ghi nhận

Owner duyệt report nhãn và đề xuất feature cụ thể, có thể giữ uncertain hoặc yêu cầu sửa grade với nguồn/lý do. Receipt phải giữ nguyên thông điệp người dùng, phạm vi và SHA manifest; không sửa lịch sử agent thành human-authored labels.

Receipt hiện tại: `data_rebuild/v1/review/phase4_owner_acceptance_v2.json`. Giữ nguyên file và gói v2. Nó ghi câu hỏi và câu trả lời “Duyệt đề xuất, giữ 6 cặp uncertain”, hash manifest/feature proposal, weights và số uncertain; là bản ghi của operator về thông điệp người dùng, không phải chữ ký mật mã.

```powershell
python scripts/finalize_rebuild_phase4.py --authority data_rebuild/v1/review/phase4_owner_acceptance_v2.json
```

Chạy lại cùng receipt trả về run đã được kiểm chứng, không tạo thêm bản hoặc refit. Receipt/gói/source/config/code/matrix sai hoặc bị sửa làm lệnh thất bại. Không sửa checksum để bỏ lỗi; cần tạo phiên bản mới và đánh giá đúng thay đổi.

Run nghiệm thu chứa `feature_contract.json`, `features/compatibility_matrix.npy`, `features/compatibility_available.npy`, `features/index.json`, calibrated `transformer/`, split gốc, receipt và nhãn đã ratify. Score/mask/index là một bộ không tách rời. Sáu uncertain giữ nguyên.

Toàn bộ194 hàng được transform sau khi lựa chọn đã đóng băng, bao gồm30 heldout. Không refit, không gán relevance labels cho test hoặc tính test metric. Không mô tả trạng thái hiện tại là “chưa tính score test”; trạng thái đúng là “không dùng test để fit/select/calibrate/evaluate relevance”.

P5 đọc qua loader để kiểm tra cả nguồn phê duyệt lẫn replay score:

```python
from src.features.rebuild_acceptance import load_approved_features

features = load_approved_features('data_rebuild/v1')
scores = features['scores']
available = features['available']
student_ids = features['index']['student_ids']
advisor_ids = features['index']['advisor_ids']
```

Loader kiểm chứng P3/config/code, receipt và gói được duyệt, giữ đúng weights, transformer JSON/IDF, split, nhãn/reviewer gốc, artifact hashes, canonical index và replay model. Không trỏ P5 vào ma trận cũ hoặc coi missing mask là score0/eligibility.

Nếu đổi nguồn, taxonomy, preprocessing, split hoặc labels phải tạo run mới và đánh giá lại phần chịu ảnh hưởng. Gate P4 đã đạt vì có cả phê duyệt cụ thể và kiểm chứng artifact, không chỉ tests pass.

Không có quyền hoặc lựa chọn cụ thể thì giữ blocked. Chưa có thời gian học kỳ/nhãn lịch sử để temporal evaluation; báo thiếu dữ liệu đúng trạng thái. P5 vẫn cần roster coordinator chọn và policy chia quota được version hóa riêng.
