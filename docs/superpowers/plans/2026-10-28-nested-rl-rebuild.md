# Nested RL Fresh Rebuild Implementation Plan

> **For agentic workers:** Use Superpowers executing-plans task by task; the user explicitly authorized parallel agents. Do not follow the historical 21–23/10 phase gates as the new specification.

**Goal:** Preserve the current repository on remote `backup`, recollect sources into a new private namespace, and implement executable within-semester feedback rounds with cross-semester checkpoint inheritance.

**Architecture:** Reuse native masked PPO/Double DQN and constrained matching. New source collectors and version classification feed a frozen fresh-data suite; a new round controller creates source-bound candidate checkpoints and evaluation reports. Existing gold, checkpoints, source data and serving release remain read-only until new evidence permits a compatible replacement.

**Tech Stack:** Existing Python, BeautifulSoup, PyMuPDF, scikit-learn, Gymnasium, PyTorch and SB3; standard HTTP/file/JSON interfaces. No new infrastructure dependency.

**Spec:** `docs/rl_hai_cap_va_corpus_giang_vien_20261027.md`, with the latest user authorization on 28/10 enabling actual new collection/implementation and superseding the URL-only stage.

## Global constraints

- Faculty/model cutoffs: V1 through 31/12/2024; V2 through 30/06/2025; V3 through 31/12/2025; V4 through 30/06/2026, Asia/Saigon. Latest student grouping: Jan–May previous-year .2, June–August previous-year .3, September–December current-year .1. Student V2 Jan–May2025, V3 June–December2025, V4 Jan–May2026; V1 historical through2024. Summer2024.3 pools into training2025.1.
- New output only under `data_rebuild/nested_rl_20261028/<run>/`; never overwrite an existing run or old data.
- Fresh live faculty HTTP, fresh source-byte student extraction; old raw/bronze/gold/features are not new collection. The URL register is a seed list only.
- Missing external accounts use FIT NEU only. Never guess identities, publication months, preferences, grades, quota confirmations or feedback.
- Year-only records cannot be assigned arbitrarily to half-year windows. Event/publication date, retrieval date and availability are separate.
- Sparse feedback means inner rounds may be unavailable/skipped. Do not manufacture four rounds or claim monotonically improving models.
- Historical document proxies may support explicitly retrospective research, not claims of prediction-time academic outcomes.

## Tasks and ownership

- [x] Backup source/docs/tests to exact remote `backup`, verify SHA; implementation on `susois/nested-rl-20261028`.
- [x] Fresh faculty collector, publication/date provenance, tests — agent `fresh_faculty`.
- [x] Fresh student full-text extraction, source inventory/aliases, precise V1–V4 classifier, tests — agent `fresh_students_versions`.
- [x] Nested learner/round manifests, parent/replay/holdout guards, training/inference parity, tests — agent `nested_rl_engine`.
- [x] Fresh feature/suite integration, baselines, readiness and CLI orchestration — root.
- [x] Run new collection, inspect data/date/missingness, run allowed new-data research smoke; do not simulate missing real feedback.
- [x] Review, integration checks, record evidence and concrete remaining requirements; continue fixing actionable failures.

## Review focus

1. Fresh fetch provenance versus merely reparsing old sources.
2. Year-only 2025/2026 data at half-year boundaries; no retrieval-time backdating.
3. Full source/alias accounting and old-data immutability.
4. Parent, signal-state and split binding across inner and outer rounds; stale replay.
5. Research-only validation versus model promotion and real educational effectiveness.

## Execution ledger

- Backup pushed and remote verified: `242fbea5351daafd682f7842cedc9ac2ff6b2c25` on `backup`.
- Latest scope authorizes new collection and implementation; keep the version calendar and nested-RL requirements from 27/10. URL-only stage is historical.
- Live FIT directory is JS-rendered; public sitemap exposes the 38 profile URLs. Crawler uses fresh sitemap/profile HTTP, not cached directory pages or disallowed API.
- Fresh faculty38/publication entries413; external accounts3 attempted, blocked with receipts. Fresh extraction219files/218unique documents/322007blocks; reviewed student version counts32/80/63/1, unassigned19, unknown11, ambiguous12.
- Latest user month correction propagated to canonical spec/PRD/SRS/data dictionary/README and cover-pages-only classifier. Original sources immutable; reviewed derivative repairs2 actual extraction defects.
- Smoke seed42/1024steps: PPO V1,V2 accepted; V3 rejected, retainV2. DQN V1 accepted,V2 rejected, retainV1. All actual warm starts equal parent and reload/inference parity passed. Final test untouched; V4 insufficient and real within-term signals absent.
- Cross-review fixed unapplied feedback, stale replay, cumulative holdout leakage, missing old-goal tests, skipped semester lineage, blocked-bootstrap failure, source-output protection and frozen encoder provenance. Future round manifests also record source code hashes.
- Old-data preservation225files unchanged by size/mtime; old advisors/students CSV hashes equal before run. Full results/commands/limits: [rebuild report](../../nested_rl_rebuild_20261028.md).
