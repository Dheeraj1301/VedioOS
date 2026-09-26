# Phase 6 — Editor earnings and payout administration

Implemented as an opt-in development milestone on 2026-09-17. The connected Supabase project's earning and redemption policy remains disabled because D10 business values, conversion, eligibility and real payout provider are not approved.

## Flow

1. Admin can configure a prospective fixed whole-coin award for each of three plan slots and custom editing. It has no exchange rate. The rule is disabled by default.
2. A new quote snapshots the exact award, rule version, precision and manual-release condition. Later changes never rewrite an accepted order. Existing paid orders without a saved rule remain `pending_policy` and receive no invented amount.
3. When the client accepts an assigned editor's version, the same transaction creates one pending ledger entry under that order's saved rule. Repeated acceptance cannot issue a second entry.
4. An admin verifies the accepted project and releases the agreed amount. Two append-only entries close pending and credit earned/redeemable coins. Repeating the release does not credit again. Refunded orders are not releasable.
5. The editor wallet displays pending, total earned, redeemable, redeemed, transaction and request history. Totals are derived from ledger entries, not an editable balance.
6. In the explicitly enabled development payout sandbox, a redemption reserves available coins under a wallet lock. An admin can simulate a failed payout (release the reserve), record a unique synthetic paid reference, or reject and release. Repeated requests with the same token and repeated outcomes are idempotent. Real money never moves in this sandbox.

Only administrators can configure/release/process; editors see and request only their wallet; clients cannot access internal earnings. In-app notifications and attributable audit events record release and redemption outcomes.

## Restrictions and open decisions

- `PAYOUT_MODE=disabled` is the default. `sandbox` requires `DEBUG=true` and is for development fixtures only. A provider adapter, signed provider event verification, payout account collection and real settlement reconciliation remain to be built before any real redemption.
- D10 still needs owner-approved coin precision/value, earning formula, pending release timing, reassignment split, minimum, refund/reversal policy and payout method. The fixed whole-coin option is supported code, not an approved production rate.
- The model/service treats coin entries as append-only and uses unique event keys. The current database owner can still mutate rows through direct SQL or bulk ORM operations; database-level immutability/segregated write privileges are a production hardening item.
- No automatic credit is made for old `pending_policy` acceptances. A separately approved audited backfill plan would be required.
- No paid subscription or upgrade was needed for this milestone.

## Evidence

- 72 backend tests pass: quote snapshots, old agreements, pending/earned/redeemable/redeemed totals, idempotent acceptance/release/request/outcome, failed/rejected reserves, role denial, inactive payout guard and existing foundation/commerce/allocation/review behavior.
- Edge browser test passes editor wallet → admin release → sandbox reserve → failed payout release → second reserve → synthetic paid outcome. The 390px wallet view has no horizontal overflow.
- `verify_wallet_concurrency` on selected PostgreSQL raced two 80-coin requests against one synthetic 120-coin wallet. Exactly one reserved. It cleaned up exact synthetic fixtures and did not enable/change the live earning policy.
- Additive migrations `operations.0004` and `0005` applied after private 41-table export `database-snapshot-20260917T052414196029Z.json`. The selected project has 42 tables in private `vedioos`, all with RLS, and browser roles have no schema access. The Security Advisor's [RLS enabled without browser policies](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) INFO notice is expected for the backend-only schema.

## Checks

```powershell
.venv/Scripts/python.exe manage.py test tests.test_earnings tests.test_delivery tests.test_assignments tests.test_commerce tests.test_foundation tests.test_database_config
.venv/Scripts/python.exe manage.py reconcile_earnings
$env:RUN_EARNING_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_earning_browser
.venv/Scripts/python.exe manage.py verify_wallet_concurrency
.venv/Scripts/python.exe manage.py check_database
```

The browser test uses isolated SQLite and synthetic accounts; the concurrency command uses the configured development PostgreSQL project and removes only its own fixture IDs. Do not enable sandbox settings on a production deployment.

`reconcile_earnings` is a separate read-only connected-environment check. It verifies that accepted-work states match the exact pending/closed/credit entries from their saved rule, redemption states match reserve/redeem/release entries, decision metadata is attributable, ledger links and signs are valid, and no wallet has a negative pending or redeemable aggregate. It prints aggregate counts only and is included in the consolidated release evidence.

On 2026-09-26 the connected reconciliation passed for two editor wallets with no acceptances, coin transactions or redemption requests. This is a clean disabled-policy baseline; it does not prove or activate a real payout provider.
