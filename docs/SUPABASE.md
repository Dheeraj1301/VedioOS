# Supabase connection

## Target

- Project: [hamsa1412's Project](https://supabase.com/dashboard/project/lmwvoniiykmfzuxigzqf)
- Project reference: `lmwvoniiykmfzuxigzqf`
- Organization ID: `xiphhufkwobtfsttdjyg`
- Region: `ap-northeast-2` (Seoul)
- Application schema: `vedioos`
- Backend database login: `vedioos_app`

The supplied `.env.vedio` file was inspected locally. Its transaction-pooler credential was rejected; its second URL was malformed and also failed after safe normalization. The file was not modified. Using the authorized Supabase connector, a dedicated application role was provisioned without changing the project administrator's password.

The working application URL is stored only in ignored `.env`. The source connection file is not imported wholesale because it contains invalid configuration. Do not copy its rejected credentials into deployment settings.

## Connection architecture

Django connects through the Supabase session pooler on port 5432 using the dedicated role. TLS uses `verify-full` with the Supabase CA, verifying both the certificate and hostname. The CA was retrieved via HTTPS from [Supabase's certificate download](https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt) and is stored in `.runtime/supabase-ca.crt`.

`DATABASE_URL`, `DATABASE_SCHEMA`, and `POSTGRES_SSLROOTCERT` configure the backend. No database credentials or privileged API keys are delivered to the browser. The role owns only the application schema, has no superuser/create-role/create-database/bypass-RLS privileges, and has a connection limit of eight. The existing project administrator retains management access.

Shared previews close their database connection after each request so simultaneous developer machines do not retain all eight session-pooler slots. `DATABASE_CONN_MAX_AGE` defaults to `0`; only set a positive value for a deployment with an explicitly sized connection pool.

The schema is not granted to `PUBLIC`, `anon`, or `authenticated`. Django's migration hook enables RLS on its tables and revokes browser API role access. Application queries run as the table owner and rely on the existing Django role/project checks. This is deliberately a server-owned data model, not Supabase Auth JWT policies.

In the Supabase Table Editor, select the **vedioos** schema. The empty `public` schema is not where this application's tables live.

## Preserved data and services

The original local database is retained at `.runtime/db.sqlite3`, with a pre-transfer snapshot at `.runtime/pre-supabase.sqlite3`. The transfer fixture is `.runtime/supabase-transfer.json`; it contains private account/session data and is ignored by Git.

Application sessions, roles and project authorization use Django's shared `users` identity persisted in Supabase PostgreSQL. Confirmed Supabase Auth email/password users are linked to that application identity by immutable Auth UUID on first successful login and receive only the client role. The backend verifies the password at Supabase, validates the short-lived access token through `/auth/v1/user`, and then discards both access and refresh tokens; it never trusts user metadata for roles. Existing Django client credentials and administrator-issued editor/admin credentials remain supported. Original media remains in the existing private S3-compatible local storage service; file metadata is in PostgreSQL. A separate Supabase Storage integration requires compatible integrity/versioning decisions and credentials.

Administrators that also require a Supabase Auth identity are provisioned only through the trusted `create_supabase_admin` command. It creates an immediately confirmed `auth.users` identity with the Admin API, stores the immutable Auth UUID in private `vedioos.users.supabase_auth_user_id`, creates the one-to-one `vedioos.admins` row, and keeps `vedioos.users.role` as the sole application-role authority. Auth user metadata is never trusted for authorization. The server-only `SUPABASE_SECRET_KEY` must remain in the ignored `.env`; prefer a separately revocable `sb_secret_` key and never expose it to browser code.

Client email verification uses Supabase Auth to create, send and validate the six digit OTP. After successful validation, VedioOS activates the matching private `vedioos.users` profile and starts a Django application session. Confirmed Supabase Auth password identities can enter through the same login form and are provisioned or linked to `vedioos.users`; editor/admin roles can never be created through that path. The legacy `vedioos.email_verification_challenges` table is retained but no longer populated by new client verification requests. Configure the OTP template and approved custom SMTP provider in Supabase Auth; keep provider credentials out of Git and browser code.

Client password recovery uses Supabase Auth's Recovery template and recovery OTP verification. Editor recovery uses the same application pages with Supabase's email-ownership OTP because editor passwords are issued and stored by VedioOS rather than managed as Supabase password identities. In **Authentication → Email Templates**, include the six-digit `{{ .Token }}` value in the Reset Password template and the applicable Magic Link/OTP template because VedioOS asks users to enter the code rather than follow a link. Configure an approved custom SMTP provider and sending domain before production use; Supabase's default sender is rate-limited and intended only for testing. No redirect URL is required for this OTP form. The backend uses only the publishable Auth key and never stores returned access or refresh tokens. After a verified reset, the private application password is authoritative for profiles already linked to their immutable Supabase UUID; legacy unlinked profiles may still complete one verified Supabase login to establish that link.

## Run and verify

```powershell
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py check_database
.venv/Scripts/python.exe manage.py check_shared_preview
.venv/Scripts/python.exe manage.py verify_cloud
.venv/Scripts/python.exe scripts/start_shared_preview.py
```

`verify_cloud` creates synthetic users/project/session records inside a transaction and rolls them back. It does not drop or flush the shared database. Normal `manage.py test` commands automatically use `vedioos.test_settings` and an isolated SQLite test database.

The verifier follows the current account contract: client registration remains inactive until its email OTP is consumed, editor self-registration redirects to login, and the synthetic editor signs in with an administrator-issued editor ID. Automated verification mocks the Supabase Auth boundary and never sends an external email or creates a persistent Auth user.

For a shared preview, set `SHARED_PREVIEW_REQUIRED=true` and use `scripts/start_shared_preview.py`. If the configured storage endpoint is loopback and unavailable, the launcher starts and initializes the repository's private storage automatically, writes its diagnostics to ignored `.runtime/storage-preview.log`, and stops that child service when the preview exits. An already-running local service or an external storage endpoint is left untouched. The launcher refuses SQLite, a missing or wrong Supabase project, a schema other than `vedioos`, mismatched Supabase Auth, failed database security checks, pending migrations, a failed transactional login/role verifier, or unavailable/misconfigured private storage. Its storage check uploads, downloads, compares, and removes synthetic bytes before Django starts. Teammates still need the same server connection, CA, storage and test-payment credentials through the team's private secret channel; the repository deliberately cannot distribute them. Password hashes and application roles live in `vedioos.users`, so accounts are shared across every correctly bound preview even though they are not listed as password identities in `auth.users`. Supabase Auth remains the email-OTP boundary described above.

For deliberate offline development:

```powershell
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --settings=vedioos.local_settings
```

This selects the retained local copy, not live Supabase data. Do not edit both copies and expect them to synchronize. Do not replay the transfer fixture into a populated cloud database.

## Provisioning history

Supabase migration history records `vedioos_private_database_foundation` and `configure_vedioos_database_login`. The latter stores a SCRAM verifier, not the plaintext password. Django owns all application table migrations; do not generate competing Supabase migrations for those models.

Future production work includes separate runtime/migration roles if needed, production hosting, backups/recovery verification, abuse controls, and the unresolved media-storage deployment. The connection alone is not a production release.

For a repeatable privilege and recovery inventory, run:

```powershell
.venv/Scripts/python.exe manage.py audit_database_security
```

The command verifies the constrained runtime role, private schema/table ownership, RLS, browser/public grants and future-object default grants. It inventories extension versions and the enabled event-trigger count without printing credentials, database/role names or private rows. The 2026-09-24 audit passed for 46 tables, five extensions and seven enabled event triggers. Reproducing provider-owned objects still requires an approved Supabase recovery procedure and D16 recovery targets.

## Verified on 2026-09-16

- Certificate-verified PostgreSQL connection succeeds as `vedioos_app` in schema `vedioos`.
- Django migrations applied; all 36 application/framework tables have RLS enabled and browser-role schema access is denied.
- 46 existing records imported, including five identities, two client profiles, two editor profiles, two project drafts, and two file records. The original SQLite database is retained.
- A second export from PostgreSQL matched all 46 source records before browser verification.
- `verify_cloud` passed registration, login/logout, all three dashboards, and role/project access checks against PostgreSQL. Its temporary data was rolled back.
- Live browser login/logout and the PostgreSQL-backed admin dashboard passed; both migrated projects rendered with no page errors. Screenshot: ignored `.runtime/screenshots/supabase-admin.png`. Reproduce against the existing synthetic admin with `node tests/cloud_browser.mjs`.
- 20 isolated configuration/foundation tests passed; Python lint/format checks passed.
- Supabase security warnings on the existing `public.rls_auto_enable()` event-trigger function were resolved by revoking public/API-role execution; the trigger itself remains intact. Migration: `restrict_rls_event_trigger_execution`.
- The remaining advisor entries are informational [RLS enabled without policies](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy). This is intentional for the private server-owned tables: API roles receive no access, and Django enforces end-user authorization. Adding public client policies would change that design.
