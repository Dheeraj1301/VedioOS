# Development pathway

## How to use this pathway

The [Day 1 local foundation](DAY_1_VERIFICATION.md) is implemented and verified. Phases 0–2 have progressed through that milestone; their broader production/large-file gates are not all complete. [Phase 3](PHASE_3.md) has a verified catalog/quote/payment-sandbox milestone. [Phase 4](PHASE_4.md) has a verified allocation milestone. [Phase 5](PHASE_5.md) has a verified review milestone. [Phase 6](PHASE_6.md) has a verified opt-in coin/sandbox payout milestone. Real checkout, payout provider, deadline rules, allocation activation and AI still require decisions. Work in dependency order, delivering small complete flows.

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

- Implement admin management of three plans and custom services with validated configuration.
- Build plan/custom selection, backend price calculation, term snapshots, payment adapter, verified payment events, invoices/history foundations, and unique paid projects.
- Show paid/unpaid queues in the presenter dashboard. Persist delivery timestamps under decided rules.

**Gate:** a payment failure cannot activate/assign a project; altered client totals are rejected. Verified payment activates exactly one project despite duplicate events. Existing order terms survive catalog edits. Real payment stays disabled until its settings/policies are ready.

## Phase 4 — Complexity, workload, and fair assignment

**2026-09-16: allocation milestone implemented and verified.** [Evidence](PHASE_4.md): capacity administration, admin complexity review, manual/reassignment, paid queues, persistent round robin, skip/wait and real PostgreSQL concurrency. Shared allocation remains off until policies are configured. AI classification is not integrated, so the full Phase 4 production gate remains open.

- Implement proficiency/availability/capacity administration, active counts, AI classification and admin overrides.
- Implement durable paid-project queues and separate round-robin pointers per level.
- Implement configured wait/skip behavior, manual assignment/reassignment, and deadline visibility.

**Gate:** E1 → E2 → E3 remains fair when E1 finishes early; restart preserves sequence. Concurrent workers cannot double-assign or exceed capacity. Unavailable editors follow policy. AI failure remains visible and recoverable. Former editors lose future project access; link-expiry behavior matches the documented policy.

## Phase 5 — Editor work, versions, review, and delivery

**Implementation gate passed 2026-09-17 with explicit synthetic review policy; production activation awaits owner-approved terms.** See [Phase 5 evidence](PHASE_5.md). Earnings remain pending Phase 6 policy.

- Build assigned-project detail with all source/reference/song/effect/notes/deadline information and original downloads.
- Implement external-edit workflow: upload draft, add client-visible note, submit review, receive revisions, upload new versions, designate final candidate.
- Implement client review, version-targeted revisions and acceptance, final download, project history, and guarded state transitions.

**Gate:** one real test project passes from paid assignment through draft → revision → revised version → client acceptance → final download. Another accepts the first draft. Prior versions survive and retain integrity. Editor submission alone cannot complete a project. Revision policy and access controls are enforced.

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

**2026-09-19: lifecycle audit inventory completed.** Initial editing and requested-revision starts now join the existing attributable lifecycle audit trail and repeated starts do not duplicate events. The full gate remains open; see [Phase 7 evidence](PHASE_7.md).

**2026-09-19: safe error recovery verified.** Browser and API permission, missing-resource and server-error responses provide actionable recovery without rendering private exception details. The full gate remains open; see [Phase 7 evidence](PHASE_7.md).

**2026-09-19: automated accessibility baseline verified.** Project workflows now provide keyboard skip navigation, live progress/error announcements, distinct download names and retryable rejected uploads. A manual assistive-technology audit remains before launch; see [Phase 7 evidence](PHASE_7.md).

- Finish client/editor/admin status dashboards, unassigned/active/review/revision/completed queues, and deadline alerts.
- Add durable role-scoped event notifications and retry handling.
- Complete audit coverage and first-version project communication; support consultation request tracking without requiring built-in video calling.
- Verify mobile client uploads, accessible forms, permission states, loading/error recovery, and responsive dashboards.

**Gate:** all 28 section-34 priorities pass the traceability checklist below. Admins can operate the full lifecycle; notifications are accurate and contain no unauthorized data. No required first-version feature is represented only by a mock.

## Phase 8 — Broader commercial features

**2026-09-24: operational analytics, client/order/project operations, client support, feature-control inventory and protected payment history verified.** Admin tools reconcile operational counts, per-client work/payment/support status, order and project workflow, deadline queues and payment records, provide a private audited support workflow, and show actual platform-control state. Undefined financial metrics, tax invoices, package sales and AI remain locked pending their owner decisions; see [Phase 8 evidence](PHASE_8.md).

- Complete premium landing-page content and approved public claims, support workflows, call scheduling/completion, and optional calling-provider integration.
- Build configurable monthly influencer packages, purchases, allowance accounting, dedicated-editor behavior, and renewal/expiry handling.
- Finish advanced analytics, feature administration, payment/invoice history, and customer retention reporting.

**Gate:** package purchase/use/limits are verified; dedicated-editor behavior follows allocation policy; calls can be managed; analytics reconcile against underlying records. Features offered publicly can actually be fulfilled.

## Phase 9 — Production readiness

**2026-09-26: configuration-audit, deployment-health, account/session, assignment-state, audit-history, notification-outbox, commerce and earnings reconciliation, snapshot-integrity, isolated row-restore, PostgreSQL privilege inventory, private-storage inventory/reconciliation, workflow reconciliation, continuous-verification and local browser-lifecycle foundations verified.** Role/profile/session relationships, allocation queues/capacity/rotation, sensitive lifecycle audit coverage, durable notification states, quote/order/payment/call relationships and editor coin/redemption ledgers pass aggregate audits, private snapshots pass a disposable 46-table restore, the constrained runtime role and private grants pass a repeatable audit, synthetic bytes pass a versioned/private storage round trip, every bucket version is accounted for, ready files reconcile to exact private objects, and payment-to-acceptance records pass aggregate consistency checks. CI and five isolated Edge suites cover the remaining local workflows. D03-D05 real commerce policy/provider choices, D07-D10 allocation/AI/earnings policy, D12 notification-provider operations, D16 account/audit retention policy, full provider-owned role/extension/trigger restore, media restore and production-provider exercises remain open. The current development environment intentionally fails the release audit; no deployment is authorized. See [Phase 9 evidence](PHASE_9.md).

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
