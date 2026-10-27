# UniMatch source-first rebuild implementation plan

**Goal:** Rebuild from the owner-approved 220 mixed-format sources and official faculty pages, preserving deployed behavior until a replacement is verified.

**Spec:** `docs/UniMatch_Agent_Rebuild_PRD.md`; the owner's clarification supersedes older PDF-only counts. User explicitly authorized implementation and multi-agent execution on 2026-10-21.

**Architecture:** Versioned private raw/bronze/silver/gold artifacts, field evidence and explicit phase gates. Keep production application files untouched during source reconstruction. Existing history is reference code only; no automatic restoration or historical dataset reuse.

**Execution:** Primary agent integrates, validates gates and reports. Separate agents own independent format readers and tests. Phase N+1 implementation begins only after Phase N is accepted. Read-only reconnaissance may inform the current plan without generating downstream datasets.

## Global constraints

- No fabricated student skills, proficiency, quotas, preferences, approvals, outcomes or faculty expertise.
- No PII, source bytes or checkpoints in Git. No production writes/deployments before verified release and required authorization.
- Preserve parent archive/conversion hashes, Unicode and original evidence. Unresolved entities stay quarantined.
- Report unavailable DB/legacy backups honestly; require backup/restore before migration/deployment.
- Existing deployment remains the incumbent. No silent model promotion.

## Ordered work and acceptance

1. **P0 — Inventory and protection.** Update `scripts/audit_rebuild_phase0.py`, its tests and reports for 220 originals: PDF/DOCX/RAR, INI excluded. Check hashes of every file, PDF parse metadata, backups and existing health. Accept only exact original count, classified/hash-covered sources and an explicit protection report.
2. **P1 — Evidence extraction.** Add PDF and Word/archive readers, then one orchestrator and candidate extractor. Sources receive extracted/quarantined/failed outcomes; archive members receive individual manifests. Write page/block text, candidates, evidence, review queue and source/entity mapping. Validate every evidence reference against stored blocks; test Unicode, conflicting identities, corrupt/encrypted input, archive traversal and conservation of all source records. Report quality separately from human approval.
3. **P2 — Official faculty.** Inspect permitted rendered directory/profile pages, robots and terms; capture raw responses and URL/time/hash. Build only evidence-supported candidate faculty profiles and report inaccessible/ambiguous records. Do not infer institutional quotas.
4. **P3 — Review and gold contracts.** Version controlled taxonomy/allowlist/exclusions, validate both stable import schemas, reconcile entities and collect human review decisions. Gold includes only approved records; report coverage/missingness and snapshot hashes. Human approval cannot be synthesized.
5. **P4 — Feature evaluation.** Train-only fitted E0–E4, source-weighted tags, reviewer ranking validation, manifests and leakage tests. Freeze a feature contract only after evidence-based selection.
6. **P5 — Shared constrained allocation and RL.** Feasibility/Hungarian first, shared Gymnasium, masked PPO and masked Double DQN including targets/replay. Same cohorts and five release seeds; no quota violations, trace fidelity and explicit research limitations. No required RL superiority.
7. **P6 — Semester updates.** Immutable snapshots, idempotent imports, offline jobs, chronological evaluation/forgetting, model compatibility and rollback drill. Require real semester/outcome evidence or label insufficiency.
8. **P7 — Product and deploy.** Additive DB/API/UI integration, separate worker/artifact storage, privacy/auth/accessibility/upload controls and live verification. Back up/restore before migrations. Deploy only verified artifacts.
9. **P8 — Grounded assistant.** Only after P0–P7. Read-only tools, deterministic matching, cited passages, ACL and injection/hallucination evaluations.

## Review focus

- Every original file remains accounted for even when corrupt or unsupported.
- Archive paths cannot escape the private extraction directory or overwrite siblings; expansion is bounded.
- Extracted values must exist in cited source text; filename hints never become unsupported field evidence.
- Duplicate/near-duplicate identity conflicts are visible, never auto-approved.
- Missing academic permissions, quotas, outcomes and temporal cohorts remain unknown and block relevant gates.

## Progress

- P0: verified, 220 original sources classified/hash-verified, 7 inventory tests passed.
- P1: verified conservation/provenance gate, immutable run `20261021T154719Z-b40d7836`; 220 candidate records, 345 OCR pages. This gate does not certify semantic extraction accuracy.
- P2: verified, 38 official profiles and 809 evidence snippets; immutable run `20261021T154610Z-9cfd4d06`.
- P3: VERIFIED snapshot 20261021T174552Z-fa7d91f3, owner-ratified report and explicit source/span/semantic rubric. Gold194 students/35 faculty; quarantine25/3. 127 tests pass. Receipts, exact assessment bindings, CSV validators and source manifests verified.
- P4: VERIFIED acceptance run `20261022T115327Z-1850251a`; 207 rebuild tests pass. Owner approved report `phase4_owner_review_v2`/E4 weights 0.25/0.25/0.50, retaining 6 uncertain. Frozen calibrated transformer and full194×35 matrix/mask/index verified; no refit or independent test metric. See `docs/rebuild_phase4_quality_report.md`.
- P5: research/offline technical gate VERIFIED, run `20261022T122801Z-fd20da3a`; five seeds42–46,10PPO/DQN checkpoints×16,384steps,281tests pass. Hungarian remains default (testmean0.259276 vs DQN0.168374/PPO0.076970), no RL promotion or real allocation authorization. See `docs/rebuild_phase5_quality_report.md` and operator guide.
- P6–P8: not started. No production deployment or website replacement has begun.
- Owner clarified a **next-semester pilot using real data**. The coordinator selects participating faculty; the authorized quota rule divides slots equally using recorded deterministic `divmod(N, M)`. The draft semester identifier is not an inferred official semester code. Unknown preferences, proficiency and outcomes remain missing.
