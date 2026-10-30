# UniMatch rebuild Phase 0

Spec: `docs/UniMatch_Agent_Rebuild_PRD.md`, supported by the RL design and data dictionary.

Scope: execute the requested source audit in the existing working tree. No restoration, training, deployment, or changes to application behavior. The supplied PRD is the approved design and phase order. Implement the audit inline, using Python standard library and installed PyMuPDF. Source artifacts stay in gitignored `data_rebuild/v1`.

- [x] Test inventory on uppercase extensions, nested/hidden files, invalid PDFs, encrypted PDFs, blank pages, byte duplicates, missing roots, and count mismatch. Four tests pass.
- [x] Inventory all source entries, SHA256, page/text counts, low-text indicators and parser failures; never infer student counts or OCR quality. Owner clarified 220 original source files across formats; verified 208 PDF + 8 DOCX + 4 RAR, one INI system file separately excluded.
- [x] Record revision, original Git changes, dependencies, missing modules/tests, schema and live/read-only health probes.
- [x] Manifest existing legacy files and back up what is accessible without overwriting sources; report unavailable artifacts and DB access explicitly. 221 source files hash-verified; Git bundle verified. Offline legacy absent, PostgreSQL backup unavailable.
- [x] Verify official faculty directory, robots and terms availability; cache source responses with hashes. Full profile extraction belongs to Phase 2.
- [x] Produce private reports plus a redacted quality/acceptance summary. Run audit tests and verify ignored paths.

Gate: exactly 220 original source inputs across accepted formats, each classified and hashed, or BLOCKED with the actual file list and discrepancy report. System files have explicit exclusions. File count does not establish unique students. Local baseline failures and missing backups remain explicit protection issues; unavailable production backup blocks migration/deployment. Do not use historical 215/38 as new training data.

Outcome: Phase 0 VERIFIED against the amended PRD. Seven inventory tests pass; actual inventory command exit 0. Prior blocked reports preserved under private reports/history. See `docs/rebuild_phase0_quality_report.md`. User clarified that existing deletions are to be left alone and implementation should be rebuilt from the three supplied documents. No application files restored or modified. Phase 1 may start; its acceptance remains independent.
