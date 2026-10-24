# Production remediation — 2026-10-24

This checklist sequences the connected-environment findings without rewriting
financial, audit or media history speculatively. A gate advances only after its
focused tests and connected read-only reconciliation pass.

## Gate 1 — Shared commerce integrity

- [x] Identify the four reported findings without exposing customer or provider data.
- [x] Classify current versus superseded quotes and payment attempts.
- [x] Confirm that unpaid brief editing intentionally retains old accepted quotes and cancelled payments.
- [x] Correct reconciliation to validate the current accepted quote and live payment attempts while retaining immutable history.
- [x] Add regression coverage for superseded quotes, cancelled payments and multiple live payments.
- [x] Rerun connected commerce reconciliation: 19 orders, 31 quotes, 8 payments, 1 event; zero critical findings.
- [ ] Resolve the 10 accepted-but-unpaid operational warnings through normal client payment/cancellation policy; do not manufacture settlements.

No shared commerce rows were changed. The four failures were false positives in
the audit rule, not damaged financial records.

## Gate 2 — Audit-history integrity

- [ ] Enumerate the eight gaps by safe aggregate category.
- [ ] Separate reconstructable missing events from legacy history that cannot be attributed honestly.
- [ ] Add or correct prospective event creation and reconciliation rules.
- [ ] Prepare a reviewed backfill plan for any reconstructable historical event.
- [ ] Capture a verified private snapshot before any approved historical write.
- [ ] Rerun audit-history reconciliation and focused lifecycle tests.

Historical audit events will not be invented. Any data backfill requires an
attributable source and the owner-approved data-repair plan required by
`AGENTS.md`.

## Gate 3 — Shared media storage

- [ ] Inventory all 38 inaccessible ready-file records by safe aggregate category.
- [ ] Determine whether each exact object version exists on another teammate's storage or a backup.
- [ ] Select and configure one shared private HTTPS S3-compatible provider.
- [ ] Copy recoverable object versions byte-for-byte and verify stored size and SHA-256.
- [ ] Preserve unrecoverable metadata as evidence; do not create replacement media.
- [ ] Pass private-storage preflight, ready-file reconciliation, inventory and authorized download denial checks.

Manual configuration is required: the owner must privately supply the chosen
shared storage endpoint, region, bucket and restricted server credentials. Git
and Supabase PostgreSQL contain metadata only; they do not contain the 38 media
objects.

## Gate 4 — Production readiness

- [ ] Configure production host names and trusted HTTPS origins.
- [ ] disable debug mode and rotate a production Django secret.
- [ ] Enable secure session/CSRF cookies, HTTPS redirect and approved HSTS policy.
- [ ] Replace loopback HTTP storage with the verified shared HTTPS provider.
- [ ] Replace test pricing and sandbox checkout with approved production commercial/payment policy, or keep checkout disabled for launch.
- [ ] Decide and record payout, earnings and external-notification launch scope.
- [ ] Configure an approved email provider, sender domain and worker schedule if external email is enabled.
- [ ] Complete representative browser, accessibility, large-file and end-to-end lifecycle checks.
- [ ] Complete provider-backed database/media backup and restore rehearsal against approved recovery targets.
- [ ] Run the consolidated release, database-security, dependency and deployment-health gates.

Production secrets must be supplied through the private deployment environment,
never chat or Git. Production deployment remains a separate owner-authorized
action after all required gates pass.
