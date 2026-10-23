# UniMatch local — chạy và kiểm chứng

Giao diện đăng nhập, landing 3D, dashboard và chatbot mới: xem [cấu hình portal](portal_setup.md). Các hướng dẫn nhập token/CSV giảng viên dưới đây chỉ mô tả giao diện lịch sử; portal hiện dùng phiên đăng nhập và bỏ CSV giảng viên.

Bản bổ sung GitHub ngày 23/10/2026 đang dùng launcher riêng, PPO 131.072 và DQN 98.304 bước. Xem [báo cáo, lệnh chạy và rollback](rebuild_github_faculty_quality_report.md). Các lệnh dưới đây giữ lại cho bundle cũ và đối chiếu lịch sử.

## Chuẩn bị

Thư mục dự án: `C:\Su\KLTNv2\KLTN`. Python environment hiện tại đã có các dependency được pin. Khi tạo environment mới:

```powershell
python -m pip install -r requirements-rebuild-web.txt
npm --prefix frontend ci
npm --prefix frontend run check
npm --prefix frontend run build
python -m pytest tests/rebuild -q
```

Raw PDF/DOCX/RAR và `data_rebuild` là dữ liệu riêng tư, không nằm trong Git. Cần khôi phục private artifacts đã duyệt: P3 gold/review, P4 transformer/approval, P5 checkpoints và P6/convergence manifests, cùng source/config đã pin. Chỉ copy source code từ Git không cung cấp dữ liệu hoặc checkpoint. Thiếu/tamper artifact khiến API trả `verified_artifacts_not_ready`, không dùng dữ liệu giả để thay thế.

Manifest hiện có chứa đường dẫn tuyệt đối trong checkout này. Khi chuyển sang đường dẫn khác, phải rebuild/restore với đường dẫn tương thích và kiểm chứng lại; không sửa hash/manifest để bỏ qua kiểm tra. Chưa tuyên bố clone công khai tự chạy đủ dataset, Docker hoặc cloud đã được nghiệm thu.

## Mở workspace

```powershell
python scripts/serve_unimatch_local.py
```

Mở `http://127.0.0.1:8767/rebuild.html`. Launcher chỉ bind loopback, tạo/reuse token ngẫu nhiên tại `data_rebuild/runtime/access.token`, không in token. Đọc file đó cục bộ và nhập vào ô Access token. Không gửi token ra ngoài hoặc commit file này. Lệnh `--port` đổi cổng; `--token-file` dùng file token riêng. Environment `UNIMATCH_REBUILD_TOKEN` là contract của API entrypoint, nhưng launcher quản lý token bằng file trên.

Launcher chọn selection từ `data_rebuild/v1/reports/convergence_gate.json` khi verified; service kiểm tra lại manifest/encoder/checkpoint. Có thể chỉ rõ `--selection <selection_manifest.json>`. Không có selection mới thì service dùng P5 native seed 42 đã kiểm chứng. Không âm thầm tải checkpoint sai registry hoặc train trong request.

Khi `phase8_local_gate.json` đã verified trong đúng scope local, launcher mở entrypoint `backend.app.rebuild_assistant_api:app`, gồm cả matching P7 và trợ lý P8. Chưa có gate P8 thì dùng entrypoint P7. Knowledge base lỗi sẽ khóa trợ lý, các chức năng matching vẫn hoạt động.

Cold bootstrap có thể chậm do kiểm tra nguồn/manifest và tải model lần đầu. Sau khởi tạo, `/health` báo ready; health trước đó là degraded. Endpoint private luôn cần token. Đây là API local một điều phối viên, không phải hệ thống phân quyền nhiều vai trò cho toàn trường.

## Nhập hồ sơ sinh viên

1. Bấm **Tải CSV mẫu**, giữ đủ 40 header; UTF-8/BOM đều được hỗ trợ.
2. Điền tối thiểu `student_id`, `thesis_title`; tên và các feature còn lại điền khi có thông tin thật. Backend điền `schema_version=1.0`, batch `local-upload`, trạng thái pending và provenance của file nhận được nếu các ô đó trống. Đây là metadata quan sát được, không xác nhận học kỳ hay học vụ.
3. Tag dùng taxonomy đúng namespace, ngăn bằng `;`. Không tự điền confidence/proficiency. Khi nhập tag, điền evidence theo schema; thiếu field liên quan sẽ có lỗi từng dòng. Không có thông tin thì để trống.
4. Giới hạn hiện tại: 10 MiB, 500 hồ sơ/lần. CSV sai header/duplicate ID/formula/taxonomy bị từ chối. Import lặp cùng file/scope/model versions trả cùng cohort ID.
5. Preferences/proficiency chưa được xác nhận không đưa vào score/reward; API cảnh báo rõ nếu file có giá trị nhưng chưa dùng. `eligibility_flags` chưa có interpreter chính sách sẽ bị từ chối, không bị bỏ qua như không có ràng buộc.

Upload chỉ phục vụ inference, không thêm vào gold hoặc train. Dữ liệu/token scope lưu dưới `data_rebuild/v1/runtime`, private; trình duyệt không lưu hồ sơ vào localStorage/sessionStorage. Chỉ token được giữ trong sessionStorage của tab. Có nút **Xóa token**.

## Chọn giảng viên và chạy

- Danh mục có 35 profile đã duyệt; năm profile thiếu feature không được chọn bằng UI cho phân bổ hiện tại. Không diễn giải điều này là giảng viên không đủ năng lực.
- Chọn các giảng viên tham gia; quota chia đều theo canonical advisor ID, xem phần dư trước khi xác nhận. Roster đã chọn là phạm vi eligibility local do điều phối xác nhận, không phải quota/eligibility được suy ra từ website.
- **Xem top-K phù hợp**: xếp hạng riêng mỗi hồ sơ, chưa áp dụng quota toàn danh sách.
- **So sánh PPO · DQN · Hungarian**: dùng cùng CSV/roster/quota, có trace thật. Hiện selected checkpoint là PPO 32.768 và DQN 24.576, seed 42. Đây là model nghiên cứu, không phải model đã promote production.
- Điểm phù hợp không phải accuracy hoặc xác suất tốt nghiệp. Q-value DQN không phải xác suất; probability PPO chỉ là policy phân bổ trong trạng thái hiện tại.
- Xem bảng, step/back/play/speed và tải kết quả. Export JSON giữ metadata/trace; export CSV là đề xuất, cần người phụ trách xem xét trước phân công thật. Không thay đổi assignment đã duyệt bằng rollback model.

## CSV giảng viên

Mở **Kiểm tra CSV giảng viên**, tải mẫu 40 cột, nhập và xem lỗi. Intake này chỉ đọc: không đổi catalog, gold, quota hoặc model. Hồ sơ khớp profile đã duyệt có thể được preview; ID/tên/feature thay đổi cần rebuild và kiểm chứng registry/encoder/model trước khi kích hoạt. Các ô capacity/active/existing load trong CSV intake không tự ghi đè policy chia đều của lượt chạy.

## Nguồn API chính

Các endpoint dưới `/api/rebuild` cần `Authorization: Bearer <token>`:

- `GET /bootstrap`, `GET /templates/students.csv`, `GET /templates/advisors.csv`.
- `POST /students/validate`, `POST /advisors/validate`: `{csv_text}`.
- `POST /quotas`: `{student_count, advisor_ids}`.
- `POST /recommend`: `{cohort_id, advisor_ids, top_k}`.
- `POST /compare`: `{cohort_id, advisor_ids, coordinator_confirmed:true}`.
- `GET /runs/{run_id}`, `GET /runs/{run_id}/{algorithm}.csv`.
- `POST /assistant`: `{question, advisor_ids?, top_k?, cohort_id?}` trong entrypoint P8.

Không đổi API entrypoint cũ, không tự deploy Vercel/Render/Neon. Trang `index.html`/các JS cũ giữ nguyên; app mới phục vụ luồng rebuild bằng entrypoint riêng vì legacy imports phụ thuộc các module đã bị xóa trước đó.

## Tra cứu giảng viên có nguồn

Ở phần **Tra cứu**, nhập chủ đề hoặc tên giảng viên. Đây là công cụ deterministic chỉ đọc, không gọi LLM. Điểm xếp hạng dùng matching function và encoder đã đóng băng. Alias của concept trong taxonomy đã duyệt có thể mở rộng câu truy vấn; việc này không tạo kỹ năng sinh viên, không fit lại vocabulary/IDF và không sửa gold.

Nếu câu hỏi có concept nhận diện được, mỗi kết quả cần passage hiển thị chứa ít nhất một concept đó. Các kết quả chỉ trùng từ chung như “máy tính” bị loại. Passage tối đa 20 từ, giữ đúng vị trí trong nguồn. Vì vậy có thể trả ít hơn top-K dù những profile khác vẫn có điểm lexical dương.

Nếu đang chọn roster, kết quả chỉ thuộc roster đó. Chưa chọn ai thì tra cứu toàn bộ 35 hồ sơ công khai đã duyệt; đây không phải danh sách cam kết tham gia hướng dẫn. Trang vẫn loại hồ sơ thiếu feature khỏi lựa chọn phân bổ. Mỗi trích dẫn hiển thị URL, ngày thu thập và SHA của bản lưu đã duyệt; không tuyên bố vừa xác minh website trực tiếp.

Quota còn trống, chất lượng hướng dẫn thực tế, tỷ lệ phân công đúng hoặc cam kết nhận sinh viên sẽ trả unknown khi không có bằng chứng. Công cụ không xuất liên hệ, bí mật hay danh sách sinh viên. Giải thích một cặp cần cohort thuộc token hiện tại và chỉ rõ duy nhất sinh viên/giảng viên; điểm phù hợp không xác nhận một assignment đã được duyệt. Không gửi token trong câu hỏi.

## Tái huấn luyện và giới hạn

`python scripts/evaluate_rl_convergence.py` là offline worker, tạo run mới, không sửa run đã chốt. Budget mặc định năm seed 42–46, từ parent 16.384 đến 24.576/32.768. `docs/rebuild_rl_convergence_quality_report.md` giải thích kết quả và CI. DQN 24k được chọn vì 32k không tiếp tục cải thiện; không tăng step vô hạn theo loss.

P6 hỗ trợ immutable semester snapshots/replay/rollback khi cần cập nhật sau này; release này không bắt xác minh học kỳ lịch sử. Mọi dữ liệu/feature/roster thay đổi vẫn phải được kiểm tra tương thích trước inference hoặc retraining.
