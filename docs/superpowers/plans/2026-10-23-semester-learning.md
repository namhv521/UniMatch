# Semester Learning Implementation Plan

> **For agentic workers:** Use the existing approved PRD, Superpowers execution and TDD; work in isolated new modules because P3–P5 source hashes are frozen.

**Goal:** Reproducible semester snapshots, offline PPO/DQN continuation, temporal evaluation, and rollback without changing the working website.

**Architecture:** Content-addressed immutable data; explicit compatible representation bridge; local offline job queue and model registry. Unknown dates, outcomes and approvals remain unknown.

**Tech Stack:** Python standard library, existing NumPy/PyTorch/SB3, pytest. No new dependency.

**Spec:** `docs/UniMatch_Agent_Rebuild_PRD.md` Phase 6 and `docs/UniMatch_2_RL_Spec_Design.md`.

## Global Constraints

- No online updates inside request handler.
- Legacy 215 records are not a trusted dataset.
- Never rewrite approved assignments during model rollback.
- Never train on validation/test; do not rename research cohorts as historical semesters.
- Register candidates separately from promotion; default remains Hungarian.

## Review Focus

- Repeated uploads and concurrent jobs must not overwrite immutable artifacts.
- Missing chronology blocks temporal claims; document timestamps alone do not prove prediction-time availability.
- Changing action order/taxonomy/representation invalidates warm start and replay.
- Dataset overlap, duplicate source groups and holdout transitions must fail closed.
- Rollback preserves approved assignment bytes and has a verifiable audit trail.

## Tasks

- [x] Audit user-provided August 2026 folder and original document term evidence. Database connection unavailable; report exact limits, no silent gold import.
- [x] TDD `src/data_pipeline/semester_snapshots.py`: idempotence, immutable hashes, provenance, closure and drift; test traversal/tampering/unknown outcomes.
- [x] TDD `src/rl/continual_dqn.py`: compatible parent load, separately attributed old/current replay, exact stratification, checkpoint integrity.
- [x] TDD `src/rl/semester_learning.py`: PPO fresh rollouts, source-bound offline queue, temporal contract isolation and forgetting metrics.
- [x] TDD `src/serving/rebuild_registry.py`: candidate registration, fail-closed approval, atomic rollback and immutable assignment history.
- [x] Run existing-checkpoint rehearsal `20261022T182220Z-9f0ee7b0`: 1,024 steps per learner, all 135 train rows encountered, reserved 59 excluded, reload/drill verified. No temporal claim.
- [x] Full rebuild suite 345 passed, independent 25 P6 + 246 P5 artifact review, 23 runtime files unchanged; publish reports.
- [ ] Curate real semester chronology and prediction-time feature availability, obtain source-bound closed assignment/outcome evidence where available, reconstruct temporal parent/encoder and measure frozen unseen-term/old-term performance. P6 remains partial and P7 is not started.
