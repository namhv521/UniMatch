# Image prompt v1

Tool: built-in Imagegen, một lần generate và một lần edit theo evidence. Mục đích: ảnh baseline cố định cho triển khai UI sau.

Quy chuẩn và giới hạn nằm trong `C:/Su/KLTNv2/DESIGN.md`.

## Prompt hiệu chỉnh cuối

```text
Edit this existing Vietnamese UI reference board precisely. Preserve all three screens, layout, fonts, palette, spacing, 3D viewport and playback controls. Correct ONLY evidence labels and results content:
1. In home top right replace the tiny illustrative reward learning curve with a small measured horizontal bar chart titled "Kết quả baseline", subtitle "220 SV · 38 GV", rows "Random 0.0304", "Greedy 0.0502", "Hungarian 0.0699"; axis meaning "Độ tương thích trung bình". No reward curve, no RL performance claim. Keep chart region same size.
2. Replace selected algorithm PPO with "MaskablePPO" wherever it appears as dropdown or selected chip. Chips should be six available full checkpoint algorithms: "MaskablePPO", "DQN", "QR-DQN", "TRPO", "ARS", "RecurrentPPO"; a final visibly disabled muted "TQC" chip may have small crossed-circle icon. Remove ordinary PPO chip. All labels must remain legible.
3. Bottom table rows "MaskablePPO" and "DQN", checkpoint cells "2M bước · seed 42", source "Local", status "Đã train · chưa benchmark", time "—". Ensure these are training metadata, not evaluated model performance.
4. Existing bottom blue informational banner text replace with "6 checkpoint đã train · chưa có benchmark RL" and supporting small "Sample 3D là minh họa; baseline lấy từ kết quả local."
5. Add tiny explicit "Mẫu minh họa" tag within 3D viewport. Preserve state sample, quota warning and controls.
6. Keep top board heading and bottom "Mẫu minh họa • Số liệu demo • Bố cục cố định".
This is final reference v1. Do not add sections or redesign. Correct Vietnamese typography.
```

## Prompt tạo ảnh ban đầu

Đối chiếu artifact: chỉ sáu model ARS, DQN, MaskablePPO, QR-DQN, RecurrentPPO, TRPO có checkpoint full đã tìm thấy. TQC phải disabled; nhãn thật lấy từ manifest (ppo-smoke là MaskablePPO). Sample 3D là demo; chart baseline lấy từ artifact local, làm tròn bốn chữ số. Các giới hạn này có ưu tiên cao hơn chữ minh họa trong ảnh.

```text
Use case: ui-mockup.
Create ONE high resolution fixed visual reference board for a Vietnamese university student-to-advisor matching website. It must be a practical, simple, professional product UI with legible Vietnamese text, not concept art. Landscape board with TWO smaller desktop screens across top (login left, home right), ONE large full-width matching dashboard across bottom. All three screens completely visible, orderly grid, generous whitespace, no devices, no photographic props. Top title outside screens: "Ghép cặp sinh viên – giảng viên" and small "Giao diện tham chiếu v1". Bottom margin "Mẫu minh họa • Số liệu demo • Bố cục cố định".
Style: white and cool light grey backgrounds, deep navy text, academic blue primary buttons, teal confirmed connections, amber warnings. Restrained 8px corner radii, fine borders, consistent Vietnamese sans-serif typography, clear readable labels. Same top navigation on home and dashboard: "Trang chủ", "Ghép cặp", "Kết quả", simple account icon. Keep UI modest, functional, coherent.
LOGIN top left: split simple layout; small left illustration of 3 student dots linked to 2 advisor dots, title "Ghép cặp phù hợp, hiểu từng quyết định", right form "Đăng nhập", labels "Email", "Mật khẩu", button "Đăng nhập", small "Xem mẫu mô phỏng".
HOME top right: headline "Tìm giảng viên phù hợp với đề tài của bạn", short description "So sánh độ tương đồng, phân bổ theo hạn mức và khám phá cách các mô hình ra quyết định." Primary button "Bắt đầu ghép cặp". Compact overview with "Sinh viên", "Giảng viên", "Kết quả đã chạy" using em dash values, three compact explanation blocks "Semantic", "Model đã train", "Reinforcement Learning", and restrained little learning-curve area labeled "Kết quả thực nghiệm" with "Chọn lần chạy để xem dữ liệu". Do not invent performance numbers or claim RL superiority.
MAIN DASHBOARD lower full width: title "Ghép cặp & mô phỏng thuật toán". A compact step indicator "Chọn dữ liệu → Chọn chế độ → Mô phỏng → Xem kết quả". At top of dashboard THREE large equal-width selection cards with literal labels:
"1. Semantic" subtitle "Xếp hạng theo độ tương đồng" sample "SV01: NLP → GV-A".
"2. Đã train · chưa dùng RL" subtitle "So sánh đặc trưng đã học" sample "Điểm tương đồng → ghép theo hạn mức" small amber badge "Cần xác nhận model".
"3. Đã train + RL" subtitle "Chọn hành động theo trạng thái" sample "SV01 → GV-A → cập nhật hạn mức". Third selected with blue border.
Next row controls: "Dữ liệu mẫu: 3 SV · 2 GV", "Thuật toán: PPO ▾", "Checkpoint: Chọn checkpoint ▾", blue button "Bắt đầu mô phỏng". Small compact available algorithms chips "PPO", "MaskablePPO", "DQN", "QR-DQN", "TRPO", "ARS", "RecurrentPPO", "TQC" labeled "Chọn model".
Below controls: LEFT 65% is large "Mô phỏng 3D" viewport on pale bluish background. Show true isometric perspective floor grid, three blue spheres labeled SV01 SV02 SV03 on one side, two teal upright advisor cylinders labeled GV-A GV-B on other side, realistic clean subtle depth shading. One solid teal edge SV01 to GV-A selected, one dashed grey candidate SV02 to GV-A, amber blocked edge from SV03 to a full GV-B, visually clear connection hierarchy. Advisor quota pill labels "GV-A: 1/2", "GV-B: 1/1". Legend "Ứng viên", "Đã ghép", "Hết hạn mức". Caption "Vị trí 3D chỉ phục vụ minh họa". Playback bar with play/pause icons, "Bước trước", "Bước tiếp", "1×", progress slider, "Bước 2/3".
RIGHT 35% is an explanation panel titled "Vì sao chọn cặp này?" with clearly separated rows "Trạng thái: SV01 đang chờ", "Hành động: Chọn GV-A", "Hạn mức: Còn 1 chỗ", "Reward: Theo cấu hình", then simple highlighted block "GV-B đã đủ hạn mức" and a tab "Nhật ký từng bước". No fabricated action probabilities.
Bottom dashboard narrow evidence table "Kết quả đã chạy" columns "Model", "Checkpoint", "Nguồn dữ liệu", "Trạng thái", sample rows "PPO | Chọn lần chạy | Local | Chưa đối chiếu", "DQN | Chọn lần chạy | Local | Chưa đối chiếu". Include explicit small banner "Mẫu minh họa — không phải kết quả benchmark". Attractive polished yet simple design, readable hierarchy, crisp type, no neon, no glass effects, no decorative gradient, no fake analytics. Preserve all three pages and 3D algorithm educational function.
```
