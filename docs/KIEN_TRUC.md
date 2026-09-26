# Ghi Chú Kiến Trúc Hệ Thống — KLTN RL Matching System

**Ngày:** 26/09/2026 | **Phiên bản:** 1.0 | **Status:** Architecture Analysis Complete

## 1. Tổng Quan Dự Án

**Tiêu đề:** Hệ Thống Phân Bổ Sinh Viên – Giảng Viên Khóa Luận Tốt Nghiệp Bằng Học Tăng Cường

**Mục tiêu:** Phát triển ứng dụng tối ưu hóa phân bổ ~200 sinh viên cho ~39 giảng viên, sử dụng Reinforcement Learning với Action Masking để:
1. Tối đa hóa độ tương thích chuyên môn
2. Tuân thủ 100% ràng buộc hard quota
3. Cân bằng tải công bằng (Fairness)

**Lộ trình:** 56 ngày (8 tuần: 21/09 – 15/11/2026)

---

## 2. Kiến Trúc 3 Tầng

```
Layer 3: React/Vite Web Dashboard (Interactive UI)
        ↓ REST API (FastAPI)
Layer 2: FastAPI Inference Backend (/api/v1/allocate, /recommend)
        ↓ Model Artifacts
Layer 1: Python ML Pipeline (Data processing, RL training, Benchmark)
```

---

## 3. MDP Formulation

**State Space:** Vector 3×39 = 117 chiều
- Compatibility scores sinh viên t với 39 giảng viên
- Remaining capacity ratio (0.0–1.0)
- Current load ratio (0.0–1.0)

**Action Space:** {0, 1, ..., 38} — gán sinh viên cho GV j

**Reward Function:**
```
r_t = w_comp × comp(t, a_t) + w_fair × ΔVar_t - w_pen × I_invalid
```

**Action Masking:** Logit của GV đầy quota → -∞ ⟹ P(invalid) = 0

---

## 4. Technology Stack

**Backend ML (Python 3.10+):**
- gymnasium, stable-baselines3, sb3-contrib (RL algorithms)
- scikit-learn (TF-IDF), sentence-transformers (embeddings)
- scipy (Hungarian algorithm), numpy, pandas

**FastAPI Backend:**
- fastapi, pydantic, sqlalchemy, uvicorn

**Frontend:**
- React 18+, Vite, TypeScript, TailwindCSS, Plotly.React

**DevOps:**
- Docker, Docker Compose, GitHub Actions (CI/CD)

---

## 5. Dữ Liệu & Validation

**Curated Data:**
- 198 đề tài (students) + 39 giảng viên
- Compatibility matrix: 198×39, values ∈ [0.0, 1.0]
- Temporal split: pre-2025 + 75% 2025 → train; 12.5% val; 12.5% test
- **Critical:** Group by student_id, TF-IDF fit on train only

**Hard Constraints:**
- Quota violations = 0 (tuyệt đối)
- Invalid proposals = 0 (với Maskable PPO)
- No data leakage

---

## 6. RL Algorithms

| Algorithm | Family | Primary? | Masking |
|-----------|--------|----------|---------|
| **Maskable PPO** | Policy Gradient | ✅ YES | ✅ Built-in |
| DQN | Value-based | Baseline | ❌ No |
| QR-DQN | Distributional | Comparison | ❌ No |
| A2C | Actor-Critic | Comparison | ❌ No |

---

## 7. Lộ Trình 56 Ngày

| Tuần | Ngày | Giai Đoạn | Sản Phẩm Chính |
|------|------|----------|---|
| 1 | 01–07 | Problem Formulation | MDP spec, Hungarian baseline |
| 2 | 08–14 | Data & NLP Pipeline | Curated data, compatibility matrix |
| 3 | 15–21 | RL Environment | GymMatchingEnv, reward function |
| 4 | 22–28 | RL Training | Checkpoints @ 200k–2M steps |
| 5 | 29–35 | Benchmark & Stats | 5 seeds, t-test, IEEE charts |
| 6 | 36–42 | Lifecycles V2–V3 | Preferences, streaming, Promotion Gate |
| 7 | 43–49 | Thesis Writing | 12 chapters (100–120 pages) |
| 8 | 50–56 | Final Delivery | Slides, defense, submission |

---

## 8. Repo Structure

```
C:\Su\KLTN\KLTN\
├── data/1.pdfs/              # Raw PDFs (FIT-NEU source)
├── src/                       # ML Pipeline (tạo ngày 02–14)
│   ├── data_pipeline/         # NLP, feature extraction
│   ├── environment/           # Gymnasium env
│   └── models/                # RL implementations
├── backend/                   # FastAPI (ngày 09–10)
├── frontend/                  # React/Vite (ngày 10)
├── configs/                   # YAML configs
├── tests/                     # Unit/integration tests
├── eval/                      # Benchmark scripts
├── outputs/                   # Checkpoints, results, figures
├── docs/                      # Technical docs
├── baocao/                    # Thesis report
├── presentation/              # Slides
├── Dockerfile                 # Container
├── docker-compose.yml
├── .env.example
└── .github/workflows/         # CI/CD
```

---

## 9. Ràng Buộc & Tiêu Chí

**Hard Requirements:**
- Quota violations = 0
- Invalid proposals = 0 (Maskable PPO)
- Zero data leakage (temporal split)

**Soft Targets:**
- Mean compatibility ≥ 88% vs Hungarian
- Load variance: minimized
- Training convergence: < 2M steps
- Inference: < 100ms per allocation

---

## 10. Next Steps (KLTN-DAY-02 onwards)

1. **DAY-02-05:** Data processing, NLP, TF-IDF
2. **DAY-06-07:** Week 1 review, Hungarian baseline
3. **DAY-08-14:** Feature engineering, data validation
4. **DAY-15-21:** Gymnasium environment, masking
5. **DAY-22-28:** RL training, hyperparameter tuning
6. **DAY-29-35:** Benchmark, evaluation, statistical tests
7. **DAY-36-42:** Dashboard, API, promotion gate
8. **DAY-43-49:** Thesis chapters
9. **DAY-50-56:** Defense prep, final submission

---

**Generated:** KLTN-DAY-01 (Environment Setup & Analysis)  
**Status:** Architecture Overview Complete ✅
