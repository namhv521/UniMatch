# Local CSV and RL Release Implementation Plan

> **For agentic workers:** Execute the approved PRD plus owner amendment task by task with TDD; delegate independent training/API/UI work and review before activation.

**Goal:** Verify whether more training helps genuine PPO/DQN, then provide local CSV inference, selected-advisor quotas, replay/export and a source-cited read-only assistant.

**Architecture:** Frozen P3/P4 source/feature contracts; immutable higher-step experiments; additive FastAPI entrypoint and frontend page. Preserve old runtime and historical gate artifacts.

**Tech Stack:** Existing Python/FastAPI/NumPy/PyTorch/SB3 and vanilla HTML/CSS/JS. No new runtime dependency.

**Spec:** `docs/UniMatch_Agent_Rebuild_PRD.md`, `docs/UniMatch_2_RL_Spec_Design.md`, `docs/UniMatch_Feature_Data_Dictionary.md`, `docs/rebuild_scope_20261023.md`.

## Global Constraints

- No historical semester verification for this release; retain source/evidence validation.
- No online updates inside request handler.
- No fabricated records, skills, feedback, model output or real accuracy labels.
- Train 135, validation 29, final test 30 preserved; five seeds, declared steps 16384/24576/32768.
- No checkpoint promotion merely because reward increases; Hungarian remains a labeled baseline and safe default.
- Keep raw private data/artifacts/tokens outside Git and client bundles.

## Review Focus

- Uploads never fit vocabulary/IDF or become approved gold automatically.
- New cohort sizes/roster selections preserve the 35-advisor action order and mask semantics.
- Token/ownership checks protect cohort data and exports; CSV/formula/HTML injection fail safely.
- Empty/missing/unscorable profiles produce honest unknown/infeasible results.
- UI and assistant show real checkpoint/trace/source evidence; local proof never implies cloud deployment.

## Tasks

- [x] Audit current local source/artifact coverage and current checkpoints.
- [x] TDD higher-step experiment runner; five-seed learning curve, paired statistics, validation-only stage selection, reload and manifest verification.
- [x] Publish revised P6 gate after experiment, keeping prior partial report immutable.
- [x] TDD additive inference service/API with existing CSV validator/frozen feature pipeline, private cohort ownership, template, roster/quota, recommend/compare/trace/export.
- [x] Add frontend CSV workflow and accessible replay; syntax/build and desktop/mobile/error-state checks (mobile responsive DOM, desktop screenshot).
- [x] End-to-end local API with actual model hashes; test hard constraints, privacy and export, publish P7 gate/runbook.
- [x] Only after P7 gate: add read-only source-cited assistant/tools with grounded matching, deterministic intent routing and clear limitations; test citations/injection/privacy/latency.
- [x] Final full regression (399 passed), independent review, private artifact manifest and phase quality reports; no automatic cloud publication.
