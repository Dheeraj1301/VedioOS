# Phase 7 — Operations and notifications

Status: in progress, first operational slice verified on 2026-09-18. The full Phase 7 gate remains open.

## Available now

- The admin overview counts paid unassigned projects, reviews, revisions, calls awaiting a schedule, and projects past an existing recorded deadline. The Projects page has unassigned, active, review, revision, and completed queues. Counts and queues use saved statuses and current assignments.
- A verified first payment creates at most one consultation request per selected stage. Failed and repeated payment events do not create duplicates. Admins can schedule an approved, active editor and mark a scheduled call complete. The after-draft call cannot be scheduled until a version has been submitted. Clients see the request state on project details. Consulting editors see only their own schedule, even when they have no access to project files. Calls take place outside the app; no meeting link or provider is integrated.
- Payment, assignment, editing start, version submission, revision, acceptance, consultation, and recorded-deadline events create durable in-app notices. Event keys make retries idempotent. An account notice without a project is visible only to its recipient; project notices require current project access. Recipients can mark their notices read.
- `python manage.py notify_overdue` can be run repeatedly by an operator or future scheduler. It alerts admins and the current editor only for confirmed paid, open projects whose **persisted** `expected_delivery_at` is in the past. It does not manufacture 24-hour deadlines. A changed deadline creates a distinct alert; the same deadline does not duplicate alerts.

## Verification

- Isolated backend tests cover unpaid versus verified consultation requests, duplicate events, admin-only scheduling, consultant file denial, private inbox/read access, paid/recorded-deadline filtering, queue display and idempotent overdue alerts. Django system and migration checks and Ruff pass.
- Additive `operations.0006` applied to the selected Supabase private `vedioos` schema after a local private row snapshot `database-snapshot-20260918T151321112761Z.json`. There were zero existing call requests/duplicate stage pairs. The unique `(project, stage)` constraint is present. `migrate --check` passes; all 42 tables have RLS and browser roles have no schema access. The Security Advisor reports only the expected [informational no-browser-policy notice](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) for this server-owned schema.
- No paid subscription or upgrade was required.

## Remaining before the Phase 7 gate

- D06 must define the deadline clock and thresholds before automatic 24-hour targets or early warnings can be enabled. The overdue command needs an approved operational schedule and monitoring.
- D12 must define consultation obligations, delivery channels, contact/meeting logistics and notification preferences. In-app notices are transactional records; external delivery and retry workers are not integrated.
- Finish project communication, broader audit coverage, mobile upload and accessibility/browser verification, and the full 28-priority traceability audit. Existing production blockers in Phases 3–6 remain open; this slice does not activate real payments, AI classification or production media hosting.
