# VedioOS

A managed video-editing service connecting clients with our internal team of human editors. Editors work in their own editing software; VedioOS manages ordering, payments, files, assignment, communication, review, delivery, and editor earnings.

**Core principle: high-quality video + privacy + fair editor allocation + human editing + a simple client experience.**

## Project status

Day 1 includes core and operational database migrations, client/editor registration, shared login/logout, protected dashboards, admin editor approval, project drafts, and private direct uploads/downloads. The Django backend is configured for [the selected Supabase PostgreSQL project](docs/SUPABASE.md), with SQLite retained as an explicit offline/test option. Media storage remains the separate private S3-compatible local service.

Phase 3 now includes admin plans/custom pricing, commercial terms, client quotes, saved order agreements, paid/unpaid order filters, payment history and an isolated signed-payment sandbox. See [Phase 3 behavior, tests and remaining decisions](docs/PHASE_3.md). Real checkout, automated assignment, revisions/acceptance, earnings/redemption, and production deployment are not active. See also [Day 1 evidence](docs/DAY_1_VERIFICATION.md) and [architecture](docs/ARCHITECTURE.md).

Phase 4 adds editor capacity controls, manual complexity review, paid queues, audited assignment/reassignment and persistent round robin with configurable skip/wait behavior. See [Phase 4 evidence and activation settings](docs/PHASE_4.md). Allocation is implemented but remains disabled in the connected environment until operating policies are configured; AI classification is not integrated.

Phase 5 adds private editor submissions, version history, revision requests, explicit client acceptance and in-app notifications. [Phase 5 verification and activation](docs/PHASE_5.md) includes real storage/browser checks and PostgreSQL concurrency checks. Review requires an agreed rule in the order snapshot; it remains unconfigured for existing orders. Acceptance records pending earnings without inventing coin values. Phase 6 is next.

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

## How to start implementation

The immediate milestone is [Day 1](docs/DAY_1.md): **Hamsa owns Client + Core Platform; Dheeraj owns Admin + Editor Operations.** Resolve the prerequisite stack decisions from Phase 0 in [the roadmap](docs/ROADMAP.md), then follow the Day 1 tasks and shared integration contract. Do not start complex assignment logic until its mandatory gate passes. Follow [AGENTS.md](AGENTS.md) for every change.

The Day 1 application and setup commands are below. Keep credentials out of this repository; `.env`, local databases, test credentials, and storage objects are ignored.

## Local setup — Windows / PowerShell

Requirements: Python 3.13, Node.js 22+, and internet access for dependency installation. Run from the repository root. No Docker daemon is required. The browser verification script uses installed Microsoft Edge.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
.venv/Scripts/python.exe scripts/setup_local.py
npm.cmd ci
npm.cmd run vendor
.venv/Scripts/python.exe scripts/install_storage.py
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py init_local
```

`setup_local.py` creates random local credentials and preserves an existing `.env`. `install_storage.py` installs SeaweedFS 4.47 from its official release after verifying its pinned SHA-256 digest. `init_local` creates a **development-only** 512 MiB per-file limit and supported-type configuration. It does not create prices, paid orders, or production policy.

Start storage in a terminal and leave it running:

```powershell
.venv/Scripts/python.exe scripts/start_storage.py
```

After storage is ready, run in another terminal:

```powershell
.venv/Scripts/python.exe manage.py init_storage
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

Open [the local application](http://127.0.0.1:8000). `--noreload` requires a server restart after Python changes; omit it during normal interactive development if automatic reloading is desired. Stop each foreground server with Ctrl+C when finished.

The app runs on port 8000; signed S3 uploads/downloads use port 9000. Storage internal services use loopback ports 28000–28002 and 38000–38003. These internal services are development infrastructure, not public endpoints. Do not expose them or use the local storage bootstrap as a production deployment recipe.

### Accounts

- Clients register at `/register/`.
- Editors apply at `/register/editor/`; they can log in while awaiting approval but cannot access assigned work until approved and assigned.
- All roles log in at `/login/` and are routed to their own dashboard.
- Create an admin through a **hidden password prompt**, replacing the example name/email with the intended manager:

```powershell
.venv/Scripts/python.exe manage.py create_admin --email manager@example.com --name "Studio Manager"
```

This command refuses to elevate an existing account silently. There are no shared/default admin credentials and no public admin signup. Admins review editor applications at `/admin/editors/`.

### Verification commands

```powershell
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/ruff.exe check .
.venv/Scripts/python.exe manage.py test tests.test_foundation
```

With real local storage running and initialized:

```powershell
$env:RUN_STORAGE_TESTS='1'
.venv/Scripts/python.exe manage.py test tests.test_storage_live
```

With both the app and storage running, verify the browser flow:

```powershell
.venv/Scripts/python.exe manage.py browser_fixture
npm.cmd run test:browser
```

The browser fixture creates a randomly credentialed **synthetic** local admin. Browser tests create clearly named synthetic clients/editors/projects and leave those records for inspection. Credentials and screenshots are saved only in ignored `.runtime/`. Live storage tests use an isolated test database and remove their own synthetic object versions. They never use real client media.

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
