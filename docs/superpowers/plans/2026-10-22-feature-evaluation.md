# Phase 4 Feature Evaluation Implementation Plan

**Goal:** Evaluate E0–E4 from the approved source-rebuild gold snapshot without leakage, invented relevance labels or changes to the incumbent website.

**Architecture:** Immutable experiment runs bind P3 gold/config hashes, grouped partitions, train-only fitted transforms, masked score matrices and field-level explanations. Validation-only blinded reviewer proposals support feature selection; owner ratification precedes release. Untouched test data never calibrates feature weights.

**Tech Stack:** Existing Python, NumPy 2.3.5, SciPy 1.17.1, scikit-learn 1.8.0; stdlib manifests/CSV/JSON. No embedding downloads, new service or production schema migration.

**Spec:** `docs/UniMatch_Agent_Rebuild_PRD.md` Phase 4; companion feature dictionary, RL spec and approved P3 snapshot `20261021T174552Z-fa7d91f3`.

## Constraints and decisions

- Preserve all P3 source lineage and unknown proficiency/preferences/participation/capacity. Never reuse 215-row artifacts.
- Explicitly non-temporal grouped research split: no confirmed semester chronology is available. Group related source hashes and exact/near titles before splitting.
- Fit E0/E1 vocabulary and IDF on train students only. Advisor catalog and validation/test texts only transform; identifiers are redaction/join keys, never learned inputs.
- E0 title text; E1 title+approved abstract/profile research text; E2 domain/topic tags; E3 evidence-weighted technologies/methods; E4 validation-calibrated convex hybrid. Unapproved publication summaries stay unavailable.
- Missing signals carry explicit masks. No fabricated zero skill/proficiency; no preference term unless confirmed input exists.
- Owner chose agent-proposed relevance labels followed by owner review. These are advisory judgments of source relevance, not historical outcomes or confirmed supervisory eligibility.
- Hungarian comparisons are private diagnostic simulations over profile candidates with declared test constraints. They cannot publish or masquerade as a semester allocation.

## Tasks

- [x] Audit P3 predecessor gate/hashes and define contracts with three agents.
- [x] Build deterministic grouping/split helper and meaningful leakage/reproducibility tests.
- [x] Build E0–E4 feature transforms, redaction, missingness, frozen safe serialization and parity tests.
- [x] Build label validation, ranking metrics and validation-only hybrid calibration with unknown-label handling.
- [x] Integrate runner: immutable input/output manifests, shape/index/dtype/hash checks, sparse/coverage/alias/PII diagnostics and diagnostic Hungarian comparisons.
- [x] Generate blinded validation review packet covering the union of top-5 results for all variants and hybrid grid candidates. Keep test absent from the packet.
- [x] Obtain agent relevance proposals with source references; expose evidence report for owner review. Report advisory metrics separately from owner-validated metrics.
- [x] Freeze a selected contract/full matrix only after ratified evidence meets gate; otherwise leave explicit P4 blocker without advancing P5.

## Verification

Fail closed on stale P3 artifacts, IDs/index mismatches, holdout fitting, group overlap, protected metadata in vocabulary, missing quality represented as mastery, incomplete relevance judgments treated as zero, test labels influencing calibration, or unapproved selection. Verify model save/load parity and artifact hashes. Report before/after limitations honestly.

## Current result — 22 October 2026

Experiment `20261022T072424Z-6f941e2a`; owner packet `data_rebuild/v1/review/phase4_owner_review_v2`. All 270 validation pairs have source-bound proposals; independent overlap 30 agrees 25/30, five disagreements retained uncertain, six uncertain overall. Owner explicitly approved the package/E4 weights 0.25/0.25/0.50 and retained six uncertain. On 25 common queries, NDCG@5 E4 calibrated 0.7274 vs E0/E1 0.6136; owner-ratified agent report, not independent test quality.

Acceptance run `20261022T115327Z-1850251a`: frozen calibrated transformer copied without refit, full matrix 194×35 with mask/index/SHA verified, validation slice and complete replay match exactly. Full transform now includes 30 heldout rows only after selection is frozen; no heldout labels, fitting, calibration or independent test metrics. 207 rebuild tests pass. P4 VERIFIED; P5 may start. Reports/runbook: `docs/rebuild_phase4_quality_report.md`, `docs/rebuild_phase4_operator_guide.md`.
