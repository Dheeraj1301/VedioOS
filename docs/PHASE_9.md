# Phase 9 — Production readiness

Status: started on 2026-09-24. The configuration-audit foundation is verified. Deployment is not authorized and the production gate remains blocked by recorded provider, business-policy and recovery decisions.

## Configuration audit

Run the release audit against the intended environment and database:

```powershell
.venv/Scripts/python.exe manage.py check_release
```

The command exits unsuccessfully when it finds a configuration blocker. `--json` provides a CI-readable report, while `--report-only` is available for development audits that must record blockers without stopping a local workflow. The report never prints secret keys, database URLs or provider credentials.

The audit checks:

- debug mode, explicit production hosts and trusted HTTPS CSRF origins;
- secure session/CSRF cookies, HTTPS redirect and one-year HSTS;
- PostgreSQL with `verify-full` TLS and a trusted CA file;
- HTTPS private storage and a configured bucket;
- a production email backend and approved sender domain;
- absence of payment/payout sandbox modes;
- consistency between enabled quotes/redemptions and provider modes;
- an enabled upload policy; and
- disabled workflows that materially limit the release.

It also prints the manual decision and exercise gates that cannot be inferred from environment variables.

## Deployment health probes

- `GET /health/live/` confirms only that the Django process can serve a request. It does not query dependencies, which lets an orchestrator distinguish a dead process from a temporarily unavailable database.
- `GET /health/ready/` verifies a database query and confirms there are no unapplied Django migrations. It returns HTTP 503 until both checks pass.
- Both responses are uncached generic JSON. Dependency names, schema details, credentials and exception text are never returned. Mutating HTTP methods are rejected.

Storage, email, payment and notification provider monitoring still requires the approved providers and D16 alert ownership; these probes do not claim those integrations are healthy.

## Pre-migration snapshot integrity

`snapshot_database` now writes a companion SHA-256 manifest for every private row snapshot. Verify the latest manifested snapshot with:

```powershell
.venv/Scripts/python.exe manage.py verify_database_snapshot
```

Pass `--against-database` immediately after capture to compare the snapshot's table inventory and row counts with the current private PostgreSQL schema. The verifier refuses paths outside ignored `.runtime`, rejects missing/malformed manifests, detects changed bytes, validates the expected `vedioos` structure and never prints row content.

The 2026-09-24 baseline created `database-snapshot-20260924T080930544992Z.json` plus its ignored manifest and verified 46 tables / 297 rows against Supabase. These artifacts contain private data and remain local.

This remains a pre-migration row snapshot. It does not contain PostgreSQL roles, grants, extensions or media objects and has no automated restore path. `pg_dump` and `pg_restore` are unavailable on this host. A real database and media backup/restore exercise remains blocked on D02/D16, the chosen providers and approved recovery targets.

## Current development baseline

The connected development configuration reports 10 expected blockers: debug mode; local-only hosts; no trusted production CSRF origin; non-secure development cookies; no HTTPS redirect/HSTS; loopback HTTP storage; console email; and a localhost sender. It reports five disabled-workflow warnings for real payments, payouts, external notification email, automatic assignment and prospective earnings.

These results are evidence that the checker fails closed. They are not a request to replace development settings with invented production values.

## Continuous verification

`.github/workflows/ci.yml` runs on every push and pull request with read-only repository permission. Its backend job installs the committed Python lock file on Python 3.13, checks Django configuration and migration drift, runs Ruff, and executes the isolated backend suite. Its frontend job installs `package-lock.json` on Node.js 22 without lifecycle scripts, syntax-checks every repository JavaScript module, rebuilds the committed hash library and fails if that output differs. The workflow receives no provider credentials and therefore cannot mutate Supabase, private storage, payments or payouts. Provider, storage and browser checks remain explicit integration gates.

`verify_cloud` provides a rollback-only check against the configured PostgreSQL database. It follows the current mandatory email-verification and administrator-issued editor-ID flows, checks all three role areas and project-level denial, and proves that its synthetic records were removed.

## Verification

- Unit checks cover a secure disabled-feature release scope, insecure settings, policy/provider inconsistencies, and secret-free JSON output.
- The full isolated suite passes 136 tests with 10 opt-in integration tests skipped.
- Django system and migration checks and Ruff pass.
- This slice changes no database schema. Supabase remains synchronized through `operations.0013`.
- No deployment, domain, provider subscription or paid upgrade was performed.

## Remaining before the Phase 9 gate

- Resolve the manual gates printed by the command, including D02–D16 as applicable to the release scope.
- Select hosting, production storage, email, payment/payout and monitoring providers; configure credentials through an approved secret store.
- Design and exercise full database and media backup/restore procedures with approved recovery targets.
- Run `check_release`, `check --deploy`, database protections, browser/accessibility checks, large-file tests and the complete client-to-payout lifecycle in the intended environment.
- Obtain explicit production deployment authorization.
