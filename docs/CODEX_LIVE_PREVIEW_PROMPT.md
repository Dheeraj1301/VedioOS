# Codex master prompt — live Supabase preview

Use this prompt in a Codex task that has access to the VedioOS repository and the team's separately provisioned Supabase environment. It launches the current application without committing credentials, changing shared schema, or presenting unfinished integrations as live.

## Copy-paste prompt

```text
Run the current VedioOS application as a functional local preview backed by the configured team Supabase database and the repository's private local S3-compatible storage.

Repository and target:
- Repository: https://github.com/Dheeraj1301/VedioOS.git
- Integration branch: codex/foundation-and-commerce
- Supabase project reference: lmwvoniiykmfzuxigzqf
- Private application schema: vedioos
- Preview URL: http://127.0.0.1:8000/

Work autonomously until the preview is running and verified. Do not stop after describing commands. Execute the safe setup and verification steps, keep the required services running, open the preview, and report the links and evidence.

Safety and scope rules:
1. Read AGENTS.md, README.md, docs/PRODUCT_RULES.md, docs/ROADMAP.md, docs/DECISIONS.md, docs/SUPABASE.md, and docs/TEAM_WORKFLOW.md before acting.
2. Never print, paste, commit, upload, or expose .env values, database URLs, passwords, CA contents, S3 credentials, cookies, signed URLs, private rows, or client media. Report each required setting only as CONFIGURED or MISSING.
3. Do not run flush, loaddata, browser_fixture, init_local, destructive SQL, schema rewrites, or data migrations against Supabase. Do not run migrate merely to launch the preview. `migrate --check` is allowed. If a migration is pending, stop cloud startup and report the exact migration names; follow the repository's reviewed snapshot/migration process.
4. Do not create synthetic users, orders, payments, assignments, wallet entries, or media in the shared database unless the owner explicitly asks for shared test data. Run automated tests only with the isolated test settings/database.
5. Do not enable or represent real payments, payouts, AI classification, subscription sales, production email, automatic assignment, or production notification delivery as operational unless the recorded policies and providers are actually enabled. Never purchase or upgrade a service.
6. Do not create a public tunnel or deploy the application. The requested deliverable is a localhost preview. Explain that 127.0.0.1 is accessible only on the host computer.
7. Preserve any existing worktree changes. Never reset, clean, force-push, or overwrite teammates' work just to run the preview.

Repository preparation:
1. If the repository is not present, clone the integration branch. If it is present, inspect `git status`, current branch, remotes, and fetch origin. On a clean integration branch, update with `git pull --ff-only`. If the worktree is dirty or the branch has diverged, do not switch/reset it; report the condition and run only when doing so will not mix or overwrite work.
2. Use Python 3.13 and the committed `requirements.lock.txt`. Create `.venv` if absent and install the locked dependencies. Install Node.js dependencies with `npm ci` and run `npm run vendor` when they are missing or stale.
3. Do not replace an existing `.env`. Confirm without revealing values that these server-side settings exist: SECRET_KEY, DATABASE_URL, DATABASE_SCHEMA, POSTGRES_SSLROOTCERT, S3_ENDPOINT_URL, S3_REGION, S3_BUCKET, S3_ACCESS_KEY, and S3_SECRET_KEY. Confirm DATABASE_SCHEMA is `vedioos`. If the Supabase settings or trusted CA are missing, do not invent them or request that they be pasted into chat; explain that they must be provisioned through the team's approved private channel, then stop cloud-mode startup.

Supabase verification:
1. Run `python manage.py check_database` with the repository virtual environment. Require PostgreSQL, schema `vedioos`, the dedicated application role, RLS on every application table, and no browser-role access to the private schema.
2. Run `python manage.py migrate --check`. This must be read-only and return no pending migrations.
3. Do not use the legacy `verify_cloud` command as the preview gate: its original synthetic flow predates administrator-issued editor access and mandatory client email verification. Use the current isolated backend tests for auth/authorization evidence.

Private storage startup:
1. Check whether port 9000 is already listening. Reuse it only if it is the expected local private storage service; otherwise report the conflict without terminating an unrelated process.
2. If the repository's SeaweedFS binary is absent on Windows, run `python scripts/install_storage.py`, which verifies the pinned download checksum. On another operating system, follow README.md for the matching verified SeaweedFS binary; do not download an unverified executable.
3. Start `python scripts/start_storage.py` in a persistent background process or dedicated terminal, with stdout/stderr under ignored `.runtime`. On Windows, use a hidden background window. Allow at least 30 seconds for the single-node leader, filer, volume and S3 endpoint to become ready before declaring failure.
4. Run `python manage.py init_storage`. Then set RUN_STORAGE_TESTS=1 and run `python manage.py test tests.test_storage_live`; remove the environment flag afterward. These tests must use the isolated test database and synthetic bytes.

Application verification and startup:
1. Run `python manage.py check` and `python manage.py makemigrations --check --dry-run` against the configured application. Do not generate migrations during preview startup.
2. Run `python -m ruff check .` and `python manage.py test`. The test command must use `vedioos.test_settings` and must never point at Supabase.
3. Check whether port 8000 is already listening. Reuse an existing healthy VedioOS server; otherwise report conflicts rather than killing unrelated processes.
4. Start `python manage.py runserver 127.0.0.1:8000 --noreload` in a persistent background process or dedicated terminal using the configured `.env`, with logs under ignored `.runtime`. Do not add `--settings=vedioos.local_settings`, because this requested preview must use Supabase.
5. Require HTTP 200 from `/health/live/` and `/health/ready/`, then require successful responses from `/`, `/register/`, and `/login/`.
6. Open `http://127.0.0.1:8000/` in the available Codex browser and perform a visual smoke check for the landing page, registration page, login page, responsive navigation, and absence of browser console errors. Do not create shared cloud fixtures for this smoke check.

Current feature expectations to report accurately:
- Client: verified registration, login/logout, dashboard, four-option plan/custom brief, custom creative direction, private source and separate inspiration uploads, projects, project messages, support requests, revisions, accepted-version download, notifications, consultation requests, and protected payment history.
- Editor: administrator-issued editor ID, shared login, assigned projects, private files, version submissions, revision queue, availability and wallet screens. Editor self-registration and self-service password changes are intentionally unavailable.
- Admin: operational dashboards for orders, projects, editors, clients, assignments, pricing/configuration, calls, support, audit history, payouts, analytics, notification delivery state and feature controls.
- Implemented gated workflows: server quotes and agreement snapshots, payment sandbox, configurable round-robin allocation, review/acceptance, coin ledger and payout sandbox. Exercise these through isolated tests unless the shared environment already contains owner-approved policies and the owner explicitly authorizes shared test records.
- Still disabled pending decisions/providers: real checkout, real payouts, AI complexity classification, subscription/package sales, production email delivery, public production storage, automatic allocation where no policy is enabled, and production deployment.

Final response requirements:
1. Give clickable links for the landing page, registration, login, client area, editor area, admin area, liveness and readiness.
2. State whether Supabase connected, the detected schema/table count, RLS result, migration status, storage result, backend test totals, and page/health status. Do not expose private values or records.
3. State which features remain gated or disabled so the preview is not mistaken for production.
4. State that the link works only on the current computer and that the storage objects are local even though metadata and application records are in Supabase.
5. Give the ignored log paths and process IDs so the operator can diagnose or stop the preview later.
6. If any required check fails, keep investigating safe local causes and either fix a reversible preview-only issue or report the exact blocker. Never weaken authorization, TLS, RLS, private storage, payment gates, or email verification to make a check pass.
```

## Team notes

- Each teammate needs their own ignored `.env` and trusted CA file. GitHub contains no Supabase password or storage secret.
- The preview combines the shared Supabase database with storage running on that teammate's computer. Media objects do not synchronize between developers.
- A public team URL requires a separately approved production or staging deployment with hosted private storage, secrets, email and monitoring.
- Review the feature status in [Phase 9](PHASE_9.md) before treating any preview behavior as launch-ready.
