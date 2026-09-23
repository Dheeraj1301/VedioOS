# Phase 8 — Broader commercial features

Status: in progress. The operational analytics slice was verified on 2026-09-24. Package sales and production business analytics remain disabled pending owner policy.

## Available now

- Admin → Analytics replaces the former placeholder with live, read-only counts for active clients, orders and payment states, projects and workflow states, open assignments, editor approval/availability, consultations, payout requests and email-delivery state.
- Every figure is derived directly from current source records. The page labels its UTC generation time and links administrators back to the corresponding operational lists for reconciliation.
- The route is protected by the existing server-side admin role check. Clients, editors and anonymous visitors cannot access it.
- Revenue, refunds, trends, delivery averages, revision rates, package performance and retention are deliberately withheld. D15 must define their formulas, financial inclusion rules and reporting timezone before those figures can be presented.

## Verification

- Focused tests reconcile representative confirmed/refunded orders, open/completed projects, assignment, editor availability, pending payout and held-notification records against the rendered analytics data.
- Access checks cover anonymous redirect, authenticated client denial and admin success.
- The full isolated suite passes 115 tests with 10 opt-in integration tests skipped. Ruff, Django system and migration checks pass.
- This slice changes no database schema. The selected Supabase migration state remains `core.0007` and `operations.0012`; ordinary application writes continue to persist there.
- No paid subscription or upgrade was required.

## Remaining before the Phase 8 gate

- D13 must define monthly package pricing, renewal, expiry, rollover, quota reservation and dedicated-editor behavior before package sales can open.
- D15 must define production analytics formulas and reporting timezone.
- D14 must supply approved public claims, testimonials, support contacts and service terms.
- Production payment, notification and meeting-provider choices remain governed by D05 and D12.
