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

## Private-storage preflight

`check_private_storage` provides an explicit provider exercise without using client media or application records. It requires bucket versioning, uploads 128 KiB of random synthetic bytes under a unique internal prefix, confirms an immutable version ID and stored size/checksum, downloads that exact version through a short-lived signed URL, verifies byte identity, and confirms that the corresponding unsigned URL is denied.

Cleanup runs after success and failure and deletes every version and delete marker for the unique probe key. The command fails when cleanup cannot be verified and never prints credentials or signed URLs. On 2026-09-24 it passed against the current loopback private-storage service and left no probe version behind. Production storage remains unverified until D02 selects and configures that provider.

`reconcile_private_storage` performs the complementary read-only consistency check. For every database file marked ready, it requests the exact persisted object version and compares stored byte size and SHA-256 checksum with database metadata. Errors are aggregated by category; client filenames, object keys, credentials and signed URLs are omitted. On 2026-09-24 both ready Supabase file records reconciled with their private objects.

The reconciliation is database-to-storage only. It does not list or delete unreferenced bucket objects because retention and orphan-cleanup policy remain part of D02.

## Workflow reconciliation

`reconcile_workflows` provides a read-only cross-record consistency audit. It checks that confirmed orders activated their projects and retained priced agreement snapshots, confirmed payment records match order amount/currency, active assignments belong to paid projects, ready files have completion/version metadata, submitted versions and revisions belong to the same project, and completed deliveries have a client-owned acceptance for the attributed version and assignment.

Failures are reported only as aggregate category counts; client, project, payment, file and storage identifiers are omitted. On 2026-09-24 the connected Supabase records passed every workflow check.

## Consolidated release evidence

Run the connected-environment checks as one fail-closed report:

```powershell
.venv/Scripts/python.exe manage.py collect_release_evidence
```

The command combines database connectivity and migration readiness, private-schema/RLS protection, workflow consistency, ready-file storage reconciliation and integrity verification of the latest manifested local snapshot. It reports only aggregate counts and stable result codes. Database names, roles, credentials, provider URLs, signed URLs, object keys and private record identifiers are omitted.

`--json` returns deterministic machine-readable output. `--report-only` records failures without stopping an audit workflow. `--active-storage` additionally performs the synthetic write/download/anonymous-denial/cleanup exercise; the default remains read-only apart from database queries and storage metadata reads. A missing local snapshot is reported as skipped because ignored snapshots are intentionally absent from fresh clones. A present but invalid snapshot fails the report.

On 2026-09-24 the connected report passed: migrations were current, 46 private-schema tables had RLS, both Supabase browser roles lacked schema access, all workflows were consistent, both ready file records matched their exact private objects, and the latest 46-table / 297-row snapshot passed integrity verification.

## PostgreSQL privilege and recovery inventory

Run the deeper database audit against the connected PostgreSQL environment:

```powershell
.venv/Scripts/python.exe manage.py audit_database_security
```

The command fails closed unless the runtime role has no superuser, role-creation, database-creation, replication or RLS-bypass flags; has a finite positive connection limit; owns the private schema and its tables; and all application tables have RLS. It also rejects public or Supabase browser-role privileges on the schema, tables, sequences, routines and future-object default ACLs. `--json` provides structured evidence and `--report-only` records drift without stopping an audit workflow.

The output inventories installed extension names, versions and schemas plus the enabled event-trigger count for recovery planning. It omits the database name, runtime-role name, credentials, connection URL and private rows. On 2026-09-24 the connected audit passed for 46 tables with zero elevated flags, connection limit eight, zero public/browser grants, five installed extensions and seven enabled event triggers.

This evidence defines what a full restore must reproduce. It does not back up or restore provider-owned roles, extensions, triggers or grants; that exercise still requires the D16 recovery target and Supabase-supported backup procedure.

## Pre-migration snapshot integrity

`snapshot_database` now writes a companion SHA-256 manifest for every private row snapshot. Verify the latest manifested snapshot with:

```powershell
.venv/Scripts/python.exe manage.py verify_database_snapshot
```

Pass `--against-database` immediately after capture to compare the snapshot's table inventory and row counts with the current private PostgreSQL schema. The verifier refuses paths outside ignored `.runtime`, rejects missing/malformed manifests, detects changed bytes, validates the expected `vedioos` structure and never prints row content.

The 2026-09-24 baseline created `database-snapshot-20260924T080930544992Z.json` plus its ignored manifest and verified 46 tables / 297 rows against Supabase. These artifacts contain private data and remain local.

`rehearse_database_restore` now validates that a manifested row snapshot can be loaded into a newly migrated, disposable SQLite database. The command requires a snapshot inside ignored `.runtime`, verifies its digest, requires an exact table/column match, restores all rows, checks migration history, foreign keys and database integrity, and removes the temporary database. It has no option that targets Supabase or another existing database.

On 2026-09-24 the command restored the 46-table / 297-row baseline successfully without modifying the live database. Unit tests also prove schema drift is rejected without printing private row content.

This remains a pre-migration row-level rehearsal. It does not restore PostgreSQL roles, grants, extensions, sequences, provider-managed backups or media objects. `pg_dump` and `pg_restore` are unavailable on this host. A full production database and media backup/restore exercise remains blocked on D02/D16, the chosen providers and approved recovery targets.

## Current development baseline

The connected development configuration reports 10 expected blockers: debug mode; local-only hosts; no trusted production CSRF origin; non-secure development cookies; no HTTPS redirect/HSTS; loopback HTTP storage; console email; and a localhost sender. It reports five disabled-workflow warnings for real payments, payouts, external notification email, automatic assignment and prospective earnings.

These results are evidence that the checker fails closed. They are not a request to replace development settings with invented production values.

Admin → Feature controls now displays D02–D16 as an explicit launch-decision queue and links to the repository's owner checklist. The checklist asks for exact activation values or an explicit first-release exclusion; it stores no credentials and changes no runtime setting by itself.

## Continuous verification

`.github/workflows/ci.yml` runs on every push and pull request with read-only repository permission. Its backend job installs the committed Python lock file on Python 3.13, checks Django configuration and migration drift, runs Ruff, and executes the isolated backend suite. Its frontend job installs `package-lock.json` on Node.js 22 without lifecycle scripts, syntax-checks every repository JavaScript module, rebuilds the committed hash library and fails if that output differs. The workflow receives no provider credentials and therefore cannot mutate Supabase, private storage, payments or payouts. Provider, storage and browser checks remain explicit integration gates.

`verify_cloud` provides a rollback-only check against the configured PostgreSQL database. It follows the current mandatory email-verification and administrator-issued editor-ID flows, checks all three role areas and project-level denial, and proves that its synthetic records were removed.

## Representative browser lifecycle

On 2026-09-24, all five opt-in Microsoft Edge walkthroughs passed against isolated temporary databases. The delivery and mobile flows used the real loopback private storage service and removed their synthetic objects afterward.

- Commerce: admin catalog configuration, server custom quote, mobile agreement acceptance, signed sandbox payment, duplicate callback and protected receipt.
- Assignment: capacity/policy configuration, manual complexity, persistent round robin, assigned-editor access, audited reassignment and former-editor denial.
- Delivery: private editor output, revision request, replacement version, explicit acceptance, first-draft acceptance and byte-identical private downloads on desktop and mobile.
- Earnings: pending credit, admin release, wallet reservation, failed payout release and successful sandbox payout.
- Operations/mobile: 390px and 320px project views, password visibility, keyboard skip navigation, separate inspiration upload, rejected-upload recovery, original-byte integrity, message isolation, notification history and the audit timeline.

The runs reported no browser page errors or horizontal overflow. Screenshots remain in ignored `.runtime/screenshots`; they contain synthetic fixtures and are not published. This is local development evidence. It does not validate a real payment/payout provider, production media hosting, email delivery, assistive technology or production load.

## Verification

- Unit checks cover a secure disabled-feature release scope, insecure settings, policy/provider inconsistencies, and secret-free JSON output.
- The full isolated suite passes 165 tests with 10 opt-in integration tests skipped.
- All five opt-in Edge lifecycle suites pass with real local private-storage integrity where applicable.
- Django system and migration checks and Ruff pass.
- This slice changes no database schema. Supabase remains synchronized through `operations.0013`.
- No deployment, domain, provider subscription or paid upgrade was performed.

## Remaining before the Phase 9 gate

- Resolve the manual gates printed by the command, including D02–D16 as applicable to the release scope.
- Select hosting, production storage, email, payment/payout and monitoring providers; configure credentials through an approved secret store.
- Exercise full PostgreSQL role/grant/extension and media backup/restore procedures with approved recovery targets; row-level restore, ready-file reconciliation and workflow reconciliation are complete.
- Run `check_release`, `check --deploy`, database protections, the storage preflight against the selected production provider, manual assistive-technology checks, approved large-file targets and the complete client-to-payout lifecycle with real providers in the intended environment.
- Obtain explicit production deployment authorization.
