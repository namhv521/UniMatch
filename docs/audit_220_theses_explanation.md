# Audit 220 đề tài là gì?

Audit là kiểm tra snapshot 220 đề tài đang dùng có đáp ứng điều kiện để chạy và đánh giá bài toán ghép sinh viên–giảng viên hay không. Không phải crawl lại, extract lại hay train lại. Tài liệu này mô tả việc cần kiểm tra; không phải kết quả audit đã hoàn thành.

## 1. Kiểm tra từng đề tài

| Nội dung | Mục đích | Xử lý nếu chưa đạt |
|---|---|---|
| ID sinh viên/đề tài không rỗng, không trùng sai | Một bản ghi phải trỏ tới đúng đối tượng; phân biệt trùng hồ sơ với nhiều đề tài hợp lệ của cùng người | Đối chiếu nguồn; không tự sinh ID để che lỗi |
| Tiêu đề và nội dung tạo features có ý nghĩa | Tránh tính điểm từ văn bản rỗng, sai hồ sơ hoặc nội dung lỗi | Kiểm tra extraction và evidence; sửa có nguồn hoặc tách chờ review |
| Năm dùng để chia split có nguồn | Bảo vệ giao thức đánh giá theo thời gian | Đối chiếu metadata adjudication và tài liệu nguồn |
| Nguồn tài liệu/evidence truy vết được | Có thể xác minh thông tin và các lần sửa | Ghi vấn đề; không coi dữ liệu không có nguồn là đã xác minh |
| Liên kết giảng viên hợp lệ khi có sử dụng | Tránh trỏ tới ID không tồn tại hoặc dùng quan hệ hướng dẫn chưa xác minh | Giữ trạng thái chưa xác minh; chặn nếu giao thức yêu cầu quan hệ này |

Tên sinh viên thiếu không nhất thiết chặn nghiên cứu nếu ID có bằng chứng và tên không được dùng trong đầu vào của mô hình. Tuy nhiên validator của pipeline version hiện yêu cầu tên; nếu áp dụng chính sách khác phải khai báo rõ phạm vi, không giả vờ rằng validator cũ đã pass.

Một trường thiếu không tự động làm toàn bộ đề tài vô dụng. Ngược lại, một bản ghi có đủ trường không có nghĩa nội dung đúng: cần kiểm tra nguồn của các trường quan trọng và danh sách `needs_review`.

## 2. Đối chiếu năm đề tài trong báo cáo lỗi cũ

Đối chiếu `outputs/data_quality/v2026-09-28/failure_report.json` với `data/curated/theses.json`, `metadata_adjudications.json` và evidence nguồn. Lượt kiểm tra trước cho thấy 4/5 nguồn đã có adjudication sửa metadata; 2/5 bản ghi hiện vẫn thiếu tên sinh viên. Không thể lấy nguyên danh sách lỗi cũ làm danh sách loại khỏi snapshot.

Audit cần xác nhận từng lỗi còn tồn tại hay đã sửa đúng; ghi kết quả và nguồn đối chiếu. Không mặc định loại cả năm, cũng không mặc định cả 220 chắc chắn đạt.

## 3. Kiểm tra snapshot và features cùng nhau

- JSON/CSV có đồng nhất các ID và trường phục vụ pipeline không?
- Số hàng/cột ma trận có khớp số đề tài và giảng viên không?
- Thứ tự ID có khớp thứ tự hàng/cột không? Đúng shape nhưng sai thứ tự vẫn cho kết quả sai người.
- Dataset, split, feature manifest và checkpoint có đúng phiên bản/hash không?
- Các split có chồng lấn hoặc bỏ sót ngoài chính sách không? Có cùng sinh viên/source xuất hiện xuyên split gây leakage không?
- Văn bản từ validation/test có bị dùng để fit preprocessing hoặc tạo thông tin giảng viên ngoài chính sách thời gian không?
- Điểm ma trận có finite và đúng miền giá trị của phương pháp được khai báo không?

Backend đã có kiểm tra một số hash/shape/order; audit tận dụng chúng và bổ sung các điều kiện chưa được kiểm chứng. Load thành công chỉ chứng minh các kiểm tra hiện có pass, không chứng minh tất cả dữ liệu sạch.

## 4. Kiểm tra giảng viên và quota

Đánh giá 38 hồ sơ theo các trường text mà feature builder/serving thực sự sử dụng; ghi riêng thông tin gốc và suy diễn, evidence, hồ sơ chưa review. Không thay text thiếu bằng tên rồi gọi đó là chuyên môn đầy đủ.

Quota chia đều `ceil(N/M)` là một giả định có thể hợp lệ cho nghiên cứu nếu được ghi rõ trong giao thức. Quota chính thức là điều kiện khác của ứng dụng vận hành. Không điền quota giả định vào hồ sơ như thể được nhà trường xác nhận.

## 5. Đầu ra audit

Một báo cáo có:

1. Thời điểm, phiên bản validator, scope và hash input.
2. Số đề tài kiểm tra, số đạt, số chờ review/tách riêng.
3. Danh sách lỗi chặn và cảnh báo; lý do ở cấp bản ghi.
4. Kết quả kiểm tra split/features và capacity policy.
5. Readiness riêng cho nghiên cứu và vận hành.

Ví dụ dưới đây chỉ minh họa schema, không phải số liệu đã xác nhận:

```json
{
  "scope": "research-serving-snapshot",
  "checked_records": 220,
  "research_ready": false,
  "operational_ready": false,
  "blocking_reasons": ["pending audit"],
  "capacity_policy": "uniform-ceiling-experimental-v1"
}
```

## 6. Quyết định sau audit

- Nếu cả 220 đạt tiêu chí nghiên cứu: giữ snapshot, split và features; sinh report mới. Không cần train lại chỉ vì cập nhật report.
- Nếu có bản ghi không đạt: đối chiếu và sửa bằng chứng nếu có; nếu không, tách vào folder chờ review kèm lý do. Khi thay nội dung/thành viên snapshot, phải kiểm tra lại split/features, provenance và khả năng dùng lại checkpoint/benchmark.
- Sau khi dữ liệu đạt: đánh giá checkpoint `research-real` cùng baseline trên validation. Data readiness không thay thế model evaluation.

Mục tiêu là quyết định bằng bằng chứng liệu nên dùng nguyên 220 đề tài, thay vì loại theo báo cáo cũ hoặc bật cờ ready thủ công.
