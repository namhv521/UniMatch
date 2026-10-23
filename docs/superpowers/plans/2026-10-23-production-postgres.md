# Production PostgreSQL deployment

User authorizes production deployment and pushing the complete implementation to `main`; confirmed target is the newer `namhv521/UniMatch` remote. Existing remote `main` hashes match across both configured remotes. Do not force-push or include private artifacts/credentials in Git.

## Architecture
Use PostgreSQL on Neon for identities, sessions, OAuth state, submitted cohorts, proposals, faculty catalog and the immutable model release. Preserve SQLite only for local development/tests. Serve FastAPI on Render with CPU-only model dependencies and a Vercel frontend proxy sharing the public origin. Allow remote access only in explicit production mode with HTTPS, PostgreSQL and session authentication; disable operator bearer credentials publicly. Keep research-status model labels and validation limitations.

## Tasks
- [ ] Add a shared SQL connection layer and additive schema isolated from legacy tables. Test persistence across store recreation and authorization isolation.
- [ ] Publish a portable, checksummed serving bundle in private SQL storage. Preserve native checkpoint bytes, feature hashes, approved source spans and model contracts. Test relocation and tamper/path rejection.
- [ ] Production startup restores verified models from SQL, publishes faculty/model metadata to SQL, and persists cohort/run records there. Test public-mode guards and authenticated operations.
- [ ] Fix Docker/build/Render manifest, same-origin authorization, security headers and startup health. Verify Linux runtime where available.
- [ ] Commit scoped code; fast-forward `main` on UniMatch, verify remote readback. Connect services, set secrets, migrate additively, deploy, then check real public health/storage/auth flows. No live-deployment claim before readback.

## External requirements
Neon/Render/Vercel connections were discovered as available but are not yet confirmed connected. OAuth provider and Cloudflare keys are also missing. Continue independent implementation while access is pending.
