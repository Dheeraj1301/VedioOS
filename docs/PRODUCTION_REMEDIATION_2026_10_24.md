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

- [x] Enumerate the eight gaps by safe aggregate category.
- [x] Separate ticket-opening/system events from genuinely missing history.
- [x] Correct reconciliation for atomic ticket openings and approved system actions.
- [x] Verify that later support replies and unknown unattributed actions still fail.
- [x] Confirm that no historical backfill or snapshot is required because no audit rows are missing.
- [x] Rerun audit-history reconciliation: 230 events, zero critical findings.

No audit rows were changed. Three opening messages were already covered by their
atomic `support.request_opened` events; five actorless rows were approved system
actions for Supabase identity deletion or catalog publication reconciliation.
Three imported clients without a historical registration event remain honest
legacy warnings and are not backfilled.

## Gate 3 — Shared media storage

- [x] Inventory all ready-file records by safe aggregate category.
- [x] Check the currently configured private store for exact versions and same-key alternatives.
- [ ] Locate the absent originals on a teammate's storage or an approved media backup.
- [ ] Select and configure one shared private HTTPS S3-compatible provider.
- [ ] Copy recoverable object versions byte-for-byte and verify stored size and SHA-256.
- [ ] Preserve unrecoverable metadata as evidence; do not create replacement media.
- [ ] Pass private-storage preflight, ready-file reconciliation, inventory and authorized download denial checks.

Manual configuration is required: the owner must privately supply the chosen
shared storage endpoint, region, bucket and restricted server credentials. Git
and Supabase PostgreSQL contain metadata only; they do not contain the 38 media
objects.

Current evidence: 40 ready records reference immutable object versions. Two are
available and pass metadata access; 38 exact keys are absent. The current bucket
contains 21 versions, including 19 versions not referenced by the shared
database. None of the 38 missing records has a same-key alternative version, so
the missing bytes cannot be reconstructed or safely relinked from this store.

## Gate 4 — Production readiness

- [x] Create a credential-free production environment template and deployment handoff.
- [x] Separate code-safe limited launch from commerce launch requirements.
- [x] Fail closed when storage credentials, Supabase password login or server-side Auth deletion synchronization are missing.
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

The hardened audit currently reports 11 blockers in the shared development
environment. The original ten remain, plus a previously undetected missing
server-only Supabase deletion-sync configuration. This is intentional fail-closed
evidence; the local preview has not been relabeled as production.

Production secrets must be supplied through the private deployment environment,
never chat or Git. Production deployment remains a separate owner-authorized
action after all required gates pass.
