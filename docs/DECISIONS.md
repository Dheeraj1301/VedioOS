# Open decisions and decision record

Do not substitute invented production values for these decisions. Development fixtures may use clearly labeled demo settings isolated from production. Resolve only the decisions needed for the current phase; unrelated open questions should not halt useful work.

## Decision register

| ID | Decision needed | Resolve before |
| --- | --- | --- |
| D01 | App/backend/database stack, authentication, hosting, environments, deployment process | Phase 1 scaffolding |
| D02 | Storage provider/region, upload limits/types, integrity verification, scanning, retention/deletion/backups, download expiry/revocation | Phase 2 production media |
| D03 | Three plan names/prices/features, currency, duration/revision limits, priority, delivery terms | Real checkout |
| D04 | Custom base/service prices, unpriced Other requests, price changes during checkout | Real checkout |
| D05 | Payment gateway, payment methods, invoice fields, applicable tax handling, refunds/cancellation/disputes | Production payment |
| D06 | 24-hour clock start, delivery milestone, working/calendar hours, review/revision/call pauses, thresholds and overrides | Deadline activation |
| D07 | Editor approval/proficiency criteria, workload capacities, availability changes, states that consume capacity | Assignment activation |
| D08 | AI provider/data sharing, classification rules, override flow, failure handling and evaluation cases | AI activation |
| D09 | Wait/skip policy, cross-level fallback, roster order/changes, pointer effects of manual assignments, queue priority and retry triggers | Automatic assignment |
| D10 | Coin value/precision, earning formula, pending/redeemable timing, reassignment allocation, payout methods/minimums and reversals | Real earnings/redemption |
| D11 | Revision counting/excess revisions, acceptance/final rules, cancellation permissions and reopening | Production review |
| D12 | Communication channels, consultation scheduling and obligations, notification providers/preferences | Production communication |
| D13 | Monthly package terms/prices, renewal/expiry/rollover, quota reservations, dedicated-editor allocation | Package sales |
| D14 | Branding/content, approved testimonials, support contacts and published service terms | Public launch |
| D15 | Analytics formulas, revenue/refund accounting, reporting timezone, retention measurement | Production analytics |
| D16 | Operational recovery targets, monitoring, backup restore, incident ownership and account lifecycle | Production launch |

## Recorded baseline

### Account and order-flow scope update — 2026-09-19

Owner instruction supersedes public editor self-registration in the earlier Day 1 brief. Editor access is now administrator-issued: an editor receives an editor ID and initial password, signs in through the shared login, and has no self-service password-change route. Detailed editor profile and proficiency data remain administrator-managed operational records. Client passwords require at least eight characters containing uppercase, lowercase, numeric and special characters; password inputs provide a visibility control.

The same instruction separates inspiration-video uploads from raw/source uploads, removes the duplicate “already have a song” music choice, adds an option to provide a song while requesting editor suggestions, and requests clearer “plan an edit” wording and authenticated Back navigation. The four-block plan/custom order flow is requested next. Custom pricing must remain server-authoritative; model-based estimates cannot be enabled until approved training examples, evaluation criteria and commercial price rules are supplied. D03, D04 and D08 remain open.

Technical email choice: new client accounts remain inactive until an expiring Django-signed verification link confirms the registered address. Resend responses do not reveal whether an account exists and use the existing database-backed rate limit. Verification is retry-safe and audit logged. Delivery uses Django's replaceable email backend with the console backend for local development; no production provider, domain, subscription or price has been approved. Existing active users remain active.

Technical order-form choice: show all three fixed plan slots and a fourth custom option at draft creation, but allow selection only for active administrator-configured plans. Persist the selected plan/custom kind and custom creative direction. Monthly package records may be displayed when active, while purchase remains disabled until D13 is approved. Custom prices continue through the existing server-authoritative catalog and quote snapshot; no browser-supplied price or untrained model output is accepted.

Custom estimate implementation: administrator-managed custom services may have one unique stable mapping code for colour grading, quality enhancement, each duration band, or wording. The live estimate and final quote both resolve those mappings on the backend and fail closed when a required price is unpublished, incomplete, missing, or uses the wrong currency. Mapped items and the custom base are included in the accepted snapshot. No prices are seeded by migration and no model output affects money.

Monthly package preparation: administrators may save validated package drafts using the existing package records, but the form deliberately excludes publication. It also deactivates any legacy active record edited through this path. Purchase, renewal, quota use and dedicated-editor allocation remain unavailable until D13 supplies executable rules.

Notification delivery foundation: every in-app notice receives one durable external-delivery record. The default state is held and the worker is disabled. When explicitly enabled, a worker claims due rows with a lease, rechecks current recipient/project access, sends through Django's replaceable email backend, and records sent, retry or cancellation state without saving exception messages. Older held messages require an explicit release command. D12 still controls provider, templates, preferences and scheduling.

Client-support foundation: clients can open private support requests and optionally link only their own projects. Shared messages are visible to that client and administrators; internal notes remain administrator-only. Administrators control status. Submission keys make creation/messages retry-safe, notifications contain event summaries, and audit entries exclude message bodies. External support contacts and service obligations remain part of D14/D12.

Feature-control inventory: the admin workspace reports existing validated policy and environment states rather than adding a generic flag that could bypass business or security gates. Configuration links lead to the current commerce, assignment, earning and package-draft controls. Provider-backed payments, payouts, notifications, package sales and AI remain disabled or locked until their recorded decisions are resolved.

### Phase 4 allocation milestone — 2026-09-16

The owner authorized continuing development. Implemented admin assessment, capacity controls and configurable transactional allocation; no provider, capacity or business policy was approved by inference. The skip/wait clarification has no recorded answer, so the shared policy remains unset and disabled. Technical choice: serialize allocation and eligibility changes on one policy row, keep independent persistent proficiency cursors, and verify concurrency on PostgreSQL. Supported operational choices and remaining D07–D09 decisions are documented in [Phase 4](PHASE_4.md). No paid service or AI integration was added.

### Ongoing Supabase synchronization — 2026-09-16

The owner explicitly requested updating the connected Supabase database/tables alongside development changes. Reviewed, tested, non-destructive Django migrations are authorized without repeated confirmation. Preserve backups, verify applied migrations and private-schema protections, and publish matching migration files to GitHub. Destructive/data-rewriting migrations require specific review and approval. This does not authorize purchases or automatic deployment of arbitrary branches. See [team workflow](TEAM_WORKFLOW.md).

### Phase 3 technical milestone and team workflow — 2026-09-16

Implemented configurable catalog, server quotes, saved agreements and an opt-in development payment sandbox. No real provider or commercial defaults were selected. D03–D06 remain unresolved; see [Phase 3](PHASE_3.md). The owner requested notification before any subscription/upgrade is needed and explicitly authorized pushing each completed major development change to GitHub for team access. This does not authorize purchases or production deployment.

### Supabase project selection — 2026-09-16

Owner explicitly selected `lmwvoniiykmfzuxigzqf` (hamsa1412's Project, Seoul) and authorized reading a local connection file. Implemented a dedicated backend database role and private `vedioos` schema through the authenticated connector after the supplied passwords were rejected. Existing Django authentication and private media storage remain in place; this decision connects PostgreSQL and does not approve a replacement auth or media service. See [Supabase setup](SUPABASE.md).

### Approved Day 1 sequencing and ownership — 2026-09-15

Source: owner's Day 1 instructions in this conversation. Person 1 is Hamsa (Client + Core Platform); Person 2 is Dheeraj (Admin + Editor Operations). The immediate scope and verification gate are recorded in [DAY_1.md](DAY_1.md). Complex assignment logic must wait until the Day 1 mandatory checks pass. The owner subsequently authorized implementing both people's work sequentially.

### D01/D02 — Day 1 technical implementation — 2026-09-15

Status: implemented technical choice within the authorized development scope. Django 5.2 with server-rendered templates, built-in password hashing/database sessions and CSRF; SQLite locally; PostgreSQL configuration available for production. Private media uses a replaceable Boto3 S3 adapter and real local SeaweedFS 4.47. MinIO was considered but its binary download returned HTTP 410; no MinIO dependency remains.

Local-only settings: 512 MiB per file, allowed type map in `upload_policy`, 900-second upload permission, 60-second download permission, single-object direct uploads with incremental SHA-256, versioned private bucket and conditional writes. These are development settings, not approved commercial terms. Production provider/region, quotas, scanning, retention, recovery, and link policy remain open. `subscriptions` names package-purchase records. Coin integer representation is an inactive schema foundation; monetary conversion and final precision remain undecided.

Rationale: deliver a complete local Day 1 flow without cloud credentials, an unavailable Docker daemon, or separate frontend/auth infrastructure. Verification: [Day 1 evidence](DAY_1_VERIFICATION.md). No existing paid orders required migration. Production choices still require the checks in [architecture](ARCHITECTURE.md).

- Human editors create deliverables externally; no automatic editing engine.
- Three roles: client, editor, authorized presenter/admin; initially two managers.
- Three configurable plans plus custom orders; monthly creator packages also in scope.
- Paid work only; client acceptance triggers earning credit.
- Original quality and private project access are mandatory.
- Persistent round-robin state per proficiency level and admin overrides are mandatory.
- 24-hour delivery is the stated target; detailed timing rules are pending.

These are requirements from the original brief, not newly selected implementation choices.

## How to record a decision

Add an entry rather than silently removing an unresolved question:

```text
Decision ID / title:
Status: proposed | approved | superseded
Date:
Owner / source of explicit decision:
Decision and exact configuration values, if applicable:
Reason and alternatives considered:
Affected requirements and files:
Effect on existing paid orders / migration:
Verification required:
Supersedes:
```

Only mark a business choice approved when supported by an explicit owner decision. Contributors can document routine technical choices within authorized scope, identifying them as implementation decisions. A proposal is not a production default.

## 2026-09-17 — Earnings implementation (D10 remains open)

Technical choice: use prospective fixed whole-coin awards as an optional admin-configured development rule. Snapshot them on new quotes, append a pending entry at client acceptance, and allow an administrator to release it once. Redemption reserves coins under a wallet lock and can be exercised only with an explicitly enabled DEBUG payout sandbox. The selected Supabase project retains a disabled policy with no configured amounts. No monetary conversion or real payout provider has been chosen; see [Phase 6](PHASE_6.md).

## 2026-09-17 — Review implementation (D11 remains open)

Technical choice within the authorized Phase 5 scope: serialize review with allocation, attribute each submitted version to its assignment, and persist one explicit acceptance per project. Keep historical file objects and release workload through terminal project status. Acceptance creates a pending-policy earning record; D10 coin amounts/splits remain unresolved.

Supported proposed D11 option `latest_request_v1` requires explicit admin selection for new quote snapshots: one request consumes one revision, only latest submissions can be accepted, acceptance completes the project, and additional revisions require another agreement. No production default or existing-order backfill was enabled. See [Phase 5](PHASE_5.md).
