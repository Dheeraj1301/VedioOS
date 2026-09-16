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
