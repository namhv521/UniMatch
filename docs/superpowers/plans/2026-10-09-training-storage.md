# Training and storage Implementation Plan

**Goal:** dữ liệu được audit, RL train đúng snapshot và chạy qua API, PostgreSQL/Docker/GitHub sẵn sàng sử dụng.
**Architecture:** giữ frontend/API; bundle dữ liệu đã xác thực cộng PostgreSQL persistence; training opt-in.
**Tech Stack:** FastAPI, NumPy, SB3, psycopg, PostgreSQL, Docker Compose.
**Spec:** `docs/superpowers/specs/2026-10-09-training-storage-design.md`.

## Constraints

Không dùng test/future để train; không đổi hash checkpoint cũ; không redesign; không chạy full training; không commit/push hoặc xóa dữ liệu.

## Tasks

- [x] Audit: thêm `scripts/audit_data.py` và tests cho file malformed/array nonfinite/snapshot split sai; chạy trên folder hiện tại và ghi report.
- [x] Training: thêm `scripts/train_real_rl.py`, tests preflight và resume sai snapshot; tái sử dụng `src/rl` trainers, ghi checkpoint ở `research-current`, registry hỗ trợ thư mục này. Run ngắn trên toàn bộ train/advisors và kiểm chứng API.
- [x] Persistence: schema SQL và `backend/app/storage.py`, import snapshot idempotent, lưu run và feedback; integrate `main.py`, tests API và PostgreSQL integration opt-in.
- [x] Packaging: Dockerfile build frontend và chứa scripts/schema, Compose dashboard/db/train profile, `.env.example`, `.gitignore`, `.dockerignore`; kiểm tra ignore, build, config, database nếu daemon khả dụng.
- [x] Handoff: runbook chi tiết và kết quả kiểm chứng, ghi rõ audit blockers và các check chưa chạy được.

## Review focus

File nguồn lỗi không đồng nghĩa snapshot active lỗi; resume sai contract phải bị từ chối; checkpoint smoke không được phục vụ trên real; database lỗi không được âm thầm bỏ mất run; private data và secret không vào build context/GitHub; stale benchmarks không được trình bày là kết quả mới.
