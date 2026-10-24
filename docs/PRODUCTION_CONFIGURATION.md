# Production configuration handoff

This is a provider-neutral handoff. It does not authorize deployment and does
not contain credentials. Populate `.env.production.example` only in the chosen
deployment platform's private environment from `docs/production.env.example`.

## Required owner inputs

1. **Public application address** — the final HTTPS hostname, for example
   `app.example.com`. It supplies `ALLOWED_HOSTS` and the matching
   `CSRF_TRUSTED_ORIGINS=https://...` value.
2. **Shared private media provider** — HTTPS S3-compatible endpoint, region,
   private versioned bucket and restricted server credentials. The provider
   must retain immutable versions and SHA-256 metadata. The 38 absent originals
   must also be supplied from the machines or backups that currently hold them.
3. **First-release checkout scope** — choose one:
   - **Limited launch:** disable public quotations and keep
     `PAYMENT_MODE=disabled`. Drafts, private uploads and in-app workflows can
     launch, but clients cannot pay or enter assignment.
   - **Commerce launch:** approve production prices, currency, terms,
     cancellation/refund rules and a real payment provider. A live provider
     adapter, webhook recovery and refund/dispute handling must then pass the
     Phase 3 gate. Razorpay test mode cannot be promoted to production.
4. **External email scope** — either keep external delivery held and use in-app
   notices, or provide the approved SMTP/API provider, verified sender domain,
   templates and worker schedule.
5. **Optional first-release exclusions** — confirm whether automatic
   assignment, earnings, payouts and recurring packages remain disabled. Their
   disabled state is a release warning, not a security blocker, when the UI does
   not offer the unfinished transaction.
6. **Recovery targets** — database and media backup frequency, retention,
   recovery-point objective, recovery-time objective and incident owner.

## Deployment procedure

1. Create the private environment from `docs/production.env.example`; replace every
   placeholder and generate a new high-entropy Django secret.
2. Install the exact locked dependencies and collect static files.
3. Run migrations with the migration role; do not use browser Supabase keys.
4. Run `manage.py check --deploy` and `manage.py check_release`.
5. Run `manage.py check_database`, `manage.py audit_database_security`,
   `manage.py check_private_storage`, `manage.py reconcile_private_storage`,
   `manage.py inventory_private_storage` and `manage.py collect_release_evidence --active-storage`.
6. Exercise anonymous denial, cross-client denial, former-editor denial, upload
   byte integrity, signed-link expiry and the approved payment path against the
   deployed HTTPS address.
7. Rehearse database and media restore to disposable targets before accepting
   production data.

Do not use `scripts/start_shared_preview.py` as a production process manager.
It is a development guard and may start loopback storage. The production host
must run the WSGI application with its own managed process, health checks,
logging, TLS termination and secret injection.

## Release interpretation

`check_release` distinguishes blockers from deliberately disabled features.
Warnings for disabled payments, payouts, external email, automatic assignment
or earnings are acceptable only when the owner explicitly excludes those
features from the first release. A passing configuration check does not override
the manual lifecycle, accessibility, large-file or restore gates.

