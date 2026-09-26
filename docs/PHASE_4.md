# Phase 4 — Editor capacity, complexity review and allocation

Implemented 2026-09-16 against original brief sections 12–17 and product rules sections 8–9. This is the allocation milestone; AI classification and production activation remain pending the decisions below.

## Available workflows

- Admin → Editors → **Manage capacity & eligibility**: approval, proficiency, availability, maximum open workload and an audited reason. The backend rejects capacity reductions below current workload and approval revocation while work remains assigned.
- Admin → Assignments: paid work needing review, waiting queue, assigned work and persistent rotation positions.
- Project assessment: an admin selects Beginner/Intermediate/Advanced and records an internal reason. A revision number prevents stale forms overwriting a newer assessment. Unpaid or unverified projects cannot enter the queue. Changing complexity preserves the current assignment until explicitly reassigned.
- Manual assignment/reassignment: requires a matching approved, active and available editor with spare capacity, a reason and the expected current assignment. Historical assignments remain. The former editor loses future project/API/download authorization; previously signed URLs retain their existing expiry (currently 60 seconds for downloads).
- Round robin: each proficiency has its own persisted last editor and sequence. Finishing early, changing availability and restarting do not reset rotation. Allocation and pointer updates commit together.
- The queue records waiting reasons, attempts and last-attempt time. Reprocessing an assigned project is idempotent.
- Admin, editor and client project screens show the assigned editor and existing deadline. Allocation/reassignment never invents or resets a deadline.

## Policy is explicit and currently disabled

The new singleton `assignment_policy` is seeded with manual and automatic allocation **off**, with choices unset. No production policy or editor capacity was invented. In Admin → Assignments → Configure allocation, select:

- Same-proficiency matching (the supported option; no automatic cross-level fallback).
- Capacity counts every open assignment, including review and revisions (the supported option).
- Registration-order roster; new members are appended. Unapproved/inactive accounts leave the eligible roster. The persisted last-editor key still anchors the rotation if that editor changes proficiency or leaves the roster.
- Manual assignment preserves or advances the rotation pointer.
- Automatic allocation skips unavailable/full editors or waits for the next roster editor. Waiting does not advance the pointer.
- Oldest confirmed-payment queue order (the supported option).

Policies can be saved as drafts. Enabling assignment validates the relevant choices. Automatic allocation runs through the **Process waiting queue** button, a project’s **Assign next in rotation** action, or:

```powershell
.venv/Scripts/python.exe manage.py process_assignments --limit 50
```

This command processes durable queued work and can be rerun after availability/capacity changes. A background scheduler is not installed. Only projects with a recorded admin complexity review enter the queue; payment confirmation alone does not guess a level.

## Payment and concurrency guards

Assignment checks the order’s confirmed state, project confirmation timestamp, and a matching confirmed payment record. Sandbox payments are excluded when `DEBUG=false`. This milestone does not provide real payment credentials or turn on checkout.

Every allocation and editor eligibility mutation locks the singleton policy row first, then order/project/editor state as needed. This serializes allocation across proficiency groups and keeps capacity reservations, assignment history, status and rotation updates atomic. No external network API call occurs under this lock. Read-only roster screens use aggregated workload counts.

The database still enforces one current assignment per project. PostgreSQL is required for concurrency guarantees; local SQLite tests verify behavior, not row-lock semantics. Future refund/completion/revision/availability workers must use the same allocation lock order when altering capacity or eligibility. Direct manual edits to live assignment/payment rows bypass these safeguards; use the application workflows.

## Supabase migration and verification

- Applied `operations.0003_assignmentpolicy_assignmentqueue_attempts_and_more`.
- Added `assignment_policy`, queue retry metadata/index, complexity revision and assignment policy snapshots.
- Preserved a consistent pre-migration row snapshot of all 39 existing tables in ignored `.runtime/database-snapshot-*.json` using `manage.py snapshot_database`. This is a private row export, not a full database/role backup; migrations remain the schema source.
- Verified 40 tables with RLS and no browser API schema access. Advisors report only the intentional [RLS-without-policies informational notice](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) for the backend-only schema.

Checks:

```powershell
.venv/Scripts/python.exe manage.py test tests.test_assignments tests.test_foundation tests.test_commerce tests.test_database_config
$env:RUN_ASSIGNMENT_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_assignment_browser
.venv/Scripts/python.exe manage.py verify_assignment_concurrency
.venv/Scripts/python.exe manage.py reconcile_assignments
.venv/Scripts/python.exe manage.py migrate --check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe manage.py check_database
.venv/Scripts/ruff.exe check .
```

52 automated checks passed, including 15 allocation tests. Coverage includes fair E1 → E2 → E3 rotation after E1 finishes, separate groups, skip/wait, stale forms, payment restrictions, capacity, audit/history and former-editor file-access denial. The real Edge browser test passed policy/capacity configuration → assessment → round robin → editor access → reassignment → old-editor denial, including mobile layout.

PostgreSQL concurrency verification creates narrowly scoped synthetic records and removes only those records afterward. Two competing admins cannot double-assign one project; two competing projects cannot overbook one editor. Shared policy stays disabled and rotation positions are preserved. It also runs an automatic allocation/retry smoke check in a rolled-back transaction. Use an isolated database instead when live allocation is enabled.

`reconcile_assignments` provides a separate read-only connected-environment check. It validates enabled policy completeness, attributed manual complexity reviews, funded queue records, waiting/assigned state, immutable assignment policy snapshots, current editor capacity, and round-robin pointer consistency. Historical assignments remain valid when later complexity or availability changes; current proficiency drift is reported as an operational warning rather than silently rewriting history.

On 2026-09-26 the connected reconciliation passed with zero complexity reviews, queue records or assignments and three zero-position proficiency rotations. The shared assignment policy remains disabled, and the command made no allocation or pointer changes.

## Remaining decisions and next milestone

- D07/D09: owner-approved capacities and operational choices must be configured before activating allocation. No answer to the skip/wait question has been recorded; the shared policy remains unset.
- D08: no AI provider, model, data-sharing policy or evaluation set was selected. The UI explicitly identifies classification as manual; no mock is presented as AI. Real AI assessment/failure/retry handling remains open.
- D03–D06: real payment and automatic delivery clocks remain pending.
- Next development milestone: editor version submissions, client review/revisions and explicit final acceptance. Earning and excess-revision rules still need their decision records.

No paid subscription, AI request or infrastructure upgrade was needed or purchased for this milestone. Source/migrations/docs are pushed together to the current GitHub integration branch.
