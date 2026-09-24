# Phase 8 — Broader commercial features

Status: in progress. Operational analytics, private client support and the admin client-operations roster were verified on 2026-09-24. Package sales and production business analytics remain disabled pending owner policy.

## Available now

- Admin → Analytics replaces the former placeholder with live, read-only counts for active clients, orders and payment states, projects and workflow states, open assignments, editor approval/availability, consultations, payout requests and email-delivery state.
- Every figure is derived directly from current source records. The page labels its UTC generation time and links administrators back to the corresponding operational lists for reconciliation.
- The route is protected by the existing server-side admin role check. Clients, editors and anonymous visitors cannot access it.
- Revenue, refunds, trends, delivery averages, revision rates, package performance and retention are deliberately withheld. D15 must define their formulas, financial inclusion rules and reporting timezone before those figures can be presented.
- Clients can open a categorized support request, optionally link one of their own projects, and continue a private conversation while the request is open. Administrators can filter the queue, send client-visible replies, keep separate internal notes, and move requests through open, in-progress, resolved and closed states.
- Backend authorization protects every support list, detail, message and status action. Another client cannot view a case or attach someone else's project; clients cannot post internal notes or change status. Submission keys make case creation and messages retry-safe.
- Support notifications contain only event summaries. Audit entries record category, request, project, audience and status changes without copying support-message bodies.
- Admin → Feature controls provides one protected inventory of actual workflow controls. It reflects persisted commerce, review, upload, assignment and earning policies plus environment-controlled payment, payout and notification modes, with links to existing configuration pages. Package sales and AI remain visibly locked pending D13 and D08.
- The control center does not introduce a generic bypass flag or display credentials. Existing validation, order snapshots, payment verification and authorization boundaries remain authoritative.
- Client payment history and the new admin payment ledger provide status filters and stable 50-record cursor pages. New records do not shift an already-issued older-history cursor. Client queries are ownership-scoped on the backend; administrators can reconcile records across clients and open confirmed receipts or the related order.
- Payment pages preserve the existing boundary: sandbox rows are labeled as test records, receipts require server-confirmed payments, and no row is represented as a tax invoice. D05 still controls legal invoice fields, tax, refunds and the real provider.
- Admin → Clients now reconciles each account with its open/completed projects, confirmed orders, open support load and latest project activity. Administrators can search by name/email, filter active, awaiting-verification and inactive accounts, and traverse stable 50-record cursor pages.
- Client status is derived from the authentication record. The roster does not add an account-state override or silently activate an unverified account.

## Verification

- Focused tests reconcile representative confirmed/refunded orders, open/completed projects, assignment, editor availability, pending payout and held-notification records against the rendered analytics data.
- Access checks cover anonymous redirect, authenticated client denial and admin success.
- The full isolated suite passes 139 tests with 10 opt-in integration tests skipped. Ruff, Django system and migration checks pass.
- Additive migration `operations.0013` created private `support_requests` and `support_messages` tables after ignored private row snapshot `database-snapshot-20260924T064606086761Z.json`. Both tables were empty after migration, the status index and audience constraint are present, all 46 tables retain RLS and browser roles have no schema access.
- The feature-control inventory changes no schema; Supabase remains synchronized through `operations.0013`.
- Payment-ledger pagination changes no schema; Supabase remains synchronized through `operations.0013`.
- Client-roster tests reconcile annotated counts, account filters, role denial and cursor rejection. This slice changes no schema; Supabase remains synchronized through `operations.0013`.
- No paid subscription or upgrade was required.

## Remaining before the Phase 8 gate

- D13 must define monthly package pricing, renewal, expiry, rollover, quota reservation and dedicated-editor behavior before package sales can open.
- D15 must define production analytics formulas and reporting timezone.
- D14 must supply approved public claims, testimonials, support contacts and service terms.
- Production payment, notification and meeting-provider choices remain governed by D05 and D12.
