# UniMatch — Nền tảng Điều phối & Tư vấn Khóa luận Tốt nghiệp End-to-End

UniMatch là hệ thống hỗ trợ phân công và quản trị vòng đời khóa luận tốt nghiệp toàn trình (End-to-End) cho Sinh viên, Giảng viên hướng dẫn và Trưởng khoa / Điều phối viên. Hệ thống kết hợp **Chuẩn hóa hồ sơ học thuật lai (Hybrid LLM + Deterministic Normalizer)**, **Trợ lý AI học vụ RAG 4 lớp Guardrails**, và **Tối ưu hóa phân công đa thuật toán** (**Hungarian**, **Maskable PPO**, **Action-Masked Double DQN**) trên tập hồ sơ chuyên môn đầy đủ của 17 giảng viên.

---

## Khởi chạy nhanh Chế độ Demo Bảo vệ Khóa luận (1-Click)

```bash
# Cài đặt thư viện frontend & build giao diện tĩnh (nếu chạy lần đầu)
npm --prefix frontend run build

# Khởi chạy máy chủ Demo Bảo vệ Khóa luận (tự động nạp 17 GV + 6 RL checkpoints + dữ liệu mẫu 5 vai trò)
python scripts/run_demo.py --reset --open-browser
```

Sau khi chạy, mở `http://127.0.0.1:8767/login.html` hoặc sử dụng **Thanh chuyển nhanh vai trò Demo** ngay trên đỉnh màn hình (`UNIMATCH_DEMO_MODE=1`, tự động vô hiệu hóa trên môi trường `production`):
- **Sinh viên (`sv1@demo.unimatch.edu.vn`)**: Đã làm khảo sát năng lực, chuẩn hóa giọng văn đề tài học thuật, xem thẻ giải thích XAI, tra cứu danh bạ giảng viên và hỏi đáp Trợ lý RAG.
- **Sinh viên mới (`sv2@demo.unimatch.edu.vn`)**: Trải nghiệm trực tiếp Interactive Quiz Cards và chuẩn hóa hồ sơ từ đầu.
- **Giảng viên (`lam.px@demo.unimatch.edu.vn`, `viet.nh@demo.unimatch.edu.vn`)**: Xem hồ sơ sinh viên đã chuẩn hóa học thuật + điểm tương thích E4, duyệt/từ chối hướng dẫn, nhận xét đề cương / giữa kỳ / bản cuối và chấm kết quả hướng dẫn cuối kỳ.
- **Trưởng khoa (`dean@demo.unimatch.edu.vn`)**: Quản lý danh sách CSV sinh viên & ma trận kỹ năng CSV giảng viên công bằng, khóa đăng ký, đối sánh **PPO vs DQN vs Hungarian**, xem phát lại Sân khấu 3D + Ma trận 2D, công bố chính thức, xuất `.xlsx` / `.csv` và gói phản hồi Continual RL.

---

## Các phân hệ cốt lõi End-to-End

1. **Khảo sát năng lực & Chuẩn hóa giọng văn học thuật (`src/serving/profile_normalizer.py`)**:
   - Sinh viên thực hiện trắc nghiệm năng lực theo vị trí chuyên môn (`roles-v2`) và nhập ý tưởng đề tài tự do (kể cả văn nói, từ lóng hoặc pha trộn thuật ngữ tiếng Việt - tiếng Anh).
   - Bộ chuẩn hóa lai chuyển đổi văn phong tự do sang **Hồ sơ đề tài học thuật chuẩn** (Tên đề tài chuẩn hóa, Tóm tắt mục tiêu & phạm vi phương pháp, Nhãn kỹ năng chuẩn Taxonomy), hiển thị đối chiếu *Trước / Sau* và gửi trực tiếp sang Giảng viên cùng mô hình phân công.
2. **Ma trận Kỹ năng Giảng viên Công bằng (`docs/advisors_full_skills.csv`, `backend/app/advisor_skills.py`)**:
   - Chuẩn hóa đầy đủ 8 nhóm năng lực & tóm tắt hướng nghiên cứu cho toàn bộ **17/17 giảng viên**, khắc phục triệt để hiện tượng thiên lệch điểm tương thích đối với các giảng viên công bố công trình thuần tiếng Việt. Hỗ trợ Trưởng khoa xuất / nhập cập nhật qua CSV.
3. **Trợ lý AI Học vụ RAG & 4 Lớp Guardrails (`src/serving/rag_agent.py`)**:
   - Kết hợp truy hồi lai **BM25 + E4 Cosine Embedding + Reciprocal Rank Fusion (RRF)** trên nguồn công bố học thuật đã kiểm chứng và hồ sơ kỹ năng giảng viên.
   - **4 lớp Guardrails nghiêm ngặt**: (1) Chống Prompt Injection & dò thông tin cá nhân chéo (PII), (2) Chặn gian lận học thuật (viết hộ khóa luận / làm bài tập hộ), (3) Bộ lọc phạm vi nghiêm ngặt từ chối 100% câu hỏi ngoài lề, (4) Trả lời đúng trọng tâm kèm trích dẫn nguồn xác thực.
4. **Tối ưu hóa Phân công Đa mô hình & Hậu phân công (`backend/app/thesis.py`, `backend/app/thesis_intake.py`)**:
   - Đối sánh trực tiếp **Hungarian**, **Maskable PPO** và **Masked Double DQN** có tôn trọng giảng viên đã nhận hướng dẫn trước, nguyện vọng xếp hạng của sinh viên và hạn ngạch (quota) tùy chỉnh.
   - Theo dõi sau công bố: nộp & duyệt 3 mốc (**Đề cương**, **Giữa kỳ**, **Bản cuối**), đánh giá kết quả hướng dẫn cuối kỳ và xuất dữ liệu ẩn danh phục vụ **Continual RL (`R4`)**.

---

## Dữ liệu & Huấn luyện Học tăng cường (Continual RL)

| Phiên bản | Kỳ | Train | Validation | Test ngoài |
| --- | --- | ---: | ---: | ---: |
| V1 | 2024 | 87 | 19 | |
| V2 | 2025.1 | 46 | 16 | |
| V3 | 2025.2 | 45 | 11 | |
| Test ngoài | 2025.3 | | | 19 |

Mỗi chuỗi mô hình có 4 vòng kế thừa checkpoint nối tiếp (`R1 -> R4`) trên không gian trạng thái 420 chiều và 17 giảng viên. Danh mục Strict gồm 6 checkpoint đã khóa SHA-256 (`PPO` và `DQN` qua `V1`, `V2`, `V3`). Chi tiết xem tại [Tóm tắt nghiên cứu RL](docs/research/rl/summary.md).

---

## Cấu trúc Repository

| Đường dẫn | Nội dung |
| --- | --- |
| [frontend/](frontend/) | Giao diện Vanilla HTML/CSS/ES Modules (Design System v2), Sân khấu Three.js 3D + 2D Replay |
| [backend/](backend/) | API FastAPI, xác thực OAuth/Email/Demo, chuẩn hóa hồ sơ, RAG Agent, điều phối & hậu phân công |
| [src/](src/) | Pipeline dữ liệu, đặc trưng E4, chuẩn hóa học thuật, RAG Guardrails, RL (PPO/DQN) & suy luận |
| [scripts/](scripts/) | Bộ khởi chạy Demo bảo vệ (`run_demo.py`), huấn luyện RL theo kỳ và kiểm định gói mô hình |
| [configs/](configs/) & [database/](database/) | Từ điển Taxonomy chuẩn và lược đồ cơ sở dữ liệu SQLite / PostgreSQL |
| [docs/](docs/) | Đặc tả sản phẩm, hồ sơ kỹ năng chuẩn 17 giảng viên (`advisors_full_skills.csv`) và tài liệu nghiên cứu |
| [tests/](tests/) | Bộ kiểm thử tự động Backend, Frontend, Guardrails RAG, Chuẩn hóa hồ sơ và Vòng đời khóa luận |

## Kiểm thử chất lượng

```bash
npm --prefix frontend run check && npm --prefix frontend run build
node tests/rebuild/test_thesis_frontend.mjs
pytest tests/rebuild -q
```
