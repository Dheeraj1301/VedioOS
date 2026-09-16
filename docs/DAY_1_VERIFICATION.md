# Day 1 verification — 2026-09-15

## Outcome

Hamsa's Client + Core Platform work and Dheeraj's Admin + Editor Operations work were implemented sequentially. The Day 1 gate passed in the local Windows environment. This is a local foundation milestone, not a production release or completion of later roadmap phases.

## Evidence

| Check | Evidence | Result |
| --- | --- | --- |
| Client registration/login/logout | Django tests plus real browser registration, logout, and login | Pass |
| Editor registration/login | Browser application saves experience and starts unapproved; login succeeds | Pass |
| Admin login | Hidden-prompt CLI provisioning test and synthetic admin browser login | Pass |
| Client cannot enter admin/editor areas | Page/API role matrix tests and browser HTTP requests return 403 | Pass |
| Editor cannot enter client/admin or unassigned projects | 403 for wrong areas, 404 for unassigned project; browser and backend tests | Pass |
| Cross-client files/projects denied | Backend requests against another client's project and file return 404 | Pass |
| No self-approved proficiency | Forged role/approval/proficiency requests rejected; admin approval audited | Pass |
| Migrations | Empty test databases apply core/operations migrations; all 26 requested tables exist | Pass |
| Private upload | Browser uploads directly to real S3 service; backend finalizes metadata | Pass |
| Original integrity | Browser and integration downloads have identical bytes/SHA-256 | Pass |
| Unauthorized download | Anonymous application request returns 401; unsigned S3 read/list returns 403 | Pass |
| Expiring access | Short-lived signed GET works initially and returns 403 after expiry | Pass |
| Immutable upload objects | Reusing PUT permission returns 412; a second upload gets a new key | Pass |
| Checksum/size tampering | Storage rejects mismatched checksums and changed signed metadata | Pass |
| Incomplete uploads | Cannot be finalized or exposed as ready files | Pass |
| All dashboards/navigation | Every requested navigation route loads for its permitted role | Pass |
| Responsive browser flow | Desktop 1440×1000 and mobile 390×844; no horizontal page overflow | Pass |
| CSRF and session protection | Forged mutations rejected; logout removes database session | Pass |

### Automated suites

- `manage.py test tests.test_foundation`: **17 tests passed**.
- `RUN_STORAGE_TESTS=1 manage.py test tests.test_storage_live`: **5 tests passed against real SeaweedFS**, not mocked storage.
- `npm run test:browser`: **end-to-end flow passed** using Microsoft Edge / Playwright; no JavaScript page errors.
- `manage.py check`: no issues.
- `manage.py makemigrations --check --dry-run`: no model/migration drift.
- Ruff checks and formatting applied to authored Python.
- agent-browser independently loaded the landing and registration pages, inspected navigation, and reported no browser errors during the initial visual check.

The browser walkthrough covers landing → client signup → dashboard → project draft → direct upload → original download → logout/login → editor application → availability → editor login → admin login → proficiency approval. Security tests also cover former-editor access after assignment ends. Only synthetic data was used.

### Local evidence files

Screenshots are in ignored `.runtime/screenshots/`: landing desktop/mobile, client dashboard, project desktop/mobile, editor dashboard, and admin desktop/mobile. Test credentials are in ignored `.runtime/browser-fixture.json`; they are not production credentials and must not be committed.

## Practical limits

**Update, 2026-09-16:** PostgreSQL connection, migration, data transfer, and transactional auth/permission checks have now been verified in the selected Supabase project. See [Supabase verification](SUPABASE.md). The original Day 1 results below describe the earlier SQLite/local-storage run.

- SQLite and a Windows loopback SeaweedFS service were tested; PostgreSQL, cloud S3, production TLS/IAM, deployment, backups, and recovery were not.
- Synthetic binary originals over 5 MiB were tested. The development cap is 512 MiB, but full-cap and interruption/load testing remain outstanding.
- Storage checks content length, checksum, and metadata. Deep media validation and malware scanning are deferred; downloaded files are forced attachments.
- Single-object upload works; resumable multipart upload and previews are deferred.
- Admin/editor operational pages beyond registration, approval, availability, and read-only records are skeletons as requested.
- Payments, automated allocation, revisions/final acceptance, earnings, redemptions, subscriptions, and notification delivery remain inactive.
- Existing signed download links can remain valid for their 60-second local TTL after reassignment; newly requested access is denied immediately.

No complex assignment logic was started. The next work should follow the roadmap and resolve the relevant commercial and deployment decisions.
