# Development pathway

## How to use this pathway

The [Day 1 local foundation](DAY_1_VERIFICATION.md) is implemented and verified. Phases 0–2 have progressed through that milestone; their broader production/large-file gates are not all complete. [Phase 3](PHASE_3.md) has a verified catalog/quote/payment-sandbox milestone. [Phase 4](PHASE_4.md) has a verified allocation milestone. [Phase 5](PHASE_5.md) has a verified review milestone. [Phase 6](PHASE_6.md) has a verified opt-in coin/sandbox payout milestone. Real checkout, payout provider, deadline rules, allocation activation and AI still require decisions. Work in dependency order, delivering small complete flows.

**2026-10-19: landing-page content control implemented.** The existing landing layout now reads all visible copy from one admin-only settings screen, while live plan details continue to come from the established pricing catalog. Administrators can publish, replace or remove a validated private MP4 for the existing hero frame; public playback uses a short-lived signed address and loops muted inline. Role denial, escaped copy, preserved links, MP4 validation, private upload metadata and playback routing have isolated test coverage. Additive migration `core.0018` creates the singleton settings record without seeding or rewriting content.

### Immediate milestone: Day 1

Follow [the Day 1 ownership and task plan](DAY_1.md). Hamsa is Person 1 (Client + Core Platform); Dheeraj is Person 2 (Admin + Editor Operations). This milestone combines foundation/auth, private storage, core and operational migrations, and basic role-specific UI. Its mandatory verification gate must pass before complex assignment implementation. Schema scaffolding for later phases does not mark those phases complete.

**Local Day 1 gate: passed on 2026-09-15.** See [test results and limitations](DAY_1_VERIFICATION.md). Catalog/quote and allocation milestones subsequently progressed as recorded below. Production policy decisions remain open; retain the existing roadmap dependencies.

The first-version scope is all 28 priorities in original brief section 34, covered by Phases 1–7. Phase 8 completes broader business features from the brief. Phase 9 is the production gate and applies before any production launch, even if later features remain disabled.

## Phase 0 — Establish decisions and architecture

- Read the brief/rules and select the stack (D01).
- Define environments, integration boundaries, entity relationships, authorization matrix, state transitions, and configuration strategy.
- Choose initial implementation slices and record decisions; resolve upcoming phase blockers progressively.
- Add verified setup commands and an environment-variable example without secrets when scaffolding is introduced.

**Gate:** architecture is documented, the next phase's blocking choices are resolved, and no production business values are invented.

## Phase 1 — Foundation, accounts, and permissions

- Scaffold the application, database migrations, local setup, and appropriate checks.
- Implement client signup/login and editor applications; privileged onboarding for the initial admins.
- Implement admin approval/proficiency management, role checks, account lifecycle, dashboard shells, and audit foundation.

**Gate:** a client, approved editor, and admin can sign in; unauthorized role elevation and cross-role access fail on the backend. A pending editor cannot receive work.

## Phase 2 — Private media and client order drafts

- Implement private original uploads, progress/retry support, validation, checksums, authorized downloads, and separate derivatives.
- Build project/order draft ownership and inputs for source files, assets, reference explanations, requirements, song preferences, and consultation choices.
- Add responsive client ordering screens and clear incomplete/error states.

**Gate:** uploaded source bytes match downloaded bytes; derivative creation leaves originals unchanged. Other clients, unassigned editors, and anonymous requests cannot access files or metadata, including by guessing IDs. Limits and interrupted uploads are handled.

## Phase 3 — Catalog, quotes, payment, and paid projects

**2026-09-16: configuration, quotes and signed sandbox implemented and verified.** [Evidence and remaining blockers](PHASE_3.md). Production payment gate remains open pending D03–D06; no real checkout is enabled.

**2026-10-06: weighted custom quotation slice implemented.** Seven owner-scored brief features, admin-managed weights/multipliers/bounds, authenticated live estimates and submission-time quote snapshots are implemented. Production activation remains off until D04 supplies the base/per-point/min/max amounts; ML remains deferred pending an approved historical dataset and evaluation rule.

**2026-10-08: locked custom checkout handoff implemented.** Saving a custom brief now creates its immutable quote and redirects to a dedicated quotation/payment screen showing the saved configuration, breakdown, terms and total. The payment CTA reuses the existing transactional checkout adapter, blocks missing/invalid totals, and shows completed payments without offering a duplicate action. No real payment provider was added; the production payment gate remains open.

**2026-10-09: custom-order browser regression fixed and verified.** Empty plan slots no longer stop the Custom form JavaScript. Both checkout and editable-draft redirects retain queued private uploads, and checkout now previews uploaded file metadata with an Edit details action. Real Edge verification passed configured quote/payment-sandbox and unconfigured-pricing fallback paths; the isolated backend suite passed 243 tests with 10 optional integrations skipped. Shared Supabase pricing and real payments remain inactive until D04–D05 are approved.

**2026-10-09: Razorpay test checkout implemented.** The backend creates a Razorpay test order from the accepted quote, opens hosted Standard Checkout, verifies the returned HMAC, fetches captured status, and matches order, amount and currency before idempotent confirmation. Test payments and receipts remain labeled and are excluded from production assignment eligibility. D05 remains open for live credentials, webhook recovery, refunds/disputes, taxes and invoices.

**2026-10-09: guarded test quotation fallback implemented.** Shared-preview quotation failure was traced to the intentionally absent commerce policy. Pricing now has an explicit persisted test/production context, a guarded command accepts deliberate synthetic values for the existing 40/20/40 weighted model, immutable quote snapshots retain that context, and test quotations are visibly labelled and rejected outside the test gateway environment. Release readiness blocks test pricing. A genuine ML predictor remains deferred under D08 until labelled training data and evaluation criteria exist.

**2026-10-09: market-reference quotation calibration.** Published Indian reel, colour-grading, captions/effects and cinematic-editing price ranges informed a higher ₹1,000–₹8,000 preview band. The active weighted policy now uses a ₹750 base and ₹150 per point, yielding ₹600 for colour grading, ₹1,560 for a normal 30–50 second edit with suggested music, and ₹4,320 for all seven features. Client copy is commercially readable while retaining an accurate no-live-charge disclosure at checkout.

Unpaid custom orders can revise project details without mutating history. Pending payment sessions are cancelled, old accepted quotes remain auditable, and a new locked quotation/payment session is created; paid and cross-client requests fail closed.

**2026-10-09: shared preview and payment-path guard.** Client project details now expose the correct next action for incomplete briefs, saved custom quotations and plan orders, restoring a visible path from quotation to payment. The team launcher verifies the selected Supabase database, private schema, Auth project, security posture and migration state before starting; it refuses an isolated SQLite preview so account and project writes cannot be mistaken for shared data.

**2026-10-18: custom quotation summary navigation restored.** Custom briefs now return to the existing order-summary page, where the complete saved breakdown, private-file list, payment action and additional terms remain in their established order before and after payment navigation. The redundant saved-quotation banner and current-rate refresh action are removed. Edit Details safely reopens only unpaid custom orders, cancels pending payment sessions, preserves history and creates a new immutable quote from the revised brief.

**2026-10-18: client payment-history discovery simplified.** Customer-facing status tabs were replaced with protected server-side search and a date-filter dropdown covering 5, 10, 30, 90 and 365 days. Status badges and administrator reconciliation filters remain. Payment-pending project screens no longer show delivery version history before that workflow is relevant.

- Implement admin management of three plans and custom services with validated configuration.
- Build plan/custom selection, backend price calculation, term snapshots, payment adapter, verified payment events, invoices/history foundations, and unique paid projects.
- Show paid/unpaid queues in the presenter dashboard. Persist delivery timestamps under decided rules.

**Gate:** a payment failure cannot activate/assign a project; altered client totals are rejected. Verified payment activates exactly one project despite duplicate events. Existing order terms survive catalog edits. Real payment stays disabled until its settings/policies are ready.

## Phase 4 — Complexity, workload, and fair assignment

**2026-09-16: allocation milestone implemented and verified.** [Evidence](PHASE_4.md): capacity administration, admin complexity review, manual/reassignment, paid queues, persistent round robin, skip/wait and real PostgreSQL concurrency. Shared allocation remains off until policies are configured. AI classification is not integrated, so the full Phase 4 production gate remains open.

- Implement proficiency/capacity administration, derived availability and active counts, AI classification and admin overrides.
- Implement durable paid-project queues and separate round-robin pointers per level.
- Implement configured wait/skip behavior, manual assignment/reassignment, and deadline visibility.

**Gate:** E1 → E2 → E3 remains fair when E1 finishes early; restart preserves sequence. Concurrent workers cannot double-assign or exceed capacity. Unavailable editors follow policy. AI failure remains visible and recoverable. Former editors lose future project access; link-expiry behavior matches the documented policy.

## Phase 5 — Editor work, versions, review, and delivery

**Implementation gate passed 2026-09-17 with explicit synthetic review policy; production activation awaits owner-approved terms.** See [Phase 5 evidence](PHASE_5.md). Earnings remain pending Phase 6 policy.

- Build assigned-project detail with all source/reference/song/effect/notes/deadline information and original downloads.
- Implement external-edit workflow: upload draft, add client-visible note, submit review, receive revisions, upload new versions, designate final candidate.
- Implement client review, version-targeted revisions and acceptance, final download, project history, and guarded state transitions.

**Gate:** one real test project passes from paid assignment through draft → revision → revised version → client acceptance → final download. Another accepts the first draft. Prior versions survive and retain integrity. Editor submission alone cannot complete a project. Revision policy and access controls are enforced.

**2026-10-03: immediate deliverable availability verified.** A successfully verified editor draft/final upload is atomically recorded as the next immutable project version and becomes downloadable by the owning client without administrator action. Multiple uploads retain filenames, categories, timestamps and version order; rejected or disallowed completions create no client-visible entry. Existing private signed-download and project-access checks remain in force.

**2026-10-15: explicit V1 workflow added.** The first deliverable must be an edited draft, displays the accepted order's saved editing-hours target from the attributable editing-start event, remains available to the client while later work continues, and has a direct editor-dashboard link. No timing default or new commercial term was invented; D06 still governs calendar/working-hour and pause details.

## Phase 6 — Earnings and payout administration

**Development flow verified 2026-09-17; production activation and database-level ledger immutability remain open.** See [Phase 6 evidence](PHASE_6.md). The connected project's coin settings remain disabled.

- Implement earning-rule snapshots, pending/earned/redeemable states, immutable coin ledger, and exactly-once acceptance credit.
- Add editor wallet totals/history and redemption request workflow with admin processing and payout outcome records.

**Gate:** repeat acceptance cannot credit twice; parallel redemptions cannot overspend; failed payouts reconcile without losing balance. Reassignment/cancellation effects match recorded policy. Real conversion/redemption stays disabled until terms and provider are configured.

## Phase 7 — First-version operations and notifications

**2026-09-18: first operations slice verified; full gate remains open.** Admin queues, paid consultation tracking, in-app notices and recorded-deadline alerts are documented in [Phase 7 evidence](PHASE_7.md).

**2026-09-18: project communication slice verified.** Shared messages and internal notes now have backend project/role checks, recipient-scoped notices and audit metadata. The full Phase 7 gate remains open; see [Phase 7 evidence](PHASE_7.md).

**2026-09-18: mobile browser flow and 28-priority audit recorded.** Synthetic direct upload and original-byte download pass at 390px/320px. [Traceability](FIRST_VERSION_TRACEABILITY.md) shows why the full gate remains open.

**2026-09-18: protected message history pagination verified.** Project conversation pages now expose older history without leaking internal notes or former-editor access. The full gate remains open; see [Phase 7 evidence](PHASE_7.md).

**2026-09-18: admin audit timeline and read/overdue audit events verified.** Sensitive event details stay out of the UI; the full gate remains open. See [Phase 7 evidence](PHASE_7.md).

**2026-09-18: protected notification history verified.** Recipients can page through older notices; current project access still controls each page and read action after editor reassignment. See [Phase 7 evidence](PHASE_7.md).

**2026-10-17: notification center and admin publishing implemented.** Authenticated workspaces use a global bell/dropdown and detailed notice pages; admins can manage targeted, persistent campaigns with private poster attachments and read counts. See [Phase 7 evidence](PHASE_7.md).

**2026-09-19: lifecycle audit inventory completed.** Initial editing and requested-revision starts now join the existing attributable lifecycle audit trail and repeated starts do not duplicate events. The full gate remains open; see [Phase 7 evidence](PHASE_7.md).

**2026-09-19: safe error recovery verified.** Browser and API permission, missing-resource and server-error responses provide actionable recovery without rendering private exception details. The full gate remains open; see [Phase 7 evidence](PHASE_7.md).

**2026-09-19: automated accessibility baseline verified.** Project workflows now provide keyboard skip navigation, live progress/error announcements, distinct download names and retryable rejected uploads. A manual assistive-technology audit remains before launch; see [Phase 7 evidence](PHASE_7.md).

**2026-10-03: editor-roster search, sorting and focused detail verified.** Admin Editors supports case-insensitive partial name, email and editor-ID search with a 250 ms debounced URL-backed query, six mutually exclusive sort choices, combined search/sort state, reset controls and a dedicated no-match state. Roster cards now retain only the linked editor name/current proficiency and unchanged inline approval controls; protected editor detail pages hold profile, portfolio, availability and workload information. Existing approval, capacity and assignment behavior remains unchanged.

- Finish client/editor/admin status dashboards, unassigned/active/review/revision/completed queues, and deadline alerts.
- Add durable role-scoped event notifications and retry handling.
- Complete audit coverage and first-version project communication; support consultation request tracking without requiring built-in video calling.
- Verify mobile client uploads, accessible forms, permission states, loading/error recovery, and responsive dashboards.

**Gate:** all 28 section-34 priorities pass the traceability checklist below. Admins can operate the full lifecycle; notifications are accurate and contain no unauthorized data. No required first-version feature is represented only by a mock.

## Phase 8 — Broader commercial features

**2026-09-24: operational analytics, client/order/project operations, client support, feature-control inventory and protected payment history verified.** Admin tools reconcile operational counts, per-client work/payment/support status, order and project workflow, deadline queues and payment records, provide a private audited support workflow, and show actual platform-control state. Undefined financial metrics, tax invoices, package sales and AI remain locked pending their owner decisions; see [Phase 8 evidence](PHASE_8.md).

**2026-10-19: recurring pricing remains client-locked.** Monthly and Yearly pricing periods are visible only as locked **Upcoming** controls on the new-order page, forged selection is rejected, and the client-facing recurring-package sections are removed. Per Reel and the existing four-card/custom-order flow remain unchanged; D13 still gates recurring package sales.

- Complete premium landing-page content and approved public claims, support workflows, call scheduling/completion, and optional calling-provider integration.
- Build configurable monthly influencer packages, purchases, allowance accounting, dedicated-editor behavior, and renewal/expiry handling.
- Finish advanced analytics, feature administration, payment/invoice history, and customer retention reporting.

**Gate:** package purchase/use/limits are verified; dedicated-editor behavior follows allocation policy; calls can be managed; analytics reconcile against underlying records. Features offered publicly can actually be fulfilled.

## Phase 9 — Production readiness

**2026-09-26: configuration-audit, deployment-health, account/session, assignment-state, delivery/review, communication/support, audit-history, notification-outbox, commerce and earnings reconciliation, snapshot-integrity, isolated row-restore, PostgreSQL privilege inventory, private-storage inventory/reconciliation, workflow reconciliation, continuous-verification and local browser-lifecycle foundations verified.** Role/profile/session relationships, allocation queues/capacity/rotation, version/revision/acceptance history, project/support audience boundaries, sensitive lifecycle audit coverage, durable notification states, quote/order/payment/call relationships and editor coin/redemption ledgers pass aggregate audits, private snapshots pass a disposable 46-table restore, the constrained runtime role and private grants pass a repeatable audit, synthetic bytes pass a versioned/private storage round trip, every bucket version is accounted for, ready files reconcile to exact private objects, and payment-to-acceptance records pass aggregate consistency checks. CI and five isolated Edge suites cover the remaining local workflows. D03-D05 real commerce policy/provider choices, D07-D11 allocation/AI/earnings/review policy, D12 notification-provider operations, D16 account/audit retention policy, full provider-owned role/extension/trigger restore, media restore and production-provider exercises remain open. The current development environment intentionally fails the release audit; no deployment is authorized. See [Phase 9 evidence](PHASE_9.md).

**2026-09-27: shared Supabase preview binding and client email OTP verified.** Team previews can require the selected project/private schema at startup and verify it with a secret-safe command. Six digit challenges persist as hashes in Supabase and the connected rollback test covers registration, activation, login and authorization. Migration `core.0008` is live with 47 protected tables. Real inbox delivery remains gated on D12's SMTP provider and verified sender decision.

**2026-10-06: client email OTP delegated to Supabase Auth.** Supabase Auth now owns generation, delivery, resend throttling and validation of the client email OTP. BRIO retains its private application identity/profile and existing session/role behavior, activating the local client only after the returned Auth user email matches. The old challenge table remains dormant and no schema migration is required. Hosted Auth email-template and custom-SMTP configuration remain required for reliable inbox delivery.

**2026-10-09: confirmed Supabase Auth clients can use shared login.** The server now verifies Supabase email/password credentials, validates the returned session against the Auth user endpoint, links the immutable Auth UUID and provisions a client application profile on first login. Tokens are discarded, editable metadata is ignored for roles, and existing admin/editor identities are protected from takeover. Migration `core.0014` stores the unique link; every correctly bound preview reads the same client projects from the private Supabase PostgreSQL schema.

**2026-10-14: verification feedback and single-session control implemented.** The email-code screen now exposes OTP, resend, cooldown, failure and success states in an accessible focused flow. Migration `core.0015` records the one approved Django session key per account. A second valid login must explicitly keep the existing device or replace it; replacement is audited and the previous browser receives a clear signed-out explanation on its next request.

- Verify complete client → payment → assignment → editor → revision/acceptance → final download → earnings flow in the intended environment.
- Check authorization for every role and project resource, original-file integrity, concurrency, event replay, and large-file interruption/recovery.
- Verify required settings, real integration credentials, backups/restore, monitoring, reconciliation, support ownership, and deployment/recovery instructions.
- Exercise representative mobile/desktop flows and operational deadline handling. Set concrete load/file-size targets from decided policies and test against them.

**Gate:** relevant phases have recorded evidence; no unresolved launch-blocking decisions remain; production integrations work; recovery is documented and exercised; release scope and disabled features are accurately described. Obtain deployment authorization when it has not already been provided.

## First-version traceability — original brief section 34

| Priority | Required capability | Phase |
| --- | --- | --- |
| 1 | Client registration/login | 1 |
| 2 | Client video upload | 2 |
| 3 | Editing requirement selection | 2 |
| 4 | Inspiration upload | 2 |
| 5 | Song selection | 2 |
| 6 | Plan selection | 3 |
| 7 | Custom pricing | 3 |
| 8 | Payment flow | 3 |
| 9 | Project creation | 3 |
| 10 | Presenter/admin dashboard | 1, 3, 7 |
| 11 | Editor registration | 1 |
| 12 | Editor proficiency management | 1, 4 |
| 13 | Editor dashboard | 1, 5, 7 |
| 14 | AI complexity classification | 4 |
| 15 | Intelligent assignment | 4 |
| 16 | Round-robin assignment | 4 |
| 17 | Editor availability | 4 |
| 18 | Editor file upload | 5 |
| 19 | Client review | 5 |
| 20 | Revision requests | 5 |
| 21 | Final approval | 5 |
| 22 | Editor coin system | 6 |
| 23 | Status tracking | 3–7 |
| 24 | Notifications | 7 |
| 25 | 24-hour deadline tracking | 3, 4, 7 |
| 26 | Secure project-level file access | 1, 2, 5 |
| 27 | Original quality preservation | 2, 5 |
| 28 | File/version history | 2, 5 |

## Full-brief coverage

| Original sections | Coverage |
| --- | --- |
| 1–2, 32, 34–35: concept, roles, priorities, principles | README, AGENTS, rules; Phases 0–9 |
| 3, 30–31: landing page and responsive design | Rules §2; Phases 2, 7–8 |
| 4–8: uploads, references, songs, plans, custom orders | Rules §4; Phases 2–3 |
| 9–12: payment, statuses, delivery, assignment | Rules §§5–8; Phases 3–5, 7 |
| 13–17: AI, editor approval, allocation, workload | Rules §§3, 8; Phases 1, 4 |
| 18–19: review, revision, consultation | Rules §10; Phases 5, 7–8 |
| 20: influencer packages | Rules §13; Phase 8 |
| 21–24: media, quality, privacy, security | Rules §9; Phases 2, 5, 9 |
| 25–26: notifications and analytics | Rules §12; Phases 7–8 |
| 27–29: data, security, audit | Rules §§3, 12, 14; Phases 1–9 |
| 33: configurable decisions | Rules §4, decision register; all phases |

## Change completion checklist

- [ ] Requested behavior and relevant brief sections are identified.
- [ ] Backend permissions and business invariants hold.
- [ ] Persistence, failure, retry, and concurrency cases are handled where relevant.
- [ ] User-visible loading, empty, success, and error states work.
- [ ] Relevant checks passed and results are recorded honestly.
- [ ] No secrets, public private-media links, or invented production settings were introduced.
- [ ] Documentation and phase evidence reflect actual implementation.

### Phase evidence template

```text
Phase / status: not started | in progress | blocked | complete
Implemented behavior:
Files / commits:
Decisions resolved:
Checks run and results:
Unverified items / blockers:
Next task:
```

### 2026-10-08 custom-brief upload handoff evidence

The browser now accepts the locked custom-checkout redirect as a valid saved-project destination, uploads selected originals and references against that project, verifies their persisted file metadata, and then continues to the quotation. This code-only fix requires no database migration; connected-environment storage verification remains dependent on valid private database and storage configuration.

### 2026-10-14 client project communication evidence

Client communication moved from project detail to dedicated list and project-scoped routes. The list is grouped into Ongoing and Completed history, and completed/cancelled projects are read-only in both the interface and transactional message service. The existing database-backed message model and project-ownership boundary are unchanged. Eleven focused tests and the full isolated suite (263 passing, 10 optional integration tests skipped) pass, along with Ruff, Django checks and migration drift checks. No schema migration is required.

### 2026-10-14 custom-form reliability evidence

Custom briefs now persist a validated inspiration URL, retain bound values and font choices on invalid submissions, focus the first invalid field, expose audited per-file removal for editable unpaid briefs, and enforce the three-reference cap against ready plus active pending files. Direct uploads retry transient PUT/verification failures and retain the remaining queue behind an explicit Retry action without duplicating completed files. The opt-in Edge recovery test passes with two forced connection failures, three-of-four selection enforcement and persisted-file removal. Additive migration `core.0015` is applied to the selected private Supabase schema after a verified 47-table/474-row ignored snapshot; RLS and browser-role isolation remain intact.

### 2026-10-18 payment-history responsive evidence

The client payment-history search and date-range controls now use a dedicated responsive layout. The expanded date menu remains inside the containing panel on desktop and stacks at full width on narrow screens, and the stylesheet cache key ensures the corrected layout replaces older cached CSS. The Edge lifecycle check asserts that the menu is visibly expanded and not clipped, captures desktop/mobile payment-history and quotation-summary views, verifies no horizontal page overflow, and completes the private upload/download integrity and role-isolation journey. No database migration is required.

### 2026-10-18 support and confirmation evidence

The client support form no longer asks for a separate Subject; the server derives a stable category/project title and preserves the existing private, retry-safe and audited workflow. Focused tests verify client ownership, cross-client denial, administrator queue visibility, shared replies, hidden internal notes, status controls and notification creation. The Edge lifecycle now opens a client request, confirms the administrator can find and reply to it, and confirms that the reply appears to the client with no page errors. Assignment notifications now state the confirmation and direct clients/editors to saved terms and responsibilities in the protected project workspace. External email delivery and cancellation/refund policy activation remain blocked by unresolved D12 and D05/D11 owner decisions; no production policy was fabricated.

### 2026-10-19 custom-form validation-state evidence

Failed custom-brief validation now stays on the live form whenever private files are queued, preserving the browser-held source, inspiration and font-reference selections together with every scalar field and the expanded wording/font controls. The first missing required field receives an inline error, error styling, scroll and focus. A persisted `Revisions needed` preference (`1-2`, `3-4`, or `5+`) appears immediately after Music preference and is carried through invalid and successful submissions without changing quotation calculation or checkout navigation. The 297-test isolated suite passes with 13 optional integrations skipped, and the opt-in Edge/private-storage recovery check passes retained upload queues, dynamic-section state, focus, retry and removal behavior. Additive migration `core.0017` is applied to the selected private Supabase schema after a verified 48-table/496-row ignored snapshot; all 48 tables retain RLS and the application schema, tables, sequences and routines retain zero public/browser-role grants.

### 2026-10-18 client and editor password-recovery evidence

Both existing sign-in pages now use the same three existing recovery steps with non-enumerating request responses, six-digit Supabase OTP verification, a ten-minute application reset grant, standard password validation, confirmation matching, previous-session revocation and attributable role-specific audit events. Provider access and refresh tokens are discarded; after a verified reset, the private application password is authoritative for an already-linked profile and an older provider password cannot bypass it. A legacy unlinked client may complete one verified provider login to establish its immutable Supabase UUID. Focused tests cover client and editor completion, unknown emails, invalid/expired/locked codes, correct OTP types, weak passwords, grant expiry, old-session invalidation, cross-links, legacy identity linking, linked old-provider-password denial and successful login with the new password. The editor entry advertises only client sign-in, while the client entry advertises editor sign-in. No extra authentication routes or database migration are required; production sending still requires the documented Supabase templates and approved SMTP configuration.

### 2026-10-19 authentication and mobile workspace UI evidence

Redundant in-card client/editor switching and login subtitles were removed while the existing footer destinations remain. Login and registration headers now expose only their alternate action. On narrow screens, the existing back/notification/logout bar appears directly below the logo and above workspace navigation. Payment-pending project detail retains one status badge in the next-step panel. Focused response tests and manual narrow-viewport checks verify the requested control count, ordering and retained destinations without backend changes.

### 2026-10-22 Supabase-authoritative email login evidence

With Supabase password login enabled, linked client and administrator email identities now authenticate against the selected Supabase Auth project and must match their stored immutable Auth UUID before the application creates its server-side session. Unknown confirmed identities remain client-only, editable Auth metadata cannot select a role, and unlinked privileged identities cannot be claimed. Editor-ID login and legacy privileged credentials remain available through the existing private identity path. The full isolated suite passes (316 tests, 13 optional integrations skipped), and the live shared preflight confirms project `lmwvoniiykmfzuxigzqf`, private schema `vedioos`, current migrations, 49 RLS-enabled tables and no browser-role schema access. No database migration is required. A non-local login URL remains a deployment task because no hosted BRIO project or production runtime configuration currently exists.

### 2026-10-22 standard-plan upload evidence

All three fixed-plan selections now expose their own source and inspiration upload controls and pass selected originals through the existing private, verified project-file workflow before proceeding. The browser rejects files beyond the three-reference limit, retains accepted selections while a plan is deselected or changed, and hides the controls when no plan is selected. The backend's existing serialized three-reference cap remains authoritative. The Custom form and its upload controls are unchanged. The full isolated suite passes 317 tests with 13 optional integrations skipped, and the opt-in Edge plan-toggle regression passes. No schema migration is required.

### 2026-10-22 published-plan reconciliation evidence

The three complete Supabase plan rows had the configured ₹399.00, ₹799.00 and ₹1,499.00 per-reel prices but stale `active = false` publication flags, which was the direct cause of the disabled client cards. Following a private 49-table snapshot, only those three owner-confirmed flags were transactionally corrected and audit recorded. A live Supabase-backed form check returns all three plans as selectable client choices. No client query, Admin UI, Custom flow, Monthly/Yearly toggle, schema or migration changed.

### 2026-10-22 admin-sidebar evidence

Calls, Notifications and Audit were removed only from the Admin workspace navigation inventory. The remaining entries preserve their prior order and rendering, the top-bar notification bell is untouched, and all three protected operational routes continue to load directly for administrators. The full isolated suite passes 318 tests with 13 optional integrations skipped. No schema or Supabase change is required.

### 2026-10-22 editor communication evidence

The Editor sidebar now links to a dedicated Project Communication list instead of Calls. Existing payment, approval and current-assignment authorization filters the Ongoing and Completed groups; direct list, detail and reply requests deny other-editor, unassigned, unpaid and former assignments. Editor replies use the existing durable shared-message service and appear immediately in the unchanged client conversation. Completed projects expose read-only history and reject backend writes. The full isolated suite passes 323 tests with 13 optional integrations skipped. No schema or Supabase migration is required.

### 2026-10-23 BRIO brand migration evidence

All user-facing `VedioOS` casing variants were replaced with `BRIO` across public and authenticated navigation, page titles, account and support copy, email content, notification delivery, checkout presentation, operator messages, configuration examples and maintained documentation. A case-insensitive repository audit found only compatibility identifiers that must remain stable: the Django `vedioos` package/import path, private Supabase schema and database role, existing storage bucket/probe prefixes, test assertions for those contracts, and the current GitHub repository URL. No database table, column, schema, migration, storage object or repository path was renamed. The full isolated suite passes 330 tests with 13 optional integrations skipped. Focused rendering tests cover the landing, registration, client/editor login and authenticated client workspace surfaces; a live Playwright/Edge smoke check confirms the landing page, page title, login and authenticated sidebar with no visible legacy brand or browser page errors. No database migration is required.

### 2026-10-23 configurable revision-plan evidence

Clients now have a protected Revisions sidebar destination that renders only published entries from a separate three-slot revision-plan catalog. Cards support keyboard-accessible exclusive selection and click-again deselection without mutating an order. Administrators configure each slot under Plans / Pricing with title, direct-currency price, description and publication state; saved changes are read directly on the next client request. The existing editing-plan model, new-edit form, quotation calculation and payment routes are unchanged. The full isolated suite passes 336 tests with 14 optional integrations skipped, and the opt-in Microsoft Edge test passes the three-card select, switch and deselect flow. Additive migration `core.0019` was applied to project `lmwvoniiykmfzuxigzqf` after ignored private snapshot `database-snapshot-20261023T055648604902Z.json`. The private schema has 50 RLS-enabled tables, zero public/browser grants, and no pending migrations; the revision catalog has zero rows until approved values are entered and published.

### 2026-10-23 landing FAQ management evidence

The public landing page now includes a published Contact Us entry in the existing accessible details/summary accordion. The Admin Landing Page editor manages FAQs as a persisted ordered list with create, edit, delete, move-up, move-down and publication controls; changes are visible on the next public request. Legacy saved edits to the former four fixed FAQ fields remain visible and gain the new default contact entry until the administrator next saves the page. Content is length-validated and HTML-escaped. The focused 10-test landing suite and full isolated suite (338 tests, 14 optional integrations skipped) pass, along with Django checks, migration drift, Ruff and JavaScript syntax checks. This uses the existing singleton JSON settings record, so no schema migration or Supabase synchronization is required.

### 2026-10-23 direct fixed-plan checkout evidence

Plan 1/2/3 briefs now persist and accept their server-calculated catalog snapshot during Save and Proceed, then route directly to an order page containing Project Files and one Make Payment action. The fixed-plan page omits quotation, estimate, payment-choice and package-change controls. Razorpay receives the immutable plan amount and currency from the backend-created order and its hosted checkout opens automatically; existing capture verification remains authoritative before payment/project status changes. Customize Your Edit retains its prior quotation, breakdown, explicit terms acceptance and payment behavior. Focused commerce/foundation coverage (86 tests) and the full isolated suite (339 tests, 14 optional integrations skipped) pass; coverage verifies fixed-price persistence, uploaded-file display, UI exclusions, exact Razorpay amount, automatic launch marker and the unchanged custom branch. Django checks, migration drift, Ruff and JavaScript syntax checks also pass. No model or database migration is required.

The fixed-plan page now also places the four explicitly supplied preview Additional terms blocks immediately below Make Payment in a muted bordered panel. Template regression coverage asserts the exact text, its placement after the CTA, and its absence from the Customize Your Edit branch. The payment action and backend settlement path are unchanged.

### 2026-10-23 checkout file-removal evidence

Fixed-plan and Customize My Edit checkout file rows now expose a confirmed Remove action for the owning client while payment is pending. Successful removal updates the page without navigation, shows an empty state when the final row is removed, persists the existing audited soft-deletion state and leaves Make Payment operational with the same server-owned amount. Backend authorization rejects non-owners, paid projects, versioned deliverables and unsupported file categories. Focused commerce/foundation coverage (86 tests) and the full isolated suite (339 tests, 14 optional integrations skipped) pass, verifying both checkout branches, persistence, audit attribution and continued checkout. Django checks, migration drift, Ruff and JavaScript syntax checks also pass. No model or database migration is required.

Follow-up hardening now deletes all versions and delete markers for the exact private object before retaining only the audited removed metadata tombstone. A storage-provider failure returns a specific 503 response and keeps the file active so the UI can retry without creating a broken metadata reference. Edit Brief and both checkout branches remove their row immediately after a successful JSON response; non-JSON server failures now report the HTTP status instead of the former generic request message. Focused coverage verifies exact-key deletion and unchanged state on a synthetic provider failure. No schema migration is required.

### 2026-10-23 standard-plan Creative Brief editing evidence

Plan 1/2/3 now show an optional Song preference / name directly after Project name. The fixed-plan checkout displays a Creative Brief with an Edit destination; reopening it restores the selected plan, project title, song preference and existing private files, and saving returns to checkout with a newly server-calculated fixed-plan snapshot. Paid/non-pending projects remain protected. Customize My Edit retains its existing form, fields, layout, quotation and checkout branch. Focused coverage passes 50 tests and the full isolated suite passes 339 tests with 14 optional integrations skipped; Django checks, migration drift, Ruff, JavaScript syntax and whitespace checks also pass. The change reuses the existing project song-information field and requires no schema migration or Supabase synchronization.

### 2026-10-23 hidden in-form custom estimate evidence

The Customize Your Edit form no longer renders the green Estimated price summary, so its option controls move directly beneath the description. The protected estimate endpoint and server-side Save and Proceed calculation remain intact, while checkout continues to show the persisted quotation amount, breakdown and existing payment controls. Focused quote-handoff coverage passes, and the full isolated suite passes 339 tests with 14 optional integrations skipped; Django checks, migration drift, Ruff, JavaScript syntax and whitespace checks also pass. No schema migration or Supabase synchronization is required.

### 2026-10-23 zero-revision custom brief evidence

The Revisions needed dropdown now starts with `0`, followed by the existing `1-2`, `3-4` and `5+` options. Server validation accepts and persists `0`, and Save and Proceed still produces the existing server-calculated custom quotation and checkout handoff. The quotation engine does not price this brief-metadata field. The full isolated suite passes 339 tests with 14 optional integrations skipped, and static/Django checks pass. Metadata-only migration `core.0020` was applied to project `lmwvoniiykmfzuxigzqf` after verified ignored snapshot `database-snapshot-20261023T110748812644Z.json` and a successful 50-table/681-row restore rehearsal. All 50 private tables retain RLS, browser/public grants remain zero, the security audit passes and no migrations are pending.

### 2026-10-23 custom revision-pricing evidence

Plans / Pricing now exposes direct-currency configuration for the `0`, `1-2`, `3-4` and `5+` custom revision tiers. Saving any tier requires all four, while an entirely blank configuration preserves existing quotes until approved rates are entered. The protected quote endpoint accepts the selected tier, and the server adds its configured amount after the unchanged feature estimate before snapshotting the total and checkout breakdown. The hidden in-form estimate remains hidden. Coverage verifies a configured zero tier, increasing paid tiers, major-to-minor conversion, API output, Save and Proceed persistence and checkout display. The full isolated suite passes 340 tests with 14 optional integrations skipped; Django, Ruff, migration-drift, JavaScript and whitespace checks pass. Additive migration `core.0021` was applied to project `lmwvoniiykmfzuxigzqf` after verified ignored snapshot `database-snapshot-20261023T111833176607Z.json` and a successful 50-table/685-row restore rehearsal. All 50 private tables retain RLS, browser/public grants remain zero, and no migrations are pending. No commercial values were seeded; administrators must enter and save all four rates.

### 2026-10-23 supplied logo evidence

The supplied orange BRIO image now replaces the generated green `B` mark in the shared public header and authenticated workspace shell, covering the landing page, login/registration and client/admin/editor dashboards. The same asset is the browser favicon. The BRIO wordmark, navigation inventory and sidebar width are unchanged; a fixed object-fit container preserves image proportions. Rendering coverage verifies the asset URL and alt text across public/auth pages and an authenticated workspace. The supplied and repository asset hashes match. The full isolated suite passes 340 tests with 14 optional integrations skipped; Django, Ruff, migration-drift, JavaScript and whitespace checks pass. This is a static-only change with no database or Supabase migration.

### 2026-10-23 project-message digit restriction evidence

Client message and Editor reply controls now reject any edit or paste that would produce six consecutive digits, keep the last valid text, show the required warning and red invalid state, and prevent invalid submission. The shared backend service independently rejects bypassed Client/Editor shared messages with HTTP 400 before persistence, notifications or audit creation. Five-digit groups and separated examples such as `12345 67890` and `123-456` remain valid. Focused Client/Editor communication coverage passes 12 tests, and the full isolated suite passes 342 tests with 14 optional integrations skipped; Django, Ruff, migration-drift, JavaScript and whitespace checks pass. The restriction does not apply to support or private internal notes. No schema migration or Supabase synchronization is required.

### 2026-10-23 simplified Admin Analytics evidence

The Admin Analytics page no longer renders the Consultations card or the Metrics awaiting policy placeholder. Its responsive grid automatically reflows the remaining operational cards without reserved gaps; all other analytics metrics, backend counts and protected destination pages remain unchanged. Regression coverage verifies the removed labels are absent while Editor capacity, Payout requests and Email delivery outbox remain visible. The focused analytics tests and full isolated suite (342 tests, 14 optional integrations skipped) pass, along with Django, migration-drift, Ruff, JavaScript syntax and whitespace checks. This presentation-only change requires no database migration or Supabase synchronization.

### 2026-10-23 pending-only Admin Orders evidence

Admin Orders now renders Pending as its sole payment-state tab and uses Pending for an unfiltered page request. Search, workflow selection, pagination, order cards and protected backend reconciliation filters remain unchanged. Regression coverage verifies the default summary and pending results, the absence of All/Confirmed/Failed/Refunded from the tab row, and preservation of explicit server-side filtering. The focused five-test order roster suite and full isolated suite (343 tests, 14 optional integrations skipped) pass, along with Django, migration-drift, Ruff, JavaScript syntax and whitespace checks. This UI/default change requires no database migration or Supabase synchronization.

### 2026-10-23 Editor Wallet navigation removal evidence

The Editor workspace sidebar no longer contains the Wallet section. Assigned projects, Project details, Revisions, Project Communication and Availability retain their existing destinations and order. The protected wallet route and its ledger/redemption implementation remain unchanged, as do Admin Payouts. Focused Editor navigation and wallet-security coverage (14 tests) and the full isolated suite (343 tests, 14 optional integrations skipped) pass, along with Django, migration-drift, Ruff, JavaScript syntax and whitespace checks. This UI-only change requires no database migration or Supabase synchronization.

### 2026-10-23 Supabase identity-deletion synchronization evidence

Linked Supabase Auth deletion drives a private-schema archival policy through server-only Auth Admin API reconciliation before Admin pages render. Deleted Clients and Editors disappear from Admin rosters; archived client projects disappear from operational Projects, Orders, Payments and analytics without destroying retained financial/audit evidence. Deleted Editors are removed from live assignments and nonterminal client projects return to Awaiting assignment. Reconciliation protects the last active application Admin. Client-project files enter a durable retry queue and a version-aware command deletes their exact private objects through the storage API before marking file rows removed. A separate dry-run/apply command supports scheduled or manual reconciliation. The Admin request fails closed with a retryable 503 when Auth inventory cannot be verified or a last-Admin deletion requires recovery. Focused identity and affected-roster coverage passes 39 tests and the full isolated suite passes 349 tests with 14 optional integrations skipped. Additive migrations `core.0022` and `core.0023` were applied to project `lmwvoniiykmfzuxigzqf` after verified pre-change snapshot `database-snapshot-20261023T124959870112Z.json`. The post-change snapshot `database-snapshot-20261023T155010683399Z.json` restored 51 tables / 717 rows in rehearsal; all 51 tables retain RLS and public/browser grants remain zero. Report-only reconciliation found two pre-existing missing Auth identities and archived both without a last-Admin block. Exact-key storage cleanup completed one queued project; one provider-unavailable job remains safely in retry state with its file rows intact.

### 2026-10-23 Admin-controlled Editor availability evidence

Editors can submit a reason-required Not Available request from Availability settings. The request remains pending without changing authoritative availability and creates a persistent Admin notification linked to the Editor profile. Admins can explicitly apply Not Available or restore automatic workload-derived availability with an audited reason. Approved overrides are displayed consistently and block both manual and round-robin assignment; workload-derived Busy behavior and existing assignments remain unchanged. The full isolated suite passes 350 tests with 14 optional integrations skipped. Additive migrations `operations.0018` and `operations.0019` were applied to project `lmwvoniiykmfzuxigzqf` after verified private snapshot `database-snapshot-20261023T164459335164Z.json`. Post-change snapshot `database-snapshot-20261023T164654563499Z.json` restored 52 tables / 728 rows in an isolated rehearsal. All 52 private tables have RLS, public/browser grants remain zero, and database security checks pass.

### 2026-10-24 round-robin re-verification evidence

The current allocation implementation was re-verified after pulling the Admin-controlled availability work. Focused backend coverage passes fair E1 → E2 → E3 rotation, pointer persistence, separate proficiency groups, skip/wait retries, inactive/unapproved/no-capacity exclusions, terminal-project release, stale-form protection, reassignment history and former-editor denial. A new regression proves an Admin Not Available override skips that editor, selects the next eligible roster member and advances the proficiency sequence exactly once. The isolated Edge walkthrough passes policy/capacity setup → complexity review → round robin → editor access → reassignment → former-editor denial at desktop and mobile sizes. Connected read-only reconciliation passes with no critical findings; it reports one paid project awaiting complexity review. The shared concurrency command correctly refused to create synthetic fixtures because live allocation is enabled, so connected state was not disturbed; row-lock concurrency remains covered by the isolated verification workflow.

### 2026-10-24 lightweight responsive and request optimization evidence

No PHP files, Composer manifests or PHP references exist, so no speculative dependency removal was performed. The 18.6 KB hashing library and its adapter now load only on private upload pages instead of every public and workspace response. Availability polling now loads only on the two Editor availability surfaces and runs every 30 seconds while visible rather than every 5 seconds globally, reducing an open availability page from up to 720 to 120 scheduled checks per hour and eliminating those requests everywhere else. Shared CSS adds safe-area padding, 44 px touch targets, narrow-screen wrapping, single-column phone cards and notification constraints without adding, removing or renaming any control. Browser checks at 390×844 iPhone, 412×915 Android, 768×1024 tablet and 1440×900 desktop sizes found no horizontal overflow and no visible control below 40 px; the public landing page now loads only the shared application and account-control scripts. The full isolated suite passes 352 tests with 14 optional integrations skipped, with Django, migration drift, Ruff, JavaScript, vendored-asset and whitespace checks also passing. No schema or Supabase migration is required.
