# UniMatch portal implementation plan

Goal: implement the portal design approved in chat on 2026-10-23.

Architecture: retain JavaScript/Three.js and matching APIs. Add server-managed OAuth/session authentication and a read-only training report endpoint. Reuse verified faculty knowledge and real decision traces.

## Tasks
- [x] Authentication: test missing configuration, state binding, session isolation, expiry and cross-origin rejection; implement server-side Turnstile and OAuth; retain bearer access for existing local scripts.
- [x] Training: test report/run binding and safe response; expose observed steps, target steps, curves, baseline, selected steps and plateau criteria without exposing local paths.
- [x] Knowledge: reproduce NLP/CV queries on verified source-enriched artifacts; fix literal-alias citation matching and search all faculty independently of allocation selection.
- [x] UI: replace connection panel, remove faculty CSV and metadata panels, add login, landing, dashboard and 3D trace scene; preserve imports, comparison and exports.
- [x] Verification: targeted API/security/retrieval tests, frontend check/build, desktop/mobile browser run, one batched UI review and corrective pass.

## Direction contract
THESIS: a friendly campus on a calm blue ocean connects students with supervisors and makes each decision understandable.
OWN-WORLD: pale blue surfaces, deep navy text, Manrope, rounded controls and sculpted 3D campus characters. White work surfaces retain clear task hierarchy.
STORY: sign in, discover the workspace, upload students, select faculty, compare and review.
FIRST VIEWPORT: left-aligned large landing headline and action beside a large interactive campus scene; workspace uses a clean full-width task flow with centered action groups.
FORM: approved code-led campus composition, no generated raster assets required.
MOTION: one animated 3D campus and decision-transfer interaction; static rendering for reduced motion, HTML explanation remains authoritative.
FINISH: test actual endpoints and traces, inspect desktop/mobile, document implemented visual rules and remaining provider configuration.

## Execution ledger
User approved the proposed design. Existing uncommitted GitHub training work is preserved. Execute inline. Authentication providers must fail closed when credentials or Turnstile are absent. Dashboard is explicitly a saved experiment report, not a live process monitor.

## Verification result
65 targeted tests passed, 1 skipped. Frontend syntax/build passed. Browser smoke passed at 1440px and 390px, including real three-step allocation replay and CSV export, with no JavaScript errors or document overflow after corrections. Fresh review found a shared-entrypoint auth regression; portal installation was moved into the base factory and covered by a regression test. External OAuth and Turnstile remain configuration-dependent and were exercised with mocks only.
