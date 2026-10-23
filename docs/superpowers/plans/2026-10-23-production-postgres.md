# Production PostgreSQL deployment

User authorizes production deployment and pushing the complete implementation to `main`; confirmed target is the newer `namhv521/UniMatch` remote. Existing remote `main` hashes match across both configured remotes. Do not force-push or include private artifacts/credentials in Git.

## Architecture
Use PostgreSQL on Neon for identities, sessions, OAuth state, submitted cohorts, proposals, faculty catalog and the immutable model release. Preserve SQLite only for local development/tests. Serve FastAPI and the frontend together on Render with CPU-only model dependencies; retain Vercel proxy as an optional later split. Allow remote access only in explicit production mode with HTTPS, PostgreSQL and session authentication; disable operator bearer credentials publicly. Keep research-status model labels and validation limitations.

## Tasks
- [x] Add a shared SQL connection layer and additive schema isolated from legacy tables. Test persistence across store recreation and authorization isolation.
- [x] Publish a portable, checksummed serving bundle in private SQL storage. Preserve native checkpoint bytes, feature hashes, approved source spans and model contracts. Test relocation and tamper/path rejection.
- [x] Production startup restores verified models from SQL, publishes faculty/model metadata to SQL, and persists cohort/run records there. Test public-mode guards and authenticated operations.
- [x] Fix Docker/build/Render manifest, same-origin authorization, security headers and startup health. Verify Linux runtime where available.
- [x] Commit scoped code; fast-forward `main` on UniMatch, verify remote readback. Connect Neon/Render, set deployment secrets, migrate additively, deploy, and verify public health/storage. Live URL and evidence are in `docs/production_deployment.md`.
- [ ] Configure real Google/GitHub/Facebook OAuth and Cloudflare Turnstile; verify sign-in, session persistence and user-scoped cohort/run flows on production.

## External requirements
Neon and Render were accessed through Chrome and production deployment is live. The user authorized creating OAuth/Turnstile applications on their accounts. GitHub app `3956407` has the production callback; generating its secret requires the user's account verification. Cloudflare sign-in is being handled by the user. Google project `fit-visitor-512500-p9` awaits consent to its User Data Policy. Meta app `1135265135823111` was created after explicit terms approval; secret access requires the user's password verification, and external release requires Meta business verification/review plus truthful public privacy/deletion information. No secrets belong in Git or these notes.
