# Phase 5 — Review and delivery

Implemented and verified on 2026-09-17 against the original brief's editor work, revisions, client approval, original-quality delivery and acceptance-before-earnings requirements.

## Workflow

1. An approved current editor starts a verified paid assignment.
2. The editor uploads an edited file through private direct storage. Clients cannot list or download unsubmitted outputs.
3. The editor submits a verified upload with a client-visible note and optional final-candidate flag. Each submission has an immutable file reference, sequence number and assignment attribution.
4. The client downloads the submitted version and either requests changes with timestamps/notes or explicitly accepts that version.
5. A revision request consumes one allowance under the selected rule. The editor starts the revision and submits a new object/version. Earlier versions remain downloadable.
6. Acceptance completes the project, releases its active-workload capacity and records exactly one acceptance. The first draft can be accepted without another upload. A final-candidate flag alone never completes a project.

Client/editor notifications are persisted in the same transaction as the action. The Notifications page shows the recipient's latest 100 updates only for projects they can still access. The editor Revisions page lists current requested/in-progress revisions. External email/SMS delivery is not integrated.

## Activation and unresolved policy

Admin → Plans / Pricing → commercial policy offers an explicitly selected review rule: one request consumes one revision; only the latest submission can be reviewed/accepted; acceptance is final; excess revisions require a separate agreement. It defaults to blank. This is a proposed supported option, not an approved production business policy.

The rule and revision allowance are snapshotted in new quotes, displayed to the client and preserved on acceptance. Orders without an agreed rule cannot run review actions. Changing admin configuration never rewrites older quotes or paid agreements. No automatic backfill or reopening/cancellation policy is implemented.

Acceptance records `pending_policy` earnings status and the submitted assignment; no wallet credit, conversion or payout is invented. D10 must resolve earning values and reassignment splits before Phase 6 crediting. Deadline calculation remains pending D06. Real checkout and production object storage remain separate setup requirements. No subscription or upgrade was required for this milestone.

## Security and transactions

All actions recheck role, project membership, payment, state and saved terms on the server. The shared allocation policy lock precedes order and project locks so completion, capacity and reassignment serialize consistently. Network storage operations occur outside these transactions. Unique acceptance project/version relationships plus locked transitions prevent repeated or competing requests from double-completing work. Repeated identical submission/revision requests reuse their existing record; conflicting details fail.

Downloads retain exact storage-version selection and temporary access URLs. No transcoding, replacement or public URLs were added. Review uses original downloads; embedded codec playback/derived previews are not implemented. Previously issued links expire under the existing 60-second access contract.

## Verification

- 64 backend tests pass, including 12 delivery tests: revision/acceptance, first draft, final-candidate guard, allowance, stale actions, unpaid/unconfigured rejection, cross-client/role/former-editor denial, private unsubmitted files, pending/foreign file rejection, replay and explicit confirmation.
- Real Edge browser test passes desktop and 390px mobile: paid assigned fixture → private S3 upload → review → revision → second upload → acceptance → byte-identical downloads of both versions. A second project accepts/downloads its first draft. Synthetic binary fixtures test integrity, not video codec playback. Storage requests use Playwright's real HTTP client; this test does not reverify browser CORS or drag-and-drop upload behavior covered by Day 1.
- `verify_delivery_concurrency` passes on selected Supabase PostgreSQL: duplicate acceptance, accept versus revise, and duplicate revisions. Exact temporary synthetic records removed afterward; existing records/configuration preserved.
- Ruff, Django checks and migration drift check pass.
- Additive core migration 0003 applied after private 40-table row export `database-snapshot-20260917T050118594224Z.json`. No destructive migration or commercial backfill. Database check confirms 41 tables, all with RLS, no browser-role schema access. Security Advisor reports only the expected backend-only [RLS enabled without browser policies](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) informational findings.

## Reproduce

```powershell
.venv/Scripts/python.exe manage.py test tests.test_delivery tests.test_assignments tests.test_commerce tests.test_foundation tests.test_database_config
.venv/Scripts/python.exe manage.py reconcile_delivery
$env:RUN_DELIVERY_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_delivery_browser
.venv/Scripts/python.exe manage.py verify_delivery_concurrency
```

Browser verification requires running private local S3 and installed Edge. Unit/browser tests use isolated test databases. The concurrency command requires development PostgreSQL, creates synthetic metadata with no real storage objects, and cleans up exact fixture IDs. If interrupted, inspect its synthetic records before retrying; never flush the shared database.

`reconcile_delivery` provides a separate read-only connected-environment check. It verifies contiguous version numbers, ready private output objects, submission assignment/uploader attribution, revision ownership and allowance snapshots, requested/addressed state, latest-version acceptance, client ownership and accepted agreement terms. It emits aggregate counts only and is included in the consolidated release evidence.

On 2026-09-26 the connected reconciliation passed with zero submitted versions, revision requests or acceptances. The command changed no project, file or review record and did not access media bytes.
