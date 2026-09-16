# Phase 3 — Catalog, quotes and payment foundation

Implemented on 2026-09-16. Requirements: original brief sections 7–9 and product rules sections 4–7.

## What works

- Admin → Plans / Pricing: three plan slots, features, prices in integer minor units, currency, revision/duration/delivery allowances, priority, publishing, custom services, and commercial terms.
- Publishing validates required plan fields. Enabling quotes requires service, delivery, refund and tax terms. No commercial defaults or sample prices are seeded into the connected database.
- Client → Project → Choose package / quote: select an active plan or custom base plus selected services. The server calculates the total and rejects submitted prices. Unavailable/mixed-currency items cannot be quoted.
- Quote review displays itemized prices and commercial terms. Explicit acceptance saves a snapshot. Catalog changes cannot rewrite displayed quotes or accepted orders. A newer quote supersedes an older unaccepted review. Starting payment locks the agreement against repricing.
- Protected order summaries, paid/unpaid admin filters, payment history and confirmed-payment receipts. Receipts are payment records, not tax invoices.
- An explicitly enabled **development sandbox** creates one retry-safe payment attempt per order and receives HMAC-authenticated events. Amount, currency, reference and order must match. Invalid/stale signatures and conflicting event IDs fail. Failure never activates work; duplicate success activates the existing project once; late failure cannot reverse success.
- Payment confirmation time persists. Expected delivery stays unset until D06 specifies an executable deadline policy. No automatic assignment or earnings are enabled.

## Current connected environment

Payment mode remains `disabled`. Catalog and commercial policy remain unconfigured. Real prices, quote publication and payment cannot be enabled accidentally by visiting the screens.

Three additive tables were migrated to Supabase: `commerce_policy`, `order_quotes`, `payment_events`. All 39 application tables have RLS; the private schema denies `anon` and `authenticated` access. Backend Django authorization remains authoritative. The security advisor reports only the intentional [RLS without policies information notice](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) for this backend-only schema. See [Supabase architecture](SUPABASE.md).

The pre-change data export is stored in ignored `.runtime/pre-phase3.json`. Verification fixtures are isolated in the test database or rolled back on PostgreSQL. No synthetic prices/payment records were retained in Supabase.

## Tests and evidence

```powershell
.venv/Scripts/python.exe manage.py test tests.test_commerce tests.test_foundation tests.test_database_config
$env:RUN_COMMERCE_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_commerce_browser
.venv/Scripts/python.exe manage.py verify_commerce_cloud
.venv/Scripts/python.exe manage.py check_database
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/ruff.exe check .
```

37 automated checks passed, including 17 commerce checks. One real Edge browser test passed through admin configuration → client custom quote → mobile acceptance → signed gateway event → duplicate callback → receipt. No browser page errors or mobile horizontal overflow. Screenshots are in ignored `.runtime/screenshots/phase3-*.png`.

The PostgreSQL verification command passed quote calculation, acceptance, payment activation, duplicate-event handling and rollback. It temporarily overrides test policy inside one transaction; all changes roll back. This is not a concurrent production gateway/load test.

## Payment adapter boundary

`core/payments.py` contains checkout and event verification/settlement. The sole implemented gateway is `sandbox`; no real provider is selected or integrated. The sandbox requires `DEBUG=true`, `PAYMENT_MODE=sandbox` and a server-only random `SANDBOX_PAYMENT_SECRET` of at least 32 characters. It is refused when `DEBUG=false`. The application `.env` remains disabled; the browser test supplies these settings only to an isolated test server.

`POST /api/payments/sandbox/webhook/` accepts a small JSON event with `event_id`, `reference`, `order_id`, integer `amount_minor`, `currency`, and `status` (`confirmed` or `failed`). `X-Sandbox-Signature` is `unix_seconds.hex_hmac_sha256(timestamp + '.' + raw_body)`; freshness tolerance is five minutes. The secret never enters client HTML. The browser test demonstrates a separate trusted test sender. No client-facing "mark paid" endpoint exists.

A real adapter must implement its provider's official signature validation and server-side payment verification, idempotent session creation, event reconciliation, expiry/retry rules and refund/dispute handling. Do not point a real provider at the sandbox endpoint or treat sandbox receipts as revenue.

## Owner decisions still required

1. D03: currency, all three plan names/prices/features, revisions/duration limits, priority and delivery allowances.
2. D04: custom base/services, handling unpriced extras and quote validity/expiry. Current development quotes preserve displayed terms without automatic expiry; this is not an approved production expiry policy.
3. D05: payment provider, account credentials, tax calculations, legal business/invoice information, refund/cancellation handling.
4. D06: delivery clock start, milestones, working/calendar hours and pause rules.

**Phase 3 is an implemented configuration/quote/sandbox milestone, not a completed real-payment production gate.** Real provider integration, tax invoices and automatic deadlines remain blocked by the decisions above. Continue to Phase 4 only with these limits visible; never allocate unpaid work.

## Cost and publishing preferences

Owner requested notification before a subscription or upgrade is needed. This milestone added no paid service, subscription or dependency. Reuse the existing stack; investigate actual usage/provider requirements before proposing expenditure. Notify the owner before buying or upgrading anything.

Owner also requested that every major change be pushed to GitHub so the team can work from current code. Commit and push each verified milestone, keep credentials/data excluded, avoid force pushes, and report the branch/commit and any push failure. This does not authorize production deployment or purchases.
