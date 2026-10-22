# Phase 5 Constrained Matching and RL Implementation Plan

> **For agentic workers:** Use Superpowers TDD/executing-plans for each owned task. Work in isolated new rebuild modules; preserve the approved predecessor artifacts and incumbent website.

**Goal:** Deliver source-bound exact allocation, a shared masked environment, real CPU-trained MaskablePPO/Double DQN and a reproducible five-seed offline comparison.

**Architecture:** Read only `load_approved_features` from verified P4 `20261022T115327Z-1850251a`. A single validated allocation problem defines canonical advisor actions, equal quotas, observed features and explicit eligibility. Exact residual feasibility drives every algorithm's mask. Train on disjoint groups within135train; validation29/test30 are evaluation only. Store checkpoints/traces/manifests privately and publish an honest technical gate, never an academic assignment or automatic model promotion.

**Tech Stack:** Existing NumPy/SciPy, Gymnasium0.29.1, PyTorch2.8.0, Stable-Baselines3 2.3.2, sb3-contrib2.3.0. CPU, one Torch thread. No new service.

**Spec:** PRD Phase5; RL SRS sections5–7,11,16; approved P4 feature contract and user-authorized equal-division policy.

## Global constraints

- Preserve35 canonical advisor IDs/actions; presence masks support subsets. Reject an unregistered advisor or incompatible feature/environment/replay contract.
- Research roster is the30 fully scorable profiles, explicitly a diagnostic assumption. It is not a confirmed semester roster or supervisory eligibility. Real allocation requires coordinator selection/eligibility/policy input.
- Unknown features/preferences stay masked. Topic terms are not personal proficiency. No outcome reward or fabricated actual feedback.
- Hard masks include capacity, available score, explicit eligibility, fixed assignments and residual global feasibility. A locally valid choice must not strand a future constrained student.
- Equal quotas use recorded canonical selected-advisor order and divmod; never silently rebalance an infeasible policy.
- Objective is compatibility plus observed preference. Normalized-load potential and completion reward have explicit separate trace components. No required RL superiority to Hungarian.
- Training budget declared before results: five seeds42–46,16,384 timesteps per algorithm/seed. This is a bounded offline benchmark, not convergence or future-semester proof. CPU smoke precedes it.
- Split135/29/30 unchanged. Three disjoint45-student training cohorts; no test/validation rows in replay or PPO rollouts. Repeated permutations are not independent real semesters.
- No production promotion/deployment. Hungarian remains the selected exact fallback. Missing real semester chronology/outcomes/roster blocks operational claims.

## Review focus

- Hall conflicts even when total capacity is sufficient; fixed future assignments must survive earlier choices.
- Epsilon exploration, greedy Q and Double-DQN bootstrap all respect masks, including terminal all-false masks and nonterminal truncation.
- Immutable action mapping and checkpoints must reject stale feature/snapshot/environment contracts.
- Every replay row carries its split/contract; loss/reward/steps and seed metrics must be measured, not placeholders.
- Source matrices/policy artifacts are immutable; traces replay exactly and never expose real data through tracked outputs.

## Tasks and ownership

### 1. Common problem and exact baselines — agent phase0

Create `src/domain/rebuild_matching.py`, `src/baselines/rebuild_baselines.py`, `tests/rebuild/test_phase5_matching.py`.

- [x] Write/run failing tests for source shape/masks, quota order, Hall/fixed conflicts, globally safe actions and final validation.
- [x] Implement AllocationProblem, equal_quotas, feasible, action_mask, validate_assignments and solve(Hungarian/Greedy/Random).
- [x] Verify exact objective against small exhaustive search; every feasible baseline completes without hard violations.

### 2. Shared Gymnasium MDP — agent word_archive

Create `src/environment/rebuild_env.py`, `tests/rebuild/test_phase5_env.py`.

- [x] Write/run failing tests for state9M+2K+1, missing masks, seeding, invalid actions and Gymnasium lifecycle.
- [x] Implement MatchingEnv with actual decision/reward/load/mask traces and final validator.
- [x] Verify trace replay, fixed assignments and common problem semantics with the baselines.

### 3. Masked Double DQN — agent pdf_extract

Create `src/rl/rebuild_dqn.py`, `tests/rebuild/test_phase5_dqn.py`.

- [x] Write/run adversarial tests for masked exploration/argmax, online masked selection/target gathering, terminal masks and replay copying.
- [x] Implement actual optimization, target network, epsilon schedule and version-bound replay/checkpoints.
- [x] Verify safe weights-only checkpoint load/hash/contract, replay parity and actual train-only provenance.

### 4. P4 cohort adapter, PPO and benchmark — root

Create `src/data_pipeline/rebuild_cohorts.py`, `src/rl/rebuild_ppo.py`, `src/evaluation/rebuild_benchmark.py`, `scripts/benchmark_rebuild_matching.py`, their Phase5 tests and isolated RL requirements.

- [x] Write/run tests for P4 binding, training/evaluation disjointness, explicit research/operational policies and immutable action mapping.
- [x] Build controlled taxonomy mention vectors with missing masks; generate3disjointtrain cohorts and frozen validation/test/stress cases.
- [x] Implement MaskablePPO with masks at rollout/predict/evaluate; safe state-only artifacts and actual loss/timestep logs.
- [x] CPU smoke, then train/evaluate5seeds at the predeclared budget. Compare Hungarian/Greedy/Random/PPO/DQN on identical cohorts/masks/quotas.
- [x] Archive per-seed objectives, normalized load fairness, runtime, lower-tail scores, traces, model/Q or policy outputs, confidence intervals, checkpoint/replay hashes and save/load reproducibility.
- [x] Independently review real artifacts, run full rebuild tests and write quality report/operator guide. Gate technical readiness separately from real allocation and model promotion. Do not startP6 until P5 checks pass.

## Result

Full run `20261022T122801Z-fd20da3a`, five seeds42–46,16,384steps peralgorithm/seed;10actual checkpoints. 281rebuild tests pass, including74Phase5. 246artifacts SHA verified;125feasible results allcomplete/zero violations,75infeasible stress results rejected,50loaded/original learned-policy traces match. Research technical gate VERIFIED; actual allocation unauthorized and no model promoted. Test mean compatibility: Hungarian0.259276, Greedy0.170531, Random0.072226, PPO0.076970, DQN0.168374. Keep Hungarian as default; no claim of RL convergence/superiority/future-term outcomes. P6 may start; incumbent untouched.
