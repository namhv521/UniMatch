# UniMatch — Data Dictionary & Feature Selection (v1.0)

**Điều chỉnh ngày 27/10/2026:** CSV import v1.0 cũ không đổi. Hiện chỉ tạo `data_rebuild/advisor_urls/giang_vien_urls.csv` gồm Tên giảng viên, FIT NEU, Google Scholar, GitHub, ResearchGate; URL thiếu để trống. Chưa thu thập, trích xuất hoặc clean dữ liệu. Quy ước phiên bản V1–V4 và RL hai cấp tại [đặc tả hiện hành](rl_hai_cap_va_corpus_giang_vien_20261027.md).

**Áp dụng cho** `students_import.csv` và `advisors_import.csv`. Hai CSV chỉ có header; không có dữ liệu cá nhân được tạo giả. File nhập UTF-8 BOM để tương thích Excel; dùng dấu phẩy CSV chuẩn, `;` ngăn nhiều taxonomy tag, JSON string cho proficiency (theo CSV quoting).

**Điều chỉnh cho inference local — 23/10/2026:** Giữ nguyên 40 cột và ngữ nghĩa feature. Không yêu cầu xác thực học kỳ lịch sử cho CSV hồ sơ mới; `semester_id` có thể là nhãn batch. Backend được điền metadata file upload quan sát được từ bytes thật khi ô provenance trống; không điền kỹ năng/confidence/proficiency còn thiếu. Upload pending được kiểm tra schema ở staging để tạo đề xuất theo xác nhận điều phối, không trở thành gold hoặc phê duyệt học vụ. Các yêu cầu gold/approval và cách đánh dấu unknown bên dưới vẫn giữ nguyên cho dữ liệu huấn luyện. Xem `rebuild_scope_20261023.md`.

## 1. Các trường bắt buộc, ý nghĩa và kiểm chứng

| Đối tượng | Trường | Bắt buộc | Cách sử dụng |
|---|---|---|---|
| SV | `schema_version`, `semester_id`, `student_id`, `thesis_title`, `source_type`, `source_file`, `source_sha256`, `review_status` | Có | Khóa định danh, text đề tài, provenance; không phải numeric features |
| GV | `schema_version`, `semester_id`, `advisor_id`, `advisor_name`, `source_type`, `source_url`, `source_sha256`, `review_status` | Có | Định danh và bằng chứng crawler; không phải feature số |
| SV/GV | `research_domain_tags`, `topic_tags` / `expertise_topic_tags` | Có thể thiếu | Topic matching; nếu thiếu đánh dấu missing, không gán bằng 0 |
| SV/GV | skill/technology tag columns | Có thể thiếu | Multi-hot/similarity khi có chứng cứ đáng tin cậy |
| SV | `preferred_advisor_ids` | Tùy chọn | Nguyện vọng xác nhận, không suy diễn từ PDF |
| GV | `active_for_semester`, `capacity_max`, `existing_load` | Bắt buộc trước phân bổ thật | Ràng buộc cứng do điều phối nhập/xác nhận; không tự lấy từ website |
| SV/GV | `*_evidence_type`, `*_evidence_refs`, `*_confidence` | Có khi tag tồn tại | Chỉ rõ observed/self_reported/inferred_from_thesis/verified_web, số trang hoặc URL, độ tin cậy |
| SV/GV | `*_proficiency_json` | Tùy chọn | Map taxonomy ID → mức 1–5 chỉ khi có thang đo/nguồn xác nhận; không nội suy độ thành thạo từ từ khóa |
| SV/GV | `review_status` | Có | pending/needs_review/approved/rejected; dữ liệu pending chưa được active |

**Quy tắc:** `schema_version=1.0`. `semester_id` là định danh kỳ ví dụ `2026-FALL` do trường quy định. Không đặt điểm kỹ năng 0 khi chưa có chứng cứ; để ô rỗng. Tag dùng lowercase snake_case không dấu với alias map versioned. Có thể lưu nhiều mã trong ô như `python;sql;docker`. Dữ liệu text có dấu tiếng Việt bình thường. CSV không chứa embedding; embedding/matrix sinh riêng và checksum.

## 2. Danh mục nhóm kỹ năng (taxonomy khởi tạo, phải được duyệt)

| Field | Ví dụ taxonomy ID / ý nghĩa |
|---|---|
| `research_domain_tags` | ai;data_science;software_engineering;information_systems;cybersecurity;networks_iot;business_analytics |
| `topic_tags` | Từ khóa chủ đề luận văn, chuẩn hóa theo taxonomy; khác với kỹ năng cá nhân |
| `skills_tags` | Kỹ năng SV có bằng chứng rõ; không suy từ đề tài thành proficiency |
| `expertise_topic_tags` | Chuyên môn GV có bằng chứng từ hồ sơ/công bố chính thức |
| `programming_languages` | python;java;javascript;typescript;cpp;csharp;r;sql — dùng taxonomy ID, không để dạng prose |
| `frameworks_libraries` | pytorch;tensorflow;scikit_learn;fastapi;django;react;spring — chỉ ghi nếu có chứng cứ |
| `databases` | postgresql;mysql;mongodb;redis;neo4j;sqlite |
| `ml_ai_methods` | classification;regression;computer_vision;nlp;llm;reinforcement_learning;time_series;recommendation_systems;optimization |
| `data_engineering_tools` | spark;airflow;kafka;dbt;etl;data_warehouse |
| `cloud_devops_tools` | docker;kubernetes;aws;gcp;azure;ci_cd;linux |
| `security_network_tools` | network_security;cryptography;web_security;networking;iot_security |
| `software_engineering_methods` | testing;software_architecture;api_design;agile;uml |
| `research_methods` | literature_review;experiment_design;survey;qualitative_analysis;quantitative_analysis |
| `math_statistics_topics` | probability;statistics;linear_algebra;optimization;graph_theory |

## 3. Đề xuất feature engineering và chọn feature

| Nhóm input | Vai trò trong matching | Khuyến nghị | Rủi ro / kiểm thử |
|---|---|---|
| Thesis title / abstract ↔ research profile | Tương tự ngữ nghĩa đề tài–chuyên môn | **MVP ưu tiên** TF-IDF + taxonomy; embedding sau benchmark | Text nghèo/nguồn không đồng đều; fit chỉ trên train |
| Topic/domain tags | Tương đồng lĩnh vực | **MVP ưu tiên** với bằng chứng | Nhãn suy diễn phải kiểm duyệt |
| Technology/method tags | Match công nghệ và phương pháp | **MVP ưu tiên có điều kiện** | Từ khóa trong đề tài ≠ kỹ năng có thể thực hiện; phân biệt proficiency |
| Student advisor preferences | Tôn trọng lựa chọn | **Dùng nếu xác nhận** | Thiếu thông tin không được tự tạo |
| Advisor capacity/availability/eligibility | Feasibility | **Hard constraint**, không phải similarity | Nguồn chính thức kỳ đó; kiểm Hall feasibility |
| Prior outcomes/feedback | Nâng reward/evaluation về lâu dài | **Phase 2** sau khi xác minh | Missing-not-at-random, thiên lệch quyết định cũ |
| Names, IDs, file paths, URLs, contacts | Audit/join/provenance | **CẤM đưa vào mô hình** | ID leakage, privacy, proxy không hợp lệ |
| Cohort year/program | Phân quyền điều kiện hoặc phân tầng benchmark | **Chỉ dùng khi chính sách cho phép** | Cấm dùng làm proxy chất lượng cá nhân |

## 4. Quy chuẩn pipeline

1. **Raw**: 220 PDF nguyên trạng và trang web/raw HTML; inventory path, SHA-256, status. Không commit tài liệu cá nhân lên Git.
2. **Bronze**: text/pdf OCR per-page và từng field kèm source/span/confidence.
3. **Silver**: thông tin đã map taxonomy, dedupe, ID resolution, cross-source evidence, review.
4. **Gold**: hai CSV đạt schema, cohort version, advisor roster/approved quota, feature whitelist; sinh compatibility matrix + manifest.
5. **Data gates**: inventory đủ hoặc explicit blocker; thiếu ID/title/provenance bị quarantine; 0 duplicated within semester; 0 invalid source reference; kiểm thủ công mẫu extract; báo cáo missingness theo từng cột.
6. **Leakage gates**: split ở cấp sinh viên và thời gian kỳ; near-duplicates phải cùng split; vocabulary/normalization learned only on training. Future semester không góp vào dữ liệu đánh giá quá khứ.
7. **Model gates**: identical environments/masks/quota, 5 seeds (nếu đủ tài nguyên), unseen cohorts, 0 infeasible output, coverage=100% khi input khả thi, kiểm regression vs Hungarian, rollback.

## 5. Ví dụ JSON proficiency (minh họa định dạng, KHÔNG phải dữ liệu thực)

`{"python":3,"sql":2}` — chỉ hợp lệ khi provenance xác nhận cách chấm mức 1–5. Ô CSV chứa JSON escaped theo chuẩn CSV. `skill_confidence`/`expertise_confidence` là số [0,1] đo chất lượng chứng cứ, không phải điểm trình độ.

## 6. Thiết kế tương thích lâu dài

- **Danh bạ URL hiện tại:** một CSV năm cột, 38 giảng viên nguồn. Không thêm dữ liệu profile, event year hoặc feedback vào danh bạ. URL không là feature số; ô trống nghĩa là chưa có URL xác minh.
- **Phiên bản dữ liệu tương lai:** V1/2024.1 đến hết 31/12/2024; V2/2024.2 từ 01/01–30/06/2025; V3/2025.1 từ 01/07–31/12/2025; V4/2025.2 từ 01/01–30/06/2026. Cửa sổ mới không trùng; snapshot/model kế thừa lịch sử được ghi riêng.
- **Vòng phản hồi tương lai:** cần semester/round/parent/signal/cutoff, nguồn xác nhận và phiên bản reward/constraint. Chưa tạo metadata hoặc dữ liệu giả ở giai đoạn lưu URL.

- Không đổi nghĩa cột giữa các kỳ; thay đổi taxonomy yêu cầu version + migration/alias backward mapping.
- Schema từ điển phải tạo ra JSON Schema/Pydantic và test import, không duy trì validator khác logic CSV.
- Nếu số GV thay đổi: chuẩn hóa tập ứng viên, mask/padding/permutation-invariance hoặc retrain; không coi advisor ID integer là một feature.
- Không dùng điểm compatibility tính trên toàn dataset để fit transform rồi đánh giá holdout; nguồn PDF mới phải được rebuild feature/split từ đầu.
- Thiếu dữ liệu kỹ năng có thể giữ nguyên missing; không được bỏ sinh viên khỏi phân bổ nếu vẫn đủ điều kiện nghiệp vụ.
