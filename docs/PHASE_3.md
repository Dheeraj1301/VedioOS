# Phase 3 — Catalog, quotes and payment foundation

## 2026-10-09 guarded test quotation fallback

The quotation failure in the shared preview was caused by an absent `CommercePolicy`, not a calculation error: all seven weighted feature rows existed, but no approved base, per-point, minimum, maximum, currency or terms had been persisted. A real ML predictor remains unavailable because the project has no labelled historical effort/price dataset or acceptance threshold.

Migration `core.0013` adds an explicit pricing context. The primary test calculation remains the owner-approved deterministic 40% time / 20% importance / 40% editor-complexity model. `configure_test_quotation` persists explicitly supplied synthetic amounts and test-only terms only while `DEBUG` and a test payment adapter are active. Test quotes carry their context in the immutable snapshot, show a prominent warning, fail outside a test environment and block release readiness. This enables Save and Proceed → locked quotation → Make Payment → Razorpay Test Checkout without treating synthetic values as production pricing.

Before applying `core.0013` to Supabase project `lmwvoniiykmfzuxigzqf`, a verified ignored snapshot captured 47 tables and 330 rows. The additive migration and guarded test configuration then completed successfully. Post-change checks confirmed current migrations, 47 RLS-protected tables, no browser-role access, a bounded shared weighted estimate and clean commerce reconciliation. The PostgreSQL quote/payment/idempotency exercise passed inside a rolled-back transaction and retained no synthetic fixture rows.

The initial ₹100–₹1,000 preview clamp was later replaced after reviewing published Indian market references. The active preview policy uses a ₹750 base, ₹150 per weighted point and a ₹1,000–₹8,000 clamp. That places colour grading at ₹600, a 30–50 second edit with suggested music at ₹1,560, and the full seven-feature selection at ₹4,320. Client wording now presents this as a market-reference estimate and keeps a single clear no-live-charge disclosure at payment boundaries, without exposing technical environment names or provider identifiers.

Accepted quotations remain immutable. An unpaid custom order can now use **Refresh quotation with current rates**: the backend locks the order, cancels only pending payment sessions, preserves prior quote/payment records for audit, rebuilds the server-owned estimate from the saved brief and creates a new immutable quote. Paid orders and cross-client requests remain denied, and a cancelled Razorpay session cannot later activate the project.

## 2026-10-09 Razorpay Test Mode

The owner supplied Razorpay test credentials through a local ignored file and selected Razorpay for the test checkout. `PAYMENT_MODE=razorpay_test` is permitted only with `DEBUG=true`, an `rzp_test_` key ID, a server-only secret and the official HTTPS API base. Credentials remain in `.env` and are excluded from Git.

After explicit quote acceptance, the backend creates a Razorpay Order from the persisted amount and currency. The client receives the public test key, gateway order ID and locked total and opens Razorpay Standard Checkout. A successful browser response is not trusted by itself: the backend recomputes the `order_id|payment_id` HMAC using the saved gateway order ID, fetches the payment from Razorpay, and requires a captured payment whose order, amount and currency match the VedioOS payment. Confirmation is transactionally idempotent through `PaymentEvent`; invalid signatures, mismatches, cross-client access and non-captured payments fail closed. Test history and receipts are visibly labeled and remain excluded from production assignment eligibility.

Focused adapter, signature, capture, authorization and UI tests pass without sending credentials to the browser or test logs. A read-only live API credential probe reached Razorpay but received HTTP 429 from the shared execution IP, so successful external API access must be rechecked from the owner/team network before claiming a live test transaction. Production keys, refunds, disputes, webhook recovery, taxes and legal invoice data remain outside this test-mode milestone.

## 2026-10-09 custom-order workflow verification

The new-order browser now tolerates unpublished plan slots, so the Custom option remains usable before plans are configured. Save and Proceed recognizes both successful checkout redirects and the editable-draft fallback used when pricing is unavailable; selected source, inspiration and font-reference files therefore continue through private upload verification in either case. The protected project API includes each visible file's category so the browser and support diagnostics can distinguish source and reference uploads without exposing storage keys or signed URLs.

The custom checkout shows the immutable quotation, selected options, itemized breakdown, total, uploaded private-file metadata and an Edit details action before payment. The Make Payment action still requires explicit terms acceptance and uses the configured payment adapter. Real checkout remains disabled until D05 selects and configures a provider.

Verification covered two real Edge flows against isolated SQLite and loopback private storage: configured weighted pricing completed Save and Proceed → inspiration upload → quotation → Make Payment → one pending sandbox payment; disabled pricing completed Save and Proceed → inspiration upload → editable brief without losing the file. The backend suite passed 243 tests with 10 optional integrations skipped. No schema change was required.

## 2026-10-06 weighted custom quotation engine

Custom briefs now include Overlays and Beat sync alongside colour grading, quality enhancement, duration, font/wording and music preference. Authenticated `POST /api/quote/` requests are validated by the backend and return a live deterministic estimate plus contributor breakdown; the legacy `/api/custom-estimate/` route remains compatible. No browser-supplied price is accepted.

The admin pricing workspace exposes Time / Importance / Complexity weights, price per complexity point, minimum/maximum bounds, currency, and editable 1–5 scores plus a multiplier for each of the seven features. Migration `core.0012` seeds only the owner-approved scores and neutral multipliers; it seeds no prices and leaves the engine disabled. Once enabled with complete price configuration, the calculation is `base + Σ(weighted feature score × feature multiplier × price per point)`, clamped to the configured bounds. Weight percentages must total 100.

Saving a configured custom brief stores its inputs, weights, feature scores, multipliers, contributor amounts, bounds and computed total in `Project.quotation_snapshot`. Quote creation reuses that server-owned snapshot, so subsequent configuration changes affect new submissions only. The implementation reports `weighted_heuristic_v1`; ML prediction remains deferred because there is no approved historical training target, minimum dataset or confidence threshold.

The client `Save and Proceed` action now creates the corresponding immutable `OrderQuote` in the same transaction and opens a dedicated custom checkout page. That page renders the saved project, selected options, optional contributor breakdown, terms, currency and total from the quote snapshot rather than recalculating current prices. Its `Make Payment` action combines explicit quote acceptance with the existing checkout adapter in one transaction; missing or invalid quotes are blocked, confirmed payments render a completed state, and a disabled provider remains safely unavailable rather than being simulated as a real integration.

Request fields are `colour_grading`, `quality_enhancement`, `reel_duration`, `wants_wording`, `wording_direction`, `song_choice`, `overlays` and `beat_sync`. The response contains `currency`, `total_minor`, `display_total`, `items`, `breakdown` and `model`. The endpoint requires an authenticated client session and CSRF protection.

Migration `core.0012` was applied to Supabase project `lmwvoniiykmfzuxigzqf` on 2026-10-06. Post-migration verification found all seven configured score rows, an unchanged project count, RLS enabled on `vedioos.quotation_features`, ownership by `vedioos_app`, and no browser-role grants. The pre-change aggregate export is retained in ignored `.runtime/pre-quotation-engine-20261006.json`.

Implemented on 2026-09-16. Requirements: original brief sections 7–9 and product rules sections 4–7.

## 2026-10-06 admin price-entry update

Administrators now enter catalog prices as ordinary currency amounts instead of integer minor units. The currency selector remains authoritative: two-decimal currencies accept at most two decimal places, while JPY and KRW accept whole amounts only. Admin forms convert validated values to the existing integer minor-unit columns before saving, and existing stored values are converted back to major units when edited. Plans, monthly/yearly plan prices, custom services, creator-package drafts and the custom base all use the same boundary. Quotes, accepted snapshots, orders and payments continue using unchanged integer minor units internally. Shared display formatting now uses the selected currency symbol and exponent. No schema or stored-data migration was required.

## 2026-09-24 custom-estimate extension

The new-order customization controls now request a live server-authoritative estimate. Administrators map at most one priced custom service to each supported customization code; the backend adds the configured custom base, rejects missing/inactive/wrong-currency mappings, returns an itemized display, and resolves the mappings again when creating the quote. Browser totals are never accepted. Migration `core.0007` adds the nullable unique mapping code without inserting production prices. The isolated suite passes 108 tests with 10 optional integrations skipped. Production activation remains blocked on approved D03–D06 commercial terms and provider settings.

## What works

- Admin → Plans / Pricing: three plan slots, features, human-readable currency amounts, currency, revision/duration/delivery allowances, priority, publishing, custom services, and commercial terms. The server converts prices to integer minor units before persistence.
- Each fixed plan may also hold optional monthly and yearly amounts. The new-order selector persists the chosen pricing period and the quote snapshot uses its matching server-owned amount; missing combinations remain unavailable. This is distinct from recurring creator packages and does not define renewal or allowance policy.
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
.venv/Scripts/python.exe manage.py reconcile_commerce
.venv/Scripts/python.exe manage.py check_database
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/ruff.exe check .
```

37 automated checks passed, including 17 commerce checks. One real Edge browser test passed through admin configuration → client custom quote → mobile acceptance → signed gateway event → duplicate callback → receipt. No browser page errors or mobile horizontal overflow. Screenshots are in ignored `.runtime/screenshots/phase3-*.png`.

The PostgreSQL verification command passed quote calculation, acceptance, payment activation, duplicate-event handling and rollback. It temporarily overrides test policy inside one transaction; all changes roll back. This is not a concurrent production gateway/load test.

The read-only `reconcile_commerce` command also checks the connected environment for malformed quote snapshots, accepted-order drift, duplicate or mismatched payments, missing/invalid payment events, unpaid consultation requests and missing paid consultation stages. It emits aggregate counts only and is included in `collect_release_evidence`.

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
