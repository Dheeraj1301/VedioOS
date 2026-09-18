# First-version traceability — original brief §34

This is a development evidence map, not a production launch claim. **Verified** means a local or isolated synthetic flow passed. **Partial** means a working foundation exists but the stated first-version behavior still needs a policy or integration. **Open** means the required capability has not been implemented.

| # | Priority | Status | Current evidence and remaining work |
| --- | --- | --- | --- |
| 1 | Client registration/login | Verified | [Day 1](DAY_1_VERIFICATION.md): browser registration, login/logout and server role checks. |
| 2 | Client video upload | Verified locally | [Day 1](DAY_1_VERIFICATION.md) and [Phase 7](PHASE_7.md): private direct upload, integrity and mobile Edge flow. Production media hosting/limits remain D02. |
| 3 | Editing requirement selection | Verified | New-order brief and server-stored requirements; [Day 1](DAY_1_VERIFICATION.md). |
| 4 | Inspiration upload | Verified locally | Private reference category and project-scoped file access; [Day 1](DAY_1_VERIFICATION.md). |
| 5 | Song selection | Verified | New-order music preference and instructions persist with the project; [Day 1](DAY_1_VERIFICATION.md). |
| 6 | Plan selection | Partial | Three configurable plan slots and server quotes work in synthetic tests; no approved live plans/prices (D03). [Phase 3](PHASE_3.md). |
| 7 | Custom pricing | Partial | Admin-configured base/services and server-calculated quotes work; commercial values/terms remain D04. [Phase 3](PHASE_3.md). |
| 8 | Payment flow | Partial | Signed, replay-safe development sandbox and protected history/receipt; no real gateway or tax/refund policy (D05). [Phase 3](PHASE_3.md). |
| 9 | Project creation | Verified | Client drafts and one paid activation on verified sandbox success; [Phase 3](PHASE_3.md). |
| 10 | Presenter/admin dashboard | Verified in development | Admin overview, paid/unpaid orders, assignment queues, status filters and protected audit timeline; [Phases 3](PHASE_3.md), [4](PHASE_4.md), [7](PHASE_7.md). |
| 11 | Editor registration | Verified | Application, login and pending approval; [Day 1](DAY_1_VERIFICATION.md). |
| 12 | Editor proficiency management | Verified in development | Admin-only assessment/approval and audit; production criteria remain D07. [Phase 4](PHASE_4.md). |
| 13 | Editor dashboard | Verified in development | Current assignments, revisions, wallet, availability and calls; [Phases 4](PHASE_4.md), [5](PHASE_5.md), [7](PHASE_7.md). |
| 14 | AI complexity classification | Open | Admin can assess complexity manually; no AI provider, evaluation or failure path (D08). [Phase 4](PHASE_4.md). |
| 15 | Intelligent editor assignment | Partial | Deterministic proficiency/capacity/availability matching and admin override pass tests; AI input and production policy remain open (D07–D09). [Phase 4](PHASE_4.md). |
| 16 | Round-robin assignment | Verified in development | Persistent per-proficiency pointer and PostgreSQL concurrency checks; policy remains disabled until selected. [Phase 4](PHASE_4.md). |
| 17 | Editor availability tracking | Verified | Editors update status; assignment checks eligibility under lock. [Phase 4](PHASE_4.md). |
| 18 | Editor file upload | Verified locally | Private verified draft/final uploads linked to versions; [Phase 5](PHASE_5.md). Production media decisions remain D02. |
| 19 | Client review | Verified in development | Client sees submitted versions and explicit review actions under snapshotted terms; [Phase 5](PHASE_5.md). |
| 20 | Revision requests | Verified in development | Version-targeted instructions and backend allowance checks; production excess/reopening policy remains D11. [Phase 5](PHASE_5.md). |
| 21 | Final approval | Verified in development | Client accepts an explicit version; repeat acceptance does not duplicate completion. [Phase 5](PHASE_5.md). |
| 22 | Editor coin system | Partial | Pending/released ledger, wallet and sandbox redemption pass tests; coin value and real payout remain D10. [Phase 6](PHASE_6.md). |
| 23 | Project status tracking | Verified in development | Protected dashboards and active/review/revision/completed queues; [Phase 7](PHASE_7.md). |
| 24 | Notifications | Partial | Durable in-app notices, recipient/project checks and deduplication; external channels/preferences and worker retries remain D12. [Phase 7](PHASE_7.md). |
| 25 | 24-hour deadline tracking | Partial | Persisted due dates are shown and overdue notices can be rerun; the 24-hour clock and warning threshold are deliberately unset pending D06. [Phase 7](PHASE_7.md). |
| 26 | Secure project-level file access | Verified locally | Backend ownership/assignment checks and short-lived signed URLs; cross-client/former-editor denial tests. [Day 1](DAY_1_VERIFICATION.md), [Phase 5](PHASE_5.md). |
| 27 | Original video quality preservation | Verified locally | Direct object uploads and byte-identical downloads; distinct output versions preserve originals. [Day 1](DAY_1_VERIFICATION.md), [Phase 5](PHASE_5.md), [Phase 7](PHASE_7.md). |
| 28 | File/version history | Verified in development | Private original metadata, immutable version references and acceptance history; [Phase 5](PHASE_5.md). |

The Phase 7 gate is **open**. Priorities 14 and 25 require their unresolved policy/provider work; priorities 6–8, 15, 22 and 24 remain partial. Cross-cutting launch checks also remain: D02 production media, D06/D12 operating policies, full accessibility review, error/retry/recovery, and Phase 9 end-to-end production verification. See the [decision register](DECISIONS.md) and [roadmap](ROADMAP.md).
