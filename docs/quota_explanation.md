# Vì sao quota hướng dẫn hiện là giả định?

Kiểm tra trực tiếp ngày 15/10/2026. Tài liệu giải thích hiện trạng, không thay đổi dữ liệu hoặc thuật toán.

## 1. Bằng chứng trong repository

Trong `data/curated/advisors.json`, cả 38 giảng viên đều có:

```json
{"quota": null, "quota_source": "not published; set per cohort ceil(N/M)"}
```

Nghĩa là bộ dữ liệu hiện chưa chứa hạn mức hướng dẫn được xác nhận cho từng giảng viên. Chuỗi `not published` là ghi chú trong dữ liệu, không đủ để kết luận trường chưa từng công bố hoặc không có quy định nội bộ. Chưa đối chiếu nguồn bên ngoài trong lần giải thích này.

`MatchingService._real_split()` tại `src/serving/service.py` hiện tính:

```python
capacity = math.ceil(len(indices) / len(self.advisors))
```

Sau đó gán cùng capacity cho tất cả giảng viên. `src/evaluation/benchmark.py` dùng cùng quy tắc để so sánh các thuật toán nhất quán.

Vì vậy, trên train 154 sinh viên và 38 giảng viên, mỗi giảng viên có capacity `ceil(154/38)=5`. Trên validation 20 sinh viên, mỗi giảng viên có capacity `ceil(20/38)=1`. Cùng một giảng viên nhận hai giá trị khác nhau tùy split: đây là cấu hình thí nghiệm, không phải hạn mức thực tế của người đó.

## 2. Vì sao dữ liệu thật vẫn có quota giả định?

Dữ liệu đề tài, sinh viên và hồ sơ giảng viên có nguồn thật không đồng nghĩa mọi trường nghiệp vụ đều được thu thập đầy đủ. Thông tin chuyên môn, công bố, môn học hoặc số đề tài từng hướng dẫn không xác định được số sinh viên giảng viên được phép nhận trong một đợt cụ thể.

Đếm số đề tài lịch sử chỉ cho biết số assignment quan sát được trong tập đã thu thập. Nó không chứng minh hạn mức tối đa, không bảo đảm bao phủ toàn bộ sinh viên và không tự xác định số chỗ còn trống trong kỳ hiện tại. Do đó không đổi số đếm lịch sử thành quota chính thức.

## 3. Tại sao dùng công thức chia đều?

Công thức là một cách đơn giản để tổng capacity đủ cho mọi sinh viên và cho các thuật toán cùng chạy trên một ràng buộc xác định. Nó hữu ích để kiểm thử phân bổ, action masking và benchmark khi thiếu quota thật.

Nó không phản ánh sự khác nhau về khối lượng công việc, khả năng nhận hướng dẫn hoặc chỉ tiêu được phân cho từng giảng viên. Kết quả `quota_violations=0` hiện chỉ chứng minh không vượt **capacity thực nghiệm**, không chứng minh tuân thủ hạn mức thực tế của trường.

## 4. Cần gì để chuyển sang quota thật?

Tối thiểu cần bảng dữ liệu có:

| Trường | Ý nghĩa |
|---|---|
| `advisor_id` | Khớp giảng viên trong snapshot |
| Kỳ/đợt/năm học | Phạm vi hiệu lực của hạn mức |
| Hạn mức tổng | Số sinh viên/đề tài tối đa được xác nhận, kèm đơn vị tính |
| Số đã nhận | Để tính số chỗ còn lại nếu đang phân bổ bổ sung |
| Nguồn và ngày xác nhận | Quyết định/bảng phân công hoặc xác nhận có thể kiểm tra |

Đơn vị “sinh viên” và “đề tài/nhóm” phải thống nhất với action/assignment của hệ thống. Nếu dữ liệu chỉ có một phần giảng viên, không tự gắn nhãn toàn bộ capacity là chính thức.

Sau khi có bảng xác nhận, cần sửa đồng bộ serving, môi trường training và benchmark để dùng cùng quota, cập nhật hash capacity policy, đánh giá lại checkpoint và chạy lại kết quả. Các model hiện được huấn luyện theo giả định chia đều không tự trở thành model đã kiểm chứng trên quota thật.

## 5. Kết luận hiện trạng

Chắc chắn: quota thật chưa được nhập trong 38 hồ sơ hiện hành; code đang tạo capacity chia đều. Chưa biết: quota chính thức nằm ở đâu, có được công bố công khai hay chỉ lưu nội bộ, và giá trị của từng giảng viên trong đợt áp dụng. Cần nguồn xác nhận để giải quyết phần thiếu này, không thể suy ra chính xác chỉ từ dữ liệu đề tài và chuyên môn.

## 6. Luồng nhập sinh viên theo đợt

Theo yêu cầu tiếp theo, trang **Nhập sinh viên** dùng một chính sách riêng: người điều phối upload danh sách và chọn GV tham gia, rồi hệ thống phân bổ cân bằng trên đúng các GV đó. Ví dụ 38 SV và 4 GV tạo quota 10–10–9–9. Chính sách của đợt này không sửa các quota null hoặc thí nghiệm train/validation đã đóng băng. Xem [hướng dẫn luồng nhập mới](student_cohort_upload.md).
