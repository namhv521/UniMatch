# Kết nối dữ liệu và model trên web local

Kiểm tra trực tiếp ngày 09/10/2026, tại `C:/Su/KLTNv2/KLTN`. Không sửa code, dữ liệu hoặc checkpoint trong lần kiểm tra này.

## Web đang chạy

- URL: http://127.0.0.1:8001
- Launcher: `python run_dashboard.py --local-demo --port 8001`.
- Process khởi động: PID 8244.
- Log: `outputs/runtime/web-20261009.stdout.log` và `web-20261009.stderr.log`. Log stdout chứa credential tạm cho phiên local.
- Trang chủ HTTP 200; health trả `healthy`, `data_loaded=true`, `quality_ready=true`, `total_advisors=38`.

Health xác nhận service nạp được artifact; không chứng minh chất lượng phân công hoặc model đã được promote.

## Dữ liệu đã kết nối, nhưng giao diện dễ gây hiểu nhầm

`backend/app/main.py` dựng `MatchingService` với root là thư mục sản phẩm `KLTN`. `src/serving/service.py` đọc:

1. `data/curated/theses.json`.
2. `data/curated/advisors.json`.
3. `data/curated/split_indices.json`.
4. `data/features/feature_manifest_v2.json`.
5. `data/features/compatibility_matrix_v2.npy`.

API có đăng nhập đã trả `real-train` gồm 154 sinh viên và 38 giảng viên, `real-validation` gồm 20 sinh viên và 38 giảng viên. Contract hiện tại chia 215 bản ghi thành train 154, validation 20, test 21, future 20.

Frontend ưu tiên bộ mẫu đầu tiên trong catalog. Bộ mẫu có điểm giả lập; phải chọn **Dữ liệu đầy đủ · train** hoặc **Dữ liệu đầy đủ · validation** để chạy trên ma trận thật. API trả nhãn ẩn danh như `SV-TRAIN-001`, `GV-001`, nên không hiện tên trong file nguồn.

Thư mục `data` không được đọc toàn bộ tự động. PDF, raw và extracted là đầu vào cho pipeline; serving đọc snapshot curated/features đã chuẩn bị. Service nạp snapshot khi khởi động, không theo dõi mọi thay đổi file theo thời gian thực. Artifact phải khớp hash, shape, split và thứ tự định danh trước khi được phục vụ.

Đã gọi `/api/v1/simulate` với semantic/Hungarian/real-train thành công: `quota_violations=0`, `invalid_proposals=0`. Quota vẫn là giả định chia đều phục vụ nghiên cứu.

## Vì sao training-smoke không xuất hiện hoặc không chạy với dữ liệu thật?

Registry trong `src/serving/model_registry.py` quét `outputs/checkpoints`, `outputs/research-real`, `outputs/research-filtered`; không quét `outputs/training-smoke`.

Cả sáu manifest trong `training-smoke` ghi `smoke=true`, `completed_timesteps=16`. Metadata đọc trực tiếp từ ZIP cho biết observation shape `[6]`, action count `2`: chỉ phù hợp môi trường mẫu có hai giảng viên. Môi trường thực trong registry yêu cầu observation `[114]`, action count `38`.

Không thể đưa các checkpoint này vào thư mục registry rồi dùng để phân công 38 giảng viên. Cần checkpoint được huấn luyện đúng không gian môi trường và contract dữ liệu.

## Trạng thái model nghiên cứu hiện tại

Catalog live trả các checkpoint trong `research-real` là `invalid`, lý do `research_contract_mismatch`. Contract dữ liệu hiện tại đã thay đổi so với snapshot dùng khi train các checkpoint đó. Registry chặn inference để tránh dùng sai dữ liệu/thứ tự mapping.

Các checkpoint được nhận ở trạng thái `toy_unpromoted` chỉ hỗ trợ `sample-2x2` và `sample-3x2`. Danh sách model trong health không có nghĩa các model ấy hỗ trợ dữ liệu thật.

Để dùng RL với snapshot hiện tại, cần checkpoint tương thích snapshot, hoặc dựng lại bundle nghiên cứu cũ đầy đủ để đánh giá riêng. Không sửa hash manifest để vượt kiểm tra. Lần này chưa train lại hoặc thay đổi bundle.

## Cách sử dụng ngay

Đăng nhập bằng credential local của launcher, vào màn hình ghép cặp, chọn chế độ semantic và thuật toán Hungarian, rồi chọn dữ liệu train hoặc validation. Đây là luồng đã kiểm tra thành công với dữ liệu thật hiện tại. Test holdout vẫn bị khóa trên dashboard.
