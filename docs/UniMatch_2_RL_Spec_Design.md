# UniMatch 2.0 — Software Requirements Specification & System Design

Version: Draft 2.0 (2026-10-21). Scope: student–advisor thesis supervision allocation using MaskablePPO and masked DQN, with semester-by-semester model updates.

**Owner amendment 2026-10-23:** The current release uses the deduplicated local corpus and new student CSV inference. Historical semester verification and unavailable temporal/outcome measurements do not block the local release. Preserve provenance, unknown fields, fixed preprocessing, train/evaluation isolation, genuine compatible PPO/DQN checkpoints and offline updates. Run the predeclared five-seed training-step experiment, report validation compatibility rather than unobserved academic accuracy, then validate the additive local API/frontend and grounded read-only assistant. This overrides conflicting mandatory historical-semester gates below. See `rebuild_scope_20261023.md`; local readiness does not mean cloud publication.

## 1. Source audit and current system

Source: https://github.com/namhv521/UniMatch (main); website: https://unimatch-neu.vercel.app/. Website could not be inspected live in the browsing environment; UI conclusions derive from source and deployment documents.

Existing stack: vanilla HTML/CSS/JS and Three.js frontend on Vercel; FastAPI backend on Render; PostgreSQL on Neon. `backend/app/cohorts.py` parses uploaded Excel, computes TF-IDF compatibility via `FeatureBuilder`, selects advisors, derives balanced quota with divmod, and assigns via Hungarian. `src/environment/matching_env.py` already provides a Gymnasium sequential assignment MDP; observation 3M (scores, remaining ratios, loads), `Discrete(M)` actions and mask based on capacity. `src/rl/ppo.py` uses `sb3_contrib.MaskablePPO`; `src/rl/dqn.py` uses plain Stable-Baselines3 DQN without mask support. `src/environment/reward.py` weights compatibility at 1 and change in load variance at 0.15, invalid-action penalty 2. `src/evaluation/promotion.py` already gates real validation results. README: 215 student/thesis records, 38 advisors, split 154/20/21/20, Hungarian default, no RL model promoted. These quantities refer to the documented historical snapshot, not verified present-day institutional enrollment.

Key gaps: cohort/upload flow and trained RL research flow diverge; no coherent semester lifecycle; historic feedback is not a validated outcome reward; capacity-only masks do not encode all operational eligibility constraints; fixed advisor ordering makes action semantics unstable under roster changes; current DQN permits invalid proposals; simulation dataset and actual student outcomes must remain distinct; deployment resources are not a training platform.

## 2. Objectives, exclusions and authority

The product creates explainable **proposals** assigning each student to one eligible advisor, optimizing subject fit, student preferences and load fairness under hard institutional constraints. Coordinators retain authority to approve, edit or reject. Research comparisons include MaskablePPO, masked DQN, and Hungarian, Greedy and Random baselines. Proposed design is not a claim of institutional approval or proof RL outperforms exact optimization.

Out of scope for MVP: automated final academic decisions, unattended on-request GPU retraining, biometric/protected-attribute-based matching, self-reported model superiority, online learning from raw unverified feedback.

## 3. Roles / functional requirements

**Coordinator**: define semester, import advisor roster and student applications, validate exceptions, define hard constraints and capacities, choose model version, preview ranked allocation, approve/edit assignments, publish results, collect structured feedback, review audit trail.

**Researcher / ML engineer**: version datasets/features and env contracts, run train/eval jobs, inspect per-seed metrics, compare against baselines, inspect masked invalid-action rates, promote/rollback candidate models, view drift and continual-learning evidence.

**Admin**: manage access and training approvals, preserve backups, revoke visibility on sensitive documents.

Key requirements (IDs):
- FR-01 Semester entity with unique code, dates, state `draft|open|locked|approved|closed`.
- FR-02 Import validated and versioned Excel/CSV student and advisor data; dedupe IDs within semester; preserve immutable original and SHA-256.
- FR-03 Import real max quotas and eligibility; optional target quotas and fixed allocations; abort or route to human review when no feasible complete matching exists.
- FR-04 Produce normalized student-advisor compatibility with provenance, missing-data flags and versioned features.
- FR-05 Run Hungarian, MaskablePPO, masked DQN under the same feasible-set rules; block invalid allocations at the environment and final validator.
- FR-06 Return assignments, per-pair score breakdown, load/capacity, warnings, audit trace, algorithm and model version.
- FR-07 Coordinator review, override (with reason), final approval, and immutable official allocation history.
- FR-08 Collect end-of-semester outcome and structured feedback with timestamps, provenance and consent; avoid equating absence of complaints with success.
- FR-09 Create new dataset version on new semester ingest; train candidate in offline job from existing checkpoint and replay mixed old/new cohorts.
- FR-10 Evaluate across held-out chronological semesters and synthetic perturbations; promote only after tests and authorized signoff.
- FR-11 Roll back model selection without rewriting historical assignments.
- FR-12 No personal data or checkpoint secrets exposed in public Git or browser responses.

## 4. Data contracts

### Semester
`semester_id`, `code`, `academic_year`, `start_date`, `end_date`, `status`, `policy_version`, `created_at`.

### Student application
`application_id`, `semester_id`, `student_id`, `thesis_title`, `thesis_description`, `skill_tags[]`, `topic_tags[]`, `preferences_ranked[]`, `academic_program`, `eligibility_flags`, `consent`, `source_sha256`, `record_status`. Student identity is separately access-controlled; no sensitive personal attributes as model inputs by default.

### Advisor participation
`advisor_id`, `semester_id`, `expertise_tags[]`, `profile_text`, `active`, `capacity_max`, `capacity_min_optional`, `target_load_optional`, `eligible_programs[]`, `restrictions[]`, `existing_load`, `source_version`.

### Outcome and feedback
`semester_id`, `student_id`, `assigned_advisor_id`, `approved_assignment_id`, `completed`, `change_requested`, `change_reason`, `completion_status`, `student_satisfaction_optional`, `advisor_satisfaction_optional`, `outcome_observed_at`, `feedback_quality`, `provenance`. Never use incomplete outcome fields as true negatives.

### Features and versions
`feature_version`, `text_model_version`, `taxonomy_version`, `vocabulary_hash`, `student_order_hash`, `advisor_order_hash`, `matrix_hash`, `normalization_manifest`, `training_semester_ids`, `data_cutoff_timestamp`. Deterministic advisor ID-to-action mapping must be versioned.

## 5. Optimization problem and feasibility

For student set S and advisors A, binary x_ij denotes assignment. `c_ij` in [0,1] is compatibility. Maximize weighted suitability/preference/fairness subject to sum_j x_ij=1, sum_i x_ij<=capacity_j and x_ij=0 if pair ineligible. Respect fixed assignments, advisor restrictions and total capacity. If any capacity is insufficient or the bipartite graph has no full matching, return `infeasible` with reasons; a mere positive global sum of capacities is insufficient to guarantee feasibility.

Quota modes: hard maximum from administration; optional minimum/target with separate feasibility checks. Balanced equal quotas such as 10–10–9–9 are a selectable simulation policy, **not** automatically the institutional rule. Fairness must compare normalized loads against capacity/target rather than penalizing justified unequal absolute loads.

## 6. Unified RL MDP

Episode: one full allocation of a semester/cohort. At reset sample one train cohort, optionally shuffle student order and apply approved augmentations. Student-order randomness is controlled and recorded. One step assigns the next student; terminal upon complete assignment or controlled infeasibility resolution.

Observation state comprises: current student representation; scored compatibility to M advisors; remaining capacity and normalized load per advisor; eligibility mask; unscheduled students' compatibility-demand summary; remaining student count; optional per-advisor utilization targets and expertise vectors. Use fixed M with a canonical advisor ID registry plus `advisor_present_mask` during MVP. Do not silently reorder advisor columns when a semester changes; introducing new advisors requires padding/permutation-consistent representation and model-compatibility verification or retraining. For scalability, evolve to per-candidate shared scorer/attention architecture rather than embedding opaque advisor IDs.

Actions: `Discrete(M)` where action j chooses a feasible advisor j. PPO: `sb3_contrib.MaskablePPO` (its masked action distribution used in learning/prediction/evaluation); DQN: implement masked epsilon-greedy exploration, masked greedy argmax and masked Bellman max targets (terminal masked correctly), rather than using stock SB3 DQN as-is. Prefer conservative behavior if no valid action. Strict final feasibility validator always runs.

Reward: `r_t = w_c*C_t + w_p*P_t + w_f*(Phi(s_{t+1})-Phi(s_t)) - w_v*invalid_t`, plus terminal reward/penalty on global metrics. `Phi` should reflect normalized utilization/target fairness. Make invalid action impossible in the production masked policy, and count any mask violation as a blocker. Reward terms bounded and monitored separately. Do not use downstream success labels until their provenance, delay and confounders are explicitly modeled and outcome collection is sufficient. Student preferences may be unavailable and should have a missingness indicator rather than fabricated values.

A safer optimality benchmark for pure sum compatibility with quota and eligibility is min-cost max-flow/Hungarian with slot expansion; compare objective under identical constraints. Hungarian can remain production fallback.

## 7. Algorithm implementations

PPO: update existing `src/rl/ppo.py`; train with vectorized randomized cohort environments, masked evaluation and a configurable policy network (e.g. 2x128 initial tuning candidate), rather than treating current tiny demo configuration `n_steps=8, batch_size=4, n_epochs=1, net_arch=[16]` as final. Track entropy, explained variance, KL divergence and deterministic validation returns. Continue model weights between semesters only if observation/action/feature contracts are compatible; collect fresh rollout (PPO is on-policy).

DQN: replace stock invalid-action pathway with masked Double DQN design; use target network, replay buffer, epsilon decay, n-step optional, prioritized replay only after baseline stability. Store transitions with next-state valid-action masks and feature/semester version. Ensure forbidden actions never selected in either action prediction or Bellman target. Replay buffer may be persisted when schema unchanged, with balanced sampling of historical and recent data; incompatible buffer discarded/migrated intentionally. Hyperparameters are tuned on train/validation, not predetermined as proof of superiority.

Identical observations, available actions, reward, train/test cohorts and evaluation seeds are mandatory for fair comparisons. Train 5 seeds initially and report mean, standard deviation and confidence intervals; 2 million steps is a budget candidate, not a guarantee.

## 8. Continual learning protocol

At semester close: (1) store validated outcomes; (2) freeze immutable snapshot; (3) run data quality, duplicate/identity, advisor and privacy checks; (4) generate train candidate from latest eligible model checkpoint and replay previous cohorts; (5) retain old representations unless deliberate, versioned change; (6) run candidate PPO and DQN training offline; (7) evaluate on unseen chronological validation and historic regression cohorts; (8) compare with deployed incumbent and Hungarian; (9) approve/promote or reject; (10) enable candidate inference for the next semester; (11) retain previous production artifacts for rollback.

Important: one real allocation semester does not supply many independent RL ground-truth rewards. Millions of steps arise from resampling historical cohorts/simulated feasible matchings and do not amount to millions of real outcome observations. Avoid automatically retraining reward models on tiny or biased feedback sets.

Chronological split: past semesters used for training; latest closed semester used for validation; a prospective later semester serves as untouched test. No training on current or future holdout outcomes. Within tiny-data early stages, clearly label retrospective offline simulations as research evidence rather than prospective benefit.

Use training plan: `warm_start + old/new cohort replay + periodic from-scratch control + validation gate`. Incremental learning must demonstrate non-regression on old semesters. If vocab, observation dimension, advisor mapping or masking contract changes, rebuild/new-version models rather than forcibly loading incompatible weights.

## 9. Schema additions (PostgreSQL)

New normalized tables:
`semesters`, `semester_students`, `semester_advisors`, `eligibility_rules`, `assignment_batches`, `assignments`, `assignment_overrides`, `semester_outcomes`, `feedback_events`, `dataset_versions`, `feature_versions`, `training_runs`, `evaluation_runs`, `model_versions`, `promotion_events`, `audit_events`.

Each training run stores `training_semesters`, `base_model_id`, `data_hash`, `feature_hash`, `env_version`, `reward_version`, `capacity_policy_hash`, `code_commit`, `seed`, `steps`, `config`, `artifact_uri`, `sha256`, `metrics` and `status`. Each assignment batch stores immutable snapshots of inputs, model version and rules, with coordinator approval status. Existing snapshots/simulation_runs/feedback can be migrated via explicit additive migrations; do not overwrite.

Keep large checkpoints/replay buffers in versioned private object storage or authorized artifact storage, store URI and checksum in DB. Never put large changing binary checkpoints in Git. Vercel/Render/Neon serve inference/metadata; run training on separately scheduled CPU/GPU worker.

## 10. API contracts (proposed)

`POST /api/v2/semesters` create semester.
`POST /api/v2/semesters/{id}/students/import` upload + validation preview.
`POST /api/v2/semesters/{id}/advisors/import` roster and quota.
`POST /api/v2/semesters/{id}/validate` feasibility + data readiness.
`POST /api/v2/semesters/{id}/allocate` body `{algorithm: "ppo|dqn|hungarian", model_version?, dry_run: true}`; returns job or synchronous feasible result plus metrics.
`POST /api/v2/allocations/{id}/approve` authorized approval.
`POST /api/v2/allocations/{id}/override` authorized change with reason and revalidation.
`POST /api/v2/semesters/{id}/outcomes` structured final outcome ingestion.
`POST /api/v2/training-runs` authorized asynchronous-job creation with exact data range and base checkpoint.
`GET /api/v2/training-runs/{id}` progress, logs URI, metrics.
`GET /api/v2/models` registry, provenance and promotion status.
`POST /api/v2/models/{id}/promote` guarded by evaluation results and admin approval.
`POST /api/v2/models/{id}/rollback` restore previous version.

Responses must include errors such as `INFEASIBLE_CAPACITY`, `ELIGIBILITY_CONFLICT`, `MODEL_CONTRACT_MISMATCH`, `TRAINING_DATA_INSUFFICIENT`, `MODEL_NOT_PROMOTED`. Do not expose personally identifying application data on public endpoints. Training calls return job IDs; backend request need not stay open.

## 11. Evaluation, gates and acceptance criteria

Metrics: complete coverage; hard constraint violations (zero); true invalid action attempts (zero); mean compatibility; preference satisfaction/top-k preference; normalized load imbalance; minimum compatibility and lower-tail scores; fairness by legitimate program/topic groups; number of manual overrides; elapsed inference time; prospective outcome quality if measured.

Compare: Random, Greedy, Hungarian, PPO, DQN across same controlled cohort suite and seeds. Report confidence intervals and differences; evaluate on shifts in students, advisor participation, quota and missing features. `optimality_ratio` should be explicitly defined relative to objective solved by exact optimizer, and must not mix incompatible reward vs compatibility scales.

Minimum gates: 100% feasible allocation when problem feasible, zero hard constraint violations, no unbounded invalid loops, no leakage, no deterioration outside prespecified margin on historical validation cohorts, reproducible version/seed/hash, inference latency within agreed SLO, explicit approval. Promotion requires demonstrable benefit on relevant objective or operational tradeoff; otherwise Hungarian remains fallback. Human override is audited, not directly treated as RL reward without analysis.

Example non-binding targets: coverage 100%, violations 0, match completion within 10 seconds for <=500 students and <=100 advisors on provisioned inference service, reproducibility exact deterministic inference given fixed seed/version, no regression in average compatibility beyond 2 percentage points against incumbent unless approved for a documented fairness gain. Final thresholds require owner signoff and measurements.

## 12. Security and governance

Private student profiles and thesis data; role-based access (student / advisor / coordinator / researcher / admin as needed), audit log and rate limits, data minimization, retention schedule, documented consent and academic approval, encrypted transport, secrets outside source control, protected raw files and model artifacts, backup + restore drill. The current single-session login approach is not sufficient for multi-role institutional rollout. Explain allocations without exposing other students' private data. AI provides decision support only.

## 13. Implementation map

Modify `backend/app/cohorts.py` to use an injected matching service with selectable `hungarian|ppo|dqn` and a common allocation result schema.
Modify `src/environment/matching_env.py`, `action_mask.py`, `reward.py` for generalized eligibility, stable ordering, normalized load, cohort-wide state and terminal score.
Extend `src/rl/ppo.py`, replace `src/rl/dqn.py` masked logic and add `src/rl/continual.py`, `src/rl/cohort_sampler.py`.
Extend `src/features/feature_builder.py` for stable/versioned features.
Extend `src/evaluation/benchmark.py`, `promotion.py` for chronological regression evaluation and guarded promotion.
Extend `src/serving/model_registry.py`, `service.py` for semantic versions and safe rollback.
Add `backend/app/semesters.py`, `training_jobs.py`, `outcomes.py`; additive DB migrations and workers.
Extend `frontend/app.js` and cohort UI with semester chooser, allocation algorithm, model version, live quota and reporting; retain 3D as optional explainability layer.
Add tests under `tests/environment`, `tests/rl`, `tests/cohorts`, `tests/evaluation`, `tests/storage`.

## 14. Roadmap

Phase 0 — baseline reproduction and data audit: verify present cohort service and artifacts, lock current benchmark, define outcomes and institutional constraints.
Phase 1 — unified MDP and matching API: share data/feature/quota logic, implement hard feasibility + mask, tests.
Phase 2 — PPO/DQN: performant training, masked target DQN, multi-seed benchmark, explainable output.
Phase 3 — semester data & continual pipeline: DB migrations, data snapshots, outcomes, replay, candidate version and offline worker.
Phase 4 — web integration and model governance: dashboard, promotion/rollback, role-based controls, audit and security.
Phase 5 — prospective pilot: actual semester outcomes and human oversight, monitoring and retrain cycles.

## 15. Definition of done

(1) Coordinator can upload one actual semester, select available advisors and correctly bound quota; (2) PPO, DQN and Hungarian produce validated, complete, auditable proposals; (3) no action invalid in model inference; (4) same evaluation contracts and data leakage guard for all methods; (5) a second closed semester can be ingested, immutable history retained, new candidate warm-started and tested; (6) promote or rollback model without changing historical assignments; (7) tests + deployment/backup/security acceptance pass. RL need not beat Hungarian to call implementation complete; results must be reported without exaggeration.


## 16. Amendment 2.1 — Clean-room data rebuild and source-of-truth reset (2026-10-21)

**Supersedes the historical 215/38 snapshot as a training/serving data source.** The 215 rows and 38 advisors remain historical audit artifacts only. The NEW student source is the contents of `C:\Su\KLTNv2\KLTN\data\1.pdfs` (user reports 220 PDFs). The NEW advisor source is `https://fit.neu.edu.vn/lecturer` and its validated profile links. These sources are unavailable inside this authored specification; no extraction has been run and no claim about 220 unique valid students or a particular new advisor count is made. The agent must execute source inspection in the user's own workspace and create verifiable inventory and evidence before training.

### 16.1 Mandatory sequence and stage gates

1. **Inventory and preserve:** record relative path, file size, SHA-256, PDF page count, text-vs-scan detection and extraction status for every item in `1.pdfs`. Require expected input count 220 or BLOCK and request investigation; never silently discard, merge, or synthesize an entry. Archive immutable raw input and crawler pages outside Git.
2. **Student extraction:** text-first PDF extraction (e.g. PyMuPDF/pdfplumber), OCR only for scan pages, with language-appropriate OCR when necessary. Retain field evidence (`source_pdf`, `page`, `extraction_method`, raw snippet), confidence, ambiguity flags, and exception queue; deduplicate *entities* separately from inventory. Human-review uncertain name/title/topic/technology mapping. Handle multiple theses per PDF and multiple PDFs per student explicitly.
3. **Advisor crawl:** respect robots, rate limits and applicable conditions; inspect whether `/lecturer` is JS-rendered and permitted APIs/detail pages. Cache retrieved HTML/JSON with URL/time/hash and provenance. Obtain public expertise/research/department/publications where available, mark absent information missing; never infer professional expertise solely from name or fabricated profile. Link identities across records only with evidence.
4. **Normalize:** Unicode Vietnamese, whitespace, aliases and controlled topic/skill taxonomy; keep original fields alongside canonical labels. Publish taxonomy version, alias dictionary, dedupe decisions and human-reviewed quality report.
5. **Import contracts:** validate both CSV contracts in `templates/students_import.csv` and `templates/advisors_import.csv` using data dictionary (`UniMatch_Feature_Data_Dictionary.md`); CSV templates are deliberately header-only; nulls are not converted into zero skill. Each source field must distinguish `observed`, `self_reported`, `inferred`, `missing` and related confidence/evidence.
6. **Feature evaluation:** measure missingness, source reliability, ID leakage, train/test leakage, sparse tags, coverage, value to matching and fairness; compare text TF-IDF vs controlled multi-label tags vs combined weighted vectors. Freeze selected features and train-only fitted transformers. Exclude contact/identity/protected or subjective unvalidated proxies from model matching.
7. **Feasibility baseline:** real maximum quotas require authorized input, cannot be inferred from faculty web profiles. Student preference must be explicitly collected rather than fabricated from PDFs. Use official constraints when available; otherwise label research-only simulated quotas and outcomes.
8. **Learning:** recreate chronological splits without leakage, benchmark Hungarian first, then masked PPO and DQN on shared Gymnasium environment and identical feature contract, train multi-seed, evaluate unseen cohorts and variation in student/advisor counts. Keep an untouched holdout.
9. **Serving/deploy:** connect new imports, assignment workflows, explanation and traces to existing Vercel/Render/Neon; release only after schema migration, security, integration, model governance and rollback pass. No silent promotion when active model is incompatible with new advisor ID mapping or feature dimension.
10. **Advanced phase:** only after core gates succeed add grounded Q&A/chatbot/agent for student↔advisor fit and advisor expertise; answer with evidence, provenance and accessible ACLs, never promise allocation. Grounded retrieval and deterministic scoring first, optional LLM later.

### 16.2 Fresh-rebuild compatibility rules

- Treat old `data/curated`, feature manifests, compatibility arrays and model checkpoints as **read-only legacy**, never overwrite or falsely relabel hashes. Generate new versioned dataset under a fresh namespace and migrate serving only on approved release.
- **Unchanged CSV format across semesters**; additional features get a schema version/migration, not silently added columns. `skills_csv` contains normalized semicolon-delimited taxonomy IDs, and other scalar proficiency columns are only evidence-backed (blank means missing).
- `student_id`, `advisor_id`, `source_*` and identifying metadata are joining/provenance fields, **not numeric ML features**. Only `feature_allowlist.yaml` determines model input.
- If PDFs have no explicit student skill statement, produce `skill_provenance=inferred_from_thesis` and do **not** equate extracted thesis terminology with personal skill mastery. Unknown proficiency remains blank. Outcome/feedback cannot be labeled retrospectively without real observation.
- Do not let an agent auto-finalize academic allocation. Coordinator approves final assignments.
- Previous-stage gates must pass before proceeding. Track `blocked`, `partial`, `verified` states and artifact checksums; no synthetic data may be presented as real.

### 16.3 Deliverable references

Read `UniMatch_Agent_Rebuild_PRD.md` as the operational agent contract, `UniMatch_Feature_Data_Dictionary.md` as the import/feature contract, and `students_import.csv` / `advisors_import.csv` as reusable header-only import templates. Those files are companion documents to this original SRS.
