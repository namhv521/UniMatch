# Chương 9. Kiến trúc hệ thống và giao diện mô phỏng

## 9.1. Kiến trúc tổng thể

Hệ thống được chia thành các lớp có ranh giới bằng artifact:

```text
Nguồn private
  -> crawl snapshot + provenance
  -> extract + identity resolution
  -> curated dataset + temporal split
  -> TF-IDF features + compatibility matrix
  -> baseline / RL environment / checkpoint registry
  -> MatchingService
  -> FastAPI cùng origin
  -> dashboard 2D + mô phỏng đồ thị 3D
```

Raw data không đi thẳng tới API. `MatchingService` chỉ tải curated dataset, split, feature manifest và ma trận sau khi kiểm hash, shape và thứ tự. Registry checkpoint độc lập với danh sách file: nó mở archive, kiểm SHA-256 và đọc space thật. FastAPI chuyển hợp đồng domain thành JSON. Frontend chỉ hiển thị dữ liệu backend trả về; không tự tính metric “đẹp hơn” hoặc tự đổi thuật toán khi lỗi.

Đây là kiến trúc mục tiêu đang được tích hợp. Sự tồn tại của file source không tự chứng minh hệ thống deploy thành công. Trạng thái release phải dựa trên test, smoke run và manifest mới.

## 9.2. API và phiên đăng nhập

Luồng dự kiến là `/login` → `/` → `/matching`, với `/results` cho các run có provenance. Các endpoint private gồm catalog, dataset, simulate/allocate, recommend, results và feedback. Server kiểm tra email/mật khẩu từ `KLTN_LOGIN_EMAIL` và `KLTN_LOGIN_PASSWORD`, tạo token ngẫu nhiên trong bộ nhớ và đặt cookie `HttpOnly`, `SameSite=Strict`. Ghi dữ liệu yêu cầu Origin cùng host hoặc origin đã cấu hình.

Session ở bộ nhớ phù hợp demo cục bộ một process, không phải kiến trúc production nhiều replica. Restart server làm mất session; chưa có rate limit, quản trị người dùng hay thu hồi phiên phân tán. Vì vậy release hiện được giới hạn ở local research dashboard.

## 9.3. Ba chế độ giao diện

1. **Semantic:** dùng ma trận similarity và baseline có quota. Đây là chế độ có đường chạy thật trên validation khi artifact hợp lệ.
2. **Đã train, chưa dùng RL:** dành cho scorer học giám sát rồi ghép bằng thuật toán cổ điển. Hiện chưa có artifact scorer được xác minh nên phải disabled.
3. **Đã train + RL:** chỉ chạy checkpoint tương thích. Checkpoint toy được phép trên sample và phải có banner “unpromoted”; dataset thật từ chối nếu space không phải 114×38.

Việc tách ba chế độ ngăn nhầm similarity là policy RL hoặc lấy checkpoint RL giả làm encoder non-RL.

## 9.4. Mô phỏng 3D

UI 3D biểu diễn đồ thị hai phía: nút sinh viên, nút giảng viên và cạnh ứng viên/đã chọn. Tọa độ phục vụ bố cục, không mang nghĩa khoảng cách embedding trừ khi có phép chiếu được định nghĩa. Nét đứt biểu thị ứng viên; nét liền biểu thị assignment; cảnh báo biểu thị quota đầy.

Mỗi event chứa step, chỉ số/ID ẩn danh, score, reward, tải trước/sau, capacities, invalid proposal, fallback và giải thích. Playback gồm phát/dừng, bước trước/sau, reset và tốc độ. Animation phải phát lại đúng event backend; không được dùng hoạt ảnh cố định rồi thay nhãn thuật toán.

Đồ thị 3D không phải giao diện duy nhất. Bảng assignment, capacity bars và event log 2D cung cấp thông tin tương đương cho người dùng bàn phím, thiết bị yếu hoặc chế độ reduced motion.

## 9.5. Trạng thái và lỗi

- **Loading:** hiển thị tiến trình, khóa thao tác chạy lặp.
- **Empty:** hướng dẫn chọn dataset và thuật toán.
- **Unavailable:** nói rõ thiếu artifact hoặc checkpoint không tương thích.
- **Error:** thông báo mã lỗi an toàn, giữ lựa chọn để thử lại.
- **Success:** hiển thị engine thực sự chạy, data/model version và metrics có nguồn.

Nếu RL bị từ chối, UI không âm thầm chuyển sang Hungarian. Nếu người dùng chọn fallback có chủ đích, kết quả phải ghi `fallback=true` và tên engine cuối.

## 9.6. Responsive và accessibility

Desktop đặt viewport cạnh panel giải thích. Mobile xếp controls → viewport → giải thích → bảng, không phụ thuộc hover. Vùng chạm tối thiểu 44 px, focus rõ, form có label, màu có ký hiệu/chữ đi kèm và thông báo trạng thái dùng vùng live thích hợp. Mục tiêu thiết kế là WCAG 2.2 AA; đây là mục tiêu cần audit, chưa phải chứng nhận.

## 9.7. Giao diện tham chiếu

Ảnh `docs/ui-reference/matching-ui-v1.png` là baseline bố cục và màu. Nó minh họa login, home và matching dashboard, không chứng minh auth, API hoặc 3D đã hoạt động. Bất kỳ ảnh demo nào chứa số phải ghi “sample” nếu không lấy từ benchmark artifact.

