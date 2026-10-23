# Open decisions and decision record

Do not substitute invented production values for these decisions. Development fixtures may use clearly labeled demo settings isolated from production. Resolve only the decisions needed for the current phase; unrelated open questions should not halt useful work.

Use the [owner decision checklist](OWNER_DECISION_CHECKLIST.md) to collect exact activation values or explicitly exclude a capability from the first release. Record approved answers in this file; never record credentials here.

## D18 — Administrator-managed landing page (2026-10-19)

Decision: preserve the approved public landing-page layout and link destinations while allowing administrators to edit every landing-page label, number, heading, paragraph, FAQ question and answer from a dedicated **Landing page** workspace screen. Dynamic plan names, prices, revision counts and features remain governed by the existing pricing catalog rather than duplicated in landing settings. The hero frame may be replaced with one validated MP4 (maximum 100 MB); it is stored in the existing private, versioned object store and rendered through a short-lived signed playback address with muted inline autoplay and looping. Removing or replacing the video returns the frame to its existing artwork and does not affect project media.

Only the admin role may change the singleton settings or upload/remove the hero video. Public visitors can request playback only for the currently published landing video; no permanent object URL or bucket access is exposed. Copy uses normal template escaping, and navigation destinations are not editable from this screen.

## Decision register

| ID | Decision needed | Resolve before |
| --- | --- | --- |
| D01 | App/backend/database stack, authentication, hosting, environments, deployment process | Phase 1 scaffolding |
| D02 | Storage provider/region, upload limits/types, integrity verification, scanning, retention/deletion/backups, download expiry/revocation | Phase 2 production media |
| D03 | Three plan names/prices/features, currency, duration/revision limits, priority, delivery terms | Real checkout |
| D04 | Custom base/service prices, unpriced Other requests, price changes during checkout | Real checkout |
| D05 | Payment gateway, payment methods, invoice fields, applicable tax handling, refunds/cancellation/disputes | Production payment |
| D06 | 24-hour clock start, delivery milestone, working/calendar hours, review/revision/call pauses, thresholds and overrides | Deadline activation |
| D07 | Editor approval/proficiency criteria and workload capacities; availability is now derived from non-terminal current assignments | Assignment activation |
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

Technical email choice, updated 2026-09-27: new client accounts remain inactive until a six digit email OTP confirms the registered address. Challenges are password-hashed in the private database, expire after ten minutes, are replaced on resend, have a sixty second resend cooldown and lock after five failed attempts. Resend responses do not reveal whether an account exists and also use the database-backed request rate limit. Verification is transactional and audit logged. Delivery uses Django's replaceable email backend with the console backend for local development; no production provider, sending domain, subscription or price has been approved. Existing active users remain active. The application continues to use Django identities rather than creating a second identity store in Supabase Auth.

Technical order-form choice: show all three fixed plan slots and a fourth custom option at draft creation, but allow selection only for active administrator-configured plans. Persist the selected plan/custom kind and custom creative direction. Monthly package records may be displayed when active, while purchase remains disabled until D13 is approved. Custom prices continue through the existing server-authoritative catalog and quote snapshot; no browser-supplied price or untrained model output is accepted.

Plan pricing-period update, 2026-09-29: the owner requested a **Per Reel / Monthly / Yearly** selector for each of the three fixed plan slots. Each plan now has separate optional administrator-managed minor-unit amounts for those periods; the existing amount is the per-reel value. Missing plan/period combinations display **Coming soon** and cannot be selected. The chosen period is saved on the draft order and included in the server-calculated quote snapshot, while Custom remains per-reel and unchanged. This does not approve any price values, recurring billing behavior, allowances, renewal, expiry, rollover or monthly-package sales; D03, D05 and D13 remain open for those production policies.

Client pricing-period lock, 2026-10-19: the owner locked Monthly and Yearly on the client new-order page until those offerings are ready. Per Reel is the only selectable/default period; the locked options remain visible with a lock and **Upcoming** feedback, and forged Monthly/Yearly submissions are rejected by the backend. The client-facing **Monthly creator plans / Recurring editing packages** block and its configuration placeholder are removed without changing the four plan/custom cards, custom brief, or Save and Proceed flow. Administrator pricing fields and existing persisted records remain intact; this UI decision does not activate or delete the deferred D13 package capability.

Plan-card interaction update, 2026-10-19: each available fixed-plan or Custom radio card can be selected and then deselected by activating the same card again. Deselecting returns the browser to no selection, hides Custom fields and disables Save and Proceed without reloading or clearing entered values or queued files. Re-selecting Custom restores the same browser-held inputs. The behavior is delegated by the shared `order_choice` field name, so it does not depend on plan IDs or names; backend required-choice validation remains unchanged.

Client project-status filter, 2026-10-19: My Projects keeps the database-backed status shown on every card and groups the complete status set for client filtering. Payment pending, payment completed and awaiting assignment are **Pending**; editor assigned, editing, uploaded draft/final, review and revision states are **Ongoing**; completed and cancelled retain their own groups. **All** is the default. Filtering is browser-local, immediate and non-navigating, with an announced result count and a dedicated no-match state.

Editor sign-in entry, 2026-09-30: the public **Editor Sign In** link now opens `/editor/signin/`, a dedicated entry screen backed by the existing shared authentication system. It accepts the administrator-issued editor ID or editor email, permits only editor-role accounts, and sends a successful login directly to the editor workspace. Client and administrator credentials remain on the regular sign-in route. This preserves the single shared user identity model and adds no separate credential store.

Derived editor availability, 2026-10-02: the owner replaced all manual editor availability choices with a single workload-derived state. Zero current assignments on non-terminal projects is **Available**; one or more is **Unavailable**. Completed and cancelled projects are excluded. The manual availability table and editor/admin status controls are removed, assignment eligibility and analytics use the same derived count, and editor screens refresh the status through an authenticated read-only endpoint. Workload capacity values remain configurable, but an active assignment makes the editor unavailable for another assignment under this rule.

Custom estimate implementation: administrator-managed custom services may have one unique stable mapping code for colour grading, quality enhancement, each duration band, or wording. The live estimate and final quote both resolve those mappings on the backend and fail closed when a required price is unpublished, incomplete, missing, or uses the wrong currency. Mapped items and the custom base are included in the accepted snapshot. No prices are seeded by migration and no model output affects money.

Monthly package preparation: administrators may save validated package drafts using the existing package records, but the form deliberately excludes publication. It also deactivates any legacy active record edited through this path. Purchase, renewal, quota use and dedicated-editor allocation remain unavailable until D13 supplies executable rules.

Notification delivery foundation: every in-app notice receives one durable external-delivery record. The default state is held and the worker is disabled. When explicitly enabled, a worker claims due rows with a lease, rechecks current recipient/project access, sends through Django's replaceable email backend, and records sent, retry or cancellation state without saving exception messages. Older held messages require an explicit release command. D12 still controls provider, templates, preferences and scheduling.

Client-support foundation, updated 2026-09-29: clients can open private support requests and optionally link only their own projects, but cannot post follow-up messages. Administrators alone can post shared replies and internal notes. A client sees only their original opening message and shared administrator replies; internal notes and any legacy client follow-ups remain hidden. Administrators see the full conversation and control status. Submission keys make creation and administrator replies retry-safe, notifications contain event summaries, and audit entries exclude message bodies. External support contacts and service obligations remain part of D14/D12.

Feature-control inventory: the admin workspace reports existing validated policy and environment states rather than adding a generic flag that could bypass business or security gates. Configuration links lead to the current commerce, assignment, earning and package-draft controls. Provider-backed payments, payouts, notifications, package sales and AI remain disabled or locked until their recorded decisions are resolved.

Payment-history foundation: clients see only their own provider records; administrators can reconcile all records. Both use stable newest-first cursor pages and server-owned status filters. Confirmed records retain protected receipt links, while sandbox labels and invoice-boundary copy prevent development records from being presented as revenue or tax invoices. D05 and D15 remain unresolved.

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

## 2026-10-04 — Admin project access through orders

Status: approved

Owner / source of explicit decision: Hamsa, admin dashboard change request.

Decision: remove the standalone Projects entry and Project Operations list from the admin dashboard. Keep the existing protected project-detail route unchanged because the admin Order detail page uses it for the **Open project** flow. Administrators access project details through Orders rather than a separate project roster.

Affected requirements and files: supersedes only the standalone admin Projects navigation/list portion of Day 1 D3; project authorization, detail content, Orders behavior, assignment operations, and client/editor project access remain unchanged.

Verification required: the admin sidebar omits Projects, `/admin/projects/` returns not found for an authenticated admin, and Order detail plus `/admin/projects/<project-id>/` continue to render for an authorized admin.

## 2026-10-06 — Human-readable admin price entry

Status: approved

Owner / source of explicit decision: Hamsa, admin pricing change request.

Decision: retain the existing multi-currency selector and integer minor-unit persistence, but present prices to administrators as actual currency amounts. Convert at the validated form boundary using the selected currency exponent; reject negative, non-numeric and over-precision values. Display monetary values with the selected currency symbol and exponent throughout the application. Existing stored values and accepted commercial snapshots are not rewritten.

Affected requirements and files: original brief configurability and pricing administration; Phase 3 catalog forms and shared money formatting. This changes no checkout, quote calculation, payment verification, client pricing-period toggle or database schema.

Verification required: INR/USD two-decimal and JPY whole-unit round trips, legacy-value rendering, invalid precision and negative input rejection, unchanged server-owned quote/payment minor-unit totals, and browser confirmation of the currency selector and dynamic symbol.

## 2026-10-06 — Remove consultation choices from the client brief

Status: approved

Owner / source of explicit decision: Hamsa, client new-order form change request.

Decision: remove the “Talk to an editor before editing” and “Talk to an editor after the draft” controls from client new-order and editable-draft forms. New client submissions no longer bind or populate either preference, including when those field names are forged in a request. Retain the existing database columns and historical consultation handling so previously recorded preferences and call records are not rewritten or dropped.

Affected requirements and files: client creative-brief UI and `ProjectForm`. Music preference, other instructions, uploads, save behavior and monthly-package presentation remain unchanged.

Verification required: both labels are absent, forged values remain false on a new project, Save and Proceed still creates the draft, and no migration is generated.

## 2026-10-06 — Supabase Auth owns client email OTP verification

Status: approved

Owner / source of explicit decision: Hamsa, request to use Supabase as the email authenticator while keeping all other application behavior unchanged.

Decision: delegate new client email OTP generation, delivery, resend throttling and validation to the selected Supabase Auth project. Keep the existing private BRIO user/profile records, passwords, Django application sessions, role authorization, editor-ID login and administrator login unchanged. Activate a matching inactive client only after Supabase Auth verifies the submitted code and returns the same normalized email. Do not persist returned Supabase access or refresh tokens. Retain the old challenge table without new writes; dropping it is outside this change.

Rationale: use the requested hosted verification service without redesigning every protected relation or changing established editor/admin authentication. Supabase Auth is an external verification boundary, not the source of application roles or project authorization.

Affected requirements and files: client registration, resend and verification endpoints; Supabase Auth project/template configuration; `core.email_verification`; environment settings and verification tests. No database migration or rewrite of existing users is required.

Verification required: mocked request/response and failure-path tests, client activation only for a matching verified email, no local challenge creation, unchanged login/logout and role isolation, hosted OTP template containing `{{ .Token }}`, custom SMTP delivery test, and live inbox confirmation.

## 2026-10-06 — Weighted custom quotation model

Status: approved scoring model; production price mapping remains unconfigured under D04

Owner / source of explicit decision: Hamsa, custom quotation-engine request and supplied seven-row score table.

Decision: support a deterministic server-side custom quotation model using Time 40%, Importance 20% and Editor Complexity 40%. Seed the approved feature scores: Colour grading 4/4/4, Quality enhancement 3/4/3, Duration 1/5/2, Font option 2/3/2, Song option 3/4/3, Overlays 4/4/4 and Beat sync 5/5/5. Add Overlays and Beat sync to the custom brief; the previously removed consultation choices remain excluded. Administrators may adjust the three weights, each feature's scores and multiplier, the existing custom base, price per complexity point, minimum, maximum and currency. The weights must total 100%.

The weighted engine stays disabled until the admin supplies approved base/per-point/min/max amounts. Until then the existing catalog-backed custom estimate remains the fallback. This records no production prices and does not resolve D04. A server-generated estimate snapshot is stored with each newly saved custom brief and is reused when its quote is created, so later score/weight/price changes do not rewrite that submitted estimate. The API and accepted quote identify the current implementation as `weighted_heuristic_v1`; no ML model is claimed because no approved historical effort/price dataset or evaluation threshold exists.

Affected requirements and files: original brief sections 4, 6, 8 and 33; Phase 3 custom estimates, admin pricing, project brief persistence and quote snapshots.

Verification required: all seven scores are seeded without prices, admin validation enforces score/weight/bound rules, client changes call the authenticated server endpoint, the same inputs/config return the same total, forged prices/fields are rejected, Overlays and Beat sync persist, and a saved snapshot survives later configuration changes.

Only mark a business choice approved when supported by an explicit owner decision. Contributors can document routine technical choices within authorized scope, identifying them as implementation decisions. A proposal is not a production default.

## 2026-10-09 — Razorpay selected for test checkout

Status: approved for test mode only; D05 remains open for production

Owner / source of explicit decision: Hamsa supplied a Razorpay test-key file and requested a Razorpay test payment wall.

Decision: add Razorpay Standard Checkout as a replaceable test-mode adapter. Create every Razorpay order on the backend from the accepted immutable BRIO quote; expose only the browser-safe test key ID; verify `order_id|payment_id` using the server secret; and fetch the Razorpay payment before recording confirmation. Require captured status and exact order, amount and currency matching. Label all resulting records and receipts as test payments and exclude them from production assignment eligibility. Keep test credentials in ignored environment configuration.

This decision does not authorize live keys, real charges, refunds, disputes, settlements, tax invoices or production launch. Those policies and provider-account requirements remain under D05.

## 2026-10-09 — Supabase Auth client password bridge

Status: approved implementation for shared client testing

Owner / source of explicit decision: Hamsa requested that confirmed users created in the selected Supabase Authentication user table be able to log in from any correctly connected BRIO preview and see the same shared application data.

Decision: retain Django sessions and the private `vedioos.users` authorization/profile identity, while accepting confirmed Supabase Auth email/password credentials for clients. After the local client-password check fails, the backend calls the selected project's password token endpoint, validates the returned short-lived token through `/auth/v1/user`, and discards all Supabase session tokens. It links the immutable Supabase Auth UUID to one application user. If no application user exists for that verified email, first login creates an active client user/profile with an unusable local password. Auth `user_metadata` never determines role or authorization. Existing editor/admin emails cannot use this bridge, and existing Django credentials remain supported during transition.

Owner clarification, 2026-10-09: existing manually created Supabase Auth users must use their configured email and password through the normal login page. A separate passwordless/email-code login route is outside this workflow and was removed. The application reports safe actionable provider states such as unconfirmed email or request throttling, while invalid email/password pairs remain generic. A successful first password login remains the only trigger that provisions and links these existing Auth identities to a client profile.

Migration `core.0014` adds the nullable unique Auth UUID link. This does not expose the private application schema to browser roles or replace backend role/project authorization. Future consolidation of public registration into Supabase password signup requires a separate migration plan for existing local-password clients and is not implied by this bridge.

Verification required: valid confirmed Auth login and first-login provisioning, immutable UUID linking, duplicate/race safety, invalid-password and provider-outage handling, admin/editor collision denial, token non-persistence, shared PostgreSQL migration/security checks, and unchanged existing login/role isolation.

## 2026-10-14 — One active application session per account

Status: approved and implemented for all BRIO roles

Owner / source of explicit decision: Hamsa requested that an account cannot remain logged in on two devices and that a second-device login receive a clear explanation and session-management choices.

Decision: retain the existing Django session system and store only the currently approved session key on the private application user. A second valid credential submission does not immediately take over the account. It presents two server-controlled choices: keep the existing device signed in, or continue on the new device. Continuing atomically designates the new session; the previous browser is signed out on its next request and receives an explanation. Pending takeover authorization expires after five minutes, invalid actions fail closed, logout clears only the matching active key, and session replacement is audit logged. No Supabase access or refresh token is persisted.

Verification required: the first device remains active when takeover is cancelled; the second device becomes active when replacement is selected; the previous browser is rejected and informed; direct replacement without a recent valid credential submission fails; APIs return an authenticated-session error; client, editor and admin login continue using the shared identity model.

## 2026-10-09 — Test-only quotation fallback

Status: approved for shared workflow testing only; D04 and D08 remain open for production

Owner / source of explicit decision: Hamsa requested that custom quotation always reach the test payment wall and asked for a calculation fallback when ML prediction is unavailable.

Decision: the existing seven-feature weighted heuristic remains the primary test quotation model because no labelled historical effort/price dataset or evaluation threshold exists for a defensible ML predictor. A persisted pricing context distinguishes `test` from `production`. The guarded `configure_test_quotation` command accepts explicit synthetic minor-unit amounts, enables the approved 40/20/40 score formula, and records test-only terms. Test quotations are visibly labelled and cannot be generated or accepted outside `DEBUG` with a test payment gateway. The release audit blocks any enabled quotation policy whose context is not `production`.

This fallback is deterministic and server-authoritative; it does not claim to be ML and never trusts a browser-provided total. Training a future model still requires an owner-approved dataset, prediction target, evaluation threshold, versioning and a human override policy under D08.

Market-reference update, 2026-10-09: published Indian short-form editing prices were reviewed before increasing the preview policy. Observed references ranged from ₹499 for a starter reel, ₹999 for a high-retention edit and ₹1,999+ for advanced motion work; another published rate card listed ₹300–₹800 for basic reels, ₹500–₹1,200 with captions/effects, ₹500–₹2,000 for professional colour grading and ₹1,500–₹5,000 for cinematic editing. Agency-oriented guidance placed a professional captioned/color-graded reel around ₹1,200–₹2,500, with broader single-reel freelancer/studio pricing extending toward ₹8,000. The shared preview therefore uses a ₹750 base, ₹150 per weighted point and a ₹1,000–₹8,000 clamp. With current scores, colour grading contributes ₹600; a normal 30–50 second edit with suggested music is ₹1,560; selecting every feature is ₹4,320. These remain provisional admin-managed rates, not an approved production rate card.

Research references: [Reelkraft Media 2026 India pricing guide](https://www.reelkraftmedia.com/blog/video-editing-cost-india-2026), [PurlyEdit published editing rates](https://www.purlyedit.in/editing_pricing), [Gigmate reel pricing](https://gigmate.in/reel-editing-service), and [Plumlet India reel pricing comparison](https://plumlet.app/reel-editing-charges-india).

Verification required: server-owned order amount, secret exclusion from HTML/logs/Git, cross-client denial, signature rejection, captured-payment matching, retry idempotency, test labeling, production-mode refusal, and an owner-network test transaction before production work continues.

## 2026-09-17 — Earnings implementation (D10 remains open)

Technical choice: use prospective fixed whole-coin awards as an optional admin-configured development rule. Snapshot them on new quotes, append a pending entry at client acceptance, and allow an administrator to release it once. Redemption reserves coins under a wallet lock and can be exercised only with an explicitly enabled DEBUG payout sandbox. The selected Supabase project retains a disabled policy with no configured amounts. No monetary conversion or real payout provider has been chosen; see [Phase 6](PHASE_6.md).

## 2026-09-17 — Review implementation (D11 remains open)

Technical choice within the authorized Phase 5 scope: serialize review with allocation, attribute each submitted version to its assignment, and persist one explicit acceptance per project. Keep historical file objects and release workload through terminal project status. Acceptance creates a pending-policy earning record; D10 coin amounts/splits remain unresolved.

Supported proposed D11 option `latest_request_v1` requires explicit admin selection for new quote snapshots: one request consumes one revision, only latest submissions can be accepted, acceptance completes the project, and additional revisions require another agreement. No production default or existing-order backfill was enabled. See [Phase 5](PHASE_5.md).

## 2026-10-15 — V1 draft timing and ongoing client visibility

Status: approved and implemented for paid assigned projects using existing order terms

Owner / source of explicit decision: Hamsa requested a required V1 submission after the specified initial editing hours, ongoing client access to V1, and a direct editor-dashboard V1 option.

Decision: the first client-visible deliverable must be uploaded as an edited draft and is labelled V1; a final-labelled upload cannot become version 1. When editing starts, the existing server-owned `delivery_hours` value in the accepted order snapshot is displayed as the V1 target measured from the attributable editing-start audit event. Missing timing terms remain explicit rather than receiving an invented default. V1 remains privately downloadable by the owning client and assigned editor while later editing or revision work continues. This does not change acceptance, revision allowances, payment gates, assignment access, or the unresolved working/calendar-hour and pause rules in D06.

Verification required: reject a final-labelled first submission; accept an edited draft as version 1; show its saved timing target to the assigned editor; keep V1 visible to the client during later revision work; expose the editor-dashboard V1 link; preserve role/project/file authorization.

## 2026-10-18 — Canonical custom quotation summary

Status: approved and implemented

Owner / source of explicit decision: owner request to restore the original project summary and payment navigation.

Decision: use the existing protected order-summary page as the single custom quotation summary before and after payment navigation. Keep the immutable saved breakdown, private-file list, payment action and additional terms on that page; remove the redundant saved-quotation banner and current-rate refresh action. Edit Details may reopen only an unpaid custom order. Saving revisions cancels pending payment sessions, clears the previously accepted order snapshot without deleting history, and creates a new server-owned immutable quote. Paid and cross-client edits remain denied.

Verification required: summary section order, persistent custom detail after payment starts, no refresh action or saved banner, functioning unpaid Edit Details, cancelled pending payment, preserved quote history, new quote from edited inputs, paid/cross-client denial and unchanged plan-order behavior.

## 2026-10-18 — Client payment-history discovery controls

Status: approved and implemented

Owner / source of explicit decision: owner request to simplify Payment History and add search and date filtering.

Decision: remove the customer-facing payment-status tab row while retaining status badges, protected status filtering for existing deep links, and the separate administrator reconciliation controls. Client Payment History provides server-side search by project/payment reference and date ranges for 5, 10, 30, 90 and 365 days. Version History is hidden while a project remains payment-pending, but preserved after payment when delivery and revisions are relevant.

## 2026-10-18 — Support intake and assignment confirmations

Status: support workflow approved and implemented; production email and financial policies remain open

Owner / source of explicit decision: owner request to remove the support Subject field, verify the client/team conversation, and confirm assignments and applicable responsibilities.

Decision: clients select a support category, optionally select one of their own projects, and enter the request message. The server derives the durable request title from the category and project so removing the free-form Subject field does not weaken admin queues, idempotency, audit evidence, or reconciliation. Administrators remain the only users who can send shared replies or internal notes, and clients continue to see only their opening message and shared administrator replies.

Every assignment creates separate durable confirmations for the client and assigned editor. The confirmation points each participant to the protected project workspace, where the immutable accepted service, delivery, cancellation/refund text and role responsibilities are visible. Each notification has an email-delivery record, but production email remains held until D12 supplies an approved provider, domain, templates, preferences and worker schedule.

D05 and D11 remain open. No cancellation deadline, refund amount, eligibility rule or processing promise was invented; those financial policies require the owner's exact approval record before real checkout or public terms can be activated.

## 2026-10-18 — Client and editor password recovery

Status: approved and implemented for active client and editor accounts

Owner / source of explicit decision: owner request for an email OTP password-recovery flow from both client and editor sign-in pages.

Decision: active clients and administrator-issued editors use the same existing three-step recovery pages: request an email, verify a six-digit OTP, then set and confirm a validated new password. Requests do not reveal whether an account exists. Supabase Auth sends and validates a recovery OTP for clients and an email-ownership OTP for editors; returned provider sessions are discarded and no provider token is retained in the Django session. After verification, the new password is written under a database lock to the authoritative private application identity, the previous application session is revoked, and the reset is audit logged. Once a client profile is linked to its immutable Supabase Auth UUID and has completed recovery, Supabase password fallback is disabled so an older provider password cannot bypass the new application password. A legacy unlinked client may still complete one verified Supabase login to establish that immutable link.

The editor and client entry screens link only to each other; the editor page does not advertise administrator sign-in, and the existing routes are reused without intermediate login pages. Production delivery requires the relevant Supabase templates to include the six-digit `{{ .Token }}` value and an approved custom SMTP provider/domain; the default sender is suitable only for limited development testing.

## 2026-10-19 — UI control preservation

Status: approved owner direction

Decision: visual redesigns may change color, layout, motion and placement, but must preserve the approved functional control inventory exactly once. Do not invent or duplicate buttons and links. The public authentication header shows only the useful alternate action, client/editor entry switching remains in the footer, the mobile workspace utility bar precedes the horizontally scrolling navigation, and payment-pending project detail shows its status only in the actionable next-step panel.

## 2026-10-22 — Supabase Auth is authoritative for linked email login

Status: approved and implemented

Owner / source of explicit decision: Hamsa requested that login use users from the selected Supabase Authentication table and that the delivered login not depend on a local-server URL.

Decision: when `SUPABASE_AUTH_PASSWORD_LOGIN_ENABLED` is enabled, an email identity that is a client or already carries a stored Supabase Auth UUID is verified by Supabase password authentication before a Django session is created. The verified email and immutable Auth UUID must match the private application identity. Existing linked roles are preserved and cannot be selected through Auth metadata; an unknown confirmed Auth identity can only be provisioned as a client. Administrator-issued editor IDs and unlinked privileged legacy identities retain their private application credentials. This supersedes the earlier transition behavior that tried the private client password first and rejected all existing privileged identities at the Supabase bridge.

No hosting provider was selected by this authentication decision. A public HTTPS URL requires an approved hosted runtime with production host, CSRF, cookie, secret, database, storage and email configuration; a loopback preview or tunnel does not satisfy that release requirement.

Verification required: confirmed linked client and linked administrator login, immutable UUID mismatch denial, unknown-user client-only provisioning, unlinked admin/editor takeover denial, provider outage/rate-limit handling, role isolation, session replacement and selected-project binding.

## 2026-10-23 — Separate configurable revision-plan catalog

Status: approved and implemented for display and selection

Owner / source of explicit decision: Hamsa requested three administrator-configured revision plans on a dedicated client Revisions page without changing the existing new-edit, quotation or payment flows.

Decision: store revision plans in three fixed slots separate from editing `plans`. Administrators can set each title, direct-currency amount, description and publication state under Plans / Pricing. Clients see only published slots and can select one card at a time or click the selected card again to clear the comparison. Selection is browser UI state only because this request does not define a revision purchase, project association, commercial snapshot, checkout or fulfillment workflow. No revision plan is seeded or published without owner-approved commercial values.

Verification required: three admin slots, major-to-minor currency conversion, published-only client visibility, client/admin role denial, exclusive selection, click-again deselection, mobile layout, unchanged editing-plan quotation and payment tests, and private-schema/RLS protection.

## 2026-10-23 — Administrator-managed landing-page FAQs

Status: approved and implemented

Owner / source of explicit decision: Hamsa requested a public Contact Us accordion and complete FAQ management in the existing Landing Page editor.

Decision: landing FAQs are an ordered list inside the existing singleton landing-page JSON configuration. Administrators can create, edit, delete, reorder, publish and unpublish entries; the public page renders only published entries using its existing native accordion pattern. Existing installations with the former four fixed question/answer keys are upgraded in memory and retain their edited copy, with a published Contact Us entry appended. The default Contact Us answer directs existing clients to the protected Support workspace and new visitors to account creation; administrators can replace it with approved email, form or phone details. FAQ content remains escaped plain text rather than administrator-authored HTML.

No schema migration is required because this extends the established JSON configuration contract. Verification required: default and legacy rendering, administrator-only access, persisted ordering and edits, delete/unpublish filtering, escaped output and unchanged non-FAQ landing content.

## 2026-10-23 — Direct fixed-plan checkout

Status: approved and implemented for the three standard plan slots

Owner / source of explicit decision: Hamsa requested a streamlined Plan 1/2/3 checkout while explicitly preserving the Customize Your Edit quotation workflow.

Decision: saving a standard-plan brief creates and accepts a server-owned immutable commercial snapshot from the selected active plan and its current administrator-configured per-reel price, then opens the order checkout directly. The fixed-plan checkout shows private project files and one Make Payment action; it does not display the quotation, price-estimate, payment-choice or terms-review sections. With Razorpay Test Mode configured, that action creates the provider order from the persisted integer-minor-unit snapshot and the gateway opens automatically on the secure checkout page. The server continues to verify signature, provider order, captured status, amount and currency before activating the project.

Custom orders retain their existing generated quotation, breakdown, explicit acceptance control, commercial terms, payment action and non-automatic Razorpay launch. No client-supplied price is accepted, and later catalog edits do not rewrite an already-saved fixed-plan agreement.

Later clarification: the fixed-plan checkout includes the owner-supplied preview Additional terms directly below Make Payment as visually secondary static copy. This narrow addition supersedes only the earlier decision to omit terms-review content from the fixed-plan page; it does not add an acceptance control or alter the custom checkout branch.

## 2026-10-23 — Checkout file removal before payment

Status: approved and implemented for fixed and custom orders

Owner / source of explicit decision: Hamsa requested removal controls for every uploaded checkout file across Plan 1/2/3 and Customize My Edit.

Decision: an owning client may remove a source, image, audio, reference, font-reference or asset file while both the project and payment remain pending, including after fixed-plan terms have been snapshotted or a payment attempt has started. Removal uses the existing protected API and durable `removed` state with an attributable audit event; the private storage object is not physically destroyed because retention and recovery policy remain unresolved. Removed records disappear from normal file queries immediately, free reference-upload capacity and cannot be downloaded. Paid projects, project versions, other clients and other roles remain denied. File removal does not recalculate or rewrite plan prices, custom quotations, accepted terms or pending payment amounts.
