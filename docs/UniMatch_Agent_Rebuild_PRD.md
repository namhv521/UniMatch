# UniMatch 2.1 — Product Requirements & Agent Execution Contract

**Status:** engineering specification, not proof of execution. **Date:** 2026-10-21. **Priority:** rebuild all data from source, then implement matching and train PPO/DQN, then production deploy and visualization; chatbot/agent is a post-MVP enhancement.

**Owner scope amendment — 2026-10-23:** All available data is local to this project and the explicitly supplied local folder. Use the deduplicated, source-validated local corpus; preserve quarantined records and report their limits. Historical semester verification is **not a release gate** for the current workflow. New student profiles are imported from the designed CSV template and scored with a frozen feature pipeline and genuine saved PPO/DQN models. The frontend selects participating advisors and previews equal quotas. Evaluate whether increasing training steps improves convergence/validation compatibility; do not call compatibility an observed academic accuracy rate. Keep train/evaluation isolation, missing values, source provenance, checkpoint compatibility, offline training and rollback. Temporal/outcome evaluation remains supported when data becomes available, but its absence does not block the local release. Proceed to P7/P8 after the revised current-phase checks pass. Cloud publication is not implied by local readiness. See `rebuild_scope_20261023.md` for the exact revised acceptance contract. This amendment takes precedence over older mandatory semester/temporal conditions below.

## 0. AGENT MISSION (copy into coding-agent task)

You are the implementing engineer for `C:\Su\KLTNv2\KLTN` / https://github.com/namhv521/UniMatch. Perform a **source-first, auditable rebuild** of the data and matching workflow. Read this file, `UniMatch_2_RL_Spec_Design.md`, and `UniMatch_Feature_Data_Dictionary.md` before changing code. The initial source of student/thesis records is **ALL source documents and archives in `C:\Su\KLTNv2\KLTN\data\1.pdfs`**. The owner clarified on **2026-10-21** that **220 means total source files across formats, not 220 PDFs**. The verified inventory is **208 PDF + 8 DOCX + 4 RAR = 220 source files**, plus **1 INI system file excluded from the source count**. This clarification supersedes references to "220 PDFs" in the companion specifications. Advisor profiles must be crawled from **https://fit.neu.edu.vn/lecturer** and the linked valid official pages. DO NOT assume the old 215-row dataset and old 38-advisor snapshot are correct, reconciled, or reusable in training. Preserve existing web behavior until a verified replacement is ready; never destroy legacy data/checkpoints; never fake extracted profiles, skill levels, quotas or feedback.

Work phase by phase, producing source artifacts, quality reports, tests and a short implementation log for every phase. Do not progress past a hard gate when requirements are not met. For external constraints that cannot be inferred (official quotas, actual student skills/preferences, outcome labels), implement import and review functionality and mark training as research-only if these are missing. Only use the current repository and user-provided local directory; do not silently fetch unrelated public theses or mix sources.

**Owner clarification — 2026-10-21:** The current rollout is a pilot on real source data for the next semester. Crawl the entire official directory, but the coordinator selects participating advisors in a frontend selection box for each allocation run. The owner-defined quota policy is **equal division across the selected advisors**: for N students and M selected advisors, assign target/capacity slots using `divmod(N, M)`, giving q+1 slots to r advisors and q to the remainder, with a recorded deterministic advisor order. Preserve the selected roster, N/M, remainder allocation and policy version in the run. Reject an empty roster. These are operational quotas derived from the explicitly authorized pilot policy, not quotas discovered on the faculty website. If eligibility makes the resulting quotas infeasible, report the conflict for coordinator review rather than silently adjusting them. A public directory entry alone does not establish supervisory eligibility. Student preferences, skills/proficiency and outcomes still require evidence; unknown fields remain missing. The semester code is configured when the coordinator creates the pilot semester, not inferred from the current date or old theses.

## 1. Product goals and non-goals

**Goals:** (1) a reproducible and validated student+advisor dataset, (2) stable reusable CSV student/advisor imports each semester, (3) explainable valid matchings, (4) a common Gymnasium environment for masked PPO, masked DQN and Hungarian baseline, (5) semester-specific updates/evaluations/promotions, (6) a live website demonstrating sample inputs, comparison metrics, decision traces and 2D/3D replay.

**Non-goals in core release:** chatbot/agent, unsupervised automatic production promotion, replacing official academic approvals, representing PDF-inferred topic words as proven student mastery, and guaranteed RL superiority to exact optimization.

## 2. Existing architecture to retain

The repository already uses static HTML/CSS/JavaScript + Three.js on Vercel, FastAPI on Render and Neon PostgreSQL. Existing relevant files: `backend/app/cohorts.py` (Excel parsing, TF-IDF, Hungarian quotas), `src/environment/matching_env.py`, `src/environment/action_mask.py`, `src/environment/reward.py`, `src/rl/ppo.py` (MaskablePPO), `src/rl/dqn.py` (plain DQN, mask improvement required), `src/features/feature_builder.py`, `src/evaluation/promotion.py`, `src/serving/service.py`, `backend/app/storage.py`, `database/schema.sql`, `frontend/app.js`, `frontend/matching-scene.js`, `frontend/visualization.js`, `scripts/train_real_rl.py`, `tests/`. Existing historical 215/38 and train/validation/test/future 154/20/21/20 are explicitly **not** accepted as the new source of truth. Use a new dataset namespace/version rather than overwrite their contracts.

## 3. Product roles and workflows

- **Data curator:** launch source inventory across formats, run extractors, resolve duplicate identities, review low-confidence fields and approve records with page-level or document-structure evidence.
- **Administrator/coordinator:** review faculty profiles, upload both CSV schemas, select participating advisors for the semester, apply the owner-authorized equal-quota policy (or later confirmed institutional restrictions), build cohort, compare algorithms, approve and publish assignments.
- **Researcher:** select dataset snapshot, feature versions, training seeds and checkpoints, compare benchmark and error analysis, initiate/promote/rollback model after gates.
- **Student (future authenticated portal):** supply skills/preferences and see authorized recommendation. Cannot browse arbitrary identifiable classmates' data.

## 4. Delivery plan — mandatory ordered phases

### Phase 0 — Workspace audit and protection

**Tasks**
1. Audit branch, dependencies, tests, migrations, web/API health and source file tree; record revision SHA and existing artifacts.
2. Locate directory `data/1.pdfs`, inventory **220 source files across formats**, count extensions case-insensitively, and distinguish folders, hidden files and excluded system files. Current accepted composition: **208 PDF, 8 DOCX, 4 RAR**; inventory the additional INI file with an explicit exclusion reason. Collect relative path, format, size and SHA256 for every source file. For each PDF also collect page count, extracted-text length, encrypted/scanned flag and parse errors. Word extraction and archive expansion are Phase 1 work, not a reason to require their conversion into 220 PDFs at Phase 0.
3. Snapshot/backup current PostgreSQL and legacy offline curated/features/checkpoints (only if access permitted). Do not check in raw PDFs or student PII. Create clean pipeline outputs under `data_rebuild/v1/{raw_index,bronze,silver,gold,reports}` (gitignored).

**Artifacts:** `reports/input_inventory.csv`, `reports/environment_audit.md`, `reports/legacy_manifest.json`.

**Gate P0:** expected source-file count equals **220 across accepted formats**, excluding documented system files, or produce a BLOCKER with the mismatched/invalid file list. The verified **208 PDF + 8 DOCX + 4 RAR** inventory satisfies the count condition; there is no missing-12-PDF blocker. Every source file must have a hash and format classification. Archive members and converted documents are derived inputs and do not increase the original-source count. Source-file count does not establish unique student count or extraction completeness.

### Phase 1 — Extract all source documents and trace every datum

**Tasks**
1. Prefer embedded PDF text per page; use OCR only on actual scan/low-text pages, preserve Vietnamese diacritics; log OCR method/version and confidence, record page coordinates when feasible.
   Extract Word text from paragraphs/tables with document-structure references; page numbers are only valid when a rendered version is available. Inspect and safely expand archives into the private rebuild namespace, reject path traversal, and preserve archive/member paths and hashes. Any conversion must record the original file hash, converter/version and derived-file hash. Unsupported, encrypted or unreadable sources remain explicit review/failure outcomes; never silently exclude them.
2. Extract candidate student ID, name, thesis title, abstract/problem statement, keywords, subject/domain, methodologies, actual named technologies, evidence snippet, source path/page and extraction method. **Never label an inferred technology as proven personal skill.**
3. Handle file with more than one thesis or no clearly identified student, missing IDs, filename collisions, nearly identical theses, and name variants. Deduplicate academic entities with provenance, not input files. Quarantine ambiguities for human review.
4. Create golden samples from different PDF and Word layouts and archive-derived documents; regression tests assert Vietnamese Unicode, metadata traceability and that every original source file and derived document is accounted for.

**Artifacts:** `bronze/pdf_pages.jsonl`, `bronze/document_blocks.jsonl`, `bronze/student_candidates.jsonl`, `reports/pdf_extraction_quality.csv`, `reports/source_extraction_quality.csv`, `reports/archive_member_manifest.csv`, `reports/review_queue.csv`, `reports/pdf_to_entity_mapping.csv`, `reports/source_to_entity_mapping.csv`.

**Gate P1:** every original source file and derived document has a traceable outcome `extracted|quarantined|failed`; archive outcomes account for all members. Every nonempty extracted field has `file/page-or-structure/snippet` trace, including its parent archive/conversion chain when applicable, and unresolved cases are visible. No silent exclusions.

### Phase 2 — Crawl official advisors with traceable evidence

**Tasks**
1. Inspect `https://fit.neu.edu.vn/lecturer` HTML, network requests and applicable terms/robots. It may be dynamically rendered; where allowed, use source APIs or browser-based capture. Respect throttling, backoff, URL scope and no authentication bypass.
2. Follow permitted lecturer detail links; extract name, affiliation, titles, listed expertise, research topics, public papers, technology terms from *verified* research text, source URL, retrieval timestamp and content SHA. Public contact links are for attribution only, never model input.
3. Generate stable advisor keys, map aliases carefully, record duplicate profiles and contradictions. Distinguish *website-derived expertise* from school-verified supervisory eligibility/quotas; never infer quota or consent to participate from a public faculty listing.
4. Persist raw page hashes + parser version, a profile audit report and manual review queue for missing/ambiguous faculty detail.

**Artifacts:** `bronze/faculty_pages.jsonl`, `silver/advisors.jsonl`, `reports/advisor_crawl_quality.csv`, `reports/advisor_review_queue.csv`.

**Gate P2:** all included lecturer records have URL/time/hash, no fabricated expertise; fetch failures explicitly reported. Any inaccessible JS/robots content remains a blocker for those missing profiles.

### Phase 3 — Normalize, reconcile and create reusable import formats

**Tasks**
1. Define `taxonomy_v1.yaml` for domains, topics, language/framework/DB/AI/data/DevOps/security/research/math fields; aliases, canonical IDs, stopwords and abbreviation handling (e.g. AI/ML/NLP/LLM, C++/C#). Preserve raw text.
2. Identify student thesis fields vs proven personal skill fields. Where the PDFs only describe a thesis, fill `topic_tags`/`research_domain_tags` and `skills_tags` only when evidence genuinely supports student skill claims; mark `inferred_from_thesis`, missing proficiency.
3. Create gold CSV from approved rows complying with `students_import.csv` / `advisors_import.csv`. Validate CSV dialect, required schema version, IDs uniqueness per semester, allowed taxonomy, valid URL and SHA format, date format, consent/review fields and JSON skills. New semester uses same headers.
4. Add `feature_allowlist.yaml` for approved matching signals and `feature_excluded.yaml` for identifiers, PII, contact, provenance and other excluded proxies.
5. Data governance: differentiated access to source PII, logging without source text leakage, retention/consent review, redacted sample data for public demo.

**Artifacts:** `silver/reconciliation_report.md`, `gold/students.csv`, `gold/advisors.csv`, `gold/snapshot_manifest.json`, `configs/data/taxonomy_v1.yaml`, validator, import unit tests.

**Gate P3:** data quality table includes extraction/field coverage, missingness, duplicate/entity resolution and provenance accuracy. All accepted gold rows `review_status=approved`; unresolved rows stay quarantine; zero confidential raw data in Git.

### Phase 4 — Feature evaluation before training

**Experiment matrix:**
- E0: TF-IDF thesis title ↔ advisor research text.
- E1: TF-IDF title+abstract ↔ advisor profile/publication summaries.
- E2: controlled multi-label domain/topic overlap.
- E3: skill/technology/method overlap **only with evidence-quality weighting**.
- E4: calibrated hybrid E1+E2+E3, plus confirmed student preference.

**Procedure:** Evaluate coverage, missingness, source quality, alias robustness, sparse profiles, explainability, advisor-top-k ranking validated by domain reviewers, and matching outcomes against Hungarian. Text preprocessing/IDF fits only train. Exclude protected/demographic/contact/IDs as input; avoid assigning high numeric proficiency from mere mention. Archive per-experiment metric/report and feature manifest.

**Gate P4:** choose feature pipeline with evidence and documented limitations; regenerate matrix with dimensions/checksums/index orders matching the new gold snapshot. No old 215x38 compatibility matrices.

### Phase 5 — Constrained matching, simulation and RL

**Algorithm contract:** common students, selected advisor candidates, compatibility scores, owner-authorized versioned quota policy and confirmed eligibility, feasibility validator and audit trace; same test cohort for Hungarian, MaskablePPO and masked DQN. For the current real-data pilot, use the equal-division policy defined above. Report infeasible cases and require human action rather than hallucinate missing assignments.

**Baseline:** Hungarian first (with hard constraints, exact optimization) + Greedy/Random research comparisons. Log objective, normalized load fairness and runtime. If objective is linear and fully known, Hungarian/min-cost-flow may be naturally optimal and RL may not outperform it; don't impose RL superiority as a gate.

**Environment:** an episode = one cohort allocation, shuffle student order within training only with recorded seeds, state includes current student topic/skill vector, candidate advisor compatibility, capacity/load ratios, eligibility mask and remaining demand summary. Action = choose valid advisor. Reward = score + preference + load fairness + terminal completion, never enforce policy only via negative reward. State/action version and roster action map immutable with checkpoint.

**PPO:** use `sb3_contrib.MaskablePPO` masks at training, prediction, and evaluation. **DQN:** implement masked epsilon-greedy actions, masked greedy argmax, **masked next-state Q target** and replay-buffer correctness; plain `stable_baselines3.DQN` without this does not satisfy requirement. If number of advisors varies, support padded/permutation-aware candidate representations or retrain with verified registry instead of reusing incompatible checkpoints.

**Training:** offline separate worker, CPU-first smoke, validated 5-seed benchmark for release candidate, declared timesteps and completion manifest. Episode sampling from disjoint training cohorts. Training on repeated synthetic permutations of one cohort is not evidence of cross-semester generalization. Separate untouched temporal holdout and synthetic stress tests.

**Gate P5:** 100% valid matches for feasible inputs, zero hard quota violations, reproducible seeds, correct mask at all action/target paths, trace fidelity, full benchmark vs Hungarian. Promote only with documented per-metric acceptance and human authorization; otherwise Hungarian stays production default.

### Phase 6 — Continuous learning each semester

At the end of each term: close approved assignments, ingest new students/faculty/availability + verified outcomes, create immutable snapshot (`semester_id`, hash, feature, taxonomy, policy, timestamps), curate only valid additions; assess drift and new topic tags. Propose model vN+1 from vN with offline training; PPO uses fresh rollouts and optional rehearsal cohorts; DQN uses validated saved replay buffer and stratified old/new replay. Freeze evaluation sets; backtest previous terms and evaluate unseen term(s), measure forgetting. Publish a new checkpoint only when registry hashes/roster action mappings are compatible and quality gates pass. **No online updates inside request handler**; fallback/rollback preserve earlier approved assignments.

**Gate P6 (amended 2026-10-23):** idempotent repeated uploads, offline retraining job manifests, automated validation/performance reports, holdout isolation, compatible genuine checkpoints and rollback drill. Complete the declared multi-seed step-increase experiment and report improvement, regression or inconclusive results honestly; RL superiority is not required. Record temporal forgetting as unavailable when verified temporal data is absent; this is not a blocker for the owner-authorized local CSV workflow.

### Phase 7 — Backend/frontend integration and deploy

**Web pages / UI flows:**
1. Semester management (create/lock/close); student CSV upload (and existing Excel converted through same validator); faculty CSV upload and a checkbox/multiselect box choosing participating advisors for the semester. Preview equal quotas over the selected roster, total capacity and remainder distribution before allocation; record the policy version. Support later confirmed institutional restrictions without fabricating values. Preview errors per row and quarantined records.
2. `Matching Lab`: choose *synthetic public sample* (2x2, 3x2, 38 students/4 advisors) or approved anonymized real snapshot; run Hungarian, PPO, DQN with identical conditions; side-by-side score/fairness/coverage/runtime, version and source provenance.
3. Animated step-by-step simulation: current student, candidate scores, valid/invalid actions, masked choices, selected advisor, load updates, forward/back/replay/reset/speed, synchronized accessible HTML decision table. PPO additionally display policy probabilities if the model exposes them; DQN display Q-values with clearly noted non-probabilistic meaning. No fabricated model behavior.
4. Training dashboard: job status, dataset/version, loss/reward curves, baselines, seed variability, action violations, checksums, approved checkpoint history, rollback.
5. Explainability: field-level score contributions with evidence tags, eligibility reasons; admin approval/overrides and audit history.

**Integration:** retain Vercel static frontend + Render FastAPI + Neon. API must not train synchronously. Worker separate from production web and should use persistent artifact store (versioned checkpoints, trainer manifests), secure permissions, migrations, integration tests, audit trace. Tests cover responsive UI, 3D fallback, accessible controls, auth, upload size/CSV injection, prompt injection (future phase), row-level data authorization and rollback.

**Current local-release amendment:** deliver an additive local API/page with token authentication, private data protection and a tested runbook; retain the old website until replacement verification. Imports are inference requests, not automatic gold approvals. Batch labels may replace verified historical semester IDs. Local live API/browser verification proves the local release only; Vercel/Render/Neon publication remains a separate deployment action.

**Gate P7:** documented runbook from clean clone + private restored sources → validated data → model training → deployment; verified live API responses and matching trace correspond to checkpoint hash; privacy and error-state checks pass.

### Phase 8 — Advanced chatbot/agent (only after P0–P7)

**User stories:** "Tôi làm luận văn về X, hợp giảng viên nào?"; "Giảng viên Y mạnh về lĩnh vực nào?"; "Ai hướng dẫn tốt NLP/computer vision/database?"; "Vì sao gợi ý GV A hơn B?". Use approved faculty knowledge base with passages, URL, crawl date, confidence and scope; student's authorized profile/skills or user-supplied topic. Return ranked results from deterministic matching function and cited evidence; use LLM only for intent parsing/explanation, never to invent quotas/supervision commitments.

**Agent tools:** `search_advisor_profiles`, `get_advisor_evidence`, `match_topic_to_advisors`, `explain_assignment`, optionally `get_current_capacity` only for authorized coordinators. Read-only by default. Resist prompt injection in crawled pages/PDF text, protect student PII, give uncertainty/"unknown" when evidence absent. Evaluate retrieval correctness, citations, hallucinations, authorization and latency before shipping.

## 5. Proposed source layout (minimize unnecessary rewrites)

```text
configs/data/taxonomy_v1.yaml
configs/data/feature_allowlist.yaml
src/data_pipeline/pdf_inventory.py
src/data_pipeline/pdf_extract.py
src/data_pipeline/lecturer_crawl.py
src/data_pipeline/reconcile.py
src/data_pipeline/csv_contracts.py
src/features/feature_selection.py
src/environment/matching_env.py          # refactor existing
src/environment/action_mask.py           # eligibility+quota masks
src/rl/ppo.py                            # reuse MaskablePPO
src/rl/dqn.py                            # custom masked DQN
src/evaluation/semester_backtest.py
src/serving/model_registry.py            # version compatibility
backend/app/semesters.py
backend/app/imports.py
backend/app/training_jobs.py
frontend/                                   # extend, not replace
scripts/rebuild_sources.py
scripts/evaluate_feature_sets.py
scripts/train_semester_models.py
tests/data_pipeline/
tests/environment/
tests/rl/
tests/serving/
```

New files are proposals, not statements of existing code. Avoid duplicating two independent matching systems; route sample, CSV import, RL and baseline through a shared `allocate()` service. Prefer existing repository conventions and tests.

## 6. Required database/API contract

**Tables:** `semesters`, `raw_source_manifests`, `student_profiles`, `advisor_profiles`, `semester_advisor_capacity`, `data_review_queue`, `taxonomy_versions`, `dataset_snapshots`, `feature_artifacts`, `assignment_runs`, `assignment_decisions`, `semester_outcomes`, `training_runs`, `model_versions`, `evaluation_runs`, `promotion_events`, `audit_log`. Use immutable snapshot FK, hashes and indexes. Restrict identifiable profile access; old DB tables remain readable through migration.

**Suggested endpoints (authenticated, scoped):**

```http
POST /api/v2/data/pdf-rebuild
POST /api/v2/data/lecturers/rebuild
GET  /api/v2/data/jobs/{job_id}
GET  /api/v2/data/quality
POST /api/v2/semesters
POST /api/v2/semesters/{id}/students/import
POST /api/v2/semesters/{id}/advisors/import
POST /api/v2/semesters/{id}/capacity
POST /api/v2/semesters/{id}/allocate
GET  /api/v2/allocations/{id}/trace
POST /api/v2/allocations/{id}/approve
POST /api/v2/semesters/{id}/outcomes/import
POST /api/v2/training-runs
GET  /api/v2/training-runs/{id}
GET  /api/v2/models
POST /api/v2/models/{id}/promote
POST /api/v2/models/{id}/rollback
GET  /api/v2/benchmarks
```

Actual long-running jobs require a queue/worker and authorization, not direct web request execution or exposing local paths from cloud. Expose redacted public sample trace endpoints only.

## 7. Quality, testing and measurable acceptance

- **Data:** 220 expected original source inventory rows across accepted formats or a documented BLOCKER; system files separately inventoried and excluded with reasons; every source document/archive and derived document mapped to extraction/quarantine/failure state; 100% approved gold rows contain source provenance; uniqueness and CSV schema tests pass. A human-reviewed stratified extraction sample must be reported with field-level precision/accuracy; do not invent thresholds if no labels exist yet.
- **Matching:** feasible input has 100% coverage, zero quota/eligibility violations, deterministic trace with seed, correct advisor IDs independent of reordered CSV rows. Infeasible input produces explicit diagnostics.
- **Evaluation:** baseline objective, compatibility mean and distribution, preference satisfaction where observed, max/normalized load imbalance, runtime, invalid-proposal rate, unseen holdout generalization, seed mean/std and old-semester forgetting. RL promotion only upon meeting documented regression tolerance and safety, not just a raw reward number.
- **Continual learning:** latest candidate trained from approved data snapshots; no future/holdout leakage; original production checkpoint remains loadable; repeated import no duplicate; rollback preserves historical results.
- **Product:** working sample modes (2x2, 3x2, CSV-created), visible distinct PPO/DQN/Hungarian traces, honest explanation of Q-values vs PPO probabilities, usable API/FE integration, and validated deployment.

## 8. Blocking issues requiring truthful reporting

1. Phase 0 verified **220 original source files: 208 PDF, 8 DOCX and 4 RAR**, plus one excluded INI system file. The owner accepted this interpretation on **2026-10-21**. Full extraction and archive-member coverage still require Phase 1 verification; neither 220 source files nor 208 PDFs establishes the number of unique students.
2. Lecturer webpage HTML available to a plain crawler may not include all dynamically rendered records; test authorized APIs/browser access and log coverage. Website being available does **not** mean a complete valid faculty dataset was collected.
3. Faculty official participation, capacity and preferences cannot be reliably inferred from that public directory. For the owner-authorized pilot, coordinator roster selection plus the recorded equal-division policy supplies participation/quota inputs. Build the semester import/review UI and require those inputs before allocation; do not claim the website or school independently verified them.
4. Student PDFs may lack self-reported skills or supervisory satisfaction. Separate **topic extraction** from **verified skills** and from **outcome labels**.
5. Cloud web deployment does not imply background model training is supported or funded. Workers and artifact persistence are explicit new components.

## 9. Definition of Done / handoff package

Deliver checked-in code (excluding private raw data), migration scripts, clean-room source-to-gold data pipeline, templates + validators, approved taxonomy, quality reports, feature ablation report, RL scripts/checkpoints with manifest, three-way benchmark, semi-automated semester update procedure, web sample replay, secure cloud deployment, tests, and a step-by-step operator runbook. Publish an honest coverage table of what is fully verified versus research-only; defer chatbot until all MVP gates are met.

### FIRST TASK TO EXECUTE

Start with **Phase 0 only**: inspect the repo and count/hash all source documents and archives, generate a format-aware inventory and explicit discrepancies report. Count the accepted 220 original source files, not 220 PDFs, and record system-file exclusions separately. Then implement Phase 1 extractors after inventory has been validated. Do not begin training, web design rewrites, or chatbot until data-source review gates permit progression.
