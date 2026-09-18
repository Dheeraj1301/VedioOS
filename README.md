# VedioOS

A managed video-editing service connecting clients with our internal team of human editors. Editors work in their own editing software; VedioOS manages ordering, payments, files, assignment, communication, review, delivery, and editor earnings.

**Core principle: high-quality video + privacy + fair editor allocation + human editing + a simple client experience.**

## Project status

Day 1 includes core and operational database migrations, client/editor registration, shared login/logout, protected dashboards, admin editor approval, project drafts, and private direct uploads/downloads. The Django backend is configured for [the selected Supabase PostgreSQL project](docs/SUPABASE.md), with SQLite retained as an explicit offline/test option. Media storage remains the separate private S3-compatible local service.

Phase 3 includes admin plans/custom pricing, commercial terms, client quotes, saved order agreements, paid/unpaid order filters, payment history and an isolated signed-payment sandbox. See [Phase 3 behavior, tests and remaining decisions](docs/PHASE_3.md). Real checkout and production deployment remain inactive. See also [Day 1 evidence](docs/DAY_1_VERIFICATION.md) and [architecture](docs/ARCHITECTURE.md).

Phase 4 adds editor capacity controls, manual complexity review, paid queues, audited assignment/reassignment and persistent round robin with configurable skip/wait behavior. See [Phase 4 evidence and activation settings](docs/PHASE_4.md). Allocation is implemented but remains disabled in the connected environment until operating policies are configured; AI classification is not integrated.

Phase 5 adds private editor submissions, version history, revision requests, explicit client acceptance and in-app notifications. [Phase 5 verification and activation](docs/PHASE_5.md) includes real storage/browser checks and PostgreSQL concurrency checks. Review requires an agreed rule in the order snapshot; it remains unconfigured for existing orders.

Phase 6 adds prospective coin rules, acceptance-linked pending credits, admin release, an editor wallet and a sandbox redemption flow with reserved balances. See [Phase 6 evidence and activation limits](docs/PHASE_6.md). The connected project's earning and redemption policy remains disabled; real coin value and payout method await owner decisions.

Phase 7 now includes admin status queues, paid consultation tracking, recipient-scoped in-app notifications and alerts for already-recorded overdue deadlines. See [Phase 7 scope and remaining work](docs/PHASE_7.md). The full Phase 7 gate remains open.

## Read before developing

| Document | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Required working instructions for coding agents and contributors |
| [Product rules](docs/PRODUCT_RULES.md) | Product scope, restrictions, workflow, and acceptance requirements |
| [Development pathway](docs/ROADMAP.md) | Dependency-ordered phases and completion gates |
| [Day 1 plan](docs/DAY_1.md) | Hamsa and Dheeraj's foundation tasks, integration contract, and mandatory proof |
| [Day 1 verification](docs/DAY_1_VERIFICATION.md) | Implemented behavior, actual checks, and remaining limits |
| [Phase 3 milestone](docs/PHASE_3.md) | Catalog/quote workflow, payment sandbox, verification and live-checkout blockers |
| [Phase 4 milestone](docs/PHASE_4.md) | Editor workload, paid queues, allocation policy, concurrency and reassignment |
| [Phase 5 milestone](docs/PHASE_5.md) | Version review, revisions, acceptance and private delivery |
| [Phase 6 milestone](docs/PHASE_6.md) | Coin ledger, wallet, release and sandbox redemption |
| [Phase 7 milestone](docs/PHASE_7.md) | Operations queues, consultations, notices and deadline alerts |
| [Architecture](docs/ARCHITECTURE.md) | Stack, models, session/permission flow, and private storage contract |
| [Supabase connection](docs/SUPABASE.md) | Selected cloud project, private schema, configuration, and verification |
| [Open decisions](docs/DECISIONS.md) | Unresolved business and architecture choices; decision record |
| [Team workflow](docs/TEAM_WORKFLOW.md) | Current Git branch, safe collaboration, local setup and publishing cadence |
| [Original brief](docs/ORIGINAL_BRIEF.md) | Complete, unmodified source requirements, sections 1–35 |

The original brief is the baseline. The rules operationalize it, and the roadmap sequences it. Sequencing a feature later does not remove it from scope. Record subsequent explicit owner decisions in the decision log. If documents conflict and no later owner decision resolves them, flag the conflict before implementing the affected behavior.

## Service journey

1. Client registers, uploads source files/assets/references, and describes the edit and song preference.
2. Client selects one of three configurable plans or chooses a custom order and sees the price.
3. The backend confirms payment and activates a uniquely identified order/project.
4. AI recommends complexity; an admin can override it. Eligible editors receive assignments through persistent round-robin allocation or admin assignment.
5. The assigned editor downloads original files, edits externally, and uploads a versioned draft.
6. The client reviews, requests revisions, or accepts a specific version.
7. Acceptance completes the project, makes the accepted final file downloadable, and credits editor coins under the applicable earning rules.

## Users

- **Client:** ordering, private files, progress, communication, calls, review, delivery, history, invoices, and recurring packages.
- **Presenter/admin:** initially two managers; orders, editors, assignment, deadlines, support, configuration, payouts, and analytics.
- **Editor:** approved proficiency, availability, assigned projects, external editing, version submissions, revisions, and coin wallet.

## Non-negotiable boundaries

- No automatic video-editing engine. AI supports complexity classification and assignment only.
- Preserve uploaded source and editor-output bytes exactly. Previews are separate derivatives.
- Private storage and backend role/project authorization are mandatory.
- Editing and assignment require confirmed payment.
- Allocation must persist a separate round-robin pointer per proficiency group and respect capacity.
- Never invent production prices, plan terms, coin values, or unresolved business policies.
- Preserve version history and audit sensitive operations.

## Clone and preview locally — Windows / PowerShell

Use **Python 3.13**, **Node.js 22+**, Git, installed **Microsoft Edge**, and internet access to install dependencies. Docker and a paid subscription are not needed for the local preview. Run these commands in PowerShell. The current team branch is `codex/foundation-and-commerce` (also the repository's current default branch).

### 1. Clone and install

```powershell
git clone --branch codex/foundation-and-commerce https://github.com/Dheeraj1301/VedioOS.git
cd VedioOS
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
npm.cmd ci
npm.cmd run vendor
.venv/Scripts/python.exe scripts/setup_local.py
.venv/Scripts/python.exe scripts/install_storage.py
.venv/Scripts/python.exe manage.py migrate --settings=vedioos.local_settings
.venv/Scripts/python.exe manage.py init_local --settings=vedioos.local_settings
```

If `py -3.13` is unavailable but `python --version` reports Python 3.13, use `python -m venv .venv` for the third command. `setup_local.py` generates a private `.env` and preserves one that already exists. `install_storage.py` downloads the pinned Windows AMD64 SeaweedFS 4.47 binary and verifies its SHA-256. Other operating systems need their matching SeaweedFS binary at `.runtime/seaweedfs/weed`. Run the remaining commands from the repository root.

`--settings=vedioos.local_settings` keeps preview data in ignored `.runtime/db.sqlite3`, even if a developer later adds a cloud `DATABASE_URL`. Do not put Supabase credentials or real media into Git. `.env`, `.runtime`, virtual environments and `node_modules` are ignored.

### 2. Start the private storage service

Open **PowerShell terminal A** in the cloned repository and leave it running:

```powershell
.venv/Scripts/python.exe scripts/start_storage.py
```

The service listens on `127.0.0.1:9000`. In **PowerShell terminal B**, initialize its private, versioned bucket and start Django:

```powershell
.venv/Scripts/python.exe manage.py init_storage --settings=vedioos.local_settings
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --settings=vedioos.local_settings
```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)**. Keep both terminals running during the preview and full browser test. Stop each with Ctrl+C. Django reloads Python changes in this mode; use `--noreload` only when you want to restart it manually. If ports 8000 or 9000 are occupied, stop the conflicting local service first; the browser and CORS tests expect these exact ports.

### 3. Create preview accounts

Clients register at `/register/`; editors apply at `/register/editor/`. All roles log in at `/login/`. Create an admin in **terminal C** with a password entered at the hidden prompt:

```powershell
.venv/Scripts/python.exe manage.py create_admin --email manager@example.com --name "Studio Manager" --settings=vedioos.local_settings
```

Use your own email and name. The command will not silently turn an existing client/editor into an admin. An editor can log in before approval, but an admin must approve proficiency at `/admin/editors/` before assignment.

| Area | Local URL | What to check |
| --- | --- | --- |
| Public landing | `/` | Service sections and responsive layout |
| Client | `/client/`, `/client/new-order/`, `/client/projects/`, `/client/payments/` | Registration, brief, private source upload and order history |
| Editor | `/editor/`, `/editor/revisions/`, `/editor/wallet/`, `/editor/availability/` | Assigned work, version submissions, revision queue and wallet |
| Admin | `/admin/`, `/admin/editors/`, `/admin/assignments/`, `/admin/pricing/`, `/admin/payouts/`, `/admin/earnings/` | Approval, allocation, catalog and earning settings |

Fresh local settings intentionally contain **no plan prices, payment gateway, assignment policy, review agreement or coin values**. Registration, drafts, uploads and role checks work immediately. Payment, assignment, review and wallet flows are exercised end to end by the isolated synthetic tests below. To explore them manually, configure the corresponding admin settings and development sandboxes first; never treat synthetic payments or payouts as real transactions. See [Phase 3](docs/PHASE_3.md), [Phase 4](docs/PHASE_4.md), [Phase 5](docs/PHASE_5.md) and [Phase 6](docs/PHASE_6.md).

## Verify the whole application

Run these commands in **terminal C** from the repository root. `manage.py test` automatically uses `vedioos.test_settings` and a separate, temporary SQLite database; it does **not** drop or flush the preview database or Supabase. The optional browser tests below create synthetic accounts and fixtures in their own temporary database.

### Backend, migrations and code checks

```powershell
.venv/Scripts/python.exe manage.py check --settings=vedioos.local_settings
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=vedioos.local_settings
.venv/Scripts/ruff.exe check .
.venv/Scripts/python.exe manage.py test
```

The last command runs the foundation, commerce, assignment, delivery and earnings backend suites. Browser and real-storage tests are intentionally opt-in, so run the commands in the next two sections for the complete check.

### Real private-storage integrity tests

With storage running and initialized in terminals A/B:

```powershell
$env:RUN_STORAGE_TESTS='1'
.venv/Scripts/python.exe manage.py test tests.test_storage_live
Remove-Item Env:RUN_STORAGE_TESTS
```

These tests upload synthetic bytes to the local private bucket, verify exact downloads, rejection of altered uploads, URL expiry and unauthorized access, then remove their test objects. They do not use client media.

### Browser walkthroughs in Microsoft Edge

The first walkthrough uses the **running local preview** and leaves its synthetic records in the local SQLite database for inspection. Create its separate local admin fixture once, then run it:

```powershell
.venv/Scripts/python.exe manage.py browser_fixture --settings=vedioos.local_settings
npm.cmd run test:browser
```

It checks registration, all three roles, a project, direct upload/download, authorization and mobile layout. The fixture credentials are stored in ignored `.runtime/browser-fixture.json`. Screenshots go to ignored `.runtime/screenshots/`.

Run the later feature walkthroughs one at a time. They each start their **own temporary Django test server** and database, so the main preview server is not required for these four commands. The delivery walkthrough does require terminal A's private storage service.

```powershell
$env:RUN_COMMERCE_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_commerce_browser
Remove-Item Env:RUN_COMMERCE_BROWSER

$env:RUN_ASSIGNMENT_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_assignment_browser
Remove-Item Env:RUN_ASSIGNMENT_BROWSER

$env:RUN_DELIVERY_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_delivery_browser
Remove-Item Env:RUN_DELIVERY_BROWSER

$env:RUN_EARNING_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_earning_browser
Remove-Item Env:RUN_EARNING_BROWSER
```

These cover admin catalog → client quote → signed sandbox payment; complexity/round-robin assignment and reassignment; draft → revision → version acceptance with byte-identical private downloads; and coin release → reservation → failed/paid **sandbox** outcomes. The synthetic browser tests do not charge cards or transfer money. Inspect `.runtime/screenshots/` for desktop/mobile captures.

### Optional checks against the shared Supabase database

The local setup above needs **no Supabase access**. Only teammates who have separately received the dedicated server-side database URL and trusted CA should use this section. Never paste credentials into code, tickets or commits. Follow [the private schema and connection guide](docs/SUPABASE.md). Set `DATABASE_URL`, `DATABASE_SCHEMA=vedioos` and `POSTGRES_SSLROOTCERT` in your ignored `.env`; keep local SeaweedFS separate because media is not shared by the database connection.

These are read-only or rollback/synthetic verification commands against the **configured PostgreSQL database**. The concurrency commands require `DEBUG=true`, remove only their exact synthetic fixtures and should be coordinated with the team if live policies have been activated:

```powershell
.venv/Scripts/python.exe manage.py check_database
.venv/Scripts/python.exe manage.py migrate --check
.venv/Scripts/python.exe manage.py verify_cloud
.venv/Scripts/python.exe manage.py verify_commerce_cloud
.venv/Scripts/python.exe manage.py verify_assignment_concurrency
.venv/Scripts/python.exe manage.py verify_delivery_concurrency
.venv/Scripts/python.exe manage.py verify_wallet_concurrency
```

For an operator-run Phase 7 deadline alert pass, use `.venv/Scripts/python.exe manage.py notify_overdue` against the intended database. It writes in-app notices only for paid, open projects with a recorded past deadline; rerunning it does not duplicate the same alert. No automatic schedule is configured yet.

`check_database` should identify PostgreSQL, the private `vedioos` schema, RLS on all application tables and no browser-role schema access. The shared database is already migrated. **Do not run `migrate`, `flush`, `browser_fixture` or `init_local` against it just to preview the app.** Schema changes follow the backup, review and migration procedure in [team workflow](docs/TEAM_WORKFLOW.md). The optional `node tests/cloud_browser.mjs` script expects an existing synthetic admin fixture and existing projects in that specific shared project; a fresh clone will not have those credentials, so it is not part of the standard checks.

### Stay current with the team

On a clean integration branch, update without overwriting teammates' changes:

```powershell
git status
git fetch origin
git pull --ff-only origin codex/foundation-and-commerce
```

Hamsa owns Client + Core Platform; Dheeraj owns Admin + Editor Operations. Follow [AGENTS.md](AGENTS.md), [the pathway](docs/ROADMAP.md) and [the team workflow](docs/TEAM_WORKFLOW.md) before changing shared models or migrations. Push verified major changes with code, migrations and docs together. Keep secrets and real client media out of Git.

## Repository layout

```text
core/          Hamsa: identity, client/project models, auth, permissions, S3 endpoints
operations/    Dheeraj: operational models, editor application, admin/editor routes
vedioos/       Django settings and URL routing
templates/     Landing, auth, client, editor, and admin server-rendered pages
static/        Responsive styling, direct upload/download JS, licensed hash library
scripts/       Local setup, verified storage installation, and startup helpers
tests/         Foundation, real storage, and browser checks
docs/          Requirements, decisions, pathway, architecture, and evidence
```

## Release definition

The first version includes all 28 priorities in original brief section 34. A landing page, mocked checkout, manual-only assignment, or incomplete wallet is an intermediate milestone. A production release requires the end-to-end and security gates in the roadmap, configured business terms, and working production integrations.
